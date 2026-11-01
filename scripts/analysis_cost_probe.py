#!/usr/bin/env python3
"""Where one analysis spends its time, and what a shared decode could save.

This is developer tooling, not a shipped command: it lives in ``scripts/`` and
is never included in the wheel or exercised by ``songlab``. It exists because
audit §10 P7 proposes an application-level cache of decoded samples keyed by
path and decode parameters, and that proposal rests on an unmeasured premise -
"a song is decoded at least three times". Before refactoring orchestration for
a saving, measure the saving.

What it answers, in this order:

* how long does one ``run_analysis()`` take, per engine step, on the first run
  in a fresh process and in steady state;
* how many decodes that run actually performs, whether they are the same
  request (same path, sample rate, mono, offset, duration), and what the
  repeats cost - that repeat total is the whole size of the prize P7 offers;
* how much of the run the decode layer is at all, cold and warm;
* what P7's *other* half is worth, when ``--chroma`` is asked for: one
  ``chroma_cqt`` call of the request the key engine makes, timed on the same
  file after the analyses (so warm, so marginal).

Method, and its one trick: each engine module holds ``decode_audio`` in its own
namespace, so the probe wraps *that name* with a timer for the duration of the
measurement and restores it afterwards. No engine is edited, no behaviour
changes, and the wrapper records the request it saw - the file plus the
effective parameters, with the service's own defaults filled in - and the size
of the samples it returned. A premise that has quietly stopped holding (a fourth
decode, a different window) is therefore reported instead of assumed. The
per-step times are the engines' own section 45 measurements, read off the
outcome.

Memory is not reported unless the platform provides it:
``performance.peak_rss_bytes`` is POSIX-only, so on Windows every row says
``null`` and no estimate is invented.

Usage::

    # a cost fixture: generated tone audio, nothing copyrighted, nothing committed
    python scripts/analysis_cost_probe.py --make-fixture .cache/cost_fixture.wav --seconds 120

    # the committed sample, three runs
    python scripts/analysis_cost_probe.py samples/vocadito_2.wav

    # machine-readable record (never commit it)
    python scripts/analysis_cost_probe.py .cache/cost_fixture.wav --json .cache/cost_probe.json

    # include the lyrics layer, which needs the `lyrics` extra and the model
    python scripts/analysis_cost_probe.py samples/vocadito_2.wav --with-lyrics

    # also price P7's other half: the chromagram the key engine computes
    python scripts/analysis_cost_probe.py .cache/cost_fixture.wav --chroma
"""

from __future__ import annotations

import argparse
import importlib.metadata
import inspect
import json
import math
import platform
import struct
import subprocess
import sys
import time
import wave
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from song_chord_lyrics_analyzer.analysis import run_analysis  # noqa: E402
from song_chord_lyrics_analyzer.audio.decode import decode_audio  # noqa: E402
from song_chord_lyrics_analyzer.engines import (  # noqa: E402
    chroma_baseline,
    key_krumhansl,
    lyrics_parakeet,
    tempo_librosa,
)
from song_chord_lyrics_analyzer.engines.base import EngineKind  # noqa: E402
from song_chord_lyrics_analyzer.engines.registry import create_default_registry  # noqa: E402
from song_chord_lyrics_analyzer.performance import peak_rss_bytes  # noqa: E402
from song_chord_lyrics_analyzer.utils.errors import (  # noqa: E402
    DependencyError,
    InputError,
    SongLabError,
)

#: The four modules that decode through the shared service, with the step each
#: one produces. A decode from anywhere else is not attributed to a step.
ENGINE_MODULES: tuple[tuple[Any, str], ...] = (
    (chroma_baseline, "chords"),
    (key_krumhansl, "key"),
    (tempo_librosa, "tempo"),
    (lyrics_parakeet, "lyrics"),
)

#: The sample rate the chord, key and tempo engines request.
SAMPLE_RATE = chroma_baseline.SAMPLE_RATE

