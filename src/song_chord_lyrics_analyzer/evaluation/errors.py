"""Which chord errors make up the measured loss (roadmap Phase I task A1).

The project has one recorded chord number -- duration CSR on 180 GuitarSet
comping takes -- and it says *how much* is lost, never *what*. ``csr 0.6312``
is equally consistent with a decoder that finds chords half a second late, an
engine that cannot tell major from minor, and a front end that hears a chord
through every rest. Those four diagnoses want four different fixes, so an
accuracy queue without this decomposition picks a fix by position in a list.

This module closes that gap with the primitives the measurement already uses:
:func:`~song_chord_lyrics_analyzer.evaluation.chords.duration_csr` walks the
overlapping timeline and calls
:func:`~song_chord_lyrics_analyzer.evaluation.chords.mirex_equal` on each sliver
of agreeing time, and :func:`decompose` walks the *same* timeline and names each
sliver instead of only summing it. The consequence is a hard invariant, pinned
by tests: ``decompose(ref, hyp).csr`` is exactly the ``csr`` that
:func:`duration_csr` returns
(same ``total_s``, same ``equal_s``), and the class seconds sum to ``total_s``.
A decomposition could therefore hide a loss in the wrong bucket, but it cannot
invent or lose CSR points.

The label classes
-----------------

Every scored second is in exactly one of :data:`AGREEMENT` or the six classes in
:data:`CHORD_ERROR_CLASSES`. ``N`` and any label the chord reader cannot voice
(an empty pitch-class set, e.g. the Harte ``N%``) count as *no chord*:

* ``spurious_chord`` -- the reference is silent and the hypothesis plays a chord.
* ``missed_chord`` -- the reference has a chord and the hypothesis is silent.
  This is the "false no-chord claim" of the roadmap; named from the reference's
  side so the two silence classes cannot be confused.
* ``wrong_root`` -- both claim a chord, MIREX scores it 0, and the root pitch
  class differs.
* ``wrong_quality`` -- same root, but the triad differs (major against minor in
  the 24-triad view).
* ``extension_or_voicing`` -- same root *and* same triad, so the loss lives in
  the extension/suspension/voicing/bass detail. The registered engine only
  speaks major, minor and ``N``, so on a live run this class is what the
  reference demands and the vocabulary cannot say: raw MIREX scores it 0 while
  :func:`~song_chord_lyrics_analyzer.evaluation.chords.triad_reduce` would call
  it right. ``C5``/``Csus2``/``Cdim`` against ``C`` are the typical members.
* ``unresolved`` -- the rules cannot attribute the loss, which for two
  no-chord claims means the pinned metric counts ``N%`` against ``N`` as a
  disagreement. Expected to be empty; if a run shows otherwise, that is a
  finding about the scorer, not about the engine, and is reported rather than
  folded into another class.

Slash/bass and extension differences that MIREX-2010 *rescues* are agreement,
because the metric does not lose them: this module explains the recorded
number, it does not replace it.

The boundary/timing view is deliberately separate
-------------------------------------------------

A boundary that landed 0.3 s late costs time in *two* label classes at once (the
band it skipped and the band it missed), so "boundary error" cannot be one more
additive bucket without double-counting. It is measured two ways instead, and
neither pretends to partition the label classes:

* :meth:`ErrorDecomposition.edge_seconds` splits every class into the part
  within ``edge_window`` seconds of a reference boundary and the part further
  from one, so a class concentrated at the edges is a timing symptom.
* :func:`snap_boundaries` / :func:`timing_view` build the counterfactual: pull
  every hypothesis boundary onto the nearest reference boundary inside the
  window, rescore, and report the CSR recovered. That figure is the *upper
  bound* on what better segmentation alone can buy -- with the labels fixed in
  place -- and it overlaps the label classes by construction.
"""

from __future__ import annotations

from bisect import bisect_left
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from song_chord_lyrics_analyzer.evaluation.chords import (
    chord_pcs,
    duration_csr,
    mirex_equal,
    triad_reduce,
)
from song_chord_lyrics_analyzer.evaluation.guitarset import ChordSegment

