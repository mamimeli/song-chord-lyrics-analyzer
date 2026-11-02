"""Unit tests for cross-platform path handling (roadmap sections 4 and 105)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from song_chord_lyrics_analyzer.utils.paths import (
    CACHE_ENV_VAR,
    DATA_ENV_VAR,
    TEMP_ENV_VAR,
    canonical_path_str,
    default_cache_dir,
    default_data_dir,
    default_export_dir,
    default_model_dir,
    default_temp_dir,
    ensure_directory,
    resolve_output_path,
    write_text_atomic,
)


class TestDefaultDirectories:
    def test_defaults_are_absolute_and_namespaced(self) -> None:
        for directory in (default_cache_dir(), default_data_dir(), default_temp_dir()):
            assert directory.is_absolute()
        assert "songlab" in str(default_cache_dir()).lower()
        assert "songlab" in str(default_data_dir()).lower()

    def test_model_and_export_dirs_live_under_data_dir(self) -> None:
        assert default_model_dir() == default_data_dir() / "models"
        assert default_export_dir() == default_data_dir() / "exports"

    def test_cache_env_override(self, monkeypatch, tmp_path: Path) -> None:
        monkeypatch.setenv(CACHE_ENV_VAR, str(tmp_path / "cache"))
        assert default_cache_dir() == tmp_path / "cache"

    def test_data_env_override(self, monkeypatch, tmp_path: Path) -> None:
        monkeypatch.setenv(DATA_ENV_VAR, str(tmp_path / "data"))
        assert default_data_dir() == tmp_path / "data"
        assert default_model_dir() == tmp_path / "data" / "models"

    def test_temp_env_override(self, monkeypatch, tmp_path: Path) -> None:
        monkeypatch.setenv(TEMP_ENV_VAR, str(tmp_path))
        assert default_temp_dir() == tmp_path

    def test_empty_env_override_is_ignored(self, monkeypatch) -> None:
        monkeypatch.setenv(CACHE_ENV_VAR, "")
        assert "songlab" in str(default_cache_dir()).lower()


class TestHelpers:
    def test_ensure_directory_creates_parents(self, tmp_path: Path) -> None:
        target = tmp_path / "a" / "b" / "c"
        assert ensure_directory(target) == target
        assert target.is_dir()

    def test_ensure_directory_is_idempotent(self, tmp_path: Path) -> None:
        ensure_directory(tmp_path)
        ensure_directory(tmp_path)
        assert tmp_path.is_dir()

    def test_relative_output_path_uses_base_dir(self, tmp_path: Path) -> None:
        resolved = resolve_output_path("out.json", base_dir=tmp_path)
        assert resolved == tmp_path / "out.json"

    def test_absolute_output_path_is_kept(self, tmp_path: Path) -> None:
        absolute = tmp_path / "out.json"
        assert resolve_output_path(absolute, base_dir=Path("/elsewhere")) == absolute

    def test_home_shortcut_is_expanded(self) -> None:
        assert "~" not in str(resolve_output_path("~/out.json"))


class TestCanonicalPathStr:
    """The document form of a path must not depend on the machine that wrote it."""

    def test_a_nested_path_keeps_forward_separators(self, tmp_path: Path) -> None:
        nested = tmp_path / "music" / "a.wav"
        assert canonical_path_str(nested) == str(nested).replace(os.sep, "/")
        assert "\\" not in canonical_path_str(nested)

    def test_a_string_and_a_path_agree(self, tmp_path: Path) -> None:
        nested = tmp_path / "music" / "a.wav"
        assert canonical_path_str(str(nested)) == canonical_path_str(nested)

    def test_it_can_be_read_back_as_a_path(self, tmp_path: Path) -> None:
        nested = tmp_path / "music" / "a.wav"
        assert Path(canonical_path_str(nested)) == nested


class TestAtomicTextWrite:
    """A file the user made must never be left half-written (roadmap L5).

    The edits sidecar and an export both overwrite a file that may already hold
    the work of a previous session. Writing it in place meant that an
    interruption - ``Ctrl+C``, a full disk, text that cannot be encoded -
    replaced the good file with a truncated one. These tests pin the two
    properties that make the overwrite safe: the bytes arrive through one
    rename inside the target's own directory, and a write that fails leaves the
    file that was there exactly as it was.
    """

    def test_the_text_lands_and_the_target_is_returned(self, tmp_path: Path) -> None:
        target = tmp_path / "chart.md"

        written = write_text_atomic(target, "# C  G  Am")

        assert written == target
        assert target.read_text(encoding="utf-8") == "# C  G  Am"

    def test_a_string_path_is_accepted(self, tmp_path: Path) -> None:
        target = str(tmp_path / "chart.md")

        assert write_text_atomic(target, "text") == Path(target)
        assert Path(target).read_text(encoding="utf-8") == "text"

    def test_an_existing_file_is_replaced_whole(self, tmp_path: Path) -> None:
        target = tmp_path / "song.songlab.json"
        write_text_atomic(target, '{"older": true, "padding": "' + "x" * 4096 + '"}')

        write_text_atomic(target, '{"newer": true}')

        assert target.read_text(encoding="utf-8") == '{"newer": true}'

    def test_the_encoding_the_caller_asks_for_is_used(self, tmp_path: Path) -> None:
        target = tmp_path / "chart.md"

        write_text_atomic(target, "caf\u00e9", encoding="latin-1")

        assert target.read_bytes() == b"caf\xe9"

    def test_a_write_that_fails_keeps_the_previous_content(self, tmp_path: Path) -> None:
        target = tmp_path / "song.songlab.json"
        write_text_atomic(target, "the sidecar worth keeping")

        # Text the requested encoding cannot represent fails part-way through
        # the write, which is the interruption this helper exists for.
        with pytest.raises(UnicodeEncodeError):
            write_text_atomic(target, "aún más", encoding="ascii")

        assert target.read_text(encoding="utf-8") == "the sidecar worth keeping"

    def test_a_failed_write_leaves_no_temporary_file_behind(self, tmp_path: Path) -> None:
        target = tmp_path / "song.songlab.json"
        write_text_atomic(target, "first")

        with pytest.raises(UnicodeEncodeError):
            write_text_atomic(target, "aún más", encoding="ascii")

        assert [entry.name for entry in tmp_path.iterdir()] == [target.name]

    def test_the_rename_happens_inside_the_targets_own_directory(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A rename is only atomic within one directory.

        A temporary written somewhere else would turn the swap into a
        copy-and-delete, which is exactly the half-written window this avoids,
        so where the temporary lives is part of the contract.
        """
        moved: list[tuple[Path, Path]] = []
        real_replace = os.replace

        def record(src: str, dst: str) -> None:
            moved.append((Path(src), Path(dst)))
            real_replace(src, dst)

        monkeypatch.setattr(os, "replace", record)
        target = tmp_path / "song.songlab.json"

        write_text_atomic(target, "text")

        assert len(moved) == 1
        source, destination = moved[0]
        assert destination == target
        assert source.parent == tmp_path
        assert source != target
        assert source.exists() is False  # the rename consumed the temporary

    def test_a_missing_directory_is_reported_not_created(self, tmp_path: Path) -> None:
        target = tmp_path / "absent" / "song.songlab.json"

        with pytest.raises(OSError):
            write_text_atomic(target, "text")

        assert target.parent.is_dir() is False
        assert list(tmp_path.iterdir()) == []