#: What a decode request means once the service's own defaults are filled in:
#: "no offset" and "offset=0.0" are the same request, and a premise check that
#: cannot tell them apart is worth nothing.
_DECODE_DEFAULTS: dict[str, Any] = {
    name: parameter.default
    for name, parameter in inspect.signature(decode_audio).parameters.items()
    if name != "path" and parameter.default is not inspect.Parameter.empty
}

#: A chord cycle for the generated cost fixture: C, G, A minor, F.
_FIXTURE_CHORDS: tuple[tuple[int, ...], ...] = ((0, 4, 7), (7, 11, 2), (9, 0, 4), (5, 9, 0))


def _request_of(path: Any, kwargs: dict[str, Any]) -> dict[str, Any]:
    """A decode call as the P7 cache would key it: file plus effective parameters."""
    return {"path": str(path), **_DECODE_DEFAULTS, **kwargs}


def _buffer_bytes(decoded: Any) -> int | None:
    """How many bytes of samples one decode put in memory, when it reports them."""
    return getattr(getattr(decoded, "samples", None), "nbytes", None)


@dataclass(frozen=True)
class DecodeCall:
    """One decode an engine performed, timed from inside the run.

    ``params`` is the request as the P7 cache would key it, so the report can
    say whether the repeats are genuinely the same request.
    """

    step: str
    seconds: float
    params: dict[str, Any]
    decoded_bytes: int | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "step": self.step,
            "seconds": round(self.seconds, 4),
            "params": self.params,
            "decoded_bytes": self.decoded_bytes,
        }


@dataclass(frozen=True)
class RunRow:
    """One ``run_analysis()`` call, measured end to end."""

    index: int
    total_seconds: float
    steps: dict[str, float]
    decodes: tuple[DecodeCall, ...]

    @property
    def decode_seconds(self) -> float:
        return sum(decode.seconds for decode in self.decodes)

    @property
    def repeat_decode_seconds(self) -> float:
        """Every decode after the first - what a shared decode could remove."""
        return sum(decode.seconds for decode in self.decodes[1:])

    @property
    def decode_share(self) -> float:
        return self.decode_seconds / self.total_seconds if self.total_seconds else 0.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "total_seconds": round(self.total_seconds, 4),
            "steps": {kind: round(seconds, 4) for kind, seconds in self.steps.items()},
            "decodes": [decode.as_dict() for decode in self.decodes],
            "decode_seconds": round(self.decode_seconds, 4),
            "repeat_decode_seconds": round(self.repeat_decode_seconds, 4),
            "decode_share": round(self.decode_share, 4),
        }


@dataclass(frozen=True)
class FileReport:
    """Every measurement taken for one input file."""

    path: Path
    audio_seconds: float
    rows: tuple[RunRow, ...]
    identical_decodes: bool
    decode_request: dict[str, Any]
    chroma_seconds: tuple[float, ...] = ()

    def steady_state(self) -> RunRow | None:
        """The last run, i.e. the one that is not paying for warm-up."""
        return self.rows[-1] if len(self.rows) > 1 else None

    @property
    def decoded_bytes(self) -> int | None:
        """What one decode of this file puts in memory, when the backend reports it."""
        return next((call.decoded_bytes for row in self.rows for call in row.decodes), None)

    def as_dict(self) -> dict[str, Any]:
        steady = self.steady_state()
        return {
            "path": str(self.path),
            "audio_seconds": round(self.audio_seconds, 4),
            "identical_decodes": self.identical_decodes,
            "decode_request": self.decode_request,
            "decoded_bytes": self.decoded_bytes,
            "chroma_seconds": [round(seconds, 4) for seconds in self.chroma_seconds],
            "runs": [row.as_dict() for row in self.rows],
            "cacheable_seconds_in_steady_state": (
                round(steady.repeat_decode_seconds, 4) if steady is not None else None
            ),
        }


