"""The numeric acceptance bar: what chord recognition has to reach, not where it is.

An accuracy vector records what the engine measured. It cannot say whether that
is *good enough*, and :func:`~benchmark.regression.compare_run` deliberately does
not try: it answers "did this run move the number", which is a question about
direction. ROADMAP §10 proposes the other question -- a CSR of at least 0.70 in
the triad-reduced view, a boundary figure under 0.12 s -- and until now that was
a table in prose with nothing beside it to check the recorded figures against.

This module reads two documents and does the comparison:

* a **bar** (``benchmark/reference/acceptance-bar.json``) -- the targets, one row
  per tracked metric, each naming the statistic it is graded on, plus the rules
  the bar publishes that this check cannot grade and why;
* a **record** -- either a committed accuracy vector or a harness
  ``aggregate.json``, on the same fixed evaluation set the bar pins.

Nothing here measures anything, and nothing here decides the numbers: the bar
carries a ``status`` field, and while it reads ``proposed`` every report says so,
because a target nobody ratified is not a verdict. Ratifying it is the
maintainer's decision (task A0); grading against it is this.

A target is not a measurement. A row marked *met* here means only that a figure
recorded elsewhere is at or above the number in the bar document; the record's
own provenance -- environment, date, corpus digest -- travels with the report.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from song_chord_lyrics_analyzer.benchmark.regression import (
    METRIC_STATISTICS,
    TRACKED_METRICS,
    AccuracyVector,
    EvaluationSet,
    evaluation_set_mismatch,
    parse_evaluation_set,
)
from song_chord_lyrics_analyzer.utils.errors import InputError

__all__ = [
    "AcceptanceBar",
    "BarReport",
    "BarRow",
    "MET",
    "NOT_RECORDED",
    "PROVISIONAL_LABEL",
    "SCHEMA_VERSION",
    "STATUS_PROPOSED",
    "STATUS_RATIFIED",
    "RowOutcome",
    "UNMET",
    "UngradedRule",
    "format_bar_report",
    "grade_run",
    "grade_vector",
    "load_bar",
]

#: The schema this module reads.
SCHEMA_VERSION = "1"

#: The document ``kind``, so a vector and a bar cannot be handed to each other.
BAR_KIND = "acceptance_bar"

#: The two states the bar document may be in. ``proposed`` means the numbers were
#: written down and not agreed; ``ratified`` means a maintainer agreed them and
#: recorded the date.
STATUS_PROPOSED = "proposed"
STATUS_RATIFIED = "ratified"
_STATUSES = (STATUS_PROPOSED, STATUS_RATIFIED)

#: The comparators a row may use. A bar row is one-sided on purpose: "CSR at
#: least 0.70" and "boundary error at most 0.12 s" are the two shapes the
#: proposed table contains.
COMPARATOR_HIGHER = ">="
COMPARATOR_LOWER = "<="
_COMPARATORS = (COMPARATOR_HIGHER, COMPARATOR_LOWER)

#: Verdicts. ``not recorded`` is kept distinct from ``unmet`` because an absent
#: figure is a gap in the record, not a failure of the engine, and the two lead
#: to different work.
MET = "met"
UNMET = "unmet"
NOT_RECORDED = "not recorded"

#: How a proposed bar is labelled in every report, so it cannot be quoted as the
#: project's acceptance criteria by accident.
PROVISIONAL_LABEL = "PROPOSED (not ratified)"

_TARGET_FIELDS = ("metric", "statistic", "comparator", "target", "label", "guards")


@dataclass(frozen=True)
class BarRow:
    """One target: a metric, the statistic it is graded on and the number."""

    metric: str
    statistic: str
    comparator: str
    target: float
    label: str
    guards: str
    note: str = ""
    required: bool = True


@dataclass(frozen=True)
class UngradedRule:
    """A rule the bar publishes that this check does not grade, and why not."""

    name: str
    rule: str
    why: str
    where: str
    value_note: str = ""


@dataclass(frozen=True)
class AcceptanceBar:
    """The committed targets, the set they apply to and their ratification state."""

    status: str
    proposed_date: str
    title: str
    metric_family: str
    evaluation_set: EvaluationSet
    rows: tuple[BarRow, ...]
    ungraded: tuple[UngradedRule, ...]
    notes: str = ""
    ratified_date: str = ""


@dataclass(frozen=True)
class RowOutcome:
    """One bar row against one record: the figure, the gap and the verdict."""

    metric: str
    label: str
    statistic: str
    comparator: str
    target: float
    guards: str
    required: bool
    verdict: str
    reason: str
    recorded: float | None = None
    margin: float | None = None
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        """A JSON-safe record of one row."""
        return {
            "metric": self.metric,
            "label": self.label,
            "statistic": self.statistic,
            "comparator": self.comparator,
            "target": self.target,
            "recorded": self.recorded,
            "margin": self.margin,
            "verdict": self.verdict,
            "reason": self.reason,
            "required": self.required,
            "guards": self.guards,
            "note": self.note,
        }


@dataclass(frozen=True)
class BarReport:
    """The bar graded against one record, with that record's provenance."""

    bar_status: str
    bar_proposed_date: str
    bar_ratified_date: str
    title: str
    evaluation_set: EvaluationSet
    engine: str
    date: str
    record_label: str
    source: str
    outcomes: tuple[RowOutcome, ...]
    ungraded: tuple[UngradedRule, ...]
    notes: str = ""

    @property
    def met_count(self) -> int:
        """Rows at or beyond their target."""
        return sum(1 for row in self.outcomes if row.verdict == MET)

    @property
    def unmet_count(self) -> int:
        """Rows recorded and below their target."""
        return sum(1 for row in self.outcomes if row.verdict == UNMET)

    @property
    def not_recorded_count(self) -> int:
        """Rows the record does not carry, so nothing was decided about them."""
        return sum(1 for row in self.outcomes if row.verdict == NOT_RECORDED)

    @property
    def required_outstanding(self) -> int:
        """Required rows that are not met -- unmet and unrecorded both count."""
        return sum(1 for row in self.outcomes if row.required and row.verdict != MET)

    @property
    def complete(self) -> bool:
        """Whether every row could be graded at all."""
        return self.not_recorded_count == 0

    @property
    def bar_met(self) -> bool:
        """Whether the record reaches the bar: every required row met."""
        return all(row.verdict == MET for row in self.outcomes if row.required)

    def to_dict(self) -> dict[str, Any]:
        """A JSON-safe record of the whole check."""
        return {
            "schema_version": SCHEMA_VERSION,
            "kind": "acceptance_check",
            "title": self.title,
            "bar_status": self.bar_status,
            "bar_proposed_date": self.bar_proposed_date,
            "bar_ratified_date": self.bar_ratified_date,
            "evaluation_set": {
                "dataset": self.evaluation_set.dataset,
                "version": self.evaluation_set.version,
                "manifest": self.evaluation_set.manifest,
                "content_digest": self.evaluation_set.content_digest,
                "takes": self.evaluation_set.takes,
                "split": self.evaluation_set.split,
                "reference": self.evaluation_set.reference,
            },
            "record": {
                "engine": self.engine,
                "date": self.date,
                "label": self.record_label,
                "source": self.source,
            },
            "summary": {
                "met": self.met_count,
                "unmet": self.unmet_count,
                "not_recorded": self.not_recorded_count,
                "required_outstanding": self.required_outstanding,
                "bar_met": self.bar_met,
            },
            "rows": [row.to_dict() for row in self.outcomes],
            "ungraded": [
                {
                    "name": rule.name,
                    "rule": rule.rule,
                    "why": rule.why,
                    "where": rule.where,
                    "value_note": rule.value_note,
                }
                for rule in self.ungraded
            ],
            "notes": self.notes,
        }


