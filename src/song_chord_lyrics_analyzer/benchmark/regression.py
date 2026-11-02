"""Accuracy vectors: the fixed evaluation set and the tracking of changes.

The chord engine's recorded accuracy is a mean over **one fixed set** -- 180
GuitarSet comping takes, the instructed lead sheet, ``instructed`` view only
(``docs/ENGINE_COMPARISON.md`` §1-3, §8). Every accuracy claim in this
repository is a number on that set, so the claim is only meaningful while the
set is pinned and a new run is compared against the run it replaced. Roadmap
Phase J asked for exactly that comparison step, because up to now the fixed set
lived in a manual table and an engine change could quietly move the number
without anyone checking which direction.

This module holds the two pieces of that check:

* an :class:`AccuracyVector` -- the metrics of one measured run, with the
  evaluation set it was measured on, the settings that produced it and the
  environment and date it was measured in;
* :func:`compare_run` -- a harness ``aggregate.json`` against a committed
  vector, which first refuses anything that was not measured on the same
  evaluation set and then reports every tracked metric as improved, regressed
  or unchanged.

Nothing here measures anything: it reads a committed vector and the aggregate a
developer has just produced (``scripts/chord_benchmark.py --check-vector``)
and compares them. The committed vectors live under ``benchmark/reference/``
(the sibling ``benchmark/*.json`` pattern is gitignored generated output), and
each one names the document section its numbers came from, so a figure in a
vector can be traced to the run that measured it.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from song_chord_lyrics_analyzer.evaluation.guitarset import (
    ANNOTATION_VIEWS,
    GuitarSetManifest,
)
from song_chord_lyrics_analyzer.utils.errors import InputError

__all__ = [
    "AccuracyVector",
    "EvaluationSet",
    "MetricDelta",
    "MetricReference",
    "RegressionReport",
    "SCHEMA_VERSION",
    "UNCHANGED_BAND",
    "compare_run",
    "evaluation_set_mismatch",
    "format_report",
    "load_vector",
    "to_document",
    "vector_from_aggregate",
    "write_vector",
]

#: The schema this module reads and writes.
SCHEMA_VERSION = "1"

#: A change smaller than one unit in the last recorded decimal is not a
#: measured change: the committed vectors publish four decimals, so anything
#: below 1e-4 is indistinguishable from their own rounding.
UNCHANGED_BAND = 1e-4

#: The statistics a vector may name, as the harness aggregate offers them.
_STATISTICS = ("mean", "median", "min", "max")

#: How each tracked metric should be read. ``higher`` and ``lower`` say which
#: direction is an improvement; ``neutral`` marks a descriptive figure that is
#: reported but never judged -- a count of chords per take says what the engine
#: did, not whether that was better.
_DIRECTIONS = {
    "csr": "higher",
    "csr_triads": "higher",
    "segment_overlap": "higher",
    "change_precision": "higher",
    "change_recall": "higher",
    "change_f1": "higher",
    "timing_reference_to_hypothesis": "lower",
    "timing_hypothesis_to_reference": "lower",
    "hypothesis_chords": "neutral",
    "hypothesis_segments": "neutral",
}

#: Labels for a human report, matching the §8 tables.
_LABELS = {
    "csr": "Duration CSR",
    "csr_triads": "Duration CSR (triad-reduced)",
    "segment_overlap": "Segment overlap (MIREX mean)",
    "change_precision": "Change precision",
    "change_recall": "Change recall",
    "change_f1": "Change F1",
    "timing_reference_to_hypothesis": "Boundary error ref -> hyp (s)",
    "timing_hypothesis_to_reference": "Boundary error hyp -> ref (s)",
    "hypothesis_chords": "Hypothesis chords per take",
    "hypothesis_segments": "Hypothesis segments per take",
}

#: Verdict names, in the order a reader cares about.
VERDICT_IMPROVED = "improved"
VERDICT_REGRESSED = "regressed"
VERDICT_UNCHANGED = "unchanged"


@dataclass(frozen=True)
class EvaluationSet:
    """Which corpus, which takes and which annotation a vector was measured on.

    ``content_digest`` is the digest of the manifest *as parsed content*
    (:meth:`GuitarSetManifest.content_digest`), not of its bytes: Git's text
    conversion hands the same committed manifest back with CRLF endings on
    Windows, so a byte digest would name a checkout rather than a set.
    """

    dataset: str
    version: str
    manifest: str
    content_digest: str
    takes: int
    split: str
    reference: str

    def describe(self) -> str:
        """One line naming the set, for messages and reports."""
        return (
            f"{self.dataset} {self.version}, {self.takes} {self.split} takes, "
            f"reference view {self.reference!r}"
        )


@dataclass(frozen=True)
class MetricReference:
    """One tracked metric: the statistic the vector publishes and its value."""

    statistic: str
    value: float


@dataclass(frozen=True)
class AccuracyVector:
    """One measured run, reduced to the figures worth tracking.

    ``settings`` and ``environment`` are provenance, not inputs to the verdict:
    a comparison across a different numpy or a different change penalty is
    still a comparison, but the report has to say so, because it is then not a
    like-for-like engine change.
    """

    engine: str
    metric_family: str
    evaluation_set: EvaluationSet
    metrics: dict[str, MetricReference]
    settings: dict[str, Any] = field(default_factory=dict)
    environment: dict[str, str] = field(default_factory=dict)
    date: str = ""
    source: str = ""
    notes: str = ""


@dataclass(frozen=True)
class MetricDelta:
    """The change of one tracked metric between the vector and a new run."""

    metric: str
    label: str
    direction: str
    statistic: str
    reference: float
    current: float
    change: float
    verdict: str


@dataclass(frozen=True)
class RegressionReport:
    """A run compared against its vector: one delta per metric, one verdict."""

    engine: str
    reference_engine: str
    evaluation_set: EvaluationSet
    deltas: tuple[MetricDelta, ...]
    verdict: str
    date: str
    source: str
    settings_changed: tuple[str, ...]
    environment_changed: bool

    def to_dict(self) -> dict[str, Any]:
        """A JSON-safe record of the comparison."""
        return {
            "schema_version": SCHEMA_VERSION,
            "kind": "accuracy_comparison",
            "engine": self.engine,
            "reference_engine": self.reference_engine,
            "verdict": self.verdict,
            "evaluation_set": {
                "dataset": self.evaluation_set.dataset,
                "version": self.evaluation_set.version,
                "manifest": self.evaluation_set.manifest,
                "content_digest": self.evaluation_set.content_digest,
                "takes": self.evaluation_set.takes,
                "split": self.evaluation_set.split,
                "reference": self.evaluation_set.reference,
            },
            "reference_date": self.date,
            "reference_source": self.source,
            "settings_changed": list(self.settings_changed),
            "environment_changed": self.environment_changed,
            "metrics": [
                {
                    "metric": delta.metric,
                    "label": delta.label,
                    "statistic": delta.statistic,
                    "direction": delta.direction,
                    "reference": delta.reference,
                    "current": delta.current,
                    "change": delta.change,
                    "verdict": delta.verdict,
                }
                for delta in self.deltas
            ],
        }


def _text(document: dict[str, Any], field_name: str, source: Path) -> str:
    """A required non-empty string, or a refusal naming the file and field."""
    value = document.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise InputError(f"{source}: {field_name!r} must be a non-empty string.")
    return value


def _finite_number(value: Any, label: str, source: Path) -> float:
    """A number that is neither NaN nor infinite.

    A vector is read by people and compared by machine, and an ``Infinity`` in
    a JSON file parses happily in Python while ``allow_nan=False`` refuses to
    write it back out -- so it is refused here, at the boundary.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InputError(f"{source}: {label} must be a number.")
    number = float(value)
    if not math.isfinite(number):
        raise InputError(f"{source}: {label} must be a finite number, got {value!r}.")
    return number


