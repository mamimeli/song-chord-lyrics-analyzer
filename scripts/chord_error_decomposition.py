#!/usr/bin/env python3
"""Name the chord errors behind the measured CSR (roadmap Phase I task A1).

Developer tooling, not a shipped command: it lives in ``scripts/``, is never in
the wheel, and is not exercised by ``songlab``.

``docs/ENGINE_COMPARISON.md`` §8 records *how much* is lost -- CSR 0.6312 on 180
GuitarSet comping takes -- and nothing in the repository has ever said *what*.
This script walks the same timeline the benchmark scores, using the same
primitives (:mod:`song_chord_lyrics_analyzer.evaluation.guitarset` for the
pinned corpus, :mod:`song_chord_lyrics_analyzer.evaluation.chords` for MIREX
equality), and instead of only summing the agreeing seconds it names every
scored second: a chord over a silent reference, silence over a reference chord,
a wrong root, a wrong quality under the right root, and a difference the
24-triad view cannot see. Alongside it, a counterfactual: pull each hypothesis
boundary onto the nearest reference boundary within a window, rescore, and
report the CSR recovered. That split is what decides whether the next accuracy
task is a decoder, a vocabulary, a bass/inversion front end or a learned engine
-- see ``ROADMAP.md`` §10.

Because the decomposition uses the identical zip that
:func:`~song_chord_lyrics_analyzer.evaluation.chords.duration_csr` uses, its
agreement bucket *is* ``equal_s`` and its total *is* ``total_s``: the run cannot
quietly redefine the metric it explains. The corpus is verified exactly like
the benchmark verifies it (SHA-256 against the committed manifest), so a
different byte stream is refused rather than reported as a new finding.

The classes are duration-weighted seconds over the whole corpus; the recorded
0.6312 is the *mean over takes*, so both are printed and neither is substituted
for the other.

Audio is never committed: GuitarSet is CC BY 4.0 but its comp takes are 462 MiB.
Download them from Zenodo 10.5281/zenodo.3371780 and point ``--corpus-dir`` at
the extracted files, exactly as for ``scripts/chord_benchmark.py``.

Usage::

    # the pinned 180-take corpus, instructed lead sheet, raw labels
    python scripts/chord_error_decomposition.py

    # the performed voicings, and the triad-reduced hypothesis the docs also quote
    python scripts/chord_error_decomposition.py --reference performed
    python scripts/chord_error_decomposition.py --label-view triad

    # a quick look at a few takes, written where you can read it
    python scripts/chord_error_decomposition.py --limit 20 --out .cache/chords/decomposition

The output directory holds ``decomposition.json`` (the numbers, plus each
take's reference and hypothesis segments so the result can be re-derived
offline) and ``decomposition.md`` (tables for ``docs/ENGINE_COMPARISON.md``,
with the environment and date beside them).

Exit codes: ``0`` decomposed something, ``1`` nothing decomposed, ``2`` a bad
request -- including a corpus that is missing or does not match the manifest.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from chord_benchmark import _VIEW_INDEX, DEFAULT_MANIFEST, _environment  # noqa: E402

from song_chord_lyrics_analyzer.engines import chroma_baseline  # noqa: E402
from song_chord_lyrics_analyzer.engines.base import ChordAnalysisOptions, EngineKind  # noqa: E402
from song_chord_lyrics_analyzer.engines.registry import create_default_registry  # noqa: E402
from song_chord_lyrics_analyzer.evaluation.chords import duration_csr, triad_reduce  # noqa: E402
from song_chord_lyrics_analyzer.evaluation.errors import (  # noqa: E402
    AGREEMENT,
    CHORD_ERROR_CLASSES,
    ErrorDecomposition,
    aggregate_decompositions,
    aggregate_timing_views,
    decompose,
    timing_view,
)
from song_chord_lyrics_analyzer.evaluation.guitarset import (  # noqa: E402
    ANNOTATION_VIEWS,
    ChordSegment,
    load_manifest,
    read_jams_chords,
    verify_take_files,
)
from song_chord_lyrics_analyzer.metrics.adapters import chord_segments  # noqa: E402
from song_chord_lyrics_analyzer.utils.errors import InputError, SongLabError  # noqa: E402

#: Same default as the benchmark's change-window, so the two runs describe
#: boundaries with the same tolerance.
DEFAULT_WINDOW = 0.5

#: ``0`` decomposed, ``1`` nothing decomposed, ``2`` bad request.
EXIT_NOTHING_MEASURED = 1

_LABEL_VIEWS = ("raw", "triad")


def _hypothesis(
    engine: Any,
    audio_path: Path,
    options: ChordAnalysisOptions,
    duration: float,
) -> tuple[list[ChordSegment], float, dict[str, Any]]:
    """Run the engine on one take and close its last event at the track end.

    The harness does exactly this (``scripts/chord_benchmark.py``); copying the
    six lines keeps the two paths from drifting apart silently while pretending
    to share an abstraction that would only exist for them.
    """
    started = time.perf_counter()
    result = engine.analyze(audio_path, options)
    wall = time.perf_counter() - started
    performance = result.metadata.get("performance")
    if not isinstance(performance, dict):
        performance = {}
    audio_seconds = performance.get("audio_seconds")
    end = float(audio_seconds) if isinstance(audio_seconds, (int, float)) else duration
    events = chord_segments(result.chords, end=end)
    segments = [(float(start), float(stop), label) for start, stop, label in events]
    return segments, wall, {"engine": result.engine, "version": result.engine_version}


def _reducing(segments: list[ChordSegment], *, label_view: str) -> list[ChordSegment]:
    """The hypothesis as the named label view scores it.

    ``triad`` reduces only the hypothesis, which is what ``score_take``'s
    ``csr_triads`` does -- the reference keeps its own spelling, so the reduced
    number is a statement about the engine's vocabulary, not about the corpus.
    """
    if label_view == "raw":
        return segments
    labels = triad_reduce([label for _start, _end, label in segments])
    return [
        (start, end, label) for (start, end, _before), label in zip(segments, labels, strict=True)
    ]


def run(args: argparse.Namespace) -> int:
    """Decompose every take the manifest pins and write the report."""
    # The common failure is a corpus that was never downloaded, and it is not
    # the engine's business: say so before checking anything else.
    if not args.corpus_dir.is_dir():
        raise InputError(
            f"GuitarSet corpus directory not found: {args.corpus_dir}",
            hint=(
                "Download GuitarSet v1.1.0 from Zenodo 10.5281/zenodo.3371780 and point "
                "--corpus-dir at the extracted audio_mono-mic and annotation files. "
                "The 462 MiB of audio is deliberately not in the repository."
            ),
        )
    manifest = load_manifest(args.manifest)
    takes = manifest.subset(split="comp")[: args.limit]
    registry = create_default_registry()
    engine = registry.get(EngineKind.CHORDS, args.engine)
    if not engine.is_available():
        raise InputError(
            f"Engine {args.engine!r} is not available in this environment.",
            hint='Install the DSP extra: pip install -e ".[dev,dsp]"',
        )

    extra: dict[str, Any] = {"decoder": args.decoder}
    if args.change_penalty is not None:
        extra["change_penalty"] = args.change_penalty
    options = ChordAnalysisOptions(extra=extra)
    environment = _environment(engine)
    out_dir: Path = args.out
    out_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, Any]] = []
    decompositions: list[ErrorDecomposition] = []
    timings: list[dict[str, float]] = []
    started = time.time()
    for index, take in enumerate(takes, 1):
        audio_path, jams_path = verify_take_files(
            take, args.corpus_dir, check_hashes=not args.no_verify
        )
        reference = read_jams_chords(jams_path, index=_VIEW_INDEX[args.reference])
        hypothesis, wall, provenance = _hypothesis(
            engine, audio_path, options, take.duration_seconds
        )
        hypothesis = _reducing(hypothesis, label_view=args.label_view)
        scored = duration_csr(reference, hypothesis)
        breakdown = decompose(reference, hypothesis, edge_window=args.edge_window)
        timing = timing_view(reference, hypothesis, window=args.snap_window)
        decompositions.append(breakdown)
        timings.append(timing)
        rows.append(
            {
                "take": take.name,
                "split": take.split,
                "reference": args.reference,
                "label_view": args.label_view,
                "engine": provenance["engine"],
                "engine_version": provenance["version"],
                "wall_seconds": round(wall, 3),
                "total_seconds": round(scored["total_s"], 3),
                "correct_seconds": round(scored["equal_s"], 3),
                "csr": scored["csr"],
                "seconds": {
                    AGREEMENT: round(breakdown.seconds[AGREEMENT], 3),
                    **{
                        name: round(breakdown.seconds[name], 3)
                        for name in CHORD_ERROR_CLASSES
                        if breakdown.seconds[name]
                    },
                },
                "timing": {key: timing[key] for key in ("csr", "csr_snapped", "csr_points_gained")},
                "reference_segments": [
                    [round(float(start), 3), round(float(end), 3), label]
                    for start, end, label in reference
                ],
                "hypothesis_segments": [
                    [round(float(start), 3), round(float(end), 3), label]
                    for start, end, label in hypothesis
                ],
            }
        )
        print(
            f"[{index:3d}/{len(takes)}] {take.name:28s} csr={scored['csr']:.3f} "
            f"lost={breakdown.lost_seconds:5.1f}s "
            + " ".join(
                f"{name}={breakdown.seconds[name]:.1f}"
                for name in CHORD_ERROR_CLASSES
                if breakdown.seconds[name] > 0.0
            )
            + f" ({wall:.1f}s)"
        )

    if not decompositions:
        print("no takes decomposed; nothing written")
        return EXIT_NOTHING_MEASURED

    total = aggregate_decompositions(decompositions)
    timing_total = aggregate_timing_views(timings)
    document: dict[str, Any] = {
        "kind": "chord_error_decomposition",
        "script": "scripts/chord_error_decomposition.py",
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        "manifest": str(args.manifest),
        "manifest_content_digest": manifest.content_digest(),
        "settings": {
            "reference": args.reference,
            "label_view": args.label_view,
            "decoder": extra["decoder"],
            "change_penalty": extra.get("change_penalty", chroma_baseline.DEFAULT_CHANGE_PENALTY),
            "edge_window": args.edge_window,
            "snap_window": args.snap_window,
            "corpus_verified": not args.no_verify,
        },
        "environment": environment,
        **total.to_dict(),
        # The recorded chord number is a mean over takes, not a duration
        # weighting; both are reported so neither can be mistaken for the other.
        "csr_mean_of_takes": sum(row["csr"] for row in rows) / len(rows),
        "timing": timing_total,
        "per_take": rows,
    }
    (out_dir / "decomposition.json").write_text(
        json.dumps(document, indent=1) + "\n", encoding="utf-8"
    )
    (out_dir / "decomposition.md").write_text(_markdown(document), encoding="utf-8")
    print()
    print(_markdown(document))
    print(f"wrote {out_dir / 'decomposition.json'} and decomposition.md")
    print(f"takes={total.takes} elapsed={time.time() - started:.0f}s")
    return 0


def _takes_label(count: int, *, qualifier: str = "") -> str:
    noun = f"{qualifier} take".strip()
    return f"{count} {noun}" if count == 1 else f"{count} {noun}s"


def _markdown(document: dict[str, Any]) -> str:
    """The report tables, with provenance beside every number."""
    settings = document["settings"]
    environment = document["environment"]
    seconds = document["seconds"]
    total = document["total_seconds"]
    lost = document["lost_seconds"]
    lines = [
        "### Which chord errors the measured loss is made of",
        "",
        "| Class | Seconds | Share of the lost CSR | At a boundary | Mid-chord |",
        "| --- | --- | --- | --- | --- |",
    ]
    lines.append(
        f"| agreed (not a loss) | {seconds[AGREEMENT]:.1f} | n/a | "
        f"{document['edge_seconds'][AGREEMENT]:.1f} | "
        f"{document['interior_seconds'][AGREEMENT]:.1f} |"
    )
    for name in CHORD_ERROR_CLASSES:
        share = document["shares_of_lost"][name]
        lines.append(
            f"| {name} | {seconds[name]:.1f} | {100.0 * share:.1f}% of the loss | "
            f"{document['edge_seconds'][name]:.1f} | "
            f"{document['interior_seconds'][name]:.1f} |"
        )
    lines.extend(
        [
            f"| **scored reference time** | **{total:.1f}** | loss = {lost:.1f} s | | |",
            "",
            f"**Aggregate CSR (duration-weighted over {_takes_label(document['takes'])}):** "
            f"{document['csr']:.4f}. Mean of per-take CSR (the figure "
            f"`scripts/chord_benchmark.py` reports): "
            f"{document['csr_mean_of_takes']:.4f}.",
            "",
            "### Boundary/timing counterfactual",
            "",
            f"Snapping every hypothesis boundary onto the nearest reference boundary "
            f"within {settings['snap_window']} s, leaving the labels alone, recovers "
            f"{document['timing']['csr_points_gained']:.4f} CSR "
            f"({document['timing']['csr']:.4f} to {document['timing']['csr_snapped']:.4f}); "
            f"{int(document['timing']['boundaries_moved'])} boundaries moved, "
            f"{int(document['timing']['segments_dropped'])} segments collapsed. This figure "
            "overlaps the class table above by construction -- it is an upper bound on what "
            "better segmentation alone can buy, not another share of the same loss.",
            "",
            f"**Run:** {_takes_label(document['takes'], qualifier='comp')}, reference view "
            f"`{settings['reference']}`, label view `{settings['label_view']}`, engine "
            f"`{environment['engine']}` {environment['engine_version']}, decoder "
            f"`{settings['decoder']}`, change penalty {settings['change_penalty']}, "
            f"edge window {settings['edge_window']} s, snap window {settings['snap_window']} s, "
            f"corpus verified={settings['corpus_verified']}.",
            f"**Environment:** {environment['platform']}, CPython {environment['python']}, "
            f"numpy {environment['numpy']}, librosa {environment['librosa']}, "
            f"commit {environment['git_commit']}.",
            f"**Date:** {document['date']} (UTC). "
            f"Corpus content digest {document['manifest_content_digest']}.",
            "",
            "Read `At a boundary` / `Mid-chord` as *where* each class sits relative to a "
            "reference chord change: a class concentrated at boundaries is a timing symptom, "
            "one concentrated mid-chord is a recognition symptom. Seconds in each column "
            "belong to that class only, so they sum to the class's own seconds.",
        ]
    )
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    """The command line."""
    parser = argparse.ArgumentParser(
        prog="chord_error_decomposition.py",
        description=(
            "Name the chord errors behind the measured CSR on the committed "
            "GuitarSet comp manifest: which class each lost second belongs to, "
            "and how much of the loss a corrected boundary would recover."
        ),
    )
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument(
        "--corpus-dir",
        type=Path,
        default=Path(".cache/chords/guitarset"),
        help="directory holding the downloaded <take>.jams and <take>_mic.wav files",
    )
    parser.add_argument(
        "--reference",
        choices=ANNOTATION_VIEWS,
        default="instructed",
        help="JAMS chord annotation to score against (never mixed in one number)",
    )
    parser.add_argument(
        "--label-view",
        choices=_LABEL_VIEWS,
        default="raw",
        help="'raw' scores the engine's own labels, 'triad' reduces them to the 24 triads",
    )
    parser.add_argument("--engine", default="chroma-baseline")
    parser.add_argument("--decoder", choices=("viterbi", "majority"), default="viterbi")
    parser.add_argument(
        "--change-penalty",
        type=float,
        default=None,
        help="Viterbi change penalty; omit to use the engine's measured default",
    )
    parser.add_argument(
        "--edge-window",
        type=float,
        default=DEFAULT_WINDOW,
        help="seconds around a reference boundary treated as boundary time",
    )
    parser.add_argument(
        "--snap-window",
        type=float,
        default=DEFAULT_WINDOW,
        help="seconds within which a hypothesis boundary may be corrected",
    )
    parser.add_argument("--limit", type=int, default=None, help="decompose at most N takes")
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="output directory (default .cache/chords/decomposition/<timestamp>)",
    )
    parser.add_argument(
        "--no-verify",
        action="store_true",
        help="skip SHA-256 verification (not reproducible; for local experiments only)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Entry point: decompose the pinned corpus, or refuse to."""
    args = build_parser().parse_args(argv)
    if args.out is None:
        args.out = Path(".cache/chords/decomposition") / datetime.now().strftime("%Y-%m-%d-%H%M%S")
    try:
        return run(args)
    except SongLabError as error:
        print(f"error: {error.message}", file=sys.stderr)
        if error.hint:
            print(f"hint: {error.hint}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