def _text(document: dict[str, Any], field_name: str, source: Path) -> str:
    """A required non-empty string, or a refusal naming the file and field."""
    value = document.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise InputError(f"{source}: {field_name!r} must be a non-empty string.")
    return value


def _number(value: Any, label: str, source: Path) -> float:
    """A finite number. A string target would silently never be met."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InputError(f"{source}: {label} must be a number.")
    number = float(value)
    if not math.isfinite(number):
        raise InputError(f"{source}: {label} must be a finite number, got {value!r}.")
    return number


def _row(document: Any, source: Path, index: int) -> BarRow:
    """One row of the bar document, with every field the table needs."""
    if not isinstance(document, dict):
        raise InputError(f"{source}: row {index} must be an object.")
    raw: dict[str, Any] = document
    missing = [field for field in _TARGET_FIELDS if field not in raw]
    if missing:
        raise InputError(f"{source}: row {index} is missing {', '.join(missing)}.")
    metric = _text(raw, "metric", source)
    if metric not in TRACKED_METRICS:
        raise InputError(
            f"{source}: row {index} sets a target for unknown metric {metric!r}.",
            hint=f"The harness reports: {', '.join(sorted(TRACKED_METRICS))}.",
        )
    statistic = _text(raw, "statistic", source)
    if statistic not in METRIC_STATISTICS:
        raise InputError(
            f"{source}: row {index} has statistic {statistic!r}.",
            hint=f"Use one of: {', '.join(METRIC_STATISTICS)}.",
        )
    comparator = _text(raw, "comparator", source)
    if comparator not in _COMPARATORS:
        raise InputError(
            f"{source}: row {index} has comparator {comparator!r}.",
            hint=f"Use {COMPARATOR_HIGHER!r} (higher is better) or {COMPARATOR_LOWER!r}.",
        )
    required = raw.get("required", True)
    if not isinstance(required, bool):
        raise InputError(f"{source}: row {index} 'required' must be true or false.")
    return BarRow(
        metric=metric,
        statistic=statistic,
        comparator=comparator,
        target=_number(raw.get("target"), f"row {index} 'target'", source),
        label=_text(raw, "label", source),
        guards=_text(raw, "guards", source),
        note=str(raw.get("note") or ""),
        required=required,
    )


def _ungraded(document: Any, source: Path, index: int) -> UngradedRule:
    """One of the rules this check hands back as ungraded."""
    if not isinstance(document, dict):
        raise InputError(f"{source}: ungraded rule {index} must be an object.")
    raw: dict[str, Any] = document
    return UngradedRule(
        name=_text(raw, "name", source),
        rule=_text(raw, "rule", source),
        why=_text(raw, "why", source),
        where=_text(raw, "where", source),
        value_note=str(raw.get("value_note") or ""),
    )


def load_bar(path: Path) -> AcceptanceBar:
    """Read a committed acceptance bar.

    Raises:
        InputError: When the file cannot be read, is not JSON or an object, is
            not a bar of the schema this module reads, carries a status outside
            ``proposed`` and ``ratified``, ratifies itself without a date, names
            an unknown metric, statistic or comparator, holds a non-finite
            target, repeats a metric in two rows, or pins no evaluation set.
    """
    source = Path(path)
    try:
        text = source.read_text(encoding="utf-8")
    except FileNotFoundError as error:
        raise InputError(
            f"{source}: no acceptance bar found.",
            hint="The committed bar is benchmark/reference/acceptance-bar.json; "
            "point --bar at it, or at a proposed replacement.",
        ) from error
    except OSError as error:
        raise InputError(f"{source}: the acceptance bar cannot be read: {error}") from error
    try:
        document = json.loads(text)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise InputError(f"{source} is not valid JSON: {error}") from error
    if not isinstance(document, dict):
        raise InputError(f"{source}: the acceptance bar must be a JSON object.")

    schema = _text(document, "schema_version", source)
    if schema != SCHEMA_VERSION:
        raise InputError(
            f"{source}: acceptance bar schema {schema!r} is not {SCHEMA_VERSION!r}.",
            hint="Update the document, or read it with the schema it declares.",
        )
    if _text(document, "kind", source) != BAR_KIND:
        raise InputError(
            f"{source}: not an acceptance bar (check the 'kind' field).",
            hint="An accuracy vector is a different document; --vector reads it.",
        )
    status = _text(document, "status", source)
    if status not in _STATUSES:
        raise InputError(
            f"{source}: unknown bar status {status!r}.",
            hint=f"Use {STATUS_PROPOSED!r} until a maintainer agrees the numbers, "
            f"then {STATUS_RATIFIED!r} with a ratified_date.",
        )
    ratified_date = str(document.get("ratified_date") or "")
    if status == STATUS_RATIFIED and not ratified_date.strip():
        raise InputError(
            f"{source}: a {STATUS_RATIFIED} bar must carry a ratified_date.",
            hint="A bar cannot be ratified by being called ratified; the date is the claim.",
        )

    rows_document = document.get("rows")
    if not isinstance(rows_document, list) or not rows_document:
        raise InputError(f"{source}: 'rows' must be a non-empty list.")
    rows = tuple(_row(raw, source, index) for index, raw in enumerate(rows_document, start=1))
    seen: set[str] = set()
    for row in rows:
        if row.metric in seen:
            raise InputError(
                f"{source}: {row.metric!r} appears in the bar twice.",
                hint="One target per metric: two rows would make the verdict ambiguous.",
            )
        seen.add(row.metric)

    ungraded_document = document.get("ungraded") or []
    if not isinstance(ungraded_document, list):
        raise InputError(f"{source}: 'ungraded' must be a list.")
    ungraded = tuple(
        _ungraded(raw, source, index) for index, raw in enumerate(ungraded_document, start=1)
    )

    return AcceptanceBar(
        status=status,
        proposed_date=_text(document, "proposed_date", source),
        title=_text(document, "title", source),
        metric_family=_text(document, "metric_family", source),
        evaluation_set=parse_evaluation_set(document.get("evaluation_set"), source),
        rows=rows,
        ungraded=ungraded,
        notes=str(document.get("notes") or ""),
        ratified_date=ratified_date,
    )


def _set_differences(expected: EvaluationSet, actual: EvaluationSet) -> list[str]:
    """Why a recorded set is not the set the bar pins."""
    problems: list[str] = []
    if actual.content_digest != expected.content_digest:
        problems.append(
            f"the manifest content digest differs "
            f"(record {actual.content_digest[:12]}…, bar {expected.content_digest[:12]}…)"
        )
    if actual.takes != expected.takes:
        problems.append(f"the record scores {actual.takes} takes, the bar pins {expected.takes}")
    if actual.reference != expected.reference:
        problems.append(
            f"the record uses the {actual.reference!r} annotation, "
            f"the bar uses {expected.reference!r}"
        )
    if (actual.dataset, actual.version) != (expected.dataset, expected.version):
        problems.append(
            f"the record is {actual.dataset} {actual.version}, "
            f"the bar is {expected.dataset} {expected.version}"
        )
    if actual.split != expected.split:
        problems.append(f"the record splits {actual.split!r}, the bar splits {expected.split!r}")
    return problems


def _require_same_set(bar: AcceptanceBar, problems: list[str]) -> None:
    """Refuse a bar/record pair that did not measure the same thing."""
    if not problems:
        return
    raise InputError(
        f"This record was not measured on the bar's fixed evaluation set "
        f"({bar.evaluation_set.describe()}).",
        hint="Not comparable: "
        + "; ".join(problems)
        + ". Grade against the bar of the set this record belongs to, "
        "or re-run over the pinned set.",
    )


def _values_or_none(metrics: dict[str, Any], row: BarRow, source: Path) -> float | None:
    """The figure one row asks for, or ``None`` when the record does not carry it."""
    entry = metrics.get(row.metric)
    if not isinstance(entry, dict):
        return None
    value = entry.get(row.statistic)
    if value is None:
        return None
    return _number(value, f"metric {row.metric!r} {row.statistic!r}", source)


def _grade_row(row: BarRow, recorded: float | None, reason: str) -> RowOutcome:
    """Compare one figure with one target, in the target's direction."""
    if recorded is None:
        return RowOutcome(
            metric=row.metric,
            label=row.label,
            statistic=row.statistic,
            comparator=row.comparator,
            target=row.target,
            guards=row.guards,
            required=row.required,
            note=row.note,
            verdict=NOT_RECORDED,
            reason=reason
            or "the record does not carry a figure for this metric, so nothing is decided",
        )
    margin = recorded - row.target if row.comparator == COMPARATOR_HIGHER else row.target - recorded
    asked = "at least" if row.comparator == COMPARATOR_HIGHER else "at most"
    return RowOutcome(
        metric=row.metric,
        label=row.label,
        statistic=row.statistic,
        comparator=row.comparator,
        target=row.target,
        guards=row.guards,
        required=row.required,
        note=row.note,
        verdict=MET if margin >= 0.0 else UNMET,
        reason=f"{asked} {row.target:.4f} was asked for",
        recorded=recorded,
        margin=margin,
    )