def _evaluation_set(document: Any, source: Path) -> EvaluationSet:
    """The pinned set, with the fields that decide what a run measures."""
    if not isinstance(document, dict):
        raise InputError(f"{source}: 'evaluation_set' must be an object.")
    raw = document
    takes = raw.get("takes")
    if isinstance(takes, bool) or not isinstance(takes, int) or takes <= 0:
        raise InputError(f"{source}: 'evaluation_set.takes' must be a positive integer.")
    reference = _text(raw, "reference", source)
    if reference not in ANNOTATION_VIEWS:
        raise InputError(
            f"{source}: unknown reference view {reference!r}.",
            hint=f"Use one of: {', '.join(ANNOTATION_VIEWS)}.",
        )
    digest = _text(raw, "content_digest", source)
    if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest.lower()):
        raise InputError(
            f"{source}: 'evaluation_set.content_digest' is not a SHA-256 hex digest.",
            hint="Regenerate it with `GuitarSetManifest.content_digest()`.",
        )
    return EvaluationSet(
        dataset=_text(raw, "dataset", source),
        version=_text(raw, "version", source),
        manifest=_text(raw, "manifest", source),
        content_digest=digest.lower(),
        takes=takes,
        split=_text(raw, "split", source),
        reference=reference,
    )


def _metrics(document: Any, source: Path) -> dict[str, MetricReference]:
    """The tracked metrics, each with the statistic it was published as."""
    if not isinstance(document, dict) or not document:
        raise InputError(f"{source}: 'metrics' must be a non-empty object.")
    metrics: dict[str, MetricReference] = {}
    for name, raw in document.items():
        if name not in _DIRECTIONS:
            raise InputError(
                f"{source}: unknown metric {name!r}.",
                hint=f"Tracked metrics: {', '.join(sorted(_DIRECTIONS))}.",
            )
        if not isinstance(raw, dict):
            raise InputError(f"{source}: metric {name!r} must be an object.")
        statistic = _text(raw, "statistic", source)
        if statistic not in _STATISTICS:
            raise InputError(
                f"{source}: metric {name!r} has statistic {statistic!r}.",
                hint=f"Use one of: {', '.join(_STATISTICS)}.",
            )
        metrics[name] = MetricReference(
            statistic=statistic,
            value=_finite_number(raw.get("value"), f"metric {name!r} value", source),
        )
    return metrics


