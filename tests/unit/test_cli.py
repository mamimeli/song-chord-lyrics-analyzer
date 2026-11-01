"""Unit tests for the CLI (roadmap sections 47, 63 and 82)."""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import pytest

from song_chord_lyrics_analyzer import __version__
from song_chord_lyrics_analyzer.cli.main import configure_utf8_stdio, main


class TestTopLevel:
    def test_help_exits_successfully(self, capsys) -> None:
        with pytest.raises(SystemExit) as excinfo:
            main(["--help"])
        assert excinfo.value.code == 0
        assert "usage: songlab" in capsys.readouterr().out

    def test_version_exits_successfully(self, capsys) -> None:
        with pytest.raises(SystemExit) as excinfo:
            main(["--version"])
        assert excinfo.value.code == 0
        assert __version__ in capsys.readouterr().out

    def test_no_command_prints_help(self, capsys) -> None:
        assert main([]) == 0
        assert "usage: songlab" in capsys.readouterr().out

    def test_unknown_command_is_an_input_error(self, capsys) -> None:
        with pytest.raises(SystemExit) as excinfo:
            main(["definitely-not-a-command"])
        assert excinfo.value.code == 2

    def test_help_lists_planned_commands(self, capsys) -> None:
        with pytest.raises(SystemExit):
            main(["--help"])
        output = capsys.readouterr().out
        for command in ("info", "doctor", "chords", "lyrics", "export"):
            assert command in output


class TestDoctorCommand:
    def test_report_is_printed(self, capsys) -> None:
        assert main(["doctor"]) == 0
        output = capsys.readouterr().out
        assert "SongLab doctor" in output
        assert "Python:" in output
        assert "Analysis engines" in output

    def test_json_output_is_valid(self, capsys) -> None:
        assert main(["doctor", "--json"]) == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["application"]["version"] == __version__
        assert set(payload["tools"]) == {"ffmpeg", "ffprobe"}
        assert payload["directories"]["cache"]


class TestInfoCommand:
    def test_reports_wav_metadata(self, tone_wav: Path, capsys) -> None:
        assert main(["info", str(tone_wav)]) == 0
        output = capsys.readouterr().out
        assert "Sample rate: 44100 Hz" in output
        assert "Channels:    stereo" in output
        assert "Bit depth:   16 bit" in output
        assert "00:00:01.000" in output

    def test_hash_flag_adds_digest(self, tone_wav: Path, capsys) -> None:
        assert main(["info", str(tone_wav), "--hash"]) == 0
        assert "SHA-256:" in capsys.readouterr().out

    def test_json_output_matches_canonical_fields(self, tone_wav: Path, capsys) -> None:
        assert main(["info", str(tone_wav), "--json"]) == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["schema_version"] == "1"
        assert payload["sample_rate"] == 44100
        assert payload["channels"] == 2
        assert payload["bit_depth"] == 16
        assert Path(payload["path"]) == tone_wav

    def test_missing_file_reports_a_friendly_error(self, tmp_path: Path, capsys) -> None:
        exit_code = main(["info", str(tmp_path / "nope.mp3")])
        assert exit_code == 2
        captured = capsys.readouterr()
        assert "Error: Audio file not found" in captured.err
        assert "Traceback" not in captured.err

    def test_directory_argument_is_rejected(self, tmp_path: Path, capsys) -> None:
        assert main(["info", str(tmp_path)]) == 2
        assert "Expected an audio file" in capsys.readouterr().err

    def test_corrupt_file_reports_an_error_not_a_traceback(self, corrupt_wav: Path, capsys) -> None:
        exit_code = main(["info", str(corrupt_wav)])
        captured = capsys.readouterr()
        assert exit_code in (2, 3)
        assert "Error:" in captured.err
        assert "Traceback" not in captured.err

    def test_missing_ffprobe_is_a_dependency_error(
        self, tmp_path: Path, monkeypatch, capsys
    ) -> None:
        from song_chord_lyrics_analyzer.audio import probe as probe_module

        audio = tmp_path / "song.mp3"
        audio.write_bytes(b"payload")
        monkeypatch.setattr(probe_module, "find_ffprobe", lambda: None)
        exit_code = main(["info", str(audio)])
        captured = capsys.readouterr()
        assert exit_code == 3
        assert "FFprobe" in captured.err
        assert "winget" in captured.err or "apt" in captured.err or "brew" in captured.err


class TestVerbosityFlags:
    def test_quiet_and_verbose_are_accepted(self, tone_wav: Path, capsys) -> None:
        assert main(["--quiet", "info", str(tone_wav)]) == 0
        assert main(["-v", "info", str(tone_wav)]) == 0
        capsys.readouterr()

    def test_unexpected_errors_do_not_leak_a_traceback_by_default(
        self, monkeypatch, capsys
    ) -> None:
        from song_chord_lyrics_analyzer.cli.commands import info as info_module

        def _explode(args):  # type: ignore[no-untyped-def]
            raise RuntimeError("simulated bug")

        monkeypatch.setattr(info_module, "run", _explode)
        assert main(["info", "whatever.wav"]) == 1
        captured = capsys.readouterr()
        assert "Unexpected error: RuntimeError" in captured.err
        assert "Traceback" not in captured.err
        assert "--debug" in captured.err

    def test_debug_flag_reports_tracebacks(self, monkeypatch, capsys) -> None:
        from song_chord_lyrics_analyzer.cli.commands import info as info_module

        def _explode(args):  # type: ignore[no-untyped-def]
            raise RuntimeError("simulated bug")

        monkeypatch.setattr(info_module, "run", _explode)
        assert main(["--debug", "info", "whatever.wav"]) == 1
        assert "Traceback" in capsys.readouterr().err


class TestStdioEncoding:
    """songlab writes UTF-8 text even when the console code page says otherwise."""

    def test_a_redirected_cp1252_console_still_receives_utf8_json(
        self, tmp_path: Path, make_wav, monkeypatch
    ) -> None:
        # A redirected stream on Windows takes the ANSI code page (cp1252), which
        # has no byte for U+266A: unconfigured, printing the path of an ordinary
        # file raises UnicodeEncodeError inside the command handler.
        buffer = io.BytesIO()
        stream = io.TextIOWrapper(buffer, encoding="cp1252")
        monkeypatch.setattr(sys, "stdout", stream)
        audio = make_wav(tmp_path / "♪.wav")

        assert main(["info", str(audio), "--json"]) == 0

        stream.flush()
        payload = json.loads(buffer.getvalue().decode("utf-8"))
        assert payload["path"].endswith("♪.wav")

    def test_a_stream_that_cannot_be_reconfigured_is_left_alone(self, monkeypatch) -> None:
        class _Captured:
            def write(self, text: str) -> int:
                return len(text)

        monkeypatch.setattr(sys, "stdout", _Captured())
        monkeypatch.setattr(sys, "stderr", _Captured())

        configure_utf8_stdio()

    def test_a_stream_that_is_already_utf8_is_not_touched(self, monkeypatch) -> None:
        """An interactive console writes UTF-8 through the platform Unicode API."""

        class _Utf8Console:
            encoding = "utf-8"

            def reconfigure(self, **kwargs: object) -> None:
                raise AssertionError("a UTF-8 console must not be reconfigured")

            def write(self, text: str) -> int:
                return len(text)

        monkeypatch.setattr(sys, "stdout", _Utf8Console())
        monkeypatch.setattr(sys, "stderr", _Utf8Console())

        configure_utf8_stdio()