def _missing_statistic_reason(metrics: dict[str, Any], row: BarRow) -> str:
    """Say *why* a row has no figure: absent metric, or a different statistic."""
    entry = metrics.get(row.metric)
    if not isinstance(entry, dict):
        return ""
    published = sorted(str(key) for key, value in entry.items() if isinstance(value, (int, float)))
    if not published:
        return ""
    return (
        f"the record does not carry a {row.metric!r} {row.statistic!r}: it was recorded as "
        f"{', '.join(published)}. A target is graded on the statistic it names; "
        "the other figure is a different number."
    )


def _report(
    bar: AcceptanceBar,
    metrics: dict[str, Any],
    *,
    engine: str,
    date: str,
    record_label: str,
    source: str,
    path: Path,
) -> BarReport:
    """Grade every row of the bar against one record."""
    if not any(row.metric in metrics for row in bar.rows):
        raise InputError(
            f"{record_label} reports none of the metrics the bar targets.",
            hint="Tracked metrics: " + ", ".join(sorted(row.metric for row in bar.rows)) + ".",
        )
    outcomes = tuple(
        _grade_row(
            row, _values_or_none(metrics, row, path), _missing_statistic_reason(metrics, row)
        )
        for row in bar.rows
    )
    return BarReport(
        bar_status=bar.status,
        bar_proposed_date=bar.proposed_date,
        bar_ratified_date=bar.ratified_date,
        title=bar.title,
        evaluation_set=bar.evaluation_set,
        engine=engine,
        date=date,
        record_label=record_label,
        source=source,
        outcomes=outcomes,
        ungraded=bar.ungraded,
        notes=bar.notes,
    )