def load_vector(path: Path) -> AccuracyVector:
    """Read a committed accuracy vector.

    Raises:
        InputError: When the file does not exist or cannot be read, is not
            JSON, an object, or is missing a required field, names an unknown
            metric or statistic, carries a non-finite number, or pins a set
            that was not measured.
    """
    source = Path(path)
    try:
        text = source.read_text(encoding="utf-8")
    except FileNotFoundError as error:
        raise InputError(
            f"{source}: no accuracy vector found.",
            hint="Point --vector at a committed file under benchmark/reference/, "
            "or write one from a measured run with --write-vector.",
        ) from error
    except OSError as error:
        raise InputError(f"{source}: the accuracy vector cannot be read: {error}") from error
    try:
        document = json.loads(text)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise InputError(f"{source} is not valid JSON: {error}") from error
    if not isinstance(document, dict):
        raise InputError(f"{source}: the accuracy vector must be a JSON object.")
    schema = _text(document, "schema_version", source)
    if schema != SCHEMA_VERSION:
        raise InputError(
            f"{source}: accuracy vector schema {schema!r} is not {SCHEMA_VERSION!r}.",
            hint="Regenerate the vector with `scripts/chord_benchmark.py --write-vector`.",
        )
    if _text(document, "kind", source) != "accuracy_vector":
        raise InputError(f"{source}: not an accuracy vector (check the 'kind' field).")
    environment = document.get("environment") or {}
    if not isinstance(environment, dict):
        raise InputError(f"{source}: 'environment' must be an object.")
    settings = document.get("settings") or {}
    if not isinstance(settings, dict):
        raise InputError(f"{source}: 'settings' must be an object.")
    return AccuracyVector(
        engine=_text(document, "engine", source),
        metric_family=_text(document, "metric_family", source),
        evaluation_set=_evaluation_set(document.get("evaluation_set"), source),
        metrics=_metrics(document.get("metrics"), source),
        settings=dict(settings),
        environment={str(key): str(value) for key, value in environment.items()},
        date=_text(document, "date", source),
        source=_text(document, "source", source),
        notes=str(document.get("notes") or ""),
    )


