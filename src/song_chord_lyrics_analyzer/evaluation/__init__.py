"""Chord evaluation (roadmap sections 44 and Phase I P1/P2).

The scoring semantics verified against the CSR oracle fixture
(``tests/fixtures/csr_oracle.json``, derived from GuitarSet comping takes):
duration-weighted Chord Sequence Recall over MIREX-2010 equality, plus the
triad-reduced reference view. Ground truth is always explicit — the fixture
records its dataset provenance (GuitarSet, CC BY 4.0) and the recorded
expected values; nothing here invents numbers.

:mod:`song_chord_lyrics_analyzer.evaluation.guitarset` adds the reproducible
corpus side: a committed manifest of GuitarSet takes with SHA-256 digests, the
JAMS chord reader, and the full per-take comparison vector used by
``scripts/chord_benchmark.py``.

:mod:`song_chord_lyrics_analyzer.evaluation.confidence` measures the per-event
confidence the chord engine reports: it refits the margin-to-probability
logistic from recorded events, so the calibration is reproducible rather than
taken on trust, and pools the reports into a calibration table, a
risk-coverage curve and an expected calibration error.

:mod:`song_chord_lyrics_analyzer.evaluation.chart` aligns a hand-written
chord chart (no timestamps) to a detected sequence and reports matches,
substitutions, missing and extra chords; it is sequence agreement, not the
timed CSR above.

:mod:`song_chord_lyrics_analyzer.evaluation.chordpro` reads a ChordPro sheet
back into the same untimed chart, which is what lets the exporter's output be
checked against its own reader instead of only against a fixture string.

:mod:`song_chord_lyrics_analyzer.evaluation.errors` names the loss that CSR
counts: it partitions the same scored timeline into spurious chord, missed
chord, wrong root, wrong quality and extension/voicing time, and measures how
much of the loss a corrected boundary would recover.
"""

from __future__ import annotations

from song_chord_lyrics_analyzer.evaluation.chart import (
    Alignment,
    AlignmentOp,
    ChordChart,
    align_chord_sequences,
    is_chord_token,
    parse_chord_chart,
    triad_label,
)
from song_chord_lyrics_analyzer.evaluation.chordpro import parse_chordpro
from song_chord_lyrics_analyzer.evaluation.chords import (
    chord_pcs,
    duration_csr,
    harte_to_label,
    mirex_equal,
    reduce_ref_view,
    triad_reduce,
)
from song_chord_lyrics_analyzer.evaluation.confidence import (
    CONFIDENCE_THRESHOLDS,
    EventOutcome,
    LogisticFit,
    apply_fit,
    calibration_report,
    combine_reports,
    fit_logistic,
    probability,
)
from song_chord_lyrics_analyzer.evaluation.errors import (
    AGREEMENT,
    CHORD_ERROR_CLASSES,
    ErrorDecomposition,
    aggregate_decompositions,
    aggregate_timing_views,
    classify_disagreement,
    decompose,
    snap_boundaries,
    timing_view,
)
from song_chord_lyrics_analyzer.evaluation.guitarset import (
    GuitarSetManifest,
    GuitarSetTake,
    aggregate_scores,
    event_outcomes,
    label_agreement,
    load_manifest,
    read_jams_chords,
    score_take,
    sha256_file,
    verify_take_files,
)

__all__ = [
    "AGREEMENT",
    "CHORD_ERROR_CLASSES",
    "CONFIDENCE_THRESHOLDS",
    "Alignment",
    "AlignmentOp",
    "ChordChart",
    "align_chord_sequences",
    "is_chord_token",
    "parse_chord_chart",
    "parse_chordpro",
    "triad_label",
    "ErrorDecomposition",
    "EventOutcome",
    "GuitarSetManifest",
    "GuitarSetTake",
    "LogisticFit",
    "aggregate_decompositions",
    "aggregate_scores",
    "aggregate_timing_views",
    "apply_fit",
    "calibration_report",
    "chord_pcs",
    "classify_disagreement",
    "combine_reports",
    "decompose",
    "duration_csr",
    "event_outcomes",
    "fit_logistic",
    "harte_to_label",
    "label_agreement",
    "load_manifest",
    "mirex_equal",
    "probability",
    "read_jams_chords",
    "reduce_ref_view",
    "score_take",
    "sha256_file",
    "snap_boundaries",
    "timing_view",
    "triad_reduce",
    "verify_take_files",
]