def grade_vector(bar: AcceptanceBar, vector: AccuracyVector) -> BarReport:
    """Grade a committed accuracy vector against the bar.

    This is the check that needs no corpus and no engine: both sides are
    documents already in the repository. It says where the *recorded* figures
    stand, not where the engine stands today.

    Raises:
        InputError: When the vector was measured on a different evaluation set
            than the bar pins, or reports none of the targeted metrics.
    """
    _require_same_set(bar, _set_differences(bar.evaluation_set, vector.evaluation_set))
    metrics = {
        name: {reference.statistic: reference.value} for name, reference in vector.metrics.items()
    }
    return _report(
        bar,
        metrics,
        engine=vector.engine,
        date=vector.date,
        record_label=f"vector of {vector.date}",
        source=vector.source,
        path=Path("<vector>"),
    )


def grade_run(bar: AcceptanceBar, aggregate: dict[str, Any]) -> BarReport:
    """Grade a harness ``aggregate.json`` against the bar.

    Every statistic the run published is available here, so a row can be graded
    on the median as well as the mean -- which is how the boundary row becomes
    gradeable at all, since §8's column never named its statistic.

    Raises:
        InputError: When the run was not measured on the bar's evaluation set,
            or reports none of the targeted metrics.
    """
    if not isinstance(aggregate, dict):
        raise InputError("the run record must be an object.")
    _require_same_set(bar, evaluation_set_mismatch(bar.evaluation_set, aggregate, pinned_by="bar"))
    metrics = aggregate.get("metrics")
    if not isinstance(metrics, dict):
        raise InputError("the run record has no 'metrics' block to grade.")
    environment = aggregate.get("environment")
    date = str(aggregate.get("date") or "")[:10]
    return _report(
        bar,
        metrics,
        engine=str(environment.get("engine") or "") if isinstance(environment, dict) else "",
        date=date,
        record_label=f"run of {date}" if date else "this run",
        source=str(aggregate.get("manifest") or ""),
        path=Path("<run>"),
    )


