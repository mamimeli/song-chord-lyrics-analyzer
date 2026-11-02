#!/usr/bin/env python3
"""Grade the recorded chord accuracy against the proposed acceptance bar.

ROADMAP §10 task A0 asks for a numeric bar and a command. This is the command;
``benchmark/reference/acceptance-bar.json`` is the bar, and it currently reads
``"status": "proposed"`` because ratifying a number is a maintainer decision, not
a merge. Every report says so on its first lines.

It compares two documents and measures nothing, so it runs with no corpus, no
audio, no numpy and no engine::

    python scripts/chord_acceptance.py                    # bar vs the committed vector
    python scripts/chord_acceptance.py --json             # the same check, machine-readable
    python scripts/chord_acceptance.py --aggregate PATH   # bar vs a fresh aggregate.json

``--aggregate`` reads the ``aggregate.json`` a ``scripts/chord_benchmark.py`` run
wrote; the run itself still needs the GuitarSet audio. Grading a fresh run rather
than the committed vector is how the boundary row becomes decidable at all, since
the recorded §8 table never named its statistic and a run does.

Exit codes: 0 when every required row is met, 1 when one is not (or is not
recorded, which decides nothing in the engine's favour), 2 for a bad argument or
an unreadable document. A ``1`` here is not a failing test -- the bar is where the
project wants to be, not where it is.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from song_chord_lyrics_analyzer.benchmark.acceptance import (  # noqa: E402
    format_bar_report,
    grade_run,
    grade_vector,
    load_bar,
)
from song_chord_lyrics_analyzer.benchmark.regression import load_vector  # noqa: E402
from song_chord_lyrics_analyzer.cli.main import configure_utf8_stdio  # noqa: E402
from song_chord_lyrics_analyzer.utils.errors import InputError, SongLabError  # noqa: E402

DEFAULT_BAR = ROOT / "benchmark" / "reference" / "acceptance-bar.json"
DEFAULT_VECTOR = ROOT / "benchmark" / "reference" / "chroma_baseline-instructed.json"

EXIT_BAR_MET = 0
EXIT_BAR_NOT_MET = 1
EXIT_ERROR = 2


def build_parser() -> argparse.ArgumentParser:
    """The command line."""
    parser = argparse.ArgumentParser(
        prog="chord_acceptance.py",
        description=(
            "Grade a recorded chord accuracy vector, or a fresh benchmark run, "
            "against the committed acceptance bar. It measures nothing."
        ),
    )
    parser.add_argument(
        "--bar",
        type=Path,
        default=DEFAULT_BAR,
        help="the acceptance bar document (default: the committed one, status 'proposed')",
    )
    record = parser.add_mutually_exclusive_group()
    record.add_argument(
        "--vector",
        type=Path,
        default=DEFAULT_VECTOR,
        help="the committed accuracy vector to grade (default)",
    )
    record.add_argument(
        "--aggregate",
        type=Path,
        default=None,
        help="grade a scripts/chord_benchmark.py aggregate.json instead of the vector",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="print the check as one JSON document instead of a table",
    )
    return parser


def _read_run(path: Path) -> dict[str, Any]:
    """A harness ``aggregate.json``, refused rather than guessed at."""
    try:
        document = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise InputError(
            f"{path}: no run record found.",
            hint="Run scripts/chord_benchmark.py first, or grade the committed "
            "vector by leaving --aggregate out.",
        ) from error
    except (OSError, json.JSONDecodeError) as error:
        raise InputError(f"{path}: the run record cannot be read: {error}") from error
    if not isinstance(document, dict):
        raise InputError(f"{path}: the run record must be a JSON object.")
    return document


def run(args: argparse.Namespace) -> int:
    """Grade the chosen record and print it; the return value is the exit code."""
    bar = load_bar(args.bar)
    if args.aggregate is not None:
        report = grade_run(bar, _read_run(args.aggregate))
    else:
        report = grade_vector(bar, load_vector(args.vector))
    if args.json:
        print(json.dumps(report.to_dict(), indent=1, allow_nan=False))
    else:
        print(format_bar_report(report))
    return EXIT_BAR_MET if report.bar_met else EXIT_BAR_NOT_MET


def main(argv: list[str] | None = None) -> int:
    """Entry point, with the project's error shape instead of a traceback."""
    args = build_parser().parse_args(argv)
    # A committed vector's source names a document section with a section mark,
    # and a Windows console code page would print it as '?'.
    configure_utf8_stdio()
    try:
        return run(args)
    except SongLabError as error:
        print(f"error: {error.message}", file=sys.stderr)
        if error.hint:
            print(f"hint: {error.hint}", file=sys.stderr)
        return EXIT_ERROR


if __name__ == "__main__":
    raise SystemExit(main())