__all__ = [
    "AGREEMENT",
    "CHORD_ERROR_CLASSES",
    "EXTENSION_OR_VOICING",
    "MISSED_CHORD",
    "ErrorDecomposition",
    "SPURIOUS_CHORD",
    "UNRESOLVED",
    "WRONG_QUALITY",
    "WRONG_ROOT",
    "aggregate_decompositions",
    "classify_disagreement",
    "decompose",
    "snap_boundaries",
    "timing_view",
]

#: Time the two label views agree on, exactly as :func:`duration_csr` scores it.
AGREEMENT = "match"
#: A chord claimed over a reference that has none.
SPURIOUS_CHORD = "spurious_chord"
#: A reference chord the hypothesis left silent.
MISSED_CHORD = "missed_chord"
#: A chord claimed with the wrong root.
WRONG_ROOT = "wrong_root"
#: The right root, the wrong triad.
WRONG_QUALITY = "wrong_quality"
#: The right triad, a difference only the extension/voicing layer can see.
EXTENSION_OR_VOICING = "extension_or_voicing"
#: A disagreement the rules above cannot attribute; expected to stay empty.
UNRESOLVED = "unresolved"

#: Every class that is lost time, in report order.
CHORD_ERROR_CLASSES: tuple[str, ...] = (
    SPURIOUS_CHORD,
    MISSED_CHORD,
    WRONG_ROOT,
    WRONG_QUALITY,
    EXTENSION_OR_VOICING,
    UNRESOLVED,
)

#: Boundary times are rounded like ``metrics.segmentation`` so float noise from
#: decoding does not decide whether two edges are the same edge.
_BOUNDARY_DECIMALS = 5

#: Seconds within which a hypothesis boundary counts as "next to" a reference one.
DEFAULT_EDGE_WINDOW = 0.5

#: Every bucket a scored second can land in, agreement first.
_ALL_CLASSES: tuple[str, ...] = (AGREEMENT, *CHORD_ERROR_CLASSES)


def _is_no_chord(label: str) -> bool:
    """Whether ``label`` claims no chord: ``N``, an ``N``-family spelling, nothing.

    The test is the one the scorer effectively makes -- a label that yields no
    pitch classes cannot be voiced -- so ``N%`` and a mis-parsed spelling are
    treated as silence rather than as an unclassifiable chord.
    """
    pitch_classes, _, _ = chord_pcs(label)
    return not pitch_classes


def classify_disagreement(reference_label: str, hypothesis_label: str) -> str:
    """Name the one class that a reference/hypothesis label pair disagrees in.

    The first question is the scorer's: MIREX-2010 equality, because anything it
    calls a match is not lost time and must not be counted as an error. Only a
    disagreement is attributed.

    Args:
        reference_label: Reference label, canonical (``harte_to_label`` applied).
        hypothesis_label: The engine's label, canonical.

    Returns:
        :data:`AGREEMENT` or exactly one member of :data:`CHORD_ERROR_CLASSES`.
    """
    if mirex_equal(reference_label, hypothesis_label) > 0.0:
        return AGREEMENT
    ref_silent = _is_no_chord(reference_label)
    hyp_silent = _is_no_chord(hypothesis_label)
    if ref_silent and hyp_silent:
        # Two ways of writing "no chord" that the pinned metric still counts as
        # a disagreement; attributed to the scorer, not to the engine.
        return UNRESOLVED
    if ref_silent:
        return SPURIOUS_CHORD
    if hyp_silent:
        return MISSED_CHORD
    _, ref_root, _ = chord_pcs(reference_label)
    _, hyp_root, _ = chord_pcs(hypothesis_label)
    if ref_root is None or hyp_root is None:
        return UNRESOLVED
    if ref_root != hyp_root:
        return WRONG_ROOT
    if triad_reduce([reference_label])[0] != triad_reduce([hypothesis_label])[0]:
        return WRONG_QUALITY
    return EXTENSION_OR_VOICING