@contextmanager
def _time_decodes(calls: list[DecodeCall]) -> Iterator[None]:
    """Time every ``decode_audio`` the engine modules call, then put it back."""
    installed: list[tuple[Any, Any]] = []

    def wrap(module: Any, step: str) -> None:
        original = module.decode_audio

        def spy(path: Any, _step: str = step, _fn: Any = original, **kwargs: Any) -> Any:
            started = time.perf_counter()
            decoded = _fn(path, **kwargs)
            calls.append(
                DecodeCall(
                    _step,
                    time.perf_counter() - started,
                    _request_of(path, kwargs),
                    _buffer_bytes(decoded),
                )
            )
            return decoded

        module.decode_audio = spy
        installed.append((module, original))

    for module, step in ENGINE_MODULES:
        wrap(module, step)
    try:
        yield
    finally:
        for module, original in installed:
            module.decode_audio = original


def _environment() -> dict[str, str]:
    """What ran this measurement, so a number can never be read as a constant."""

    def version(distribution: str) -> str:
        try:
            return importlib.metadata.version(distribution)
        except importlib.metadata.PackageNotFoundError:
            return "not installed"

    try:
        commit = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        commit = "unknown"
    return {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "numpy": version("numpy"),
        "librosa": version("librosa"),
        "soundfile": version("soundfile"),
        "onnx_asr": version("onnx-asr"),
        "git_commit": commit,
    }


def _fixture_loop(seconds_per_chord: float, sample_rate: int) -> bytes:
    """One raw 16-bit mono PCM loop of C - G - A minor - F, as bytes."""
    frames_per_chord = max(1, round(seconds_per_chord * sample_rate))
    voices = max(len(chord) for chord in _FIXTURE_CHORDS)
    peak = int(0.2 * 32767 / voices)
    frames = bytearray()
    for chord in _FIXTURE_CHORDS:
        hertz = [440.0 * 2.0 ** ((60 + pitch - 69) / 12.0) for pitch in chord]
        for index in range(frames_per_chord):
            value = peak * sum(math.sin(2.0 * math.pi * h * index / sample_rate) for h in hertz)
            frames.extend(struct.pack("<h", max(-32768, min(32767, int(value)))))
    return bytes(frames)


