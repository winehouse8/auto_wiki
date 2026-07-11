#!/usr/bin/env python3
"""Deterministic, read-only memory hygiene observations for Living Wiki.

This module reads configuration and canonical state snapshots supplied by a
caller.  It reports review-due ("stale") claims, inactive lifecycle records,
metadata-only sources, and unresolved harmful/irrelevant feedback.  It never
changes a trust level, lifecycle status, source, claim, or file.

Staleness is an age-based review warning.  It is not evidence that a claim is
false, obsolete, deprecated, or less mature.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

try:  # Package import in tests and library use.
    from tools import memory_feedback as feedback_schema
except ImportError:  # Direct execution as python3 tools/memory_hygiene.py.
    import memory_feedback as feedback_schema  # type: ignore[no-redef]


SCHEMA_VERSION = "living-wiki-memory-hygiene-report/v1"
SECONDS_PER_DAY = 86_400
ACTIVE_STATUS = "active"
INACTIVE_STATUSES = frozenset({"deprecated", "superseded", "invalidated", "archived"})
LIFECYCLE_STATUSES = frozenset({ACTIVE_STATUS, *INACTIVE_STATUSES})
CONCERNING_OUTCOMES = frozenset({"harmful", "irrelevant"})
FEEDBACK_OUTCOMES = ("helpful", "harmful", "irrelevant", "unknown")
FEEDBACK_STATUSES = frozenset({"open", "resolved"})


class MemoryHygieneError(ValueError):
    """Raised for malformed inputs that make a deterministic report unsafe."""


def canonical_json(value: Any, *, pretty: bool = False) -> str:
    """Return environment-independent JSON with stable key ordering."""

    if pretty:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value: Any) -> str:
    text = value if isinstance(value, str) else canonical_json(value)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def parse_time(value: str | dt.datetime, *, field: str = "timestamp") -> dt.datetime:
    """Parse an ISO-8601 timestamp and require an explicit UTC offset."""

    if isinstance(value, dt.datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        normalized = value.strip()
        if normalized.endswith("Z"):
            normalized = normalized[:-1] + "+00:00"
        try:
            parsed = dt.datetime.fromisoformat(normalized)
        except ValueError as exc:
            raise MemoryHygieneError(f"{field} must be a valid ISO-8601 timestamp") from exc
    else:
        raise MemoryHygieneError(f"{field} must be a non-empty ISO-8601 timestamp")
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise MemoryHygieneError(f"{field} must include an explicit UTC offset")
    return parsed.astimezone(dt.timezone.utc)


def iso_time(value: str | dt.datetime, *, field: str = "timestamp") -> str:
    return parse_time(value, field=field).replace(microsecond=0).isoformat()


def _records(value: Sequence[Mapping[str, Any]], *, label: str) -> list[Mapping[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise MemoryHygieneError(f"{label} must be a list")
    records: list[Mapping[str, Any]] = []
    seen: set[str] = set()
    for number, item in enumerate(value, 1):
        if not isinstance(item, Mapping):
            raise MemoryHygieneError(f"{label}[{number}] must be an object")
        record_id = item.get("id")
        if not isinstance(record_id, str) or not record_id.strip():
            raise MemoryHygieneError(f"{label}[{number}] requires a non-empty id")
        if record_id in seen:
            raise MemoryHygieneError(f"duplicate {label} id: {record_id}")
        seen.add(record_id)
        records.append(item)
    return records


def freshness_thresholds(config: Mapping[str, Any]) -> dict[str, int | None]:
    """Validate producer-configured freshness classes without inventing defaults."""

    if not isinstance(config, Mapping):
        raise MemoryHygieneError("config must be an object")
    raw = config.get("staleness_days")
    if not isinstance(raw, Mapping) or not raw:
        raise MemoryHygieneError("config.staleness_days must be a non-empty object")
    result: dict[str, int | None] = {}
    for name in sorted(raw):
        if not isinstance(name, str) or not name.strip():
            raise MemoryHygieneError("freshness class names must be non-empty strings")
        value = raw[name]
        if value is None:
            result[name] = None
            continue
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise MemoryHygieneError(f"staleness_days.{name} must be a non-negative integer or null")
        result[name] = value
    return result


def lifecycle_status(record: Mapping[str, Any], *, kind: str) -> str:
    """Read additive lifecycle spellings while never using confidence.status.

    The v4 ledger already stores ``source.status``.  v4.1 producers may use a
    top-level ``lifecycle_status`` or a ``lifecycle.status`` object.  Claims
    without an explicit lifecycle remain active for backward compatibility.
    """

    nested = record.get("lifecycle")
    candidates = [record.get("lifecycle_status")]
    if isinstance(nested, Mapping):
        candidates.append(nested.get("status"))
    if kind in {"claim", "source"}:
        candidates.append(record.get("status"))
    for candidate in candidates:
        if candidate is None:
            continue
        if not isinstance(candidate, str) or candidate not in LIFECYCLE_STATUSES:
            raise MemoryHygieneError(
                f"{kind} {record.get('id')}: lifecycle status must be one of "
                + ", ".join(sorted(LIFECYCLE_STATUSES))
            )
        return candidate
    return ACTIVE_STATUS


def _replacement_ids(record: Mapping[str, Any]) -> list[str]:
    nested = record.get("lifecycle") if isinstance(record.get("lifecycle"), Mapping) else {}
    values: list[Any] = []
    for container in (nested, record):
        for field in ("replaced_by", "replacement_id", "superseded_by"):
            if container.get(field) is not None:
                value = container.get(field)
                if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
                    values.extend(value)
                else:
                    values.append(value)
        for field in ("replacement_ids", "superseded_by_ids"):
            item = container.get(field)
            if isinstance(item, Sequence) and not isinstance(item, (str, bytes)):
                values.extend(item)
    return sorted({value.strip() for value in values if isinstance(value, str) and value.strip()})


def freshness_reference(claim: Mapping[str, Any]) -> tuple[str, Any] | None:
    """Return the first present timestamp using the RFC-defined precedence."""

    candidates = (
        ("last_verified_at", claim.get("last_verified_at")),
        (
            "confidence.computed_at",
            claim.get("confidence", {}).get("computed_at")
            if isinstance(claim.get("confidence"), Mapping)
            else None,
        ),
        ("created_at", claim.get("created_at")),
    )
    for field, value in candidates:
        if isinstance(value, dt.datetime):
            return field, iso_time(value, field=field)
        if isinstance(value, str):
            if value.strip():
                return field, value
            continue
        if value is not None:
            return field, value
    return None


def evaluate_staleness(
    claims: Sequence[Mapping[str, Any]],
    *,
    thresholds: Mapping[str, int | None],
    now: str | dt.datetime,
) -> dict[str, Any]:
    """Return review-due claims without changing their truth or lifecycle."""

    now_value = parse_time(now, field="now")
    stale: list[dict[str, Any]] = []
    unassessable: list[dict[str, str]] = []
    future_references: list[dict[str, str]] = []
    timeless: list[str] = []
    assessed = 0
    for claim in sorted(claims, key=lambda item: str(item.get("id", ""))):
        claim_id = str(claim["id"])
        freshness = claim.get("freshness")
        if not isinstance(freshness, str) or freshness not in thresholds:
            unassessable.append(
                {"id": claim_id, "reason": "unconfigured_or_missing_freshness_class"}
            )
            continue
        threshold = thresholds[freshness]
        if threshold is None:
            timeless.append(claim_id)
            continue
        reference = freshness_reference(claim)
        if reference is None:
            unassessable.append({"id": claim_id, "reason": "missing_reference_timestamp"})
            continue
        reference_field, raw_reference = reference
        try:
            reference_at = parse_time(raw_reference, field=f"{claim_id}.{reference_field}")
        except MemoryHygieneError:
            unassessable.append(
                {
                    "id": claim_id,
                    "reason": "invalid_or_timezone_free_reference_timestamp",
                    "reference_field": reference_field,
                }
            )
            continue
        if reference_at > now_value:
            future_references.append(
                {
                    "id": claim_id,
                    "reference_field": reference_field,
                    "reference_at": reference_at.replace(microsecond=0).isoformat(),
                }
            )
            continue
        assessed += 1
        due_at = reference_at + dt.timedelta(days=threshold)
        if now_value < due_at:
            continue
        age_days = round((now_value - reference_at).total_seconds() / SECONDS_PER_DAY, 6)
        stale.append(
            {
                "id": claim_id,
                "freshness": freshness,
                "threshold_days": threshold,
                "age_days": age_days,
                "reference_field": reference_field,
                "reference_at": reference_at.replace(microsecond=0).isoformat(),
                "review_due_at": due_at.replace(microsecond=0).isoformat(),
                "lifecycle_status": lifecycle_status(claim, kind="claim"),
                "severity": "warning",
                "meaning": "review_due_not_falsehood",
            }
        )
    return {
        "semantics": "Stale means age-based review is due; it does not mean false, obsolete, deprecated, or lower-confidence.",
        "thresholds_days": {key: thresholds[key] for key in sorted(thresholds)},
        "assessed_claims": assessed,
        "stale_count": len(stale),
        "active_stale_count": sum(item["lifecycle_status"] == ACTIVE_STATUS for item in stale),
        "stale_claims": stale,
        "timeless_claim_ids": sorted(timeless),
        "unassessable_claims": sorted(unassessable, key=lambda item: item["id"]),
        "future_reference_claims": sorted(future_references, key=lambda item: item["id"]),
    }


def evaluate_lifecycle(
    claims: Sequence[Mapping[str, Any]], sources: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    """Summarize lifecycle state; no transition is performed."""

    def one_kind(items: Sequence[Mapping[str, Any]], kind: str) -> dict[str, Any]:
        counts = {status: 0 for status in sorted(LIFECYCLE_STATUSES)}
        inactive: list[dict[str, Any]] = []
        issues: list[dict[str, str]] = []
        for item in sorted(items, key=lambda value: str(value.get("id", ""))):
            status = lifecycle_status(item, kind=kind)
            counts[status] += 1
            if status in INACTIVE_STATUSES:
                replacements = _replacement_ids(item)
                inactive.append(
                    {
                        "id": item["id"],
                        "status": status,
                        "replacement_ids": replacements,
                    }
                )
                if status == "superseded" and not replacements:
                    issues.append({"id": str(item["id"]), "reason": "superseded_missing_replaced_by"})
        return {
            "counts": counts,
            "inactive_count": len(inactive),
            f"inactive_{kind}s": inactive,
            "issues": issues,
        }

    return {"claims": one_kind(claims, "claim"), "sources": one_kind(sources, "source")}


def evaluate_sources(sources: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """List sources without an immutable artifact record."""

    metadata_only: list[dict[str, str]] = []
    for source in sorted(sources, key=lambda item: str(item.get("id", ""))):
        artifact = source.get("artifact")
        if not isinstance(artifact, Mapping) or not artifact.get("path") or not artifact.get("sha256"):
            metadata_only.append(
                {"id": str(source["id"]), "lifecycle_status": lifecycle_status(source, kind="source")}
            )
    return {
        "source_count": len(sources),
        "artifact_backed_count": len(sources) - len(metadata_only),
        "metadata_only_count": len(metadata_only),
        "metadata_only_sources": metadata_only,
        "semantics": "Metadata-only is a preservation warning, not a source credibility or truth judgment.",
    }


def _feedback_records(
    payload: Mapping[str, Any] | None,
) -> tuple[list[Mapping[str, Any]], bool]:
    if payload is None:
        return [], False
    try:
        feedback_schema.validate_feedback_collection(payload)
    except feedback_schema.MemoryFeedbackError as exc:
        raise MemoryHygieneError(f"invalid canonical memory feedback ledger: {exc}") from exc
    value = payload.get("feedback")
    return _records(value, label="feedback"), True


def _feedback_resolved(item: Mapping[str, Any]) -> bool:
    return item.get("status") == "resolved"


def _target_ids(item: Mapping[str, Any]) -> list[str]:
    targets = item.get("targets")
    if not isinstance(targets, list) or any(
        not isinstance(value, str) or not value.strip() for value in targets
    ):
        raise MemoryHygieneError(f"feedback {item.get('id')}: targets must be a list of non-empty strings")
    return sorted({value.strip() for value in targets})


def _validate_feedback(item: Mapping[str, Any]) -> None:
    try:
        feedback_schema.validate_retrieval_feedback(item)
    except feedback_schema.MemoryFeedbackError as exc:
        raise MemoryHygieneError(f"feedback {item.get('id')}: {exc}") from exc


def evaluate_feedback(
    payload: Mapping[str, Any] | None,
    *,
    known_target_ids: set[str],
) -> dict[str, Any]:
    """Aggregate privacy-minimal feedback; content and raw queries are omitted."""

    records, present = _feedback_records(payload)
    counts: dict[str, int] = {outcome: 0 for outcome in FEEDBACK_OUTCOMES}
    unresolved_feedback: list[dict[str, Any]] = []
    unresolved_targets: set[str] = set()
    unknown_targets: set[str] = set()
    issues: list[dict[str, str]] = []
    resolved_count = 0
    for item in sorted(records, key=lambda value: str(value.get("id", ""))):
        _validate_feedback(item)
        feedback_id = str(item["id"])
        normalized_outcome = str(item["outcome"])
        counts[normalized_outcome] = counts.get(normalized_outcome, 0) + 1
        targets = _target_ids(item)
        unknown_targets.update(target for target in targets if target not in known_target_ids)
        resolved = _feedback_resolved(item)
        if resolved:
            resolved_count += 1
        if normalized_outcome in CONCERNING_OUTCOMES and not resolved:
            if not targets:
                issues.append({"id": feedback_id, "reason": "concerning_feedback_missing_target"})
            unresolved_feedback.append(
                {"feedback_id": feedback_id, "outcome": normalized_outcome, "target_ids": targets}
            )
            unresolved_targets.update(targets)
    return {
        "present": present,
        "feedback_count": len(records),
        "outcome_counts": {key: counts[key] for key in sorted(counts)},
        "resolved_count": resolved_count,
        "unresolved_concerning_count": len(unresolved_feedback),
        "unresolved_concerning_feedback": unresolved_feedback,
        "unresolved_harmful_or_irrelevant_target_ids": sorted(unresolved_targets),
        "unknown_target_ids": sorted(unknown_targets),
        "issues": sorted(issues, key=lambda item: (item["id"], item["reason"])),
        "privacy": "Only feedback IDs, outcomes, and target IDs are projected; raw queries and free text are omitted.",
        "policy_effect": "audit_only_no_ranking_trust_lifecycle_or_deletion_effect",
    }


def build_report(
    *,
    config: Mapping[str, Any],
    claims: Sequence[Mapping[str, Any]],
    sources: Sequence[Mapping[str, Any]],
    feedback: Mapping[str, Any] | None = None,
    now: str | dt.datetime,
) -> dict[str, Any]:
    """Build a deterministic report from in-memory snapshots without mutation."""

    thresholds = freshness_thresholds(config)
    claim_records = _records(claims, label="claims")
    source_records = _records(sources, label="sources")
    feedback_records, feedback_present = _feedback_records(feedback)
    # Re-wrap the validated feedback to avoid a second ambiguous schema read.
    feedback_value: Mapping[str, Any] | None = (
        {"version": 1, "feedback": feedback_records} if feedback_present else None
    )
    known_ids = {str(item["id"]) for item in claim_records + source_records}
    staleness = evaluate_staleness(claim_records, thresholds=thresholds, now=now)
    lifecycle = evaluate_lifecycle(claim_records, source_records)
    preservation = evaluate_sources(source_records)
    feedback_result = evaluate_feedback(feedback_value, known_target_ids=known_ids)
    as_of = iso_time(now, field="now")
    return {
        "schema_version": SCHEMA_VERSION,
        "report_type": "memory_hygiene_observation",
        "as_of": as_of,
        "input_fingerprints": {
            "config_sha256": digest(config),
            "claims_sha256": digest(list(claim_records)),
            "sources_sha256": digest(list(source_records)),
            "feedback_sha256": digest(feedback_records) if feedback_present else None,
        },
        "summary": {
            "claims": len(claim_records),
            "sources": len(source_records),
            "stale_claims": staleness["stale_count"],
            "active_stale_claims": staleness["active_stale_count"],
            "unassessable_claims": len(staleness["unassessable_claims"]),
            "future_reference_claims": len(staleness["future_reference_claims"]),
            "inactive_claims": lifecycle["claims"]["inactive_count"],
            "inactive_sources": lifecycle["sources"]["inactive_count"],
            "metadata_only_sources": preservation["metadata_only_count"],
            "feedback": feedback_result["feedback_count"],
            "unresolved_harmful_or_irrelevant_targets": len(
                feedback_result["unresolved_harmful_or_irrelevant_target_ids"]
            ),
        },
        "staleness": staleness,
        "lifecycle": lifecycle,
        "preservation": preservation,
        "feedback": feedback_result,
        "invariants": {
            "read_only": True,
            "trust_mutated": False,
            "lifecycle_mutated": False,
            "status_mutated": False,
            "content_deleted": False,
            "staleness_changes_truth_value": False,
            "staleness_changes_confidence": False,
            "feedback_changes_ranking_or_trust": False,
            "host_paths_included": False,
            "wall_clock_used": False,
        },
    }


def _load_object(path: Path, *, label: str, optional: bool = False) -> Mapping[str, Any] | None:
    if optional and not path.exists():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise MemoryHygieneError(f"missing required input: {label}") from exc
    except OSError as exc:
        raise MemoryHygieneError(f"cannot read {label}: {type(exc).__name__}") from exc
    except json.JSONDecodeError as exc:
        raise MemoryHygieneError(f"invalid JSON in {label} at line {exc.lineno}") from exc
    if not isinstance(value, Mapping):
        raise MemoryHygieneError(f"{label} must contain a JSON object")
    return value


def evaluate_repository(root: Path | str, *, now: str | dt.datetime) -> dict[str, Any]:
    """Read the four repository inputs and return a path-free report."""

    base = Path(root)
    config = _load_object(base / "config" / "wiki.json", label="config/wiki.json")
    claims_payload = _load_object(base / "state" / "claims.json", label="state/claims.json")
    sources_payload = _load_object(base / "state" / "sources.json", label="state/sources.json")
    feedback = _load_object(
        base / "state" / "memory_feedback.json",
        label="state/memory_feedback.json",
        optional=True,
    )
    assert config is not None and claims_payload is not None and sources_payload is not None
    claims = claims_payload.get("claims")
    sources = sources_payload.get("sources")
    if not isinstance(claims, list):
        raise MemoryHygieneError("state/claims.json must contain a claims list")
    if not isinstance(sources, list):
        raise MemoryHygieneError("state/sources.json must contain a sources list")
    return build_report(config=config, claims=claims, sources=sources, feedback=feedback, now=now)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Deterministic read-only Living Wiki memory hygiene report"
    )
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parents[1], help="Wiki repository root"
    )
    parser.add_argument(
        "--now",
        required=True,
        help="explicit timezone-aware ISO-8601 evaluation time; wall clock is never consulted",
    )
    parser.add_argument("--compact", action="store_true", help="emit single-line canonical JSON")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        report = evaluate_repository(args.root, now=args.now)
    except MemoryHygieneError as exc:
        sys.stderr.write(canonical_json({"error": str(exc)}) + "\n")
        return 2
    sys.stdout.write(canonical_json(report, pretty=not args.compact))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