def _status_line(report: BarReport) -> str:
    """The one line that says what kind of number this bar is."""
    if report.bar_status == STATUS_RATIFIED:
        return f"ratified {report.bar_ratified_date}"
    return f"{PROVISIONAL_LABEL}, proposed {report.bar_proposed_date}"


def format_bar_report(report: BarReport) -> str:
    """The check as lines for a terminal or a document section."""
    lines = [
        report.title,
        f"bar: {_status_line(report)}",
        f"evaluation set: {report.evaluation_set.describe()}",
        f"graded against: {report.record_label} (engine {report.engine})",
        f"record source: {report.source}",
        "",
        "| Measure | Statistic | Bar | Recorded | Margin | Verdict |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in report.outcomes:
        recorded = "--" if row.recorded is None else f"{row.recorded:.4f}"
        margin = "--" if row.margin is None else f"{row.margin:+.4f}"
        lines.append(
            f"| {row.label} | {row.statistic} | {row.comparator} {row.target:.4f} | "
            f"{recorded} | {margin} | {row.verdict} |"
        )
    lines.append("")
    lines.append(
        f"met {report.met_count}, unmet {report.unmet_count}, "
        f"not recorded {report.not_recorded_count}; "
        f"{'the bar is reached' if report.bar_met else 'the bar is NOT reached'} "
        f"({report.required_outstanding} required row(s) outstanding)."
    )
    unrecorded = [row for row in report.outcomes if row.verdict == NOT_RECORDED]
    for row in unrecorded:
        lines.append(f"  - {row.label}: {row.reason}")
    if report.ungraded:
        lines.append("")
        lines.append("Rules the bar publishes that are not graded by this check:")
        for rule in report.ungraded:
            lines.append(f"  - {rule.name}: {rule.rule}")
            lines.append(f"      why: {rule.why}")
            lines.append(f"      where: {rule.where}")
            if rule.value_note:
                lines.append(f"      recorded: {rule.value_note}")
    if report.notes:
        lines.append("")
        lines.append(report.notes)
    return "\n".join(lines)
