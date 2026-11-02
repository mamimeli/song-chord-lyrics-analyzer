"""Chord-error decomposition tests (roadmap §10 task A1).

The recorded chord number says *how much* is lost; these tests pin *what* is
lost. ``evaluation/errors.py`` must:

* partition the scored timeline -- the class seconds sum to exactly the
  ``total_s`` that :func:`~song_chord_lyrics_analyzer.evaluation.chords.duration_csr`
  reports, and its agreement bucket is exactly the ``equal_s`` it reports, so a
  decomposition cannot invent or lose CSR points;
* name the disagreement, not just count it: a silent reference, a silent
  hypothesis, a wrong root, a wrong quality under the same root, and a
  difference the 24-triad view does not see;
* keep the boundary/timing view separate from the label view, because a boundary
  that moved shows up as label losses too -- :func:`snap_boundaries` is the
  counterfactual that measures how much of the loss is timing.

Everything here runs without numpy, librosa or the corpus: the pairs are
synthetic ``(start, end, label)`` segments. The last section drives
``scripts/chord_error_decomposition.py`` over a generated one-take corpus, the
way ``test_chord_benchmark_harness.py`` drives the benchmark.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from song_chord_lyrics_analyzer.evaluation.chords import duration_csr
from song_chord_lyrics_analyzer.evaluation.errors import (
    AGREEMENT,
    CHORD_ERROR_CLASSES,
    EXTENSION_OR_VOICING,
    MISSED_CHORD,
    SPURIOUS_CHORD,
    UNRESOLVED,
    WRONG_QUALITY,
    WRONG_ROOT,
    aggregate_decompositions,
    aggregate_timing_views,
    classify_disagreement,
    decompose,
    snap_boundaries,
    timing_view,
)
from song_chord_lyrics_analyzer.metrics.segmentation import segment_overlap


# --------------------------------------------------------------------------- #
# Naming one disagreement
# --------------------------------------------------------------------------- #
def test_agreement_is_named_before_any_error() -> None:
    assert classify_disagreement("C", "C") == AGREEMENT
    assert classify_disagreement("N", "N") == AGREEMENT
    assert classify_disagreement("N%", "N%") == AGREEMENT


@pytest.mark.parametrize(
    ("reference", "hypothesis", "expected"),
    [
        # A chord over a silent reference, and silence over a reference chord.
        ("N", "C", SPURIOUS_CHORD),
        ("C", "N", MISSED_CHORD),
        # An N-family spelling is still no chord, so the direction is the same.
        ("N%", "C", SPURIOUS_CHORD),
        ("C", "N%", MISSED_CHORD),
        # The root is what differs.
        ("C", "D", WRONG_ROOT),
        ("C", "Am", WRONG_ROOT),
        ("A#", "B", WRONG_ROOT),
        # Same root, different triad.
        ("C", "Cm", WRONG_QUALITY),
        ("Cm", "C", WRONG_QUALITY),
        ("Bb", "Bbm", WRONG_QUALITY),
        # Same triad: a spelling difference the 24-triad view does not see.
        ("C5", "C", EXTENSION_OR_VOICING),
        ("Csus2", "C", EXTENSION_OR_VOICING),
        ("Cdim", "C", EXTENSION_OR_VOICING),
    ],
)
def test_a_disagreement_is_classified_by_what_differs(
    reference: str, hypothesis: str, expected: str
) -> None:
    assert classify_disagreement(reference, hypothesis) == expected


def test_a_mirex_match_is_not_an_error_even_when_the_spelling_differs() -> None:
    """The classes follow the metric: MIREX-2010 equality is the arbiter.

    ``Cmaj7`` sounds ``C`` to the scorer (three shared pitch classes) and a
    slash bass is rescued, so neither is lost time and neither is a class.
    """
    assert classify_disagreement("Cmaj7", "C") == AGREEMENT
    assert classify_disagreement("C/E", "C") == AGREEMENT
    assert classify_disagreement("C7", "C") == AGREEMENT
    assert classify_disagreement("C:maj", "C") == AGREEMENT


def test_two_no_chord_spellings_are_the_scorers_not_the_engines() -> None:
    """``N%`` against ``N`` is a disagreement the pinned metric really does score.

    Attributing it to a chord class would misdescribe the engine, so it is named
    as unresolved and stays visible in the report.
    """
    assert classify_disagreement("N", "N%") == UNRESOLVED
    assert classify_disagreement("N%", "N") == UNRESOLVED


def test_the_class_list_is_the_set_of_losses() -> None:
    assert AGREEMENT not in CHORD_ERROR_CLASSES
    assert set(CHORD_ERROR_CLASSES) == {
        SPURIOUS_CHORD,
        MISSED_CHORD,
        WRONG_ROOT,
        WRONG_QUALITY,
        EXTENSION_OR_VOICING,
        UNRESOLVED,
    }


# --------------------------------------------------------------------------- #
# The partition: class seconds are the scored timeline
# --------------------------------------------------------------------------- #
def _timeline(*labels: str) -> list[tuple[float, float, str]]:
    """One-second segments, so each label contributes exactly 1.0 s."""
    return [(float(index), float(index + 1), label) for index, label in enumerate(labels)]


def test_the_classes_partition_the_scored_time_exactly() -> None:
    reference = _timeline("C", "G", "Am", "N", "F", "C")
    hypothesis = _timeline("C", "D", "Am", "F", "N", "Cm")

    result = decompose(reference, hypothesis)

    assert result.total_seconds == pytest.approx(6.0)
    assert result.correct_seconds == pytest.approx(2.0)
    assert result.lost_seconds == pytest.approx(4.0)
    assert result.seconds == {
        AGREEMENT: pytest.approx(2.0),
        SPURIOUS_CHORD: pytest.approx(1.0),  # reference N, hypothesis F
        MISSED_CHORD: pytest.approx(1.0),  # reference F, hypothesis N
        WRONG_ROOT: pytest.approx(1.0),  # G against D
        WRONG_QUALITY: pytest.approx(1.0),  # C against Cm
        EXTENSION_OR_VOICING: pytest.approx(0.0),
        UNRESOLVED: pytest.approx(0.0),
    }
    assert result.csr == pytest.approx(2.0 / 6.0)


def test_the_decomposition_reproduces_the_duration_csr_it_decomposes() -> None:
    """A decomposition that disagreed with the pinned metric would be worthless."""
    reference = _timeline("C:maj", "G:maj", "A:min7", "F:maj", "N", "D:maj")
    hypothesis = _timeline("C", "A", "Am", "Fmaj7", "G", "Dm")

    scored = duration_csr(reference, hypothesis)
    result = decompose(reference, hypothesis)

    assert result.total_seconds == pytest.approx(scored["total_s"])
    assert result.correct_seconds == pytest.approx(scored["equal_s"])
    assert result.csr == pytest.approx(scored["csr"])
    assert sum(result.seconds.values()) == pytest.approx(scored["total_s"])


def test_the_shares_of_the_loss_and_the_csr_points_agree() -> None:
    reference = _timeline("C", "C", "C", "C")
    hypothesis = _timeline("D", "Am", "N", "C")

    result = decompose(reference, hypothesis)

    assert result.shares_of_lost()[WRONG_ROOT] == pytest.approx(2.0 / 3.0)
    assert result.shares_of_lost()[MISSED_CHORD] == pytest.approx(1.0 / 3.0)
    # Two wrong roots on 4 s of reference cost 50 CSR points.
    assert result.csr_points_lost()[WRONG_ROOT] == pytest.approx(0.5)
    assert sum(result.csr_points_lost().values()) == pytest.approx(1.0 - result.csr)
    assert sum(result.shares_of_lost().values()) == pytest.approx(1.0)


def test_partial_overlaps_are_weighted_by_their_own_duration() -> None:
    reference = [(0.0, 2.0, "C"), (2.0, 3.0, "G")]
    # One hypothesis segment spans both references.
    hypothesis = [(0.0, 3.0, "D")]

    result = decompose(reference, hypothesis)

    assert result.total_seconds == pytest.approx(3.0)
    assert result.seconds[WRONG_ROOT] == pytest.approx(3.0)
    assert result.correct_seconds == pytest.approx(0.0)


def test_time_outside_the_overlap_is_not_counted() -> None:
    """Only the overlapping timeline is scored, so only it is decomposed."""
    reference = [(0.0, 1.0, "C"), (2.0, 3.0, "D")]
    hypothesis = [(0.0, 1.0, "D"), (5.0, 6.0, "D")]

    result = decompose(reference, hypothesis)

    assert result.total_seconds == pytest.approx(1.0)
    assert result.seconds[WRONG_ROOT] == pytest.approx(1.0)


def test_an_empty_side_decomposes_to_nothing() -> None:
    for hypothesis in ([], [(0.0, 1.0, "C")]):
        reference = [] if hypothesis else [(0.0, 1.0, "C")]
        result = decompose(reference, hypothesis)
        assert result.total_seconds == 0.0
        assert result.csr == 0.0
        assert result.lost_seconds == 0.0
        assert result.shares_of_lost() == dict.fromkeys(CHORD_ERROR_CLASSES, 0.0)


# --------------------------------------------------------------------------- #
# Where in the chord the loss sits
# --------------------------------------------------------------------------- #
def test_a_loss_next_to_a_reference_boundary_is_counted_as_an_edge_loss() -> None:
    reference = [(0.0, 2.0, "C"), (2.0, 4.0, "G")]
    # D covers 1.8-2.2: the whole wrong-root band straddles the boundary at 2.
    hypothesis = [(0.0, 1.8, "C"), (1.8, 2.2, "D"), (2.2, 4.0, "G")]

    result = decompose(reference, hypothesis, edge_window=0.5)

    assert result.seconds[WRONG_ROOT] == pytest.approx(0.4)
    assert result.edge_seconds[WRONG_ROOT] == pytest.approx(0.4)
    assert result.interior_seconds[WRONG_ROOT] == pytest.approx(0.0)
    assert (
        result.edge_seconds[AGREEMENT] + result.interior_seconds[AGREEMENT]
        == result.seconds[AGREEMENT]
    )


def test_a_long_loss_is_split_between_edge_and_interior_time() -> None:
    """A band that reaches past the window is only partly a boundary problem."""
    reference = [(0.0, 4.0, "C"), (4.0, 8.0, "G")]
    hypothesis = [(0.0, 4.0, "C"), (4.0, 6.0, "D"), (6.0, 8.0, "G")]

    narrow = decompose(reference, hypothesis, edge_window=0.5)
    wide = decompose(reference, hypothesis, edge_window=2.0)

    assert narrow.seconds[WRONG_ROOT] == pytest.approx(2.0)
    assert narrow.edge_seconds[WRONG_ROOT] == pytest.approx(0.5)
    assert narrow.interior_seconds[WRONG_ROOT] == pytest.approx(1.5)
    assert wide.edge_seconds[WRONG_ROOT] == pytest.approx(2.0)
    assert wide.interior_seconds[WRONG_ROOT] == pytest.approx(0.0)


def test_the_edge_split_never_double_counts_overlapping_bands() -> None:
    reference = [(0.0, 1.0, "C"), (1.0, 2.0, "C"), (2.0, 3.0, "C")]
    hypothesis = [(0.0, 3.0, "D")]

    result = decompose(reference, hypothesis, edge_window=1.0)

    # Boundaries at 1 and 2 give bands that cover the whole 3 s: edge is 3.0,
    # never 4.0.
    assert result.edge_seconds[WRONG_ROOT] == pytest.approx(3.0)
    assert result.interior_seconds[WRONG_ROOT] == pytest.approx(0.0)


# --------------------------------------------------------------------------- #
# Aggregate over takes
# --------------------------------------------------------------------------- #
def test_aggregating_takes_sums_the_seconds_not_the_ratios() -> None:
    short = decompose(_timeline("C", "C"), _timeline("D", "C"))  # csr 0.5 of 2 s
    long = decompose(_timeline("C", "C", "C", "C"), _timeline("N", "N", "N", "C"))  # 0.25 of 4 s

    total = aggregate_decompositions([short, long])

    assert total.total_seconds == pytest.approx(6.0)
    assert total.correct_seconds == pytest.approx(2.0)
    # Duration-weighted: the mean of the two ratios would be 0.375.
    assert total.csr == pytest.approx(1.0 / 3.0)
    assert total.seconds[WRONG_ROOT] == pytest.approx(1.0)
    assert total.seconds[MISSED_CHORD] == pytest.approx(3.0)
    assert total.takes == 2


def test_aggregating_nothing_is_empty_not_a_zero_division() -> None:
    total = aggregate_decompositions([])

    assert total.takes == 0
    assert total.total_seconds == 0.0
    assert total.csr == 0.0
    assert total.shares_of_lost() == dict.fromkeys(CHORD_ERROR_CLASSES, 0.0)


def test_edge_splitting_survives_aggregation() -> None:
    # The whole take disagrees, and its only reference boundaries are its own
    # ends: half a second at each end is edge time, the middle is interior.
    first = decompose([(0.0, 2.0, "C")], [(0.0, 2.0, "D")], edge_window=0.5)
    second = decompose([(0.0, 2.0, "G")], [(0.0, 2.0, "G")], edge_window=0.5)

    total = aggregate_decompositions([first, second])

    assert total.seconds[WRONG_ROOT] == pytest.approx(2.0)
    assert total.edge_seconds[WRONG_ROOT] == pytest.approx(1.0)
    assert total.interior_seconds[WRONG_ROOT] == pytest.approx(1.0)
    assert total.seconds[AGREEMENT] == pytest.approx(2.0)
    assert (
        total.edge_seconds[WRONG_ROOT] + total.interior_seconds[WRONG_ROOT]
        == total.seconds[WRONG_ROOT]
    )


def test_a_decomposition_serialises_as_plain_numbers() -> None:
    result = decompose(_timeline("C", "G"), _timeline("C", "D"))

    document = json.loads(json.dumps(result.to_dict()))

    assert set(document) == {
        "takes",
        "edge_window",
        "total_seconds",
        "correct_seconds",
        "lost_seconds",
        "csr",
        "seconds",
        "edge_seconds",
        "interior_seconds",
        "shares_of_lost",
        "csr_points_lost",
    }
    assert document["takes"] == 1
    assert document["csr"] == pytest.approx(0.5)
    assert document["seconds"][WRONG_ROOT] == pytest.approx(1.0)
    assert document["edge_seconds"][WRONG_ROOT] == pytest.approx(1.0)


# --------------------------------------------------------------------------- #
# Boundary/timing: the counterfactual
# --------------------------------------------------------------------------- #
def test_snapping_moves_a_late_hypothesis_edge_onto_the_reference_boundary() -> None:
    reference = [(0.0, 2.0, "C"), (2.0, 4.0, "G")]
    hypothesis = [(0.0, 1.8, "C"), (1.8, 4.0, "G")]

    snapped = snap_boundaries(reference, hypothesis, window=0.5)

    assert snapped == [(0.0, 2.0, "C"), (2.0, 4.0, "G")]


def test_snapping_leaves_an_edge_outside_the_window_alone() -> None:
    reference = [(0.0, 2.0, "C"), (2.0, 4.0, "G")]
    hypothesis = [(0.0, 1.0, "C"), (1.0, 4.0, "G")]

    snapped = snap_boundaries(reference, hypothesis, window=0.5)

    assert snapped == hypothesis


def test_snapping_never_creates_an_empty_segment() -> None:
    reference = [(0.0, 2.0, "C"), (2.0, 4.0, "Am")]
    # 1.9-2.1 collapses onto the single boundary at 2 and is dropped.
    hypothesis = [(0.0, 1.9, "C"), (1.9, 2.1, "C"), (2.1, 4.0, "Am")]

    snapped = snap_boundaries(reference, hypothesis, window=0.5)

    assert all(end > start for start, end, _label in snapped)
    assert snapped == [(0.0, 2.0, "C"), (2.0, 4.0, "Am")]


def test_snapping_merges_neighbours_left_with_the_same_label() -> None:
    reference = [(0.0, 2.0, "C"), (2.0, 4.0, "C")]
    hypothesis = [(0.0, 1.9, "C"), (1.9, 2.1, "C"), (2.1, 4.0, "C")]

    snapped = snap_boundaries(reference, hypothesis, window=0.5)

    assert snapped == [(0.0, 4.0, "C")]


def test_snapping_an_empty_reference_returns_the_hypothesis_unchanged() -> None:
    hypothesis = [(0.0, 1.0, "C")]

    assert snap_boundaries([], hypothesis, window=0.5) == hypothesis
    assert snap_boundaries([(0.0, 1.0, "C")], [], window=0.5) == []


def test_the_timing_view_reports_what_fixing_boundaries_would_gain() -> None:
    # The labels are right; only the 0.2 s seam is in the wrong place.
    reference = [(0.0, 2.0, "C"), (2.0, 4.0, "G")]
    hypothesis = [(0.0, 1.8, "C"), (1.8, 4.0, "G")]

    scored = duration_csr(reference, hypothesis)
    result = timing_view(reference, hypothesis, window=0.5)

    assert result["csr"] == pytest.approx(scored["csr"])
    assert result["total_seconds"] == pytest.approx(scored["total_s"])
    assert result["csr_snapped"] == pytest.approx(1.0)
    assert result["csr_points_gained"] == pytest.approx(1.0 - scored["csr"])
    assert result["boundaries_moved"] == 1
    assert result["segments_dropped"] == 0
    assert result["window"] == pytest.approx(0.5)


def test_the_timing_view_is_zero_when_the_boundaries_already_agree() -> None:
    reference = [(0.0, 2.0, "C"), (2.0, 4.0, "G")]
    hypothesis = [(0.0, 2.0, "C"), (2.0, 4.0, "D")]

    result = timing_view(reference, hypothesis, window=0.5)

    assert result["csr_points_gained"] == pytest.approx(0.0)
    assert result["boundaries_moved"] == 0
    assert result["csr_snapped"] == pytest.approx(result["csr"])


def test_the_timing_view_reports_a_label_loss_it_cannot_fix() -> None:
    """Snapping boundaries must not be able to raise CSR on a wrong chord."""
    result = timing_view([(0.0, 4.0, "C")], [(0.0, 4.0, "D")], window=0.5)

    assert result["csr_points_gained"] == pytest.approx(0.0)


def test_the_timing_view_degrades_without_anything_to_score() -> None:
    result = timing_view([], [], window=0.5)

    assert result["csr"] == 0.0
    assert result["csr_snapped"] == 0.0
    assert result["csr_points_gained"] == 0.0


def test_aggregate_timing_views_weighs_takes_by_their_scored_time() -> None:
    reference = [(0.0, 2.0, "C"), (2.0, 4.0, "G")]
    late = timing_view(reference, [(0.0, 1.8, "C"), (1.8, 4.0, "G")], window=0.5)
    clean = timing_view(reference, reference, window=0.5)

    total = aggregate_timing_views([late, clean])

    assert total["total_seconds"] == pytest.approx(8.0)
    # Only one take of the two had a boundary to fix.
    assert total["csr"] == pytest.approx((late["equal_seconds"] + 4.0) / 8.0)
    assert total["csr_snapped"] == pytest.approx(1.0)
    assert total["boundaries_moved"] == 1
    assert aggregate_timing_views([])["csr_points_gained"] == 0.0


# --------------------------------------------------------------------------- #
# A realistic case: timing error and label error on the same timeline
# --------------------------------------------------------------------------- #
def test_a_shifted_hypothesis_shows_up_as_edge_losses_and_a_timing_gain() -> None:
    reference = [(0.0, 2.0, "C"), (2.0, 4.0, "G"), (4.0, 6.0, "Am")]
    # Every boundary is 0.4 s late and the labels are otherwise right.
    hypothesis = [(0.0, 2.4, "C"), (2.4, 4.4, "G"), (4.4, 6.0, "Am")]

    result = decompose(reference, hypothesis, edge_window=0.5)
    timing = timing_view(reference, hypothesis, window=0.5)

    # The labels disagree only in the shifted bands, and all of that loss sits
    # within half a second of a reference boundary.
    assert result.lost_seconds == pytest.approx(0.8)
    assert result.edge_seconds[WRONG_ROOT] == pytest.approx(0.8)
    assert sum(result.interior_seconds[name] for name in CHORD_ERROR_CLASSES) == pytest.approx(0.0)
    # The whole loss is timing: snapping the edges recovers it.
    assert timing["csr_points_gained"] == pytest.approx(1.0 - result.csr)
    assert segment_overlap(reference, snap_boundaries(reference, hypothesis, window=0.5)) > (
        segment_overlap(reference, hypothesis)
    )


# --------------------------------------------------------------------------- #
# scripts/chord_error_decomposition.py over a synthetic corpus
# --------------------------------------------------------------------------- #
ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "chord_error_decomposition.py"

#: C major, G major, A minor, F major -- two seconds each, as in the harness test.
PROGRESSION: list[tuple[int, ...]] = [(0, 4, 7), (7, 11, 2), (9, 0, 4), (5, 9, 0)]
SECONDS_PER_CHORD = 2.0
#: What the generated audio plays, as a lead sheet would write it.
LABELS = ("C:maj", "G:maj", "A:min", "F:maj")


def _engine_available() -> bool:
    from song_chord_lyrics_analyzer.engines import ChromaBaselineEngine

    return ChromaBaselineEngine().is_available()


requires_dsp = pytest.mark.skipif(
    not _engine_available(), reason="optional DSP stack (numpy/librosa) not installed"
)


def _run(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *arguments],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def _pin_corpus(corpus: Path, labels: tuple[str, ...] = LABELS) -> Path:
    """Generate one take and pin it with the benchmark harness's own manifest writer."""
    from fixtures.audio import write_chord_wav

    corpus.mkdir(parents=True, exist_ok=True)
    write_chord_wav(
        corpus / "01_Demo_comp_mic.wav",
        chords=PROGRESSION,
        seconds_per_chord=SECONDS_PER_CHORD,
    )
    (corpus / "01_Demo_comp.jams").write_text(
        json.dumps(
            {
                "annotations": [
                    {
                        "namespace": "chord",
                        "data": [
                            {
                                "time": index * SECONDS_PER_CHORD,
                                "duration": SECONDS_PER_CHORD,
                                "value": value,
                            }
                            for index, value in enumerate(labels)
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    manifest = corpus.parent / "manifest.json"
    pinned = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "chord_benchmark.py"),
            "--corpus-dir",
            str(corpus),
            "--write-manifest",
            str(manifest),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert pinned.returncode == 0, pinned.stderr
    return manifest


def _measure(corpus: Path, out: Path, *arguments: str) -> dict:
    manifest = _pin_corpus(corpus)
    result = _run(
        "--manifest",
        str(manifest),
        "--corpus-dir",
        str(corpus),
        "--out",
        str(out),
        *arguments,
    )
    assert result.returncode == 0, result.stderr
    return json.loads((out / "decomposition.json").read_text(encoding="utf-8"))


@requires_dsp
def test_the_script_decomposes_a_generated_take(tmp_path: Path) -> None:
    out = tmp_path / "decomposition"
    document = _measure(tmp_path / "corpus", out)

    assert document["kind"] == "chord_error_decomposition"
    assert document["takes"] == 1
    assert document["settings"]["reference"] == "instructed"
    assert document["environment"]["engine"] == "chroma-baseline"
    assert document["environment"]["git_commit"]
    assert document["date"]
    # The report rounds each bucket to a millisecond, so the parts sum to the
    # whole within that rounding -- not to the last float.
    assert sum(document["seconds"].values()) == pytest.approx(document["total_seconds"], abs=0.01)
    assert {"csr", "csr_snapped", "csr_points_gained"} <= set(document["timing"])
    assert "lost CSR" in (out / "decomposition.md").read_text(encoding="utf-8")
    assert "Environment:" in (out / "decomposition.md").read_text(encoding="utf-8")


@requires_dsp
def test_the_script_reports_the_same_csr_the_harness_measures(tmp_path: Path) -> None:
    """The artifact carries the segments it scored, so its number re-derives.

    A reader with no corpus can take ``reference_segments`` and
    ``hypothesis_segments`` out of the JSON and reproduce the CSR the run
    decomposed -- to the millisecond the artifact rounds its times to, which is
    the only reason the two agree to within ``abs`` rather than exactly.
    """
    out = tmp_path / "decomposition"
    document = _measure(
        tmp_path / "corpus",
        out,
        "--reference",
        "instructed",
    )
    row = document["per_take"][0]

    assert row["take"] == "01_Demo_comp"
    scored = duration_csr(
        [(float(start), float(end), label) for start, end, label in row["reference_segments"]],
        [(float(start), float(end), label) for start, end, label in row["hypothesis_segments"]],
    )
    assert row["csr"] == pytest.approx(scored["csr"], abs=1e-3)
    assert row["total_seconds"] == pytest.approx(scored["total_s"], abs=1e-2)
    correct = sum(take["correct_seconds"] for take in document["per_take"])
    assert document["correct_seconds"] == pytest.approx(correct)
    assert document["csr"] == pytest.approx(correct / document["total_seconds"], abs=1e-3)


@requires_dsp
def test_a_clean_take_decomposes_into_boundary_time_only(tmp_path: Path) -> None:
    """The engine transcribes this fixture correctly, so its loss is seams.

    What is left over is a band either side of each reference boundary, and the
    counterfactual says so: snapping every boundary inside the window recovers
    the whole difference. That is the timing/label separation working.
    """
    document = _measure(tmp_path / "corpus", tmp_path / "out")

    assert document["csr"] > 0.9
    assert document["lost_seconds"] > 0.0
    assert sum(document["edge_seconds"][name] for name in CHORD_ERROR_CLASSES) == pytest.approx(
        document["lost_seconds"], abs=1e-6
    )
    assert document["timing"]["csr_points_gained"] == pytest.approx(1.0 - document["csr"], abs=1e-6)


@requires_dsp
def test_the_script_names_a_mislabeled_reference_take(tmp_path: Path) -> None:
    """An F major played and annotated A minor is a wrong root, not a wrong quality."""
    corpus = tmp_path / "corpus"
    out = tmp_path / "out"
    _pin_corpus(corpus, ("C:maj", "G:maj", "A:min", "A:min"))
    result = _run(
        "--manifest",
        str(corpus.parent / "manifest.json"),
        "--corpus-dir",
        str(corpus),
        "--out",
        str(out),
    )

    assert result.returncode == 0, result.stderr
    document = json.loads((out / "decomposition.json").read_text(encoding="utf-8"))

    assert document["seconds"][WRONG_ROOT] > document["seconds"][WRONG_QUALITY]
    assert document["shares_of_lost"][WRONG_ROOT] > 0.3


@requires_dsp
def test_the_triad_label_view_is_a_no_op_for_a_triad_engine(tmp_path: Path) -> None:
    """``--label-view triad`` reduces the hypothesis, which is already reduced.

    The registered engine speaks only major, minor and ``N`` (vocabulary phase
    1), so the two views must agree exactly -- a record of what the option does
    *today*, and the check that it is not silently rewriting the metric. It
    becomes a real comparison as soon as an engine with extensions is measured.
    """
    corpus = tmp_path / "corpus"
    manifest = _pin_corpus(corpus)

    raw = _run(
        "--manifest", str(manifest), "--corpus-dir", str(corpus), "--out", str(tmp_path / "a")
    )
    reduced = _run(
        "--manifest",
        str(manifest),
        "--corpus-dir",
        str(corpus),
        "--label-view",
        "triad",
        "--out",
        str(tmp_path / "b"),
    )

    assert raw.returncode == 0, raw.stderr
    assert reduced.returncode == 0, reduced.stderr
    raw_document = json.loads((tmp_path / "a" / "decomposition.json").read_text(encoding="utf-8"))
    triad_document = json.loads((tmp_path / "b" / "decomposition.json").read_text(encoding="utf-8"))
    assert triad_document["settings"]["label_view"] == "triad"
    assert raw_document["settings"]["label_view"] == "raw"
    assert triad_document["seconds"] == raw_document["seconds"]
    assert triad_document["csr"] == pytest.approx(raw_document["csr"])


def test_the_script_refuses_an_absent_corpus_rather_than_inventing_a_number(
    tmp_path: Path,
) -> None:
    result = _run(
        "--manifest",
        str(ROOT / "tests" / "fixtures" / "guitarset_comp_manifest.json"),
        "--corpus-dir",
        str(tmp_path / "nowhere"),
        "--out",
        str(tmp_path / "out"),
        "--limit",
        "1",
    )

    assert result.returncode == 2
    assert "not found" in result.stderr
    assert "10.5281/zenodo.3371780" in result.stderr
    assert not (tmp_path / "out" / "decomposition.json").exists()


@requires_dsp
def test_the_script_refuses_bytes_that_do_not_match_the_manifest(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus"
    manifest = _pin_corpus(corpus)
    with (corpus / "01_Demo_comp_mic.wav").open("ab") as handle:
        handle.write(b"\x00\x00")

    result = _run(
        "--manifest",
        str(manifest),
        "--corpus-dir",
        str(corpus),
        "--out",
        str(tmp_path / "out"),
    )

    assert result.returncode == 2
    assert "does not match the manifest" in result.stderr
    assert not (tmp_path / "out" / "decomposition.json").exists()