def _boundaries(segments: Sequence[ChordSegment]) -> list[float]:
    """Sorted unique change points of a segmentation, rounded for comparison."""
    return sorted(
        {
            round(value, _BOUNDARY_DECIMALS)
            for start, end, _label in segments
            for value in (float(start), float(end))
        }
    )


def _edge_seconds(start: float, end: float, boundaries: Sequence[float], window: float) -> float:
    """How much of ``[start, end)`` lies within ``window`` of a boundary.

    A sliver is not simply "at the edge" or "in the middle": a 0.4 s band that
    straddles a boundary is half one and half the other, and the time is split
    accordingly.
    """
    if window <= 0.0 or not boundaries:
        return 0.0
    left = bisect_left(boundaries, start - window)
    covered: list[tuple[float, float]] = []
    for index in range(left, len(boundaries)):
        boundary = boundaries[index]
        if boundary - window > end:
            break
        band_start = max(start, boundary - window)
        band_end = min(end, boundary + window)
        if band_end > band_start:
            covered.append((band_start, band_end))
    total = 0.0
    cursor = float("-inf")
    for band_start, band_end in covered:
        from_point = max(band_start, cursor)
        if band_end > from_point:
            total += band_end - from_point
            cursor = band_end
    return total


@dataclass(frozen=True)
class ErrorDecomposition:
    """Duration-weighted seconds per error class for one or many segmentations.

    Built by :func:`decompose` (one take) and :func:`aggregate_decompositions`
    (a corpus). ``takes`` counts the segmentations folded into the totals, so a
    run report can say how much audio the numbers cover.
    """

    total_seconds: float
    correct_seconds: float
    seconds: dict[str, float]
    edge_seconds: dict[str, float]
    interior_seconds: dict[str, float]
    edge_window: float
    takes: int = 1

    @property
    def lost_seconds(self) -> float:
        """Scored reference time that is not agreement."""
        return max(0.0, self.total_seconds - self.correct_seconds)

    @property
    def csr(self) -> float:
        """The duration CSR this decomposition explains, by construction."""
        return self.correct_seconds / self.total_seconds if self.total_seconds else 0.0

    def shares_of_lost(self) -> dict[str, float]:
        """Each class's share of the *loss* -- what the roadmap asks for.

        These sum to 1.0 whenever anything was lost, so the largest one names
        the next task. With nothing lost they are all ``0.0`` rather than a
        division by zero.
        """
        lost = self.lost_seconds
        if lost <= 0.0:
            return dict.fromkeys(CHORD_ERROR_CLASSES, 0.0)
        return {name: self.seconds[name] / lost for name in CHORD_ERROR_CLASSES}

    def csr_points_lost(self) -> dict[str, float]:
        """Each class's share of the *reference timeline*: the CSR it costs.

        These sum to ``1 - csr``, which is how a class is read as "worth N CSR
        points if fixed" -- an upper bound only, because the classes are on the
        actual boundaries, not on corrected ones.
        """
        if not self.total_seconds:
            return dict.fromkeys(CHORD_ERROR_CLASSES, 0.0)
        return {name: self.seconds[name] / self.total_seconds for name in CHORD_ERROR_CLASSES}

    def to_dict(self) -> dict[str, Any]:
        """Plain JSON-safe numbers, for a run report next to its provenance."""
        return {
            "takes": self.takes,
            "edge_window": self.edge_window,
            "total_seconds": round(self.total_seconds, 3),
            "correct_seconds": round(self.correct_seconds, 3),
            "lost_seconds": round(self.lost_seconds, 3),
            "csr": self.csr,
            "seconds": {name: round(self.seconds[name], 3) for name in _ALL_CLASSES},
            "edge_seconds": {name: round(self.edge_seconds[name], 3) for name in _ALL_CLASSES},
            "interior_seconds": {
                name: round(self.interior_seconds[name], 3) for name in _ALL_CLASSES
            },
            "shares_of_lost": {name: value for name, value in self.shares_of_lost().items()},
            "csr_points_lost": {name: value for name, value in self.csr_points_lost().items()},
        }


