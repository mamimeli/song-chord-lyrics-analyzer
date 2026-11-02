"""Tests for the numeric acceptance bar and the command that grades it (A0).

The bar is ROADMAP §10's table: the numbers chord recognition has to *reach*,
as opposed to the accuracy vector, which records where it is. These tests need
no optional dependency and no corpus -- grading reads two JSON documents -- so
they run in the same environment the CI matrix installs.

Every figure here is either written into a fixture or the arithmetic difference
between the committed vector and the committed bar. The last test is the only
one that touches the recorded values, and it asserts the relationship between
two documents this repository already publishes, not a new measurement.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from song_chord_lyrics_analyzer.benchmark.acceptance import (
    MET,
    NOT_RECORDED,
    SCHEMA_VERSION,
    STATUS_PROPOSED,
    STATUS_RATIFIED,
    UNMET,
    BarReport,
    format_bar_report,
    grade_run,
    grade_vector,
    load_bar,
)
from song_chord_lyrics_analyzer.benchmark.regression import (
    _DIRECTIONS,
    AccuracyVector,
    EvaluationSet,
    MetricReference,
    load_vector,
    write_vector,
)
from song_chord_lyrics_analyzer.utils.errors import InputError

ROOT = Path(__file__).resolve().parents[2]
COMMITTED_BAR = ROOT / "benchmark" / "reference" / "acceptance-bar.json"
COMMITTED_VECTOR = ROOT / "benchmark" / "reference" / "chroma_baseline-instructed.json"

#: The evaluation set the bar pins. Synthetic records use a stand-in digest so a
#: fixture cannot be mistaken for the corpus.
SYNTHETIC_DIGEST = "a" * 64


def _bar_document(**overrides: Any) -> dict[str, Any]:
    """The committed bar document, with the top-level fields overridable."""
    document = json.loads(COMMITTED_BAR.read_text(encoding="utf-8"))
    for key, value in overrides.items():
        if value is None:
            document.pop(key, None)
        else:
            document[key] = value
    if "evaluation_set" not in overrides:
        document["evaluation_set"]["content_digest"] = SYNTHETIC_DIGEST
    return document


def _write(tmp_path: Path, document: dict[str, Any], name: str = "bar.json") -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(document, indent=1) + "\n", encoding="utf-8")
    return path


def _bar(tmp_path: Path, **overrides: Any) -> Path:
    """A bar on the synthetic set, ready to hand to a grader."""
    return _write(tmp_path, _bar_document(**overrides))


def _vector(
    tmp_path: Path, metrics: dict[str, MetricReference], *, takes: int = 180
) -> AccuracyVector:
    """A vector on the synthetic set, written and read back through the file."""
    vector = AccuracyVector(
        engine="chroma-baseline",
        metric_family="chords",
        evaluation_set=EvaluationSet(
            dataset="GuitarSet",
            version="1.1.0",
            manifest="tests/fixtures/guitarset_comp_manifest.json",
            content_digest=SYNTHETIC_DIGEST,
            takes=takes,
            split="comp",
            reference="instructed",
        ),
        metrics=metrics,
        settings={"decoder": "viterbi", "change_penalty": 0.4},
        environment={"platform": "Linux x86_64", "numpy": "2.5.3"},
        date="2026-10-27",
        source="tests: a synthetic vector",
    )
    write_vector(vector, tmp_path / "vector.json")
    return load_vector(tmp_path / "vector.json")


def _passing(metrics: dict[str, float]) -> dict[str, MetricReference]:
    return {name: MetricReference("mean", value) for name, value in metrics.items()}


def _aggregate(metrics: dict[str, dict[str, float]], **overrides: Any) -> dict[str, Any]:
    """A harness aggregate on the synthetic set."""
    document: dict[str, Any] = {
        "manifest": "tests/fixtures/guitarset_comp_manifest.json",
        "manifest_content_digest": SYNTHETIC_DIGEST,
        "date": "2026-11-02 09:00:00",
        "settings": {"reference": "instructed", "decoder": "viterbi"},
        "environment": {"engine": "chroma-baseline", "platform": "Linux x86_64"},
        "metrics": {"count": 180, **metrics},
    }
    document.update(overrides)
    return document


ALL_ABOVE = {
    "csr": 0.68,
    "csr_triads": 0.7124,
    "segment_overlap": 0.9,
    "change_f1": 0.95,
    "timing_reference_to_hypothesis": 0.12,
}


# --------------------------------------------------------------------------- #
# The committed document
# --------------------------------------------------------------------------- #


def test_the_committed_bar_is_a_proposed_bar_of_the_pinned_set() -> None:
    bar = load_bar(COMMITTED_BAR)
    assert bar.status == STATUS_PROPOSED
    assert bar.evaluation_set.takes == 180
    assert bar.evaluation_set.reference == "instructed"
    assert bar.proposed_date == "2026-11-02"
    # A proposed bar has no ratification date; the status is the only place a
    # reader could otherwise invent one.
    assert bar.ratified_date == ""


def test_the_bar_carries_the_numbers_the_roadmap_table_publishes() -> None:
    bar = load_bar(COMMITTED_BAR)
    rows = {row.metric: row for row in bar.rows}
    assert (rows["csr_triads"].comparator, rows["csr_triads"].target) == (">=", 0.70)
    assert (rows["csr"].comparator, rows["csr"].target) == (">=", 0.68)
    assert (rows["segment_overlap"].comparator, rows["segment_overlap"].target) == (">=", 0.86)
    assert (rows["change_f1"].comparator, rows["change_f1"].target) == (">=", 0.88)
    assert (
        rows["timing_reference_to_hypothesis"].comparator,
        rows["timing_reference_to_hypothesis"].target,
    ) == ("<=", 0.12)


def test_the_bar_names_the_statistic_the_boundary_row_was_left_ambiguous(
    tmp_path: Path,
) -> None:
    """§8's boundary column never said which statistic it printed.

    The bar may not inherit that: a target without a named statistic is a
    number two people can both claim to have reached.
    """
    bar = load_bar(COMMITTED_BAR)
    timing = next(row for row in bar.rows if row.metric == "timing_reference_to_hypothesis")
    assert timing.statistic == "mean"
    assert "statistic" in timing.note


def test_every_bar_row_names_a_metric_the_harness_reports() -> None:
    """A row for a figure the harness cannot produce is a bar nobody can reach."""
    bar = load_bar(COMMITTED_BAR)
    for row in bar.rows:
        assert row.metric in _DIRECTIONS
        assert row.label
        assert row.guards


def test_the_bar_records_the_rules_it_cannot_grade_and_why() -> None:
    bar = load_bar(COMMITTED_BAR)
    assert {rule.name for rule in bar.ungraded} == {
        "vocabulary_no_loss",
        "confidence_ece",
        "second_corpus_triad_csr",
    }
    for rule in bar.ungraded:
        assert rule.rule
        assert rule.why
        assert rule.where


@pytest.mark.parametrize(
    ("field", "value", "fragment"),
    [
        ("schema_version", "99", "schema"),
        ("kind", "accuracy_vector", "acceptance bar"),
        ("status", "agreed", "status"),
        ("rows", [], "non-empty"),
        ("proposed_date", None, "proposed_date"),
        ("evaluation_set", None, "evaluation_set"),
    ],
)
def test_a_malformed_bar_is_refused(tmp_path: Path, field: str, value: Any, fragment: str) -> None:
    document = _bar_document()
    if value is None:
        document.pop(field, None)
    else:
        document[field] = value
    with pytest.raises(InputError) as error:
        load_bar(_write(tmp_path, document, name=f"bar-{fragment}.json"))
    assert fragment in str(error.value.message)


def test_a_row_for_an_unknown_metric_is_refused(tmp_path: Path) -> None:
    document = _bar_document()
    document["rows"][0]["metric"] = "csr_but_nicer"
    with pytest.raises(InputError, match="unknown metric"):
        load_bar(_write(tmp_path, document))


def test_a_row_with_a_non_finite_target_is_refused(tmp_path: Path) -> None:
    document = _bar_document()
    document["rows"][0]["target"] = "Infinity"
    with pytest.raises(InputError, match="finite"):
        load_bar(_write(tmp_path, document))


def test_a_row_with_an_unknown_comparator_is_refused(tmp_path: Path) -> None:
    document = _bar_document()
    document["rows"][0]["comparator"] = "~="
    with pytest.raises(InputError, match="comparator"):
        load_bar(_write(tmp_path, document))


def test_a_bar_with_two_rows_for_one_metric_is_refused(tmp_path: Path) -> None:
    document = _bar_document()
    document["rows"].append(dict(document["rows"][0]))
    with pytest.raises(InputError, match="twice"):
        load_bar(_write(tmp_path, document))


def test_a_ratified_bar_without_a_date_is_refused(tmp_path: Path) -> None:
    document = _bar_document(status=STATUS_RATIFIED, ratified_date=None)
    with pytest.raises(InputError, match="ratified_date"):
        load_bar(_write(tmp_path, document))


# --------------------------------------------------------------------------- #
# Grading a recorded vector
# --------------------------------------------------------------------------- #


def test_a_record_at_or_better_than_every_target_meets_the_bar(tmp_path: Path) -> None:
    report = grade_vector(load_bar(_bar(tmp_path)), _vector(tmp_path, _passing(ALL_ABOVE)))
    assert [row.verdict for row in report.outcomes] == [MET] * len(report.outcomes)
    assert report.bar_met
    assert report.required_outstanding == 0
    # A row met exactly at its target has a margin of zero, not a negative one.
    assert next(r for r in report.outcomes if r.metric == "csr").margin == pytest.approx(0.0)


def test_a_metric_the_record_does_not_carry_is_not_recorded(tmp_path: Path) -> None:
    metrics = dict(ALL_ABOVE)
    del metrics["timing_reference_to_hypothesis"]
    report = grade_vector(load_bar(_bar(tmp_path)), _vector(tmp_path, _passing(metrics)))
    timing = next(r for r in report.outcomes if r.metric == "timing_reference_to_hypothesis")
    assert timing.verdict == NOT_RECORDED
    assert timing.recorded is None
    assert "does not carry" in timing.reason
    assert not report.complete
    # An absent figure is not a failed one: the report keeps the two apart.
    assert (report.met_count, report.unmet_count) == (4, 0)


def test_a_statistic_the_record_publishes_differently_is_not_recorded(tmp_path: Path) -> None:
    document = _bar_document()
    document["rows"] = [row for row in document["rows"] if row["metric"] == "csr"]
    document["rows"][0]["statistic"] = "median"
    report = grade_vector(
        load_bar(_write(tmp_path, document)),
        _vector(tmp_path, {"csr": MetricReference("mean", 0.9)}),
    )
    assert report.outcomes[0].verdict == NOT_RECORDED
    assert "median" in report.outcomes[0].reason
    assert "mean" in report.outcomes[0].reason


def test_a_lower_is_better_row_is_graded_in_the_right_direction(tmp_path: Path) -> None:
    document = _bar_document()
    document["rows"] = [
        row for row in document["rows"] if row["metric"] == "timing_reference_to_hypothesis"
    ]
    bar = load_bar(_write(tmp_path, document))
    worse = _vector(tmp_path, {"timing_reference_to_hypothesis": MetricReference("mean", 0.2)})
    better = _vector(tmp_path, {"timing_reference_to_hypothesis": MetricReference("mean", 0.05)})
    assert grade_vector(bar, worse).outcomes[0].verdict == UNMET
    assert grade_vector(bar, worse).outcomes[0].margin == pytest.approx(-0.08)
    assert grade_vector(bar, better).outcomes[0].verdict == MET
    assert grade_vector(bar, better).outcomes[0].margin == pytest.approx(0.07)


def test_a_vector_of_a_different_evaluation_set_is_refused(tmp_path: Path) -> None:
    bar = load_bar(_bar(tmp_path))
    with pytest.raises(InputError) as error:
        grade_vector(bar, _vector(tmp_path, _passing(ALL_ABOVE), takes=30))
    # The refusal names the set in the message and the reasons in the hint, the
    # same shape the regression gate uses.
    assert "not measured on the bar's fixed evaluation set" in error.value.message
    assert "30 takes" in str(error.value.hint)
    assert "180" in str(error.value.hint)


def test_a_vector_of_another_annotation_view_is_refused(tmp_path: Path) -> None:
    document = _bar_document()
    document["evaluation_set"]["reference"] = "performed"
    bar = load_bar(_write(tmp_path, document))
    with pytest.raises(InputError, match="performed"):
        grade_vector(bar, _vector(tmp_path, _passing(ALL_ABOVE)))


def test_a_record_that_reports_none_of_the_bar_is_refused(tmp_path: Path) -> None:
    bar = load_bar(_bar(tmp_path))
    with pytest.raises(InputError, match="none of the metrics"):
        grade_vector(bar, _vector(tmp_path, {"hypothesis_chords": MetricReference("mean", 13.07)}))


# --------------------------------------------------------------------------- #
# Grading a fresh run
# --------------------------------------------------------------------------- #


def test_a_run_is_graded_from_the_statistics_it_reports(tmp_path: Path) -> None:
    report = grade_run(
        load_bar(_bar(tmp_path)),
        _aggregate(
            {
                "csr": {"mean": 0.70},
                "csr_triads": {"mean": 0.72, "median": 0.71},
                "segment_overlap": {"mean": 0.87},
                "change_f1": {"mean": 0.89},
                "timing_reference_to_hypothesis": {"mean": 0.14, "median": 0.11},
            }
        ),
    )
    assert report.record_label.startswith("run of 2026-11-02")
    # The bar asks for the mean boundary figure, so 0.14 is the number graded
    # and not the flattering 0.11 beside it.
    timing = next(r for r in report.outcomes if r.metric == "timing_reference_to_hypothesis")
    assert timing.recorded == pytest.approx(0.14)
    assert timing.verdict == UNMET
    assert report.unmet_count == 1
    assert report.met_count == 4


def test_a_run_on_another_digest_is_refused(tmp_path: Path) -> None:
    aggregate = _aggregate({"csr": {"mean": 0.9}})
    aggregate["manifest_content_digest"] = "b" * 64
    with pytest.raises(InputError, match="content digest"):
        grade_run(load_bar(_bar(tmp_path)), aggregate)


def test_a_run_that_reports_none_of_the_bar_is_refused(tmp_path: Path) -> None:
    with pytest.raises(InputError, match="none of the metrics"):
        grade_run(load_bar(_bar(tmp_path)), _aggregate({"reference_chords": {"mean": 12.0}}))


def test_a_run_of_the_wrong_size_is_refused(tmp_path: Path) -> None:
    aggregate = _aggregate({"csr": {"mean": 0.9}})
    aggregate["metrics"]["count"] = 20
    with pytest.raises(InputError, match="takes"):
        grade_run(load_bar(_bar(tmp_path)), aggregate)


# --------------------------------------------------------------------------- #
# Reporting
# --------------------------------------------------------------------------- #


def test_the_report_says_the_bar_is_not_ratified(tmp_path: Path) -> None:
    report = grade_vector(
        load_bar(_bar(tmp_path)), _vector(tmp_path, {"csr": MetricReference("mean", 0.9)})
    )
    text = format_bar_report(report)
    assert "PROPOSED" in text
    assert "not ratified" in text
    assert "not graded by this check" in text


def test_a_ratified_bar_reports_the_date_it_was_ratified(tmp_path: Path) -> None:
    bar = load_bar(_bar(tmp_path, status=STATUS_RATIFIED, ratified_date="2026-11-02"))
    report = grade_vector(bar, _vector(tmp_path, {"csr": MetricReference("mean", 0.9)}))
    text = format_bar_report(report)
    assert "ratified 2026-11-02" in text
    assert "PROPOSED" not in text


def test_the_report_is_json_safe_and_keeps_the_provenance(tmp_path: Path) -> None:
    report = grade_vector(
        load_bar(_bar(tmp_path)), _vector(tmp_path, {"csr": MetricReference("mean", 0.9)})
    )
    document = report.to_dict()
    assert document["kind"] == "acceptance_check"
    assert document["schema_version"] == SCHEMA_VERSION
    assert document["bar_status"] == STATUS_PROPOSED
    assert document["evaluation_set"]["takes"] == 180
    assert len(document["rows"]) == len(report.outcomes)
    assert len(document["ungraded"]) == 3
    json.dumps(document, allow_nan=False)


def test_an_unmet_row_and_an_absent_row_are_told_apart_in_the_summary(
    tmp_path: Path,
) -> None:
    metrics = dict(ALL_ABOVE)
    metrics["csr"] = 0.5
    del metrics["change_f1"]
    report = grade_vector(load_bar(_bar(tmp_path)), _vector(tmp_path, _passing(metrics)))
    assert (report.met_count, report.unmet_count, report.not_recorded_count) == (3, 1, 1)
    assert report.bar_met is False
    assert report.required_outstanding == 2


# --------------------------------------------------------------------------- #
# scripts/chord_acceptance.py
# --------------------------------------------------------------------------- #

SCRIPT = ROOT / "scripts" / "chord_acceptance.py"


def _run_script(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *arguments],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_the_command_grades_the_committed_documents() -> None:
    """The default invocation needs no corpus, so it must answer in every venv."""
    result = _run_script()
    assert result.returncode == 1, result.stderr
    assert "PROPOSED" in result.stdout
    assert "not ratified" in result.stdout
    assert "the bar is NOT reached" in result.stdout
    assert "not graded by this check" in result.stdout
    assert result.stdout.count("| unmet |") == 4


def test_the_command_prints_one_json_document_when_asked() -> None:
    result = _run_script("--json")
    assert result.returncode == 1, result.stderr
    document = json.loads(result.stdout)
    assert document["kind"] == "acceptance_check"
    assert document["bar_status"] == STATUS_PROPOSED
    assert document["summary"]["unmet"] == 4
    assert document["summary"]["not_recorded"] == 1
    assert document["summary"]["bar_met"] is False


def test_the_command_exits_zero_when_every_required_row_is_met(tmp_path: Path) -> None:
    """A passing bar has to be reachable, or the exit code means nothing."""
    bar_path = _bar(tmp_path)
    vector_path = tmp_path / "passing.json"
    write_vector(
        AccuracyVector(
            engine="chroma-baseline",
            metric_family="chords",
            evaluation_set=load_bar(bar_path).evaluation_set,
            metrics=_passing(ALL_ABOVE),
            settings={"decoder": "viterbi"},
            environment={"platform": "Linux x86_64"},
            date="2026-11-02",
            source="tests: a synthetic passing vector",
        ),
        vector_path,
    )
    result = _run_script("--bar", str(bar_path), "--vector", str(vector_path))
    assert result.returncode == 0, result.stdout + result.stderr
    assert "the bar is reached" in result.stdout


def test_the_command_refuses_a_record_of_another_evaluation_set(tmp_path: Path) -> None:
    vector_path = tmp_path / "other-set.json"
    write_vector(
        AccuracyVector(
            engine="chroma-baseline",
            metric_family="chords",
            evaluation_set=EvaluationSet(
                dataset="GuitarSet",
                version="1.1.0",
                manifest="tests/fixtures/guitarset_comp_manifest.json",
                content_digest="c" * 64,
                takes=20,
                split="comp",
                reference="instructed",
            ),
            metrics=_passing(ALL_ABOVE),
            settings={"decoder": "viterbi"},
            environment={"platform": "Linux x86_64"},
            date="2026-11-02",
            source="tests: a vector of a smaller set",
        ),
        vector_path,
    )
    result = _run_script("--vector", str(vector_path))
    assert result.returncode == 2
    assert "not measured on the bar's fixed evaluation set" in result.stderr
    assert "20 takes" in result.stderr


def test_the_command_refuses_a_missing_bar(tmp_path: Path) -> None:
    result = _run_script("--bar", str(tmp_path / "nope.json"))
    assert result.returncode == 2
    assert "no acceptance bar found" in result.stderr


# --------------------------------------------------------------------------- #
# The real documents
# --------------------------------------------------------------------------- #


def test_the_committed_vector_does_not_meet_the_committed_bar() -> None:
    """The four figures §8 records sit below the four targets §10 proposes.

    This asserts the relationship between two committed documents -- the same
    subtraction the command prints -- and adds no measurement. If a later run
    carries the engine past a target, or either document is edited, this test
    fails and the change has to be deliberate.
    """
    bar = load_bar(COMMITTED_BAR)
    report = grade_vector(bar, load_vector(COMMITTED_VECTOR))
    assert isinstance(report, BarReport)
    assert report.bar_met is False
    assert report.unmet_count == 4
    assert report.not_recorded_count == 1
    margins = {row.metric: row.margin for row in report.outcomes}
    assert margins["csr_triads"] == pytest.approx(0.6384 - 0.70)
    assert margins["csr"] == pytest.approx(0.6312 - 0.68)
    assert margins["segment_overlap"] == pytest.approx(0.8454 - 0.86)
    assert margins["change_f1"] == pytest.approx(0.8553 - 0.88)
    # The vector deliberately omits the boundary column, because §8 does not
    # say which statistic its 0.158 s was printed as.
    timing = next(r for r in report.outcomes if r.metric == "timing_reference_to_hypothesis")
    assert timing.verdict == NOT_RECORDED
