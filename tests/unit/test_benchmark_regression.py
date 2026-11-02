"""Tests for the accuracy vector and the tracking of changes (roadmap Phase J).

The vector is the piece that turns "we measured CSR on 180 takes" into
"this run did or did not move that number on that set". These tests need no
optional dependency: the corpus manifest is read with the stdlib only, so the
committed vector -- and the figures it is allowed to carry -- are checked in the
same environment the CI matrix installs. The end-to-end wiring into
``scripts/chord_benchmark.py`` is covered in ``test_chord_benchmark_harness.py``,
behind the DSP marker.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from song_chord_lyrics_analyzer.benchmark.regression import (
    SCHEMA_VERSION,
    UNCHANGED_BAND,
    AccuracyVector,
    EvaluationSet,
    MetricReference,
    compare_run,
    evaluation_set_mismatch,
    format_report,
    load_vector,
    to_document,
    vector_from_aggregate,
    write_vector,
)
from song_chord_lyrics_analyzer.evaluation.guitarset import load_manifest
from song_chord_lyrics_analyzer.utils.errors import InputError

ROOT = Path(__file__).resolve().parents[2]
COMMITTED_VECTOR = ROOT / "benchmark" / "reference" / "chroma_baseline-instructed.json"
COMMITTED_MANIFEST = ROOT / "tests" / "fixtures" / "guitarset_comp_manifest.json"

#: The figures docs/ENGINE_COMPARISON.md §8 publishes for the adopted run.
#: They are the measured 180-take means of 2026-10-27, repeated here only so a
#: silent edit of the committed vector fails a test.
DOCUMENTED_MEANS = {
    "csr": 0.6312,
    "csr_triads": 0.6384,
    "segment_overlap": 0.8454,
    "change_f1": 0.8553,
    "hypothesis_chords": 13.07,
}


def _aggregate(
    *,
    digest: str = "a" * 64,
    takes: int = 180,
    reference: str = "instructed",
    metrics: dict[str, dict[str, float]] | None = None,
    engine: str = "chroma-baseline",
    numpy: str = "2.5.3",
    platform_name: str = "Linux x86_64",
) -> dict[str, Any]:
    """A harness aggregate with the §8 figures in it."""
    values = metrics
    if values is None:
        values = {name: {"mean": value} for name, value in DOCUMENTED_MEANS.items()}
    return {
        "manifest": "tests/fixtures/guitarset_comp_manifest.json",
        "manifest_sha256": "b" * 64,
        "manifest_content_digest": digest,
        "date": "2026-11-01 09:00:00",
        "settings": {
            "reference": reference,
            "decoder": "viterbi",
            "change_penalty": 0.4,
            "change_window": 0.5,
            "engine_options": {},
        },
        "environment": {
            "platform": platform_name,
            "python": "3.13.5",
            "engine": engine,
            "numpy": numpy,
            "librosa": "1.0.0",
            "git_commit": "deadbe1",
        },
        "metrics": {"count": takes, **values},
    }


def _vector(
    tmp_path: Path,
    metrics: dict[str, MetricReference],
    *,
    digest: str = "a" * 64,
    takes: int = 180,
    reference: str = "instructed",
    settings: dict[str, Any] | None = None,
    environment: dict[str, str] | None = None,
) -> AccuracyVector:
    """A vector of the given metrics, written and read back through the file."""
    vector = AccuracyVector(
        engine="chroma-baseline",
        metric_family="chords",
        evaluation_set=EvaluationSet(
            dataset="GuitarSet",
            version="1.1.0",
            manifest="tests/fixtures/guitarset_comp_manifest.json",
            content_digest=digest,
            takes=takes,
            split="comp",
            reference=reference,
        ),
        metrics=metrics,
        settings=settings or {"decoder": "viterbi", "change_penalty": 0.4},
        environment=environment or {"platform": "Linux x86_64", "numpy": "2.5.3"},
        date="2026-10-27",
        source="tests: a synthetic vector",
        notes="",
    )
    path = tmp_path / "vector.json"
    write_vector(vector, path)
    return load_vector(path)


def _csr(value: float) -> dict[str, MetricReference]:
    return {"csr": MetricReference(statistic="mean", value=value)}


# --------------------------------------------------------------------------- #
# The committed vector
# --------------------------------------------------------------------------- #
class TestTheCommittedVector:
    def test_it_loads_and_carries_the_documented_figures(self) -> None:
        vector = load_vector(COMMITTED_VECTOR)
        assert vector.engine == "chroma-baseline"
        assert vector.metric_family == "chords"
        assert {name: metric.value for name, metric in vector.metrics.items()} == pytest.approx(
            DOCUMENTED_MEANS
        )
        assert all(metric.statistic == "mean" for metric in vector.metrics.values())

    def test_it_names_the_pinned_evaluation_set(self) -> None:
        vector = load_vector(COMMITTED_VECTOR)
        assert vector.evaluation_set.takes == 180
        assert vector.evaluation_set.reference == "instructed"
        assert vector.evaluation_set.split == "comp"
        assert vector.evaluation_set.dataset == "GuitarSet"

    def test_its_digest_is_the_digest_of_the_committed_manifest(self) -> None:
        """The vector must name the set the repository actually pins."""
        vector = load_vector(COMMITTED_VECTOR)
        manifest = load_manifest(COMMITTED_MANIFEST)
        assert vector.evaluation_set.content_digest == manifest.content_digest()
        assert vector.evaluation_set.takes == len(manifest.takes)

    def test_its_source_section_and_date_are_recorded(self) -> None:
        vector = load_vector(COMMITTED_VECTOR)
        assert "ENGINE_COMPARISON.md" in vector.source
        assert vector.date == "2026-10-27"

    def test_the_file_is_what_the_writer_would_produce(self, tmp_path: Path) -> None:
        """A hand-checked figure cannot sneak in an unsorted or edited file."""
        vector = load_vector(COMMITTED_VECTOR)
        assert json.loads(COMMITTED_VECTOR.read_text(encoding="utf-8")) == to_document(vector)


# --------------------------------------------------------------------------- #
# Reading a vector
# --------------------------------------------------------------------------- #
class TestLoadingAVector:
    def _write(self, tmp_path: Path, document: dict[str, Any]) -> Path:
        path = tmp_path / "vector.json"
        path.write_text(json.dumps(document), encoding="utf-8")
        return path

    def test_a_valid_document_round_trips_through_the_writer(self, tmp_path: Path) -> None:
        vector = _vector(tmp_path, _csr(0.5))
        assert vector.metrics["csr"].value == 0.5
        assert vector.evaluation_set.content_digest == "a" * 64

    def test_it_refuses_a_file_that_is_not_json(self, tmp_path: Path) -> None:
        path = tmp_path / "broken.json"
        path.write_text("{not json", encoding="utf-8")
        with pytest.raises(InputError, match="not valid JSON"):
            load_vector(path)

    def test_it_refuses_a_path_that_is_not_there(self, tmp_path: Path) -> None:
        """``--vector`` is a command-line path, so a typo is a message not a trace."""
        with pytest.raises(InputError, match="no accuracy vector found"):
            load_vector(tmp_path / "does-not-exist.json")

    def test_it_refuses_another_schema(self, tmp_path: Path) -> None:
        document = to_document(_vector(tmp_path, _csr(0.5)))
        document["schema_version"] = "99"
        with pytest.raises(InputError, match="schema"):
            load_vector(self._write(tmp_path, document))

    def test_it_refuses_a_file_of_another_kind(self, tmp_path: Path) -> None:
        document = to_document(_vector(tmp_path, _csr(0.5)))
        document["kind"] = "benchmark_report"
        with pytest.raises(InputError, match="accuracy vector"):
            load_vector(self._write(tmp_path, document))

    def test_it_refuses_a_metric_it_cannot_read(self, tmp_path: Path) -> None:
        document = to_document(_vector(tmp_path, _csr(0.5)))
        document["metrics"]["csr_sounds_great"] = {"statistic": "mean", "value": 0.9}
        with pytest.raises(InputError, match="unknown metric"):
            load_vector(self._write(tmp_path, document))

    def test_it_refuses_a_statistic_the_aggregate_does_not_offer(self, tmp_path: Path) -> None:
        document = to_document(_vector(tmp_path, _csr(0.5)))
        document["metrics"]["csr"]["statistic"] = "p95"
        with pytest.raises(InputError, match="statistic"):
            load_vector(self._write(tmp_path, document))

    def test_it_refuses_a_number_that_is_not_finite(self, tmp_path: Path) -> None:
        document = to_document(_vector(tmp_path, _csr(0.5)))
        document["metrics"]["csr"]["value"] = float("inf")
        with pytest.raises(InputError, match="finite"):
            load_vector(self._write(tmp_path, document))

    def test_it_refuses_an_empty_metric_block(self, tmp_path: Path) -> None:
        document = to_document(_vector(tmp_path, _csr(0.5)))
        document["metrics"] = {}
        with pytest.raises(InputError, match="non-empty"):
            load_vector(self._write(tmp_path, document))

    def test_it_refuses_an_unknown_annotation_view(self, tmp_path: Path) -> None:
        document = to_document(_vector(tmp_path, _csr(0.5)))
        document["evaluation_set"]["reference"] = "guessed"
        with pytest.raises(InputError, match="reference view"):
            load_vector(self._write(tmp_path, document))

    def test_it_refuses_a_digest_that_is_not_a_digest(self, tmp_path: Path) -> None:
        document = to_document(_vector(tmp_path, _csr(0.5)))
        document["evaluation_set"]["content_digest"] = "short"
        with pytest.raises(InputError, match="SHA-256"):
            load_vector(self._write(tmp_path, document))

    def test_it_refuses_a_set_with_no_takes(self, tmp_path: Path) -> None:
        document = to_document(_vector(tmp_path, _csr(0.5)))
        document["evaluation_set"]["takes"] = 0
        with pytest.raises(InputError, match="positive integer"):
            load_vector(self._write(tmp_path, document))

    def test_it_refuses_a_missing_provenance_field(self, tmp_path: Path) -> None:
        document = to_document(_vector(tmp_path, _csr(0.5)))
        del document["source"]
        with pytest.raises(InputError, match="source"):
            load_vector(self._write(tmp_path, document))


# --------------------------------------------------------------------------- #
# Is this run the vector's evaluation set?
# --------------------------------------------------------------------------- #
class TestTheEvaluationSetGuard:
    def test_a_run_on_the_same_set_is_comparable(self) -> None:
        vector = AccuracyVector(**document_keys(_vector_stub(digest="a" * 64, takes=180)))
        assert evaluation_set_mismatch(vector, _aggregate(digest="a" * 64)) == []

    def test_a_subset_run_is_reported_as_incomparable(self, tmp_path: Path) -> None:
        vector = _vector(tmp_path, _csr(0.5), digest="a" * 64, takes=180)
        problems = evaluation_set_mismatch(vector, _aggregate(digest="a" * 64, takes=30))
        assert problems == ["the run scored 30 takes, the vector pins 180"]

    def test_a_different_corpus_is_reported_as_incomparable(self, tmp_path: Path) -> None:
        vector = _vector(tmp_path, _csr(0.5), digest="a" * 64)
        problems = evaluation_set_mismatch(vector, _aggregate(digest="c" * 64))
        assert len(problems) == 1
        assert "content digest differs" in problems[0]

    def test_a_run_that_recorded_no_digest_is_reported(self, tmp_path: Path) -> None:
        vector = _vector(tmp_path, _csr(0.5))
        aggregate = _aggregate()
        del aggregate["manifest_content_digest"]
        assert evaluation_set_mismatch(vector, aggregate) == [
            "the run does not record the manifest's content digest"
        ]

    def test_the_other_annotation_view_is_reported(self, tmp_path: Path) -> None:
        vector = _vector(tmp_path, _csr(0.5), reference="instructed")
        problems = evaluation_set_mismatch(vector, _aggregate(reference="performed"))
        assert "performed" in problems[0] and "instructed" in problems[0]

    def test_compare_run_refuses_an_incomparable_run(self, tmp_path: Path) -> None:
        vector = _vector(tmp_path, _csr(0.5), digest="a" * 64)
        with pytest.raises(InputError, match="not measured on the vector's fixed evaluation set"):
            compare_run(vector, _aggregate(digest="d" * 64))

    def test_compare_run_refuses_a_metric_the_run_does_not_report(self, tmp_path: Path) -> None:
        vector = _vector(tmp_path, _csr(0.5), digest="a" * 64)
        aggregate = _aggregate(digest="a" * 64, metrics={})
        with pytest.raises(InputError, match="does not report 'csr'"):
            compare_run(vector, aggregate)


def _vector_stub(*, digest: str, takes: int) -> dict[str, Any]:
    """A vector as a dict, for the one test that builds it without a file."""
    return to_document(
        AccuracyVector(
            engine="chroma-baseline",
            metric_family="chords",
            evaluation_set=EvaluationSet(
                dataset="GuitarSet",
                version="1.1.0",
                manifest="tests/fixtures/guitarset_comp_manifest.json",
                content_digest=digest,
                takes=takes,
                split="comp",
                reference="instructed",
            ),
            metrics=_csr(0.5),
        )
    )


def document_keys(document: dict[str, Any]) -> dict[str, Any]:
    """Rebuild the dataclass arguments from a serialized vector."""
    return {
        "engine": document["engine"],
        "metric_family": document["metric_family"],
        "evaluation_set": EvaluationSet(**document["evaluation_set"]),
        "metrics": {
            name: MetricReference(**values) for name, values in document["metrics"].items()
        },
        "settings": document["settings"],
        "environment": document["environment"],
        "date": document["date"],
        "source": document["source"],
        "notes": document["notes"],
    }


# --------------------------------------------------------------------------- #
# The verdict
# --------------------------------------------------------------------------- #
class TestTheVerdict:
    def test_a_gain_beyond_the_band_is_improved(self, tmp_path: Path) -> None:
        vector = _vector(tmp_path, _csr(0.6), digest="a" * 64)
        report = compare_run(vector, _aggregate(digest="a" * 64, metrics={"csr": {"mean": 0.62}}))
        assert report.verdict == "improved"
        assert report.deltas[0].change == pytest.approx(0.02)

    def test_a_loss_beyond_the_band_is_regressed(self, tmp_path: Path) -> None:
        vector = _vector(tmp_path, _csr(0.6), digest="a" * 64)
        report = compare_run(vector, _aggregate(digest="a" * 64, metrics={"csr": {"mean": 0.58}}))
        assert report.verdict == "regressed"

    def test_the_same_run_is_unchanged(self, tmp_path: Path) -> None:
        vector = _vector(tmp_path, dict(_csr(0.6)), digest="a" * 64)
        report = compare_run(vector, _aggregate(digest="a" * 64, metrics={"csr": {"mean": 0.6}}))
        assert report.verdict == "unchanged"

    def test_a_change_inside_the_band_is_not_a_measured_change(self, tmp_path: Path) -> None:
        """The vectors publish four decimals, so the fifth is their rounding."""
        vector = _vector(tmp_path, _csr(0.6), digest="a" * 64)
        within = compare_run(
            vector, _aggregate(digest="a" * 64, metrics={"csr": {"mean": 0.6 + UNCHANGED_BAND}})
        )
        beyond = compare_run(
            vector,
            _aggregate(digest="a" * 64, metrics={"csr": {"mean": 0.6 + UNCHANGED_BAND * 2}}),
        )
        assert within.verdict == "unchanged"
        assert beyond.verdict == "improved"

    def test_a_smaller_boundary_error_is_an_improvement(self, tmp_path: Path) -> None:
        key = "timing_reference_to_hypothesis"
        vector = _vector(
            tmp_path,
            {key: MetricReference(statistic="median", value=0.16)},
            digest="a" * 64,
        )
        report = compare_run(
            vector,
            _aggregate(digest="a" * 64, metrics={key: {"median": 0.12}}),
        )
        assert report.verdict == "improved"
        assert report.deltas[0].direction == "lower"

    def test_a_chord_count_is_reported_but_never_judged(self, tmp_path: Path) -> None:
        vector = _vector(
            tmp_path, {"hypothesis_chords": MetricReference("mean", 13.07)}, digest="a" * 64
        )
        report = compare_run(
            vector,
            _aggregate(digest="a" * 64, metrics={"hypothesis_chords": {"mean": 25.0}}),
        )
        assert report.verdict == "unchanged"
        assert report.deltas[0].verdict == "reported"

    def test_one_regression_decides_the_overall_verdict(self, tmp_path: Path) -> None:
        vector = _vector(
            tmp_path,
            {
                "csr": MetricReference("mean", 0.60),
                "change_f1": MetricReference("mean", 0.85),
            },
            digest="a" * 64,
        )
        report = compare_run(
            vector,
            _aggregate(
                digest="a" * 64,
                metrics={"csr": {"mean": 0.65}, "change_f1": {"mean": 0.80}},
            ),
        )
        assert {delta.metric: delta.verdict for delta in report.deltas} == {
            "csr": "improved",
            "change_f1": "regressed",
        }
        assert report.verdict == "regressed"

    def test_it_names_the_engine_that_ran(self, tmp_path: Path) -> None:
        vector = _vector(tmp_path, _csr(0.6), digest="a" * 64)
        report = compare_run(
            vector,
            _aggregate(digest="a" * 64, engine="learned-engine", metrics={"csr": {"mean": 0.7}}),
        )
        assert (report.engine, report.reference_engine) == ("learned-engine", "chroma-baseline")
        assert report.verdict == "improved"

    def test_it_reports_changed_settings_and_environment(self, tmp_path: Path) -> None:
        vector = _vector(
            tmp_path,
            _csr(0.6),
            digest="a" * 64,
            settings={"decoder": "viterbi", "change_penalty": 0.4},
            environment={"platform": "Linux x86_64", "numpy": "2.5.3"},
        )
        aggregate = _aggregate(
            digest="a" * 64,
            metrics={"csr": {"mean": 0.6}},
            platform_name="Windows-10",
        )
        aggregate["settings"]["change_penalty"] = 0.6
        report = compare_run(vector, aggregate)
        assert report.settings_changed == ("change_penalty",)
        assert report.environment_changed is True

    def test_an_unrecorded_environment_is_not_a_difference(self, tmp_path: Path) -> None:
        vector = _vector(tmp_path, _csr(0.6), digest="a" * 64, environment={})
        report = compare_run(vector, _aggregate(digest="a" * 64, metrics={"csr": {"mean": 0.6}}))
        assert report.environment_changed is False

    def test_a_setting_the_vector_never_recorded_is_not_a_change(self, tmp_path: Path) -> None:
        """The vector pins the settings it measured; the rest are new to it, not moved."""
        vector = _vector(tmp_path, _csr(0.6), digest="a" * 64, settings={"decoder": "viterbi"})
        report = compare_run(vector, _aggregate(digest="a" * 64, metrics={"csr": {"mean": 0.6}}))
        assert report.settings_changed == ()


# --------------------------------------------------------------------------- #
# The report
# --------------------------------------------------------------------------- #
class TestTheReport:
    def test_it_prints_the_verdict_and_one_row_per_metric(self, tmp_path: Path) -> None:
        vector = _vector(tmp_path, _csr(0.6), digest="a" * 64)
        report = compare_run(vector, _aggregate(digest="a" * 64, metrics={"csr": {"mean": 0.62}}))
        lines = format_report(report).splitlines()
        assert lines[0].startswith("verdict: improved")
        assert "Duration CSR" in "\n".join(lines)
        assert "+0.0200" in "\n".join(lines)

    def test_it_warns_when_the_environment_changed(self, tmp_path: Path) -> None:
        vector = _vector(
            tmp_path, _csr(0.6), digest="a" * 64, environment={"platform": "Linux x86_64"}
        )
        report = compare_run(
            vector,
            _aggregate(
                digest="a" * 64,
                metrics={"csr": {"mean": 0.6}},
                platform_name="Windows-10",
            ),
        )
        assert "not like-for-like" in format_report(report)

    def test_it_says_which_figures_are_only_described(self, tmp_path: Path) -> None:
        vector = _vector(
            tmp_path, {"hypothesis_chords": MetricReference("mean", 13.07)}, digest="a" * 64
        )
        report = compare_run(
            vector,
            _aggregate(digest="a" * 64, metrics={"hypothesis_chords": {"mean": 13.07}}),
        )
        assert "reported, not judged" in format_report(report)

    def test_the_dict_form_is_json_safe(self, tmp_path: Path) -> None:
        vector = _vector(tmp_path, _csr(0.6), digest="a" * 64)
        report = compare_run(vector, _aggregate(digest="a" * 64, metrics={"csr": {"mean": 0.62}}))
        encoded = json.dumps(report.to_dict(), allow_nan=False)
        assert json.loads(encoded)["verdict"] == "improved"
        assert json.loads(encoded)["schema_version"] == SCHEMA_VERSION


# --------------------------------------------------------------------------- #
# Adopting a new vector
# --------------------------------------------------------------------------- #
class TestAdoptingARunAsAVector:
    def test_it_keeps_the_run_figures_and_the_set_it_scored(self, tmp_path: Path) -> None:
        manifest = load_manifest(COMMITTED_MANIFEST)
        aggregate = _aggregate(digest=manifest.content_digest(), takes=len(manifest.takes))
        vector = vector_from_aggregate(
            aggregate,
            manifest=manifest,
            source="tests: this run",
        )
        path = tmp_path / "adopted.json"
        write_vector(vector, path)
        reloaded = load_vector(path)
        assert reloaded.metrics["csr"].value == pytest.approx(DOCUMENTED_MEANS["csr"])
        assert reloaded.evaluation_set.takes == 180
        assert reloaded.evaluation_set.split == "comp"
        assert reloaded.evaluation_set.content_digest == manifest.content_digest()
        assert reloaded.date == "2026-11-01"
        assert reloaded.environment["platform"] == "Linux x86_64"

    def test_it_refuses_a_run_with_no_metrics(self, tmp_path: Path) -> None:
        manifest = load_manifest(COMMITTED_MANIFEST)
        aggregate = _aggregate(digest=manifest.content_digest())
        aggregate["metrics"] = {"count": 180}
        with pytest.raises(InputError, match="none of the tracked metrics"):
            vector_from_aggregate(aggregate, manifest=manifest, source="tests")

    def test_it_refuses_a_run_that_scored_nothing(self, tmp_path: Path) -> None:
        manifest = load_manifest(COMMITTED_MANIFEST)
        aggregate = _aggregate(digest=manifest.content_digest(), takes=0)
        with pytest.raises(InputError, match="no takes"):
            vector_from_aggregate(aggregate, manifest=manifest, source="tests")

    def test_it_refuses_a_non_finite_figure(self, tmp_path: Path) -> None:
        manifest = load_manifest(COMMITTED_MANIFEST)
        aggregate = _aggregate(
            digest=manifest.content_digest(),
            metrics={"csr": {"mean": float("nan")}},
        )
        with pytest.raises(InputError, match="finite"):
            vector_from_aggregate(aggregate, manifest=manifest, source="tests")