def _block(document: dict[str, Any], key: str) -> dict[str, Any]:
    """A nested block of a run record, or an empty one when it is absent.

    A harness aggregate is read as whatever JSON it is, so every block access
    has to survive a missing or mistyped parent; an absent block means "the run
    did not record it", never "it recorded nothing".
    """
    value = document.get(key)
    return value if isinstance(value, dict) else {}


def evaluation_set_mismatch(vector: AccuracyVector, aggregate: dict[str, Any]) -> list[str]:
    """Why this run was not measured on the vector's evaluation set.

    Args:
        vector: The committed figures.
        aggregate: A harness ``aggregate.json`` read as a dict.

    Returns:
        list[str]: One reason per thing that makes the two incomparable, empty
        when the run scored the very set the vector pins.
    """
    problems: list[str] = []
    digest = aggregate.get("manifest_content_digest")
    if not isinstance(digest, str) or not digest:
        problems.append("the run does not record the manifest's content digest")
    elif digest.lower() != vector.evaluation_set.content_digest:
        vector_digest = vector.evaluation_set.content_digest[:12]
        problems.append(
            f"the corpus manifest content digest differs (run {digest[:12]}…, "
            f"vector {vector_digest}…)"
        )
    count = _block(aggregate, "metrics").get("count")
    if isinstance(count, int) and count != vector.evaluation_set.takes:
        pinned = vector.evaluation_set.takes
        problems.append(f"the run scored {count} takes, the vector pins {pinned}")
    view = _block(aggregate, "settings").get("reference")
    if isinstance(view, str) and view != vector.evaluation_set.reference:
        problems.append(
            f"the run used the {view!r} annotation, the vector uses "
            f"{vector.evaluation_set.reference!r}"
        )
    return problems


def _run_metrics(vector: AccuracyVector, aggregate: dict[str, Any]) -> dict[str, float]:
    """The statistics a run reports for the vector's tracked metrics."""
    summary = _block(aggregate, "metrics")
    if not summary:
        raise InputError("the run record has no 'metrics' block to compare against.")
    current: dict[str, float] = {}
    for name, reference in vector.metrics.items():
        values = summary.get(name)
        if not isinstance(values, dict) or values.get(reference.statistic) is None:
            raise InputError(
                f"the run does not report {name!r} as a {reference.statistic!r}, "
                f"which the vector {vector.source!r} tracks.",
                hint="Score the same metric family, or update the vector to the metrics measured.",
            )
        current[name] = _finite_number(
            values[reference.statistic],
            f"run metric {name!r} {reference.statistic!r}",
            Path("<run>"),
        )
    return current


