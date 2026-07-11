#!/usr/bin/env python3
"""Pure, deterministic retrieval-feedback and lifecycle primitives.

Retrieval feedback is an attributed diagnostic observation.  It is never an
epistemic trust input, ranking update, deletion request, or executable action.
Lifecycle helpers return copies and append transition history; they never
delete a subject or mutate the caller's object.

Python 3.10+ standard library only.  There is intentionally no I/O or CLI in
this module; the canonical ledger writer belongs to the governed control plane.
"""

from __future__ import annotations

import copy
import datetime as dt
import hashlib
import json
import re
from collections.abc import Iterable, Mapping, Sequence
from typing import Any


FEEDBACK_OUTCOMES = frozenset({"helpful", "harmful", "irrelevant", "unknown"})
FEEDBACK_STATUSES = frozenset({"open", "resolved"})
LIFECYCLE_STATUSES = frozenset({"active", "deprecated", "superseded", "invalidated", "archived"})

FEEDBACK_FIELDS = frozenset(
    {
        "id",
        "actor_id",
        "created_at",
        "task_ref",
        "targets",
        "outcome",
        "rationale",
        "evidence_refs",
        "trust_effect",
        "automatic_action",
        "status",
    }
)
FEEDBACK_OPTIONAL_FIELDS = frozenset({"resolution"})
RESOLUTION_FIELDS = frozenset({"actor_id", "at", "rationale"})

TRANSITION_FIELDS = frozenset(
    {
        "id",
        "target_ref",
        "from_status",
        "to_status",
        "actor_id",
        "reason",
        "replacement_ref",
        "created_at",
        "automatic_action",
        "destructive_action",
    }
)

ALLOWED_LIFECYCLE_TRANSITIONS: dict[str, frozenset[str]] = {
    "active": frozenset({"deprecated", "superseded", "invalidated", "archived"}),
    "deprecated": frozenset({"active", "superseded", "invalidated", "archived"}),
    "invalidated": frozenset({"active", "superseded", "archived"}),
    "superseded": frozenset({"archived"}),
    "archived": frozenset(),
}

# Opaque references deliberately exclude whitespace, query punctuation and
# control characters.  They are identifiers, not a place to store raw queries.
REF_RE = re.compile(r"^[A-Za-z0-9가-힣][A-Za-z0-9가-힣:._/@#-]{0,511}$")
TASK_REF_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9:._/@#-]{2,255}$")


class MemoryFeedbackError(ValueError):
    """Schema, integrity, or lifecycle invariant violation."""


def canonical_json(value: Any) -> str:
    """Return canonical UTF-8-safe JSON text for hashing and byte comparison."""

    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def canonical_bytes(value: Any) -> bytes:
    return canonical_json(value).encode("utf-8")


