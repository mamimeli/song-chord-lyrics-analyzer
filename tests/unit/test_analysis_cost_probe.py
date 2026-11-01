"""Cost-probe tests (roadmap Phase I P7 evidence).

``scripts/analysis_cost_probe.py`` is developer tooling, but the claim it exists
to settle - "a song is decoded at least three times, and a shared decode would
save that" - is a claim about this repository's orchestration. These tests drive
the real script through a subprocess, over generated audio only, and check both
halves: the parts that must work in a Qt-/DSP-free environment (fixture
building, argument errors), and the premise itself once the optional DSP stack
is present (three decodes, one identical request, and a steady-state saving
that excludes the first decode).

The premise class shares one subprocess run, because a cold analysis in a fresh
interpreter is exactly the expensive thing being measured. No timing taken here
is quoted anywhere: those numbers are recorded, with their environment and date,
in ``docs/ENGINE_COMPARISON.md`` §10.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import wave
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from song_chord_lyrics_analyzer.engines import ChromaBaselineEngine

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "analysis_cost_probe.py"

#: The three layers that decode the whole file, and the sample rate they ask for.
DECODING_STEPS = {"chords", "key", "tempo"}
SAMPLE_RATE = 22_050
FIXTURE_SECONDS = 6.0

requires_dsp = pytest.mark.skipif(
    not ChromaBaselineEngine().is_available(),
    reason="optional DSP stack (numpy/librosa) not installed",
)


def _run(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *arguments],
        capture_output=True,
        text=True,
        check=False,
    )


def _fixture(path: Path, *, seconds: float = FIXTURE_SECONDS) -> subprocess.CompletedProcess[str]:
    return _run("--make-fixture", str(path), "--seconds", str(seconds))


class TestOfflineBehaviour:
    """What must work in every environment, including the Qt-/DSP-free one."""

    def test_the_fixture_is_generated_tone_audio(self, tmp_path: Path) -> None:
        path = tmp_path / "cost.wav"
        assert _fixture(path, seconds=4.0).returncode == 0
        with wave.open(str(path), "rb") as reader:
            assert reader.getnchannels() == 1
            assert reader.getsampwidth() == 2
            assert reader.getframerate() == SAMPLE_RATE
            assert reader.getnframes() / reader.getframerate() == pytest.approx(4.0)

    def test_a_non_positive_fixture_is_refused(self, tmp_path: Path) -> None:
        result = _fixture(tmp_path / "cost.wav", seconds=0)
        assert result.returncode == 2
        assert "--seconds" in result.stderr

    def test_an_input_file_is_required(self) -> None:
        result = _run()
        assert result.returncode == 2
        assert "hint" in result.stderr

    def test_a_missing_file_is_refused_before_any_timing(self, tmp_path: Path) -> None:
        result = _run(str(tmp_path / "not-here.wav"))
        assert result.returncode == 2
        assert "error" in result.stderr

    def test_the_number_of_runs_is_validated(self, tmp_path: Path) -> None:
        path = tmp_path / "cost.wav"
        assert _fixture(path, seconds=0.2).returncode == 0
        result = _run(str(path), "--runs", "0")
        assert result.returncode == 2
        assert "runs" in result.stderr

    def test_the_lyrics_layer_is_opt_in(self) -> None:
        result = _run("--help")
        assert result.returncode == 0
        assert "--with-lyrics" in result.stdout


@pytest.fixture(scope="module")
def probe() -> Iterator[dict[str, Any]]:
    """One real two-run probe of a generated file, shared by the premise tests.

    A cold analysis pays seconds of library warm-up in every fresh interpreter,
    so the measurement is taken once and asserted many times.
    """
    with tempfile.TemporaryDirectory() as directory:
        temporary = Path(directory)
        audio = temporary / "cost.wav"
        assert _fixture(audio).returncode == 0
        record_path = temporary / "record.json"
        result = _run(str(audio), "--runs", "2", "--chroma", "--json", str(record_path))
        assert result.returncode == 0, result.stderr
        record = json.loads(record_path.read_text(encoding="utf-8"))
        yield {
            "stdout": result.stdout,
            "audio": audio,
            "file": record["files"][0],
            "record": record,
        }


@requires_dsp
class TestTheP7Premise:
    """What an analysis actually does to the audio, measured through the probe."""

    def test_one_analysis_decodes_the_file_once_per_layer(self, probe: dict[str, Any]) -> None:
        decodes = probe["file"]["runs"][0]["decodes"]
        assert {decode["step"] for decode in decodes} == DECODING_STEPS
        assert len(decodes) == 3

    def test_the_wrapper_is_removed_after_each_run(self, probe: dict[str, Any]) -> None:
        # A leaked wrapper would time every decode twice on the next run.
        assert len(probe["file"]["runs"][1]["decodes"]) == 3

    def test_the_three_decodes_are_one_request(self, probe: dict[str, Any]) -> None:
        request = probe["file"]["decode_request"]
        assert request == {
            "path": str(probe["audio"]),
            "sample_rate": SAMPLE_RATE,
            "mono": True,
            "offset": 0.0,
            "duration": None,
            "backend": "auto",
        }
        assert probe["file"]["identical_decodes"] is True

    def test_the_repeated_decodes_are_what_a_cache_could_remove(
        self, probe: dict[str, Any]
    ) -> None:
        steady = probe["file"]["runs"][-1]
        first_decode = steady["decodes"][0]["seconds"]
        assert steady["repeat_decode_seconds"] == pytest.approx(
            steady["decode_seconds"] - first_decode, abs=0.005
        )
        assert probe["file"]["cacheable_seconds_in_steady_state"] == pytest.approx(
            steady["repeat_decode_seconds"], abs=0.005
        )

    def test_the_samples_one_decode_returns_are_measured(self, probe: dict[str, Any]) -> None:
        # 6 s of mono float32 at 22 050 Hz: the buffer a cache would reuse.
        assert probe["file"]["decoded_bytes"] == int(FIXTURE_SECONDS * SAMPLE_RATE * 4)

    def test_the_report_states_the_environment_and_the_saving(self, probe: dict[str, Any]) -> None:
        stdout = probe["stdout"]
        assert "environment:" in stdout
        assert "date:" in stdout
        assert "layers under test: chords, key, tempo" in stdout
        assert "identical request: True" in stdout
        assert "a shared decode could remove at most" in stdout

    def test_the_record_carries_the_environment(self, probe: dict[str, Any]) -> None:
        environment = probe["record"]["environment"]
        assert {"platform", "python", "numpy", "librosa", "git_commit"} <= set(environment)
        assert probe["record"]["runs_requested"] == 2

    def test_the_chroma_pass_prices_the_shared_feature_half(self, probe: dict[str, Any]) -> None:
        chroma = probe["file"]["chroma_seconds"]
        assert len(chroma) == 2
        assert all(seconds > 0 for seconds in chroma)
        assert "a shared chromagram would remove one of those per run" in probe["stdout"]