def make_fixture(path: Path, *, seconds: float, sample_rate: int = SAMPLE_RATE) -> Path:
    """Write generated tone audio long enough that per-second cost is visible.

    A loop of C - G - A minor - F: harmonic content the chord and key engines
    can work on, no rhythm, and no recording. It exists so the measurement is
    reproducible without private or copyrighted material.
    """
    if seconds <= 0:
        raise InputError(f"--seconds must be positive, got {seconds!r}")
    loop = _fixture_loop(2.0, sample_rate)
    frames = int(seconds * sample_rate)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(sample_rate)
        written = 0
        while written < frames:
            chunk = min(len(loop) // 2, frames - written)
            writer.writeframes(loop[: chunk * 2])
            written += chunk
    return path


def probe_file(
    path: Path,
    *,
    registry: Any,
    runs: int,
    input_hash: bool = False,
) -> FileReport:
    """Measure ``runs`` analyses of ``path`` in this process, plus the decodes."""
    if runs < 1:
        raise InputError(f"runs must be at least 1, got {runs}")
    rows: list[RunRow] = []
    requests: list[dict[str, Any]] = []
    duration = 0.0
    for index in range(1, runs + 1):
        calls: list[DecodeCall] = []
        with _time_decodes(calls):
            started = time.perf_counter()
            outcome = run_analysis(path, registry=registry, input_hash=input_hash)
            total = time.perf_counter() - started
        duration = outcome.result.audio.duration
        steps = {
            step.kind: step.processing_time_seconds
            for step in outcome.steps
            if step.processing_time_seconds is not None
        }
        rows.append(RunRow(index, total, steps, tuple(calls)))
        requests.extend(call.params for call in calls)
    return FileReport(
        path=path,
        audio_seconds=duration,
        rows=tuple(rows),
        identical_decodes=bool(requests) and all(r == requests[0] for r in requests),
        decode_request=requests[0] if requests else {},
    )


def probe_chroma(path: Path, *, repeats: int) -> tuple[float, ...]:
    """Time the chromagram the key engine asks for - P7's other half.

    The key engine and the chord engine both call ``librosa.feature.chroma_cqt``
    at the same sample rate and hop, so a shared feature could in principle
    remove one of those calls. Whether that is worth anything is a timing
    question, and whether it is *allowed* is a label question: the two engines do
    not pass the same tuning. This measures only the first.

    The pass runs after the analyses, so the libraries are already warm and the
    number is a marginal saving, not a cold one.
    """
    try:
        import librosa
    except ImportError as error:
        raise DependencyError(
            "The chroma pass needs librosa, which is not installed.",
            hint='Install the DSP extra: pip install -e ".[dev,dsp]"',
        ) from error
    decoded = decode_audio(path, sample_rate=SAMPLE_RATE, mono=True)
    timings: list[float] = []
    for _ in range(repeats):
        started = time.perf_counter()
        librosa.feature.chroma_cqt(
            y=decoded.samples,
            sr=int(decoded.sample_rate),
            hop_length=key_krumhansl.HOP_LENGTH,
        )
        timings.append(time.perf_counter() - started)
    return tuple(timings)


def format_report(reports: Sequence[FileReport], environment: dict[str, str]) -> str:
    """The console report: environment first, then one block per file."""
    lines = [
        "environment: {platform} / CPython {python}".format(**environment),
        "libraries: numpy {numpy}, librosa {librosa}, soundfile {soundfile}, "
        "onnx-asr {onnx_asr} (commit {git_commit})".format(**environment),
        f"date: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} (UTC)",
        "memory: peak RSS is POSIX-only; on Windows it is reported as null, "
        "so no memory figure appears here",
    ]
    for report in reports:
        kinds = sorted({kind for row in report.rows for kind in row.steps})
        lines.append("")
        lines.append(f"{report.path}  ({report.audio_seconds:.3f} s of audio)")
        header = f"  {'run':>3}  {'total':>7}" + "".join(f" {kind:>8}" for kind in kinds)
        header += f" {'decodes':>8}  {'decode':>7}  {'share':>6}  {'repeats':>7}"
        lines.append(header)
        for row in report.rows:
            cells = f"  {row.index:>3}  {row.total_seconds:>7.2f}"
            cells += "".join(
                f" {row.steps[kind]:>8.2f}" if kind in row.steps else " " * 9 for kind in kinds
            )
            cells += (
                f" {len(row.decodes):>8}  {row.decode_seconds:>7.2f}  "
                f"{100 * row.decode_share:>5.1f}%  {row.repeat_decode_seconds:>7.2f}"
            )
            lines.append(cells)
        steady = report.steady_state()
        request = {key: value for key, value in report.decode_request.items() if key != "path"}
        lines.append(
            f"  decodes in run 1: {len(report.rows[0].decodes)}, identical request: "
            f"{report.identical_decodes} {request}"
        )
        if report.decoded_bytes is None:
            lines.append(
                "  each decode returns samples whose size the backend does not report, "
                "so the memory side of P7 is not measured here"
            )
        else:
            lines.append(
                f"  each of those decodes returns {report.decoded_bytes / (1024 * 1024):.1f} MiB "
                f"of samples, which is what a cache would reuse instead of decoding again"
            )
        if report.chroma_seconds:
            timings = ", ".join(f"{seconds:.2f}" for seconds in report.chroma_seconds)
            lines.append(
                f"  one chroma_cqt call of the key engine's request costs "
                f"{timings} s (measured after the analyses, so warm): a shared "
                f"chromagram would remove one of those per run"
            )
        if steady is not None:
            lines.append(
                f"  a shared decode could remove at most "
                f"{steady.repeat_decode_seconds:.2f} s of the steady-state "
                f"{steady.total_seconds:.2f} s run "
                f"({100 * steady.repeat_decode_seconds / steady.total_seconds:.1f}%), "
                f"and nothing from the first run's cold decode"
            )
    return "\n".join(lines) + "\n"


def run(args: argparse.Namespace) -> int:
    """Probe every requested file and print the report."""
    registry = create_default_registry()
    if not args.with_lyrics:
        registry.unregister(EngineKind.LYRICS, lyrics_parakeet.ENGINE_NAME)
    running = [kind.value for kind in EngineKind if registry.names(kind)]
    print(f"layers under test: {', '.join(running)}")

    reports: list[FileReport] = []
    for path in args.paths:
        report = probe_file(path, registry=registry, runs=args.runs, input_hash=args.input_hash)
        if args.chroma:
            report = replace(report, chroma_seconds=probe_chroma(path, repeats=args.runs))
        reports.append(report)
    environment = _environment()
    report_text = format_report(reports, environment)
    print(report_text, end="")

    if args.json is not None:
        record = {
            "tool": "analysis_cost_probe",
            "date": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
            "environment": environment,
            "layers": running,
            "runs_requested": args.runs,
            "peak_rss_bytes": peak_rss_bytes(),
            "files": [report.as_dict() for report in reports],
        }
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(record, indent=1, allow_nan=False) + "\n", encoding="utf-8")
        print(f"wrote {args.json} (do not commit it)")
    return 0


