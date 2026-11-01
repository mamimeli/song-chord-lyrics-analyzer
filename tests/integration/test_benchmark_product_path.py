"""The product workflow as a benchmark case (roadmap Phase J, sections 44-46).

``samples/cases/vocadito_6.json`` is the committed case this module checks: a real
recording from ``samples/`` (a CC-BY-4.0 vocadito excerpt), the dataset's own
annotated lyric line as the reference, and a hypothesis plus run cost produced by
the registered lyrics engine and recorded with its environment and date in
``docs/BENCHMARK.md``.

It is the benchmark half of the product path, so the assertions are about the
*chain*, not about accuracy: the case loads, its audio is the committed sample,
its reference is still the annotation, and scoring it produces exactly the metric
families the ground truth can support. The engine's measured error rate on this
excerpt is a documented result (``docs/ENGINE_COMPARISON.md``), not a test
threshold - a test that pinned a WER would fail on a different onnxruntime, not
on a broken product.

Two honest limits, both by design:

* The stored case is scored without any optional dependency, so this module runs
  in the plain ``dev`` environment the CI matrix installs.
* The one test that re-runs the engine needs the DSP stack, ``onnx-asr`` and the
  Parakeet weights already in the local cache; tests never download a model.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest

from song_chord_lyrics_analyzer.benchmark import (
    BenchmarkCase,
    build_report,
    load_case,
    load_cases,
    run_engine_on_cases,
    score_case,
    to_csv,
    to_json,
    to_markdown,
)
from song_chord_lyrics_analyzer.cli.main import main
from song_chord_lyrics_analyzer.engines.lyrics_parakeet import ENGINE_VERSION, ParakeetLyricsEngine
from song_chord_lyrics_analyzer.metrics.lyrics import character_error_rate, word_error_rate
from song_chord_lyrics_analyzer.performance import real_time_factor

ROOT = Path(__file__).resolve().parents[2]
CASES = ROOT / "samples" / "cases"
CASE_FILE = CASES / "vocadito_6.json"
SIDECAR = ROOT / "samples" / "vocadito_6.json"

#: Where ``onnx-asr`` keeps the converted Parakeet checkpoint. Its presence is the
#: "already downloaded" signal; nothing here fetches it.
MODEL_CACHE = (
    Path.home() / ".cache" / "huggingface" / "hub" / "models--istupakov--parakeet-tdt-0.6b-v3-onnx"
)

requires_real_engine = pytest.mark.skipif(
    not (
        importlib.util.find_spec("librosa")
        and importlib.util.find_spec("onnx_asr")
        and MODEL_CACHE.exists()
    ),
    reason="the lyrics stack or its cached model is missing (tests never download models)",
)

pytestmark = pytest.mark.integration


@pytest.fixture
def case() -> BenchmarkCase:
    return load_case(CASE_FILE)


def _sidecar() -> dict[str, Any]:
    return json.loads(SIDECAR.read_text(encoding="utf-8"))


class TestTheCommittedCase:
    """The case is a real file, a real annotation, and a recorded run."""

    def test_the_audio_is_the_committed_sample(self, case: BenchmarkCase) -> None:
        audio = case.audio_path()
        assert audio is not None
        assert audio.resolve() == (SIDECAR.with_suffix(".wav")).resolve()
        assert audio.exists()
        assert _sidecar()["audio"] == "vocadito_6.wav"

    def test_the_reference_is_the_dataset_annotation(self, case: BenchmarkCase) -> None:
        """One source of truth: the case copies the sidecar, it does not retype it."""
        assert case.reference["lyrics_text"] == _sidecar()["lyrics_text"]

    def test_the_case_carries_the_provenance_of_a_measured_run(self, case: BenchmarkCase) -> None:
        assert case.engine == "parakeet-onnx"
        assert case.engine_version == ENGINE_VERSION
        assert case.model == "nemo-parakeet-tdt-0.6b-v3"
        assert case.duration_seconds == _sidecar()["duration_seconds"]
        assert case.processing_time_seconds is not None
        assert case.processing_time_seconds > 0.0
        # Peak RSS is a figure this platform cannot report, so it stays null.
        assert case.peak_memory_bytes is None

    def test_only_the_families_the_ground_truth_supports_are_declared(
        self, case: BenchmarkCase
    ) -> None:
        """vocadito annotates lyrics; it records no chords, key or tempo."""
        sidecar = _sidecar()
        assert sidecar["chords"] is None
        assert sidecar["key"] is None
        assert sidecar["tempo"] is None
        assert sidecar["word_timestamps"] is None
        assert set(case.reference) == {"lyrics_text"}


class TestScoringTheStoredPair:
    """The metric chain on a real file, with no optional dependency in sight."""

    def test_the_stored_pair_scores_the_lyrics_family(self, case: BenchmarkCase) -> None:
        metrics = score_case(case)["metrics"]

        reference = case.reference["lyrics_text"]
        hypothesis = case.hypothesis["lyrics_text"]
        assert metrics["lyrics.wer"] == pytest.approx(word_error_rate(reference, hypothesis))
        assert metrics["lyrics.cer"] == pytest.approx(character_error_rate(reference, hypothesis))
        assert metrics["performance.real_time_factor"] == pytest.approx(
            real_time_factor(case.duration_seconds, case.processing_time_seconds)
        )

    def test_an_unsupported_family_is_absent_not_zero(self, case: BenchmarkCase) -> None:
        metrics = score_case(case)["metrics"]

        assert not [key for key in metrics if key.startswith(("chords.", "key.", "tempo."))]

    def test_the_directory_loads_as_one_case(self) -> None:
        cases = load_cases(CASES)

        assert [item.song for item in cases] == ["vocadito_6"]

    def test_the_report_renders_every_format(self, case: BenchmarkCase) -> None:
        report = build_report([case])

        assert to_json(report)
        assert "vocadito_6" in to_csv(report)
        assert "parakeet-onnx" in to_markdown(report)

    def test_the_command_scores_the_case_directory(self, tmp_path: Path) -> None:
        assert main(["benchmark", str(CASES), "--output", str(tmp_path / "report")]) == 0

        written = (tmp_path / "report" / "benchmark.json").read_text(encoding="utf-8")
        assert json.loads(written)["summary"]["parakeet-onnx"]["cases"] == 1


@requires_real_engine
@pytest.mark.slow
class TestTheEngineRerunOnTheSameCase:
    """``--engine`` re-produces the hypothesis instead of trusting the stored one.

    Structural checks only, and no re-measured accuracy claim: the recorded error
    rates belong to ``docs/BENCHMARK.md`` and ``docs/ENGINE_COMPARISON.md``, with
    their own environment and date.
    """

    def test_the_run_fills_the_lyrics_family_and_its_cost(
        self, case: BenchmarkCase, tmp_path: Path
    ) -> None:
        engine = ParakeetLyricsEngine()
        assert engine.is_available()

        updated, runs = run_engine_on_cases([case], engine)

        assert len(runs) == 1
        result = updated[0]
        assert result.engine == "parakeet-onnx"
        assert result.hypothesis["lyrics_text"].strip()
        words = result.hypothesis["lyrics_words"]
        assert words, "the model reports token timestamps, so words are timed"
        duration = result.duration_seconds
        assert duration is not None
        assert all(0.0 <= float(word["start"]) <= duration for word in words)
        assert result.processing_time_seconds and result.processing_time_seconds > 0.0
        # The reference side is never touched by a run.
        assert result.reference == case.reference
        assert score_case(result)["metrics"]["lyrics.wer"] == pytest.approx(
            word_error_rate(case.reference["lyrics_text"], result.hypothesis["lyrics_text"])
        )

    def test_the_command_runs_the_registered_engine(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert main(["benchmark", str(CASES), "--engine", "parakeet-onnx", "--json"]) == 0

        payload = json.loads(capsys.readouterr().out)
        row = payload["cases"][0]
        assert row["engine"] == "parakeet-onnx"
        assert row["metrics"]["lyrics.wer"] is not None