def compare_run(vector: AccuracyVector, aggregate: dict[str, Any]) -> RegressionReport:
    """Compare a harness aggregate against the vector it should be measured with.

    The evaluation set is checked first and a mismatch is refused: a number
    from 30 takes, a different annotation view or another corpus is not a
    change in the engine, and reporting one as such would be the exact error
    this check exists to prevent.

    Args:
        vector: The committed figures to compare against.
        aggregate: A ``scripts/chord_benchmark.py`` ``aggregate.json`` read as
            a dict.

    Returns:
        RegressionReport: One delta per tracked metric and an overall verdict.

    Raises:
        InputError: When the run was not measured on the vector's evaluation
            set, or when it does not report a metric the vector tracks.
    """
    if not isinstance(aggregate, dict):
        raise InputError("the run record must be an object.")
    problems = evaluation_set_mismatch(vector, aggregate)
    if problems:
        raise InputError(
            "This run was not measured on the vector's fixed evaluation set "
            f"({vector.evaluation_set.describe()}).",
            hint="Not comparable: "
            + "; ".join(problems)
            + ". Re-run over the pinned set (the full --limit the manifest names), "
            "or track a separate vector for that set.",
        )

    settings = _block(aggregate, "settings")
    environment = _block(aggregate, "environment")
    current_values = _run_metrics(vector, aggregate)
    deltas: list[MetricDelta] = []
    for name, reference in vector.metrics.items():
        direction = _DIRECTIONS[name]
        change = current_values[name] - reference.value
        verdict = _verdict(direction, change)
        deltas.append(
            MetricDelta(
                metric=name,
                label=_LABELS[name],
                direction=direction,
                statistic=reference.statistic,
                reference=reference.value,
                current=current_values[name],
                change=change,
                verdict=verdict,
            )
        )

    judged = [delta for delta in deltas if delta.direction != "neutral"]
    if any(delta.verdict == VERDICT_REGRESSED for delta in judged):
        verdict = VERDICT_REGRESSED
    elif any(delta.verdict == VERDICT_IMPROVED for delta in judged):
        verdict = VERDICT_IMPROVED
    else:
        verdict = VERDICT_UNCHANGED

    changed_settings = tuple(
        sorted(key for key in vector.settings if vector.settings[key] != settings.get(key))
    )
    reference_engine = str(environment.get("engine") or "")
    return RegressionReport(
        engine=reference_engine or vector.engine,
        reference_engine=vector.engine,
        evaluation_set=vector.evaluation_set,
        deltas=tuple(deltas),
        verdict=verdict,
        date=vector.date,
        source=vector.source,
        settings_changed=changed_settings,
        environment_changed=_environment_differs(vector.environment, environment),
    )


def _verdict(direction: str, change: float) -> str:
    """Read one delta: a gain beyond the band, a loss beyond it, or nothing."""
    if direction == "neutral":
        return "reported"
    signed = change if direction == "higher" else -change
    if signed > UNCHANGED_BAND:
        return VERDICT_IMPROVED
    if signed < -UNCHANGED_BAND:
        return VERDICT_REGRESSED
    return VERDICT_UNCHANGED


#: The environment keys whose difference makes a comparison not like-for-like.
_ENVIRONMENT_KEYS = ("platform", "python", "numpy", "librosa")


def _environment_differs(
    vector_environment: dict[str, str],
    run_environment: dict[str, Any],
) -> bool:
    """Whether the run happened in a materially different environment.

    Unknown on either side counts as no difference: a vector transcribed from a
    document section may not name every library, and that must not turn every
    comparison into a warning.
    """
    for key in _ENVIRONMENT_KEYS:
        expected = vector_environment.get(key)
        actual = run_environment.get(key)
        if expected and actual and str(expected) != str(actual):
            return True
    return False