def build_parser() -> argparse.ArgumentParser:
    """The command line."""
    parser = argparse.ArgumentParser(
        prog="analysis_cost_probe.py",
        description=(
            "Measure where run_analysis() spends its time, and what a shared "
            "decode between the chord, key and tempo engines could save."
        ),
    )
    parser.add_argument("paths", type=Path, nargs="*", help="audio files to probe")
    parser.add_argument("--runs", type=int, default=3, help="analyses per file (default 3)")
    parser.add_argument(
        "--with-lyrics",
        action="store_true",
        help="include the lyrics layer (needs the `lyrics` extra and the model download)",
    )
    parser.add_argument(
        "--input-hash",
        action="store_true",
        help="let the service hash the file into provenance (off by default: not the subject)",
    )
    parser.add_argument(
        "--chroma",
        action="store_true",
        help=(
            "also time the chroma_cqt request the key engine makes, after the "
            "analyses - the prize P7's shared-feature half would collect"
        ),
    )
    parser.add_argument(
        "--json",
        type=Path,
        default=None,
        metavar="PATH",
        help="also write a machine-readable record to this path",
    )
    parser.add_argument(
        "--make-fixture",
        type=Path,
        default=None,
        metavar="PATH",
        help="write generated tone audio here and exit (keep it in the gitignored cache)",
    )
    parser.add_argument(
        "--seconds",
        type=float,
        default=120.0,
        help="length of the generated fixture (default 120)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Entry point: build a fixture, or run the measurement."""
    args = build_parser().parse_args(argv)
    try:
        if args.make_fixture is not None:
            path = make_fixture(args.make_fixture, seconds=args.seconds)
            with wave.open(str(path), "rb") as reader:
                duration = reader.getnframes() / float(reader.getframerate())
                sample_rate = reader.getframerate()
            print(f"wrote {path}: {duration:.3f} s, {sample_rate} Hz mono PCM_16")
            return 0
        if not args.paths:
            raise InputError(
                "No input file.",
                hint="Pass an audio file, or --make-fixture .cache/cost_fixture.wav first.",
            )
        return run(args)
    except SongLabError as error:
        print(f"error: {error.message}", file=sys.stderr)
        if error.hint:
            print(f"hint: {error.hint}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