def digest_value(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def stable_id(prefix: str, value: Any) -> str:
    return f"{prefix}-{digest_value(value)[:12].upper()}"


def normalize_timestamp(value: str | dt.datetime) -> str:
    """Require timezone-aware ISO-8601 and normalize it to UTC seconds."""

    if isinstance(value, dt.datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        normalized = value.strip()
        if normalized.endswith("Z"):
            normalized = normalized[:-1] + "+00:00"
        try:
            parsed = dt.datetime.fromisoformat(normalized)
        except ValueError as exc:
            raise MemoryFeedbackError(f"invalid ISO-8601 timestamp: {value}") from exc
    else:
        raise MemoryFeedbackError("timestamp must be a non-empty ISO-8601 string or datetime")
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise MemoryFeedbackError("timestamp must include a timezone offset")
    return parsed.astimezone(dt.timezone.utc).replace(microsecond=0).isoformat()


def _nonempty_text(value: Any, name: str, *, maximum: int = 4096) -> str:
    if not isinstance(value, str) or not value.strip():
        raise MemoryFeedbackError(f"{name} must be a non-empty string")
    cleaned = value.strip()
    if len(cleaned) > maximum:
        raise MemoryFeedbackError(f"{name} exceeds {maximum} characters")
    if any(ord(character) < 32 and character not in "\n\t" for character in cleaned):
        raise MemoryFeedbackError(f"{name} contains control characters")
    return cleaned


def _reference(value: Any, name: str, *, task: bool = False) -> str:
    cleaned = _nonempty_text(value, name, maximum=256 if task else 512)
    pattern = TASK_REF_RE if task else REF_RE
    if not pattern.fullmatch(cleaned):
        requirement = "opaque token without whitespace or query text" if task else "opaque reference token"
        raise MemoryFeedbackError(f"{name} must be an {requirement}")
    return cleaned


def _reference_list(value: Any, name: str, *, required: bool) -> list[str]:
    if not isinstance(value, list):
        raise MemoryFeedbackError(f"{name} must be a list")
    cleaned = [_reference(item, f"{name} item") for item in value]
    if required and not cleaned:
        raise MemoryFeedbackError(f"{name} must not be empty")
    if len(set(cleaned)) != len(cleaned):
        raise MemoryFeedbackError(f"{name} must not contain duplicates")
    return cleaned


def _normalized_reference_list(value: Sequence[str], name: str, *, required: bool) -> list[str]:
    if isinstance(value, (str, bytes)):
        raise MemoryFeedbackError(f"{name} must be a sequence of references, not text")
    cleaned = [_reference(item, f"{name} item") for item in value]
    if required and not cleaned:
        raise MemoryFeedbackError(f"{name} must not be empty")
    return sorted(set(cleaned))


def _feedback_identity_payload(record: Mapping[str, Any]) -> dict[str, Any]:
    """Return immutable creation fields; resolution never changes identity."""

    return {
        "actor_id": record["actor_id"],
        "created_at": record["created_at"],
        "task_ref": record["task_ref"],
        "targets": record["targets"],
        "outcome": record["outcome"],
        "rationale": record["rationale"],
        "evidence_refs": record["evidence_refs"],
        "trust_effect": "none",
        "automatic_action": False,
    }


def feedback_digest(record: Mapping[str, Any], *, validate: bool = True) -> str:
    """Stable digest of immutable feedback identity fields.

    It deliberately excludes status/resolution so resolving an observation
    does not manufacture a new observation ID.
    """

    if validate:
        validate_retrieval_feedback(record)
    return digest_value(_feedback_identity_payload(record))


def feedback_state_digest(record: Mapping[str, Any]) -> str:
    """Digest the complete validated current state, including resolution."""

    validate_retrieval_feedback(record)
    return digest_value(dict(record))


def make_retrieval_feedback(
    *,
    actor_id: str,
    targets: Sequence[str],
    outcome: str,
    task_ref: str,
    rationale: str,
    evidence_refs: Sequence[str] = (),
    created_at: str | dt.datetime,
) -> dict[str, Any]:
    """Create an open, audit-only retrieval-feedback record.

    No clock default is provided: callers must supply ``created_at`` so the
    same inputs are byte-identical and independently replayable.
    """

    record: dict[str, Any] = {
        "actor_id": _reference(actor_id, "actor_id"),
        "created_at": normalize_timestamp(created_at),
        "task_ref": _reference(task_ref, "task_ref", task=True),
        "targets": _normalized_reference_list(targets, "targets", required=True),
        "outcome": outcome,
        "rationale": _nonempty_text(rationale, "rationale"),
        "evidence_refs": _normalized_reference_list(evidence_refs, "evidence_refs", required=False),
        "trust_effect": "none",
        "automatic_action": False,
        "status": "open",
    }
    if outcome not in FEEDBACK_OUTCOMES:
        raise MemoryFeedbackError(f"outcome must be one of {sorted(FEEDBACK_OUTCOMES)}")
    record["id"] = stable_id("MFB", _feedback_identity_payload(record))
    validate_retrieval_feedback(record)
    return record


# Short aliases are useful to control-plane integrations while retaining the
# explicit retrieval terminology in the canonical API.
make_feedback = make_retrieval_feedback


def validate_retrieval_feedback(record: Mapping[str, Any]) -> list[str]:
    """Strictly validate one canonical feedback record or raise.

    Unknown fields are rejected.  This is a security property: callers cannot
    smuggle ``raw_query``, trust promotion, ranking, deletion, or executable
    action fields into the ledger.
    """

    if not isinstance(record, Mapping):
        raise MemoryFeedbackError("feedback record must be an object")
    fields = set(record)
    missing = FEEDBACK_FIELDS - fields
    extra = fields - FEEDBACK_FIELDS - FEEDBACK_OPTIONAL_FIELDS
    errors: list[str] = []
    if missing:
        errors.append(f"missing fields: {', '.join(sorted(missing))}")
    if extra:
        errors.append(f"unknown fields: {', '.join(sorted(extra))}")
    if errors:
        raise MemoryFeedbackError("; ".join(errors))

    try:
        _reference(record["id"], "id")
        _reference(record["actor_id"], "actor_id")
        normalized_time = normalize_timestamp(record["created_at"])
        if normalized_time != record["created_at"]:
            errors.append("created_at must use canonical UTC seconds")
        _reference(record["task_ref"], "task_ref", task=True)
        targets = _reference_list(record["targets"], "targets", required=True)
        evidence = _reference_list(record["evidence_refs"], "evidence_refs", required=False)
        if targets != sorted(targets):
            errors.append("targets must be sorted")
        if evidence != sorted(evidence):
            errors.append("evidence_refs must be sorted")
        _nonempty_text(record["rationale"], "rationale")
    except MemoryFeedbackError as exc:
        errors.append(str(exc))

    if record["outcome"] not in FEEDBACK_OUTCOMES:
        errors.append(f"outcome must be one of {sorted(FEEDBACK_OUTCOMES)}")
    if record["trust_effect"] != "none":
        errors.append("trust_effect must be exactly 'none'")
    if record["automatic_action"] is not False:
        errors.append("automatic_action must be exactly false")
    if record["status"] not in FEEDBACK_STATUSES:
        errors.append(f"status must be one of {sorted(FEEDBACK_STATUSES)}")

    has_resolution = "resolution" in record
    if record["status"] == "open" and has_resolution:
        errors.append("open feedback must not contain resolution")
    if record["status"] == "resolved" and not has_resolution:
        errors.append("resolved feedback requires resolution")
    if has_resolution:
        resolution = record["resolution"]
        if not isinstance(resolution, Mapping):
            errors.append("resolution must be an object")
        else:
            missing_resolution = RESOLUTION_FIELDS - set(resolution)
            extra_resolution = set(resolution) - RESOLUTION_FIELDS
            if missing_resolution:
                errors.append(f"resolution missing fields: {', '.join(sorted(missing_resolution))}")
            if extra_resolution:
                errors.append(f"resolution unknown fields: {', '.join(sorted(extra_resolution))}")
            if not missing_resolution:
                try:
                    _reference(resolution["actor_id"], "resolution.actor_id")
                    normalized = normalize_timestamp(resolution["at"])
                    if normalized != resolution["at"]:
                        errors.append("resolution.at must use canonical UTC seconds")
                    if normalized < record["created_at"]:
                        errors.append("resolution.at must not precede created_at")
                    _nonempty_text(resolution["rationale"], "resolution.rationale")
                except MemoryFeedbackError as exc:
                    errors.append(str(exc))

    if not errors:
        expected_id = stable_id("MFB", _feedback_identity_payload(record))
        if record["id"] != expected_id:
            errors.append(f"id integrity mismatch: expected {expected_id}")
    if errors:
        raise MemoryFeedbackError("; ".join(errors))
    return []


validate_feedback = validate_retrieval_feedback


def validate_feedback_collection(payload: Mapping[str, Any]) -> list[str]:
    """Validate canonical ``state/memory_feedback.json`` payload shape."""

    if not isinstance(payload, Mapping):
        raise MemoryFeedbackError("feedback collection must be an object")
    if set(payload) != {"version", "feedback"}:
        missing = {"version", "feedback"} - set(payload)
        extra = set(payload) - {"version", "feedback"}
        parts = []
        if missing:
            parts.append(f"missing collection fields: {', '.join(sorted(missing))}")
        if extra:
            parts.append(f"unknown collection fields: {', '.join(sorted(extra))}")
        raise MemoryFeedbackError("; ".join(parts))
    if payload["version"] != 1:
        raise MemoryFeedbackError("feedback collection version must be 1")
    if not isinstance(payload["feedback"], list):
        raise MemoryFeedbackError("feedback collection feedback must be a list")
    seen: set[str] = set()
    for record in payload["feedback"]:
        validate_retrieval_feedback(record)
        if record["id"] in seen:
            raise MemoryFeedbackError(f"duplicate feedback id in canonical collection: {record['id']}")
        seen.add(record["id"])
    return []


def make_feedback_collection(records: Iterable[Mapping[str, Any]] = ()) -> dict[str, Any]:
    """Return canonical version-1 payload after deterministic deduplication."""

    payload = {"version": 1, "feedback": deduplicate_feedback(records)}
    validate_feedback_collection(payload)
    return payload


def resolve_retrieval_feedback(
    record: Mapping[str, Any],
    *,
    actor_id: str,
    rationale: str,
    at: str | dt.datetime,
) -> dict[str, Any]:
    """Return a resolved copy; the original and diagnostic outcome are intact."""

    validate_retrieval_feedback(record)
    resolution = {
        "actor_id": _reference(actor_id, "resolution.actor_id"),
        "at": normalize_timestamp(at),
        "rationale": _nonempty_text(rationale, "resolution.rationale"),
    }
    if resolution["at"] < record["created_at"]:
        raise MemoryFeedbackError("resolution.at must not precede created_at")
    if record["status"] == "resolved":
        if record.get("resolution") == resolution:
            return copy.deepcopy(dict(record))
        raise MemoryFeedbackError("resolved feedback cannot be silently rewritten")
    result = copy.deepcopy(dict(record))
    result["status"] = "resolved"
    result["resolution"] = resolution
    validate_retrieval_feedback(result)
    return result


resolve_feedback = resolve_retrieval_feedback


def _merge_duplicate(existing: Mapping[str, Any], candidate: Mapping[str, Any]) -> dict[str, Any]:
    if feedback_state_digest(existing) == feedback_state_digest(candidate):
        return copy.deepcopy(dict(existing))
    if existing["status"] == "open" and candidate["status"] == "resolved":
        return copy.deepcopy(dict(candidate))
    if existing["status"] == "resolved" and candidate["status"] == "open":
        return copy.deepcopy(dict(existing))
    raise MemoryFeedbackError(f"conflicting duplicate feedback state for {existing['id']}")


def _deduplicate_with_stats(records: Iterable[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    by_digest: dict[str, dict[str, Any]] = {}
    total = 0
    for record in records:
        total += 1
        validate_retrieval_feedback(record)
        key = feedback_digest(record, validate=False)
        if key in by_digest:
            by_digest[key] = _merge_duplicate(by_digest[key], record)
        else:
            by_digest[key] = copy.deepcopy(dict(record))
    unique = sorted(by_digest.values(), key=lambda item: (item["created_at"], item["id"]))
    return unique, total - len(unique)


def deduplicate_feedback(records: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Deduplicate by stable creation digest with monotonic resolution merge."""

    unique, _ = _deduplicate_with_stats(records)
    return unique


dedupe_feedback = deduplicate_feedback


def aggregate_feedback_report(
    records: Iterable[Mapping[str, Any]],
    *,
    generated_at: str | dt.datetime,
) -> dict[str, Any]:
    """Create a deterministic diagnostic report with no automatic consequence."""

    unique, duplicate_count = _deduplicate_with_stats(records)
    outcome_counts = {outcome: 0 for outcome in sorted(FEEDBACK_OUTCOMES)}
    status_counts = {status: 0 for status in sorted(FEEDBACK_STATUSES)}
    actor_counts: dict[str, int] = {}
    target_rows: dict[str, dict[str, Any]] = {}
    evidence_attached = 0
    for record in unique:
        outcome_counts[record["outcome"]] += 1
        status_counts[record["status"]] += 1
        actor_counts[record["actor_id"]] = actor_counts.get(record["actor_id"], 0) + 1
        if record["evidence_refs"]:
            evidence_attached += 1
        for target in record["targets"]:
            row = target_rows.setdefault(
                target,
                {
                    "target_ref": target,
                    "total": 0,
                    "unresolved": 0,
                    "outcomes": {outcome: 0 for outcome in sorted(FEEDBACK_OUTCOMES)},
                },
            )
            row["total"] += 1
            row["outcomes"][record["outcome"]] += 1
            if record["status"] != "resolved":
                row["unresolved"] += 1
    generated = normalize_timestamp(generated_at)
    report_body = {
        "schema_version": 1,
        "generated_at": generated,
        "input_records": len(unique) + duplicate_count,
        "unique_records": len(unique),
        "duplicate_records": duplicate_count,
        "outcome_counts": outcome_counts,
        "status_counts": status_counts,
        "evidence": {"attached": evidence_attached, "missing": len(unique) - evidence_attached},
        "actors": [
            {"actor_id": actor_id, "count": actor_counts[actor_id]} for actor_id in sorted(actor_counts)
        ],
        "targets": [target_rows[target] for target in sorted(target_rows)],
        "trust_effect": "none",
        "automatic_action": False,
        "selection_bias_warning": (
            "Feedback is selectively observed diagnostic data, not epistemic ground truth, "
            "ranking authority, or deletion authority."
        ),
    }
    return {
        "report_id": stable_id("MFR", report_body),
        "report_digest": digest_value(report_body),
        **report_body,
    }


aggregate_feedback = aggregate_feedback_report


def render_feedback_report(report: Mapping[str, Any]) -> bytes:
    """Serialize a report deterministically after checking safety constants."""

    if report.get("trust_effect") != "none" or report.get("automatic_action") is not False:
        raise MemoryFeedbackError("aggregate report cannot encode trust or automatic action")
    expected_body = {key: value for key, value in report.items() if key not in {"report_id", "report_digest"}}
    if report.get("report_digest") != digest_value(expected_body):
        raise MemoryFeedbackError("aggregate report digest mismatch")
    if report.get("report_id") != stable_id("MFR", expected_body):
        raise MemoryFeedbackError("aggregate report id mismatch")
    return canonical_bytes(dict(report)) + b"\n"


def _transition_identity_payload(transition: Mapping[str, Any]) -> dict[str, Any]:
    return {key: transition[key] for key in sorted(TRANSITION_FIELDS - {"id"})}


def lifecycle_transition_digest(transition: Mapping[str, Any], *, validate: bool = True) -> str:
    if validate:
        validate_lifecycle_transition(transition)
    return digest_value(_transition_identity_payload(transition))


def make_lifecycle_transition(
    *,
    target_ref: str,
    from_status: str,
    to_status: str,
    actor_id: str,
    reason: str,
    created_at: str | dt.datetime,
    replacement_ref: str | None = None,
) -> dict[str, Any]:
    """Create an attributed non-destructive transition envelope."""

    transition: dict[str, Any] = {
        "target_ref": _reference(target_ref, "target_ref"),
        "from_status": from_status,
        "to_status": to_status,
        "actor_id": _reference(actor_id, "actor_id"),
        "reason": _nonempty_text(reason, "reason"),
        "replacement_ref": (
            _reference(replacement_ref, "replacement_ref") if replacement_ref is not None else None
        ),
        "created_at": normalize_timestamp(created_at),
        "automatic_action": False,
        "destructive_action": False,
    }
    transition["id"] = stable_id("LCT", _transition_identity_payload(transition))
    validate_lifecycle_transition(transition)
    return transition


def validate_lifecycle_transition(transition: Mapping[str, Any]) -> list[str]:
    if not isinstance(transition, Mapping):
        raise MemoryFeedbackError("lifecycle transition must be an object")
    missing = TRANSITION_FIELDS - set(transition)
    extra = set(transition) - TRANSITION_FIELDS
    errors: list[str] = []
    if missing:
        errors.append(f"missing transition fields: {', '.join(sorted(missing))}")
    if extra:
        errors.append(f"unknown transition fields: {', '.join(sorted(extra))}")
    if errors:
        raise MemoryFeedbackError("; ".join(errors))
    try:
        _reference(transition["id"], "id")
        target_ref = _reference(transition["target_ref"], "target_ref")
        _reference(transition["actor_id"], "actor_id")
        _nonempty_text(transition["reason"], "reason")
        normalized = normalize_timestamp(transition["created_at"])
        if normalized != transition["created_at"]:
            errors.append("created_at must use canonical UTC seconds")
        replacement = transition["replacement_ref"]
        if replacement is not None:
            replacement = _reference(replacement, "replacement_ref")
            if replacement == target_ref:
                errors.append("replacement_ref must differ from target_ref")
    except MemoryFeedbackError as exc:
        errors.append(str(exc))

    source = transition["from_status"]
    destination = transition["to_status"]
    if source not in LIFECYCLE_STATUSES:
        errors.append(f"from_status must be one of {sorted(LIFECYCLE_STATUSES)}")
    if destination not in LIFECYCLE_STATUSES:
        errors.append(f"to_status must be one of {sorted(LIFECYCLE_STATUSES)}")
    if source in ALLOWED_LIFECYCLE_TRANSITIONS and destination not in ALLOWED_LIFECYCLE_TRANSITIONS[source]:
        errors.append(f"lifecycle transition is not allowed: {source} -> {destination}")
    if destination == "superseded" and not transition["replacement_ref"]:
        errors.append("superseded transition requires replacement_ref")
    if destination != "superseded" and transition["replacement_ref"] is not None:
        errors.append("replacement_ref is only valid for a superseded transition")
    if transition["automatic_action"] is not False:
        errors.append("automatic_action must be exactly false")
    if transition["destructive_action"] is not False:
        errors.append("destructive_action must be exactly false")
    if not errors:
        expected_id = stable_id("LCT", _transition_identity_payload(transition))
        if transition["id"] != expected_id:
            errors.append(f"transition id integrity mismatch: expected {expected_id}")
    if errors:
        raise MemoryFeedbackError("; ".join(errors))
    return []


def apply_lifecycle_transition(
    subject: Mapping[str, Any], transition: Mapping[str, Any]
) -> dict[str, Any]:
    """Project a transition onto a copied subject and append full history.

    Existing subject keys, including confidence/source trust fields, are never
    removed or rewritten except the explicit additive lifecycle projection.
    """

    if not isinstance(subject, Mapping):
        raise MemoryFeedbackError("lifecycle subject must be an object")
    validate_lifecycle_transition(transition)
    subject_id = subject.get("id")
    if not isinstance(subject_id, str) or not subject_id:
        raise MemoryFeedbackError("lifecycle subject requires an id")
    if subject_id != transition["target_ref"]:
        raise MemoryFeedbackError("transition target_ref does not match subject id")
    existing_history = subject.get("lifecycle_history", [])
    if not isinstance(existing_history, list):
        raise MemoryFeedbackError("subject lifecycle_history must be a list")
    for prior in existing_history:
        validate_lifecycle_transition(prior)
        if prior["id"] == transition["id"]:
            if prior != transition:
                raise MemoryFeedbackError("conflicting lifecycle transition with duplicate id")
            return copy.deepcopy(dict(subject))
    current = subject.get("lifecycle_status", "active")
    if current not in LIFECYCLE_STATUSES:
        raise MemoryFeedbackError(f"subject has invalid lifecycle_status: {current}")
    if current != transition["from_status"]:
        raise MemoryFeedbackError(
            f"transition prior state mismatch: subject={current}, transition={transition['from_status']}"
        )

    result = copy.deepcopy(dict(subject))
    result["lifecycle_status"] = transition["to_status"]
    result["lifecycle_reason"] = transition["reason"]
    result["lifecycle_updated_at"] = transition["created_at"]
    result["lifecycle_updated_by"] = transition["actor_id"]
    if transition["to_status"] == "superseded":
        result["replaced_by"] = transition["replacement_ref"]
    # Never delete an earlier replaced_by projection when a superseded subject
    # is later archived; history remains the authoritative audit trail.
    result["lifecycle_history"] = copy.deepcopy(existing_history) + [copy.deepcopy(dict(transition))]
    return result


def transition_lifecycle(
    subject: Mapping[str, Any],
    *,
    to_status: str,
    actor_id: str,
    reason: str,
    created_at: str | dt.datetime,
    replacement_ref: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Convenience wrapper returning ``(updated_copy, transition_envelope)``."""

    if not isinstance(subject, Mapping):
        raise MemoryFeedbackError("lifecycle subject must be an object")
    target_ref = subject.get("id")
    if not isinstance(target_ref, str) or not target_ref:
        raise MemoryFeedbackError("lifecycle subject requires an id")
    from_status = subject.get("lifecycle_status", "active")
    transition = make_lifecycle_transition(
        target_ref=target_ref,
        from_status=from_status,
        to_status=to_status,
        actor_id=actor_id,
        reason=reason,
        replacement_ref=replacement_ref,
        created_at=created_at,
    )
    return apply_lifecycle_transition(subject, transition), transition


__all__ = [
    "ALLOWED_LIFECYCLE_TRANSITIONS",
    "FEEDBACK_FIELDS",
    "FEEDBACK_OPTIONAL_FIELDS",
    "FEEDBACK_OUTCOMES",
    "FEEDBACK_STATUSES",
    "LIFECYCLE_STATUSES",
    "MemoryFeedbackError",
    "aggregate_feedback",
    "aggregate_feedback_report",
    "apply_lifecycle_transition",
    "canonical_bytes",
    "canonical_json",
    "dedupe_feedback",
    "deduplicate_feedback",
    "feedback_digest",
    "feedback_state_digest",
    "lifecycle_transition_digest",
    "make_feedback",
    "make_feedback_collection",
    "make_lifecycle_transition",
    "make_retrieval_feedback",
    "normalize_timestamp",
    "render_feedback_report",
    "resolve_feedback",
    "resolve_retrieval_feedback",
    "stable_id",
    "transition_lifecycle",
    "validate_feedback",
    "validate_feedback_collection",
    "validate_lifecycle_transition",
    "validate_retrieval_feedback",
]
