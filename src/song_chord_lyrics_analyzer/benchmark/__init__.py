"""Benchmark package (roadmap section 46).

Scores reference/hypothesis pairs with the roadmap section 44 metric family
and writes ``benchmark.json``, ``benchmark.csv`` and ``benchmark.md``. A
case that declares an ``audio`` file can have its hypothesis produced by a
real engine run (``songlab benchmark --engine NAME``, section 46 + section 45
performance capture); otherwise the stored results are scored as they are.

``regression`` is the other half: the committed accuracy vectors of the fixed
evaluation set, and the comparison that says whether a run improved or
regressed them (roadmap Phase J). It measures nothing.

``acceptance`` grades a recorded vector or a fresh run against the numeric
acceptance bar of roadmap section 10 -- the targets, as opposed to the figures.
It also measures nothing, and while the bar is still marked ``proposed`` every
report says so.
"""

from __future__ import annotations

from song_chord_lyrics_analyzer.benchmark.acceptance import (
    AcceptanceBar,
    BarReport,
    BarRow,
    RowOutcome,
    UngradedRule,
    format_bar_report,
    grade_run,
    grade_vector,
    load_bar,
)
from song_chord_lyrics_analyzer.benchmark.cases import BenchmarkCase, load_case, load_cases
from song_chord_lyrics_analyzer.benchmark.regression import (
    AccuracyVector,
    compare_run,
    evaluation_set_mismatch,
    format_report,
    load_vector,
    vector_from_aggregate,
    write_vector,
)
from song_chord_lyrics_analyzer.benchmark.report import (
    build_report,
    score_case,
    to_csv,
    to_json,
    to_markdown,
    write_reports,
)
from song_chord_lyrics_analyzer.benchmark.runner import EngineRun, run_engine_on_cases

__all__ = [
    "AcceptanceBar",
    "AccuracyVector",
    "BarReport",
    "BarRow",
    "BenchmarkCase",
    "EngineRun",
    "RowOutcome",
    "UngradedRule",
    "build_report",
    "compare_run",
    "evaluation_set_mismatch",
    "format_bar_report",
    "format_report",
    "grade_run",
    "grade_vector",
    "load_bar",
    "load_case",
    "load_cases",
    "load_vector",
    "run_engine_on_cases",
    "score_case",
    "to_csv",
    "to_json",
    "to_markdown",
    "vector_from_aggregate",
    "write_reports",
    "write_vector",
]