def _empty_buckets() -> dict[str, float]:
    return dict.fromkeys(_ALL_CLASSES, 0.0)


def decompose(
    reference: Sequence[ChordSegment],
    hypothesis: Sequence[ChordSegment],
    *,
    edge_window: float = DEFAULT_EDGE_WINDOW,
) -> ErrorDecomposition:
    """Split the scored time of one take into the classes it disagrees in.

    Walks the same zip over the two segmentations as
    :func:`~song_chord_lyrics_analyzer.evaluation.chords.duration_csr`, on the
    same assumptions it makes: both sides sorted by start time, non-overlapping
    within themselves, labels already canonical. Time only one side covers is
    not scored, so it is not decomposed either.

    Args:
        reference: Timed reference labels (``read_jams_chords`` output).
        hypothesis: Timed engine labels (``metrics.adapters.chord_segments``).
        edge_window: Seconds around a reference boundary treated as edge time.

    Returns:
        An :class:`ErrorDecomposition` whose ``csr`` equals the recorded metric.
    """
    seconds = _empty_buckets()
    edge = _empty_buckets()
    interior = _empty_buckets()
    boundaries = _boundaries(reference)
    total = 0.0
    index = other = 0
    while index < len(reference) and other < len(hypothesis):
        ref_start, ref_end, ref_label = reference[index]
        hyp_start, hyp_end, hyp_label = hypothesis[other]
        overlap = min(ref_end, hyp_end) - max(ref_start, hyp_start)
        if overlap > 0:
            name = classify_disagreement(ref_label, hyp_label)
            seconds[name] += overlap
            edge[name] += _edge_seconds(
                max(ref_start, hyp_start), min(ref_end, hyp_end), boundaries, edge_window
            )
            total += overlap
        if ref_end <= hyp_end:
            index += 1
        else:
            other += 1
    for name in _ALL_CLASSES:
        interior[name] = seconds[name] - edge[name]
    return ErrorDecomposition(
        total_seconds=total,
        correct_seconds=seconds[AGREEMENT],
        seconds=seconds,
        edge_seconds=edge,
        interior_seconds=interior,
        edge_window=edge_window,
    )


def aggregate_decompositions(
    rows: Sequence[ErrorDecomposition],
) -> ErrorDecomposition:
    """Fold per-take decompositions into one, weighting by duration.

    A corpus number is the sum of the seconds, never the mean of the ratios:
    eight takes of 30 s and two of 3 s are not eight-and-two equal votes. The
    edge window is the run's, taken from the first row.
    """
    if not rows:
        return ErrorDecomposition(
            total_seconds=0.0,
            correct_seconds=0.0,
            seconds=_empty_buckets(),
            edge_seconds=_empty_buckets(),
            interior_seconds=_empty_buckets(),
            edge_window=DEFAULT_EDGE_WINDOW,
            takes=0,
        )
    seconds = _empty_buckets()
    edge = _empty_buckets()
    interior = _empty_buckets()
    total = correct = 0.0
    for row in rows:
        total += row.total_seconds
        correct += row.correct_seconds
        for name in _ALL_CLASSES:
            seconds[name] += row.seconds.get(name, 0.0)
            edge[name] += row.edge_seconds.get(name, 0.0)
            interior[name] += row.interior_seconds.get(name, 0.0)
    return ErrorDecomposition(
        total_seconds=total,
        correct_seconds=correct,
        seconds=seconds,
        edge_seconds=edge,
        interior_seconds=interior,
        edge_window=rows[0].edge_window,
        takes=sum(row.takes for row in rows),
    )


def _snap_point(value: float, boundaries: Sequence[float], window: float) -> float:
    """The nearest reference boundary to ``value``, or ``value`` itself.

    Outside ``window`` the boundary is left where the engine put it: snapping
    further than that would correct the hypothesis with the reference, which is
    how a counterfactual becomes leakage.
    """
    if not boundaries:
        return value
    index = bisect_left(boundaries, value)
    best = value
    best_distance = window
    for candidate in boundaries[max(index - 1, 0) : index + 1]:
        distance = abs(candidate - value)
        if distance <= best_distance:
            best = candidate
            best_distance = distance
    return best


def snap_boundaries(
    reference: Sequence[ChordSegment],
    hypothesis: Sequence[ChordSegment],
    *,
    window: float,
) -> list[ChordSegment]:
    """The hypothesis with each boundary pulled onto the nearest reference one.

    Only boundaries inside ``window`` move; a segment whose ends collapse onto
    the same boundary is dropped (it occupies no time) and neighbours left with
    the same label are merged, so the counterfactual is still a segmentation and
    not a list of touching duplicates. Labels are never touched: what changes is
    *when* the engine says a chord starts, nothing else.
    """
    if not hypothesis:
        return []
    boundaries = _boundaries(reference)
    snapped: list[ChordSegment] = []
    for start, end, label in hypothesis:
        new_start = _snap_point(float(start), boundaries, window)
        new_end = _snap_point(float(end), boundaries, window)
        if new_end <= new_start:
            continue
        if snapped and snapped[-1][2] == label and snapped[-1][1] == new_start:
            previous = snapped.pop()
            snapped.append((previous[0], new_end, label))
        else:
            snapped.append((new_start, new_end, label))
    return snapped


def timing_view(
    reference: Sequence[ChordSegment],
    hypothesis: Sequence[ChordSegment],
    *,
    window: float,
) -> dict[str, float]:
    """CSR before and after boundary correction, as JSON-safe numbers.

    ``csr_points_gained`` is the difference: how much of the loss a boundary
    could not have caused, because correcting it was enough. It is reported
    beside :func:`decompose`, not folded into it -- see the module docstring.
    """
    scored = duration_csr(list(reference), list(hypothesis))
    snapped = snap_boundaries(reference, hypothesis, window=window)
    corrected = duration_csr(list(reference), snapped)
    boundaries = _boundaries(reference)
    # Distinct boundary *times*, not segment endpoints: two neighbouring
    # segments share an edge, and a seam that moved is one error, not two.
    endpoints = {round(float(value), _BOUNDARY_DECIMALS) for seg in hypothesis for value in seg[:2]}
    moved = sum(1 for value in endpoints if _snap_point(value, boundaries, window) != value)
    return {
        "window": window,
        "total_seconds": scored["total_s"],
        "equal_seconds": scored["equal_s"],
        "snapped_equal_seconds": corrected["equal_s"],
        "csr": scored["csr"],
        "csr_snapped": corrected["csr"],
        "csr_points_gained": corrected["csr"] - scored["csr"],
        "boundaries_moved": moved,
        "segments_dropped": len(hypothesis) - len(snapped),
    }


def aggregate_timing_views(views: Sequence[dict[str, float]]) -> dict[str, float]:
    """Fold per-take timing views into the run's number, weighting by duration."""
    if not views:
        return {
            "window": 0.0,
            "total_seconds": 0.0,
            "equal_seconds": 0.0,
            "snapped_equal_seconds": 0.0,
            "csr": 0.0,
            "csr_snapped": 0.0,
            "csr_points_gained": 0.0,
            "boundaries_moved": 0,
            "segments_dropped": 0,
        }
    total = sum(float(view["total_seconds"]) for view in views)
    equal = sum(float(view["equal_seconds"]) for view in views)
    snapped = sum(float(view["snapped_equal_seconds"]) for view in views)
    csr = equal / total if total else 0.0
    csr_snapped = snapped / total if total else 0.0
    return {
        "window": float(views[0]["window"]),
        "total_seconds": total,
        "equal_seconds": equal,
        "snapped_equal_seconds": snapped,
        "csr": csr,
        "csr_snapped": csr_snapped,
        "csr_points_gained": csr_snapped - csr,
        "boundaries_moved": sum(int(view["boundaries_moved"]) for view in views),
        "segments_dropped": sum(int(view["segments_dropped"]) for view in views),
    }