def format_report(report: RegressionReport) -> str:
    """The comparison as lines for a terminal."""
    lines = [
        f"verdict: {report.verdict}  "
        f"(engine {report.engine}, vector {report.reference_engine} "
        f"measured {report.date})",
        f"evaluation set: {report.evaluation_set.describe()}",
        f"reference: {report.source}",
        "",
        "| Metric | Statistic | Vector | This run | Change | Verdict |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for delta in report.deltas:
        lines.append(
            f"| {delta.label} | {delta.statistic} | {delta.reference:.4f} | "
            f"{delta.current:.4f} | {delta.change:+.4f} | {delta.verdict} |"
        )
    if report.settings_changed:
        lines.append(
            f"\nsettings differ from the vector: {', '.join(report.settings_changed)} -- "
            "this run is not the vector's configuration."
        )
    if report.environment_changed:
        lines.append(
            "the environment differs from the vector's, so this comparison is not "
            "like-for-like: a platform or library change moves these numbers too, "
            "so read the delta as a comparison, not as one engine change."
        )
    neutral = [delta.label for delta in report.deltas if delta.direction == "neutral"]
    if neutral:
        lines.append(
            f"reported, not judged: {', '.join(neutral)} "
            "(a count says what the engine did, not whether it was better)."
        )
    return "\n".join(lines)


def vector_from_aggregate(
    aggregate: dict[str, Any],
    *,
    manifest: GuitarSetManifest,
    source: str,
    notes: str = "",
) -> AccuracyVector:
    """Turn a measured run into a vector, keeping only documented figures.

    Every value comes from the aggregate this run produced -- nothing is
    rounded up, invented or copied from another corpus -- and the evaluation
    set is taken from the manifest that was scored, not typed by hand.
    """
    summary = _block(aggregate, "metrics")
    if not summary:
        raise InputError("this run produced no metrics block to turn into a vector.")
    settings = _block(aggregate, "settings")
    environment = _block(aggregate, "environment")
    metrics: dict[str, MetricReference] = {}
    for name in _DIRECTIONS:
        values = summary.get(name)
        if isinstance(values, dict) and values.get("mean") is not None:
            metrics[name] = MetricReference(
                statistic="mean",
                value=_finite_number(values["mean"], f"metric {name!r} mean", Path("<run>")),
            )
    if not metrics:
        raise InputError("this run reported none of the tracked metrics.")
    takes = int(summary.get("count") or 0)
    if takes <= 0:
        raise InputError("this run scored no takes, so it cannot define a vector.")
    splits = {take.split for take in manifest.takes}
    date = str(aggregate.get("date") or "")[:10]
    return AccuracyVector(
        engine=str(environment.get("engine") or manifest.dataset),
        metric_family="chords",
        evaluation_set=EvaluationSet(
            dataset=manifest.dataset,
            version=manifest.version,
            manifest=str(aggregate.get("manifest") or ""),
            content_digest=manifest.content_digest(),
            takes=takes,
            split=splits.pop() if len(splits) == 1 else "mixed",
            reference=str(settings.get("reference") or ""),
        ),
        metrics=metrics,
        settings={
            key: value
            for key, value in settings.items()
            if key in {"decoder", "change_penalty", "change_window", "engine_options"}
        },
        environment={
            key: str(environment[key])
            for key in _ENVIRONMENT_KEYS
            if environment.get(key) and str(environment[key]) != "not installed"
        },
        date=date,
        source=source,
        notes=notes,
    )


#: The statistic and direction each vector metric publishes, so a generated
#: file reads the way the committed ones do.
def to_document(vector: AccuracyVector) -> dict[str, Any]:
    """The JSON document for a vector, in the committed files' shape."""
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "accuracy_vector",
        "metric_family": vector.metric_family,
        "engine": vector.engine,
        "evaluation_set": {
            "dataset": vector.evaluation_set.dataset,
            "version": vector.evaluation_set.version,
            "manifest": vector.evaluation_set.manifest,
            "content_digest": vector.evaluation_set.content_digest,
            "takes": vector.evaluation_set.takes,
            "split": vector.evaluation_set.split,
            "reference": vector.evaluation_set.reference,
        },
        "settings": vector.settings,
        "metrics": {
            name: {"statistic": metric.statistic, "value": metric.value}
            for name, metric in sorted(vector.metrics.items())
        },
        "environment": vector.environment,
        "date": vector.date,
        "source": vector.source,
        "notes": vector.notes,
    }


def write_vector(vector: AccuracyVector, path: Path) -> None:
    """Write a vector as committed JSON, finite numbers only.

    ``ensure_ascii=False`` keeps the section marks of a ``source`` string
    readable: these files are committed so a person can check a figure against
    the document that measured it.
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(to_document(vector), indent=1, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )
