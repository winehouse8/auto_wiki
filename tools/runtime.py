#!/usr/bin/env python3
"""Bounded, auditable collaboration runtime for the Living Wiki.

This module deliberately does not fetch the network, invoke a shell, edit the
canonical Wiki ledgers, or publish anything.  It supplies the deterministic
control-plane pieces around those effects: actor-neutral collaboration records,
lexical retrieval, dependency/semantic impact previews, bounded work plans,
permission decisions, and append-only run receipts.

The public functions accept an explicit ``root`` or explicit data wherever
possible so callers and tests do not have to mutate repository globals.
Python 3.10+ standard library only.
"""

from __future__ import annotations

import argparse
import copy
import datetime as dt
import hashlib
import json
import math
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = 1
ZERO_HASH = "0" * 64

RECORD_KINDS = frozenset({"commitment", "contribution", "review"})
INTENTS = frozenset({"direction", "correction", "lead", "objection"})
RECORD_STATES = frozenset(
    {"draft", "proposed", "acknowledged", "active", "resolved", "withdrawn", "rejected", "superseded"}
)
TERMINAL_RECORD_STATES = frozenset({"resolved", "withdrawn", "rejected", "superseded"})
RECORD_TRANSITIONS: dict[str, frozenset[str]] = {
    "draft": frozenset({"proposed", "withdrawn"}),
    "proposed": frozenset({"acknowledged", "active", "rejected", "withdrawn", "superseded"}),
    "acknowledged": frozenset({"active", "resolved", "rejected", "withdrawn", "superseded"}),
    "active": frozenset({"resolved", "withdrawn", "superseded"}),
    "resolved": frozenset(),
    "withdrawn": frozenset(),
    "rejected": frozenset(),
    "superseded": frozenset(),
}

COLLABORATION_FIELDS = frozenset(
    {
        "schema_version",
        "id",
        "record_kind",
        "intent",
        "actor_id",
        "content",
        "targets",
        "stance",
        "status",
        "created_at",
        "updated_at",
        "supersedes",
        "metadata",
    }
)

AUTO_ACTIONS = frozenset(
    {
        "content.draft",
        "metadata.update.reversible",
        "evaluation.run",
        "validation.run",
        "render.preview",
        "retrieval.search",
        "impact.preview",
        "external.research.plan",
        "receipt.record",
    }
)
HIGH_RISK_ACTIONS = frozenset(
    {
        "raw.delete",
        "governance.modify",
        "trust-policy.modify",
        "external.publish",
        "credential.use",
        "paid.operation",
        "files.move.bulk",
        "harness.self_modify",
        "canonical.promote",
    }
)
DENIED_ACTIONS = frozenset(
    {
        "raw.overwrite",
        "event.rewrite",
        "credential.exfiltrate",
        "execute.untrusted",
        "gate.bypass",
        "audit.delete",
    }
)
EXTERNAL_EFFECT_PREFIXES = ("external.fetch", "external.search", "external.send", "network.")

TOKEN_RE = re.compile(r"[a-z0-9]+|[가-힣]+", re.IGNORECASE)
STOP_WORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "for",
        "from",
        "in",
        "is",
        "it",
        "of",
        "on",
        "or",
        "that",
        "the",
        "to",
        "with",
        "것",
        "그",
        "및",
        "수",
        "은",
        "는",
        "이",
        "가",
        "을",
        "를",
        "에",
        "의",
        "와",
        "과",
    }
)


class RuntimeErrorBase(RuntimeError):
    """A deterministic validation or runtime error."""


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value: Any) -> str:
    text = value if isinstance(value, str) else canonical_json(value)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def stable_id(prefix: str, *parts: Any) -> str:
    joined = "\x1f".join(str(part).strip() for part in parts)
    return f"{prefix}-{digest(joined)[:12].upper()}"


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def parse_time(value: str | dt.datetime | None) -> dt.datetime:
    if value is None:
        return dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
    if isinstance(value, dt.datetime):
        parsed = value
    else:
        normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
        try:
            parsed = dt.datetime.fromisoformat(normalized)
        except ValueError as exc:
            raise RuntimeErrorBase(f"invalid ISO-8601 timestamp: {value}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc).replace(microsecond=0)


def iso_time(value: str | dt.datetime | None) -> str:
    return parse_time(value).isoformat()


def _strings(value: Any, field_name: str, *, allow_empty: bool = True) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
        raise RuntimeErrorBase(f"{field_name} must be a list of non-empty strings")
    result = list(dict.fromkeys(item.strip() for item in value))
    if not allow_empty and not result:
        raise RuntimeErrorBase(f"{field_name} must not be empty")
    return result


def make_collaboration_record(
    *,
    actor_id: str,
    record_kind: str,
    intent: str,
    content: str,
    targets: Sequence[str],
    stance: str | None = None,
    status: str = "proposed",
    created_at: str | dt.datetime | None = None,
    supersedes: Sequence[str] = (),
    metadata: Mapping[str, Any] | None = None,
    record_id: str | None = None,
) -> dict[str, Any]:
    """Create the same collaboration envelope for a human or an agent.

    ``actor_id`` is intentionally opaque.  Prefixes such as ``human:`` and
    ``agent:`` never change this schema or its validation rules.
    """

    timestamp = iso_time(created_at)
    clean_targets = list(dict.fromkeys(str(item).strip() for item in targets if str(item).strip()))
    clean_supersedes = list(dict.fromkeys(str(item).strip() for item in supersedes if str(item).strip()))
    generated_id = stable_id(
        "COL",
        actor_id,
        record_kind,
        intent,
        content,
        canonical_json(clean_targets),
        timestamp,
    )
    record = {
        "schema_version": SCHEMA_VERSION,
        "id": record_id or generated_id,
        "record_kind": record_kind,
        "intent": intent,
        "actor_id": actor_id,
        "content": content,
        "targets": clean_targets,
        "stance": stance,
        "status": status,
        "created_at": timestamp,
        "updated_at": timestamp,
        "supersedes": clean_supersedes,
        "metadata": copy.deepcopy(dict(metadata or {})),
    }
    validate_collaboration_record(record)
    return record


def validate_collaboration_record(record: Mapping[str, Any]) -> list[str]:
    """Validate a collaboration record or raise ``RuntimeErrorBase``.

    The empty return value makes the function convenient for validation gates.
    Extensions belong in ``metadata`` so envelopes remain actor-neutral.
    """

    missing = COLLABORATION_FIELDS - set(record)
    extra = set(record) - COLLABORATION_FIELDS
    errors: list[str] = []
    if missing:
        errors.append(f"missing fields: {', '.join(sorted(missing))}")
    if extra:
        errors.append(f"unknown fields (put extensions in metadata): {', '.join(sorted(extra))}")
    if errors:
        raise RuntimeErrorBase("; ".join(errors))
    if record["schema_version"] != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION}")
    if record["record_kind"] not in RECORD_KINDS:
        errors.append(f"record_kind must be one of {sorted(RECORD_KINDS)}")
    if record["intent"] not in INTENTS:
        errors.append(f"intent must be one of {sorted(INTENTS)}")
    if record["status"] not in RECORD_STATES:
        errors.append(f"status must be one of {sorted(RECORD_STATES)}")
    for name in ("id", "actor_id", "content"):
        if not isinstance(record[name], str) or not record[name].strip():
            errors.append(f"{name} must be a non-empty string")
    if record["stance"] is not None and (not isinstance(record["stance"], str) or not record["stance"].strip()):
        errors.append("stance must be null or a non-empty string")
    try:
        _strings(record["targets"], "targets", allow_empty=False)
        _strings(record["supersedes"], "supersedes")
        created = parse_time(record["created_at"])
        updated = parse_time(record["updated_at"])
        if updated < created:
            errors.append("updated_at must not precede created_at")
    except RuntimeErrorBase as exc:
        errors.append(str(exc))
    if not isinstance(record["metadata"], dict):
        errors.append("metadata must be an object")
    if errors:
        raise RuntimeErrorBase("; ".join(errors))
    return []


def transition_collaboration_record(
    record: Mapping[str, Any],
    new_status: str,
    *,
    actor_id: str,
    reason: str,
    at: str | dt.datetime | None = None,
) -> dict[str, Any]:
    """Return a transitioned copy and retain an attribution trail."""

    validate_collaboration_record(record)
    current = str(record["status"])
    if new_status not in RECORD_STATES:
        raise RuntimeErrorBase(f"unknown lifecycle state: {new_status}")
    if new_status not in RECORD_TRANSITIONS[current]:
        raise RuntimeErrorBase(f"invalid lifecycle transition: {current} -> {new_status}")
    if not actor_id.strip() or not reason.strip():
        raise RuntimeErrorBase("transition actor_id and reason are required")
    result = copy.deepcopy(dict(record))
    timestamp = iso_time(at)
    if parse_time(timestamp) < parse_time(record["updated_at"]):
        raise RuntimeErrorBase("transition timestamp must not precede the current updated_at")
    history = result["metadata"].setdefault("transitions", [])
    if not isinstance(history, list):
        raise RuntimeErrorBase("metadata.transitions must be a list")
    history.append(
        {"from": current, "to": new_status, "actor_id": actor_id, "reason": reason, "at": timestamp}
    )
    result["status"] = new_status
    result["updated_at"] = timestamp
    validate_collaboration_record(result)
    return result


@dataclass(frozen=True)
class SearchDocument:
    doc_id: str
    text: str
    kind: str = "unknown"
    metadata: Mapping[str, Any] = field(default_factory=dict)


def tokenize(text: str) -> list[str]:
    return [token for token in TOKEN_RE.findall(text.lower()) if len(token) > 1 and token not in STOP_WORDS]


def _flatten_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, Mapping):
        return " ".join(_flatten_text(value[key]) for key in sorted(value))
    if isinstance(value, Sequence):
        return " ".join(_flatten_text(item) for item in value)
    return ""


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeErrorBase(f"cannot read {path}: {exc}") from exc


def build_search_documents(
    root: Path | str = ROOT,
    *,
    include_wiki: bool = True,
    include_inactive: bool = False,
    max_wiki_file_bytes: int = 256_000,
) -> list[SearchDocument]:
    """Build a deterministic, read-only corpus from canonical state and Wiki.

    Raw artifacts are deliberately excluded.  Wiki text is untrusted evidence,
    never an instruction, and results only expose a bounded snippet.
    """

    base = Path(root)
    documents: list[SearchDocument] = []
    state_specs = {
        "claims": ("claims", "claim", ("id", "statement", "scope", "kind", "tags", "notes", "confidence")),
        "sources": (
            "sources",
            "source",
            ("id", "title", "authors", "publisher", "source_type", "publication_status", "notes", "assessment"),
        ),
        "campaigns": (
            "campaigns",
            "campaign",
            ("id", "question", "why_now", "notes", "stop_conditions", "claim_ids", "source_ids", "status"),
        ),
    }
    for file_stem, (list_key, kind, fields) in state_specs.items():
        payload = _read_json(base / "state" / f"{file_stem}.json", {list_key: []})
        items = payload.get(list_key, []) if isinstance(payload, dict) else []
        if not isinstance(items, list):
            raise RuntimeErrorBase(f"state/{file_stem}.json: {list_key} must be a list")
        for item in items:
            if not isinstance(item, dict) or not isinstance(item.get("id"), str):
                continue
            lifecycle = item.get("lifecycle_status")
            if lifecycle is None and kind == "source":
                lifecycle = item.get("status")
            if kind in {"claim", "source"} and not include_inactive and (lifecycle or "active") != "active":
                continue
            text = " ".join(_flatten_text(item.get(key)) for key in fields)
            documents.append(
                SearchDocument(
                    f"{kind}:{item['id']}",
                    text,
                    kind,
                    {"ref": item["id"], "origin": f"state/{file_stem}.json"},
                )
            )
    if include_wiki:
        wiki_root = base / "wiki"
        if wiki_root.is_dir():
            for path in sorted(wiki_root.rglob("*.md"), key=lambda item: item.as_posix()):
                try:
                    size = path.stat().st_size
                except OSError as exc:
                    raise RuntimeErrorBase(f"cannot stat {path}: {exc}") from exc
                if size > max_wiki_file_bytes:
                    continue
                relative = path.relative_to(base).as_posix()
                try:
                    text = path.read_text(encoding="utf-8")
                except (OSError, UnicodeDecodeError):
                    continue
                if not include_inactive:
                    match = re.search(
                        r"(?m)^lifecycle_status:\s*[\"']?([A-Za-z-]+)[\"']?\s*$",
                        text[:4096],
                    )
                    if match and match.group(1) in {"deprecated", "superseded", "invalidated", "archived"}:
                        continue
                documents.append(
                    SearchDocument(f"wiki:{relative}", text, "wiki", {"path": relative, "untrusted": True})
                )
    return sorted(documents, key=lambda item: item.doc_id)


class BM25Index:
    """Small deterministic Okapi BM25-like lexical index."""

    def __init__(self, documents: Iterable[SearchDocument], *, k1: float = 1.2, b: float = 0.75):
        self.documents = sorted(documents, key=lambda item: item.doc_id)
        self.k1 = float(k1)
        self.b = float(b)
        self.tokens: list[list[str]] = [tokenize(doc.text) for doc in self.documents]
        self.lengths = [len(tokens) for tokens in self.tokens]
        self.average_length = sum(self.lengths) / len(self.lengths) if self.lengths else 0.0
        self.term_frequencies: list[dict[str, int]] = []
        document_frequency: dict[str, int] = {}
        for tokens in self.tokens:
            frequencies: dict[str, int] = {}
            for token in tokens:
                frequencies[token] = frequencies.get(token, 0) + 1
            self.term_frequencies.append(frequencies)
            for token in frequencies:
                document_frequency[token] = document_frequency.get(token, 0) + 1
        count = len(self.documents)
        self.idf = {
            token: math.log(1.0 + (count - frequency + 0.5) / (frequency + 0.5))
            for token, frequency in document_frequency.items()
        }

    def search(self, query: str, *, limit: int = 10) -> list[dict[str, Any]]:
        if limit < 0:
            raise RuntimeErrorBase("search limit must be non-negative")
        query_tokens = list(dict.fromkeys(tokenize(query)))
        if not query_tokens or not self.documents or limit == 0:
            return []
        results: list[dict[str, Any]] = []
        for index, document in enumerate(self.documents):
            length = self.lengths[index]
            normalizer = 1.0 - self.b + self.b * (length / self.average_length) if self.average_length else 1.0
            score = 0.0
            matched: list[str] = []
            for token in query_tokens:
                frequency = self.term_frequencies[index].get(token, 0)
                if not frequency:
                    continue
                matched.append(token)
                numerator = frequency * (self.k1 + 1.0)
                denominator = frequency + self.k1 * normalizer
                score += self.idf[token] * numerator / denominator
            if score <= 0:
                continue
            compact = re.sub(r"\s+", " ", document.text).strip()
            results.append(
                {
                    "doc_id": document.doc_id,
                    "kind": document.kind,
                    "score": round(score, 12),
                    "matched_terms": sorted(matched),
                    "snippet": compact[:280],
                    "metadata": dict(document.metadata),
                }
            )
        results.sort(key=lambda item: (-item["score"], item["doc_id"]))
        return results[:limit]


def lexical_search(
    query: str,
    *,
    root: Path | str = ROOT,
    documents: Iterable[SearchDocument] | None = None,
    limit: int = 10,
    include_inactive: bool = False,
) -> list[dict[str, Any]]:
    corpus = (
        list(documents)
        if documents is not None
        else build_search_documents(root, include_inactive=include_inactive)
    )
    return BM25Index(corpus).search(query, limit=limit)


NEGATION_MARKERS = (
    " not ",
    " never ",
    " no ",
    "false",
    "incorrect",
    "obsolete",
    "deny",
    "reject",
    "아니다",
    "않",
    "없",
    "금지",
    "반대",
    "거짓",
    "폐기",
    "철회",
    "중단",
    "삭제",
)
CONFLICT_CUES = ("correction", "object", "challenge", "contradict", "수정", "이의", "반박", "반대", "오류")
ANTONYM_PAIRS = (
    ("allow", "deny"),
    ("enable", "disable"),
    ("include", "exclude"),
    ("automatic", "manual"),
    ("support", "reject"),
    ("허용", "금지"),
    ("자동", "수동"),
    ("포함", "제외"),
    ("유지", "폐기"),
)


def _negative_polarity(text: str) -> bool:
    padded = f" {text.lower()} "
    return any(marker in padded for marker in NEGATION_MARKERS)


def semantic_conflict_candidates(
    proposed_text: str,
    results: Sequence[Mapping[str, Any]],
    *,
    minimum_score: float = 0.05,
) -> list[dict[str, Any]]:
    """Flag lexical candidates only; this never declares a semantic conflict."""

    proposed = proposed_text.lower()
    proposed_negative = _negative_polarity(proposed)
    has_cue = any(cue in proposed for cue in CONFLICT_CUES)
    candidates: list[dict[str, Any]] = []
    for result in results:
        score = float(result.get("score", 0.0))
        if score < minimum_score:
            continue
        snippet = str(result.get("snippet", "")).lower()
        reasons: list[str] = []
        if proposed_negative != _negative_polarity(snippet):
            reasons.append("polarity_mismatch")
        if has_cue:
            reasons.append("explicit_conflict_cue")
        for left, right in ANTONYM_PAIRS:
            if (left in proposed and right in snippet) or (right in proposed and left in snippet):
                reasons.append(f"antonym:{left}/{right}")
        if reasons:
            candidates.append(
                {
                    "doc_id": result.get("doc_id"),
                    "score": score,
                    "reasons": sorted(set(reasons)),
                    "status": "candidate_requires_review",
                }
            )
    candidates.sort(key=lambda item: (-item["score"], str(item["doc_id"])))
    return candidates


def _state_items(root: Path, name: str) -> list[dict[str, Any]]:
    payload = _read_json(root / "state" / f"{name}.json", {name: []})
    result = payload.get(name, []) if isinstance(payload, dict) else []
    if not isinstance(result, list):
        raise RuntimeErrorBase(f"state/{name}.json: {name} must be a list")
    return [item for item in result if isinstance(item, dict)]


def impact_preview(
    target_refs: Sequence[str],
    proposed_text: str,
    *,
    root: Path | str = ROOT,
    search_limit: int = 12,
) -> dict[str, Any]:
    """Preview dependency propagation and possible semantic conflicts."""

    base = Path(root)
    claims = _state_items(base, "claims")
    sources = _state_items(base, "sources")
    campaigns = _state_items(base, "campaigns")
    claim_by_id = {item.get("id"): item for item in claims if isinstance(item.get("id"), str)}
    source_by_id = {item.get("id"): item for item in sources if isinstance(item.get("id"), str)}
    campaign_by_id = {item.get("id"): item for item in campaigns if isinstance(item.get("id"), str)}
    known = set(claim_by_id) | set(source_by_id) | set(campaign_by_id)
    direct = list(dict.fromkeys(str(ref).strip() for ref in target_refs if str(ref).strip()))
    impacted_claims = {ref for ref in direct if ref in claim_by_id}
    impacted_sources = {ref for ref in direct if ref in source_by_id}
    impacted_campaigns = {ref for ref in direct if ref in campaign_by_id}
    edges: set[tuple[str, str, str]] = set()

    for claim_id, claim in claim_by_id.items():
        for evidence in claim.get("evidence", []) if isinstance(claim.get("evidence"), list) else []:
            source_id = evidence.get("source_id") if isinstance(evidence, dict) else None
            if not isinstance(source_id, str):
                continue
            edges.add((source_id, "evidence_for", claim_id))
            if source_id in impacted_sources:
                impacted_claims.add(claim_id)
            if claim_id in impacted_claims:
                impacted_sources.add(source_id)
        for predecessor in claim.get("supersedes", []) if isinstance(claim.get("supersedes"), list) else []:
            if isinstance(predecessor, str):
                edges.add((claim_id, "supersedes", predecessor))
                if claim_id in impacted_claims or predecessor in impacted_claims:
                    impacted_claims.update((claim_id, predecessor))

    # Close campaign membership after claim/source expansion.
    for campaign_id, campaign in campaign_by_id.items():
        campaign_claims = {item for item in campaign.get("claim_ids", []) if isinstance(item, str)}
        campaign_sources = {item for item in campaign.get("source_ids", []) if isinstance(item, str)}
        for claim_id in campaign_claims:
            edges.add((campaign_id, "contains_claim", claim_id))
        for source_id in campaign_sources:
            edges.add((campaign_id, "contains_source", source_id))
        if campaign_id in impacted_campaigns:
            impacted_claims.update(campaign_claims)
            impacted_sources.update(campaign_sources)
        elif campaign_claims & impacted_claims or campaign_sources & impacted_sources:
            impacted_campaigns.add(campaign_id)

    # A campaign target may introduce dependencies; close once more.
    # Only a directly targeted campaign expands to all of its members. A
    # campaign reached as a dependent of one claim must not make every sibling
    # claim look affected.
    direct_campaigns = {ref for ref in direct if ref in campaign_by_id}
    for campaign_id in sorted(direct_campaigns):
        campaign = campaign_by_id[campaign_id]
        impacted_claims.update(item for item in campaign.get("claim_ids", []) if isinstance(item, str))
        impacted_sources.update(item for item in campaign.get("source_ids", []) if isinstance(item, str))
    # Campaign membership may have introduced claims whose evidence sources were
    # not present in campaign.source_ids. Include that canonical dependency too.
    for claim_id in list(impacted_claims):
        claim = claim_by_id.get(claim_id, {})
        for evidence in claim.get("evidence", []) if isinstance(claim.get("evidence"), list) else []:
            source_id = evidence.get("source_id") if isinstance(evidence, dict) else None
            if isinstance(source_id, str):
                impacted_sources.add(source_id)

    search_results = lexical_search(proposed_text, root=base, limit=search_limit) if proposed_text.strip() else []
    conflicts = semantic_conflict_candidates(proposed_text, search_results)
    relevant_edges = [
        {"from": start, "relation": relation, "to": end}
        for start, relation, end in sorted(edges)
        if start in impacted_sources | impacted_claims | impacted_campaigns
        and end in impacted_sources | impacted_claims | impacted_campaigns
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "direct_targets": direct,
        "unknown_targets": sorted(set(direct) - known),
        "impacted": {
            "claims": sorted(impacted_claims),
            "sources": sorted(impacted_sources),
            "campaigns": sorted(impacted_campaigns),
        },
        "dependency_edges": relevant_edges,
        "semantic_matches": search_results,
        "semantic_conflict_candidates": conflicts,
        "warning": "Lexical candidates are triage hints, not semantic judgments.",
    }


def decide_permission(
    action: str | Mapping[str, Any],
    *,
    actor: Mapping[str, Any] | None = None,
    policy: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return ``auto``, ``review``, or ``deny`` without actor-kind privilege."""

    action_obj = {"action_type": action} if isinstance(action, str) else dict(action)
    action_type = str(action_obj.get("action_type", "")).strip()
    if not action_type:
        raise RuntimeErrorBase("action_type is required")
    custom = dict(policy or {})
    deny = DENIED_ACTIONS | frozenset(custom.get("deny_actions", []))
    high = HIGH_RISK_ACTIONS | frozenset(custom.get("review_actions", []))
    auto = AUTO_ACTIONS | frozenset(custom.get("auto_actions", []))
    reasons: list[str] = []
    risk = "low"
    builtin_deny = any(action_type == item or action_type.startswith(item + ".") for item in DENIED_ACTIONS)
    builtin_high = any(action_type == item or action_type.startswith(item + ".") for item in HIGH_RISK_ACTIONS)
    if builtin_deny or action_type in deny:
        decision = "deny"
        risk = "prohibited"
        reasons.append("action violates an immutable/audit/security boundary")
    elif (
        builtin_high
        or action_type in high
        or action_obj.get("risk") == "high"
        or action_obj.get("irreversible", False)
    ):
        decision = "review"
        risk = "high"
        reasons.append("high-risk or irreversible actions are never automatic")
    elif (
        action_type.startswith("external.") or action_type.startswith("network.")
    ) and not action_type.endswith(".plan"):
        decision = "review"
        risk = "medium"
        reasons.append("external effects require an explicit executor/approval boundary")
    elif action_type in auto and not action_obj.get("irreversible", False):
        decision = "auto"
        reasons.append("allowlisted low-risk reversible control-plane action")
    else:
        decision = "review"
        risk = "medium"
        reasons.append("unknown or non-allowlisted action defaults to review")
    if action_obj.get("irreversible", False) and decision == "auto":
        decision = "review"
        risk = "high"
        reasons = ["irreversible actions are never automatic"]
    return {
        "decision": decision,
        "risk": risk,
        "action_type": action_type,
        "actor_id": (actor or {}).get("id"),
        "actor_kind_used_for_decision": False,
        "reasons": reasons,
    }


DEFAULT_LIMITS: dict[str, int] = {
    "max_campaigns": 3,
    "max_actions": 3,
    "max_minutes": 45,
    "max_sources": 3,
    "action_minutes": 15,
    "sources_per_action": 1,
}


def _receipt_campaign_times(receipts: Sequence[Mapping[str, Any]]) -> dict[str, dt.datetime]:
    latest: dict[str, dt.datetime] = {}
    for receipt in receipts:
        # Planning, review, failure, and dry-run receipts do not satisfy a
        # research cadence. A standalone external receipt counts only after its
        # reporter marks it completed; run receipts count completed actions.
        if receipt.get("campaign_id") and receipt.get("status") == "completed":
            campaign_id = receipt.get("campaign_id")
            when = receipt.get("completed_at") or receipt.get("created_at")
            if isinstance(campaign_id, str) and isinstance(when, str):
                try:
                    parsed = parse_time(when)
                except RuntimeErrorBase:
                    pass
                else:
                    if campaign_id not in latest or parsed > latest[campaign_id]:
                        latest[campaign_id] = parsed
        when = receipt.get("completed_at") or receipt.get("created_at")
        if not isinstance(when, str):
            continue
        try:
            parsed = parse_time(when)
        except RuntimeErrorBase:
            continue
        for action in receipt.get("actions", []) if isinstance(receipt.get("actions"), list) else []:
            campaign_id = action.get("campaign_id") if isinstance(action, dict) else None
            action_status = action.get("status") if isinstance(action, dict) else None
            if (
                action_status == "completed"
                and isinstance(campaign_id, str)
                and (campaign_id not in latest or parsed > latest[campaign_id])
            ):
                latest[campaign_id] = parsed
    return latest


def _stop_reason(campaign: Mapping[str, Any], now: dt.datetime) -> str | None:
    status = campaign.get("status")
    if status not in {"queued", "active"}:
        return f"lifecycle:{status}"
    runtime = campaign.get("runtime", {}) if isinstance(campaign.get("runtime"), dict) else {}
    if runtime.get("stopped"):
        return f"runtime:{runtime.get('stopped_reason', 'stopped')}"
    used_minutes = max(0, int(runtime.get("used_minutes", 0)))
    used_sources = max(0, int(runtime.get("used_sources", 0)))
    if used_minutes >= max(0, int(campaign.get("max_minutes", 0))):
        return "budget:max_minutes"
    if used_sources >= max(0, int(campaign.get("max_sources", 0))):
        return "budget:max_sources"
    met = set(runtime.get("met_stop_conditions", [])) if isinstance(runtime.get("met_stop_conditions"), list) else set()
    for condition in campaign.get("stop_conditions", []) if isinstance(campaign.get("stop_conditions"), list) else []:
        if isinstance(condition, str) and condition in met:
            return f"condition:{condition}"
        if not isinstance(condition, dict):
            continue
        kind = condition.get("type")
        if kind == "deadline" and isinstance(condition.get("at"), str) and now >= parse_time(condition["at"]):
            return "condition:deadline"
        if kind == "sources_gte" and used_sources >= int(condition.get("value", 0)):
            return "condition:sources_gte"
        if kind == "minutes_gte" and used_minutes >= int(condition.get("value", 0)):
            return "condition:minutes_gte"
        if kind == "flag" and condition.get("name") in met:
            return f"condition:{condition.get('name')}"
    return None


def build_bounded_schedule(
    *,
    root: Path | str = ROOT,
    campaigns: Sequence[Mapping[str, Any]] | None = None,
    interests: Sequence[Mapping[str, Any]] | None = None,
    receipts: Sequence[Mapping[str, Any]] = (),
    limits: Mapping[str, int] | None = None,
    now: str | dt.datetime | None = None,
) -> dict[str, Any]:
    """Create a priority/cadence/budget bounded plan; execute nothing."""

    base = Path(root)
    timestamp = parse_time(now)
    campaign_items = list(campaigns) if campaigns is not None else _state_items(base, "campaigns")
    if interests is None:
        payload = _read_json(base / "config" / "interests.json", {"interests": []})
        interest_items = payload.get("interests", []) if isinstance(payload, dict) else []
    else:
        interest_items = list(interests)
    interest_by_id = {
        item.get("id"): item for item in interest_items if isinstance(item, Mapping) and isinstance(item.get("id"), str)
    }
    applied = dict(DEFAULT_LIMITS)
    applied.update({key: int(value) for key, value in dict(limits or {}).items()})
    if any(value < 0 for value in applied.values()):
        raise RuntimeErrorBase("scheduler limits must be non-negative")
    last_runs = _receipt_campaign_times(receipts)
    eligible: list[tuple[float, str, Mapping[str, Any], int, int]] = []
    skipped: list[dict[str, str]] = []
    for campaign in campaign_items:
        campaign_id = str(campaign.get("id", ""))
        if not campaign_id:
            skipped.append({"campaign_id": "<missing>", "reason": "invalid:missing_id"})
            continue
        stop = _stop_reason(campaign, timestamp)
        if stop:
            skipped.append({"campaign_id": campaign_id, "reason": stop})
            continue
        interest = interest_by_id.get(campaign.get("interest_id"), {})
        cadence_days = max(0, int(campaign.get("cadence_days", interest.get("cadence_days", 0))))
        last_run = last_runs.get(campaign_id)
        runtime = campaign.get("runtime", {}) if isinstance(campaign.get("runtime"), dict) else {}
        if last_run is None and isinstance(runtime.get("last_run_at"), str):
            last_run = parse_time(runtime["last_run_at"])
        if last_run is not None and timestamp < last_run + dt.timedelta(days=cadence_days):
            due = (last_run + dt.timedelta(days=cadence_days)).isoformat()
            skipped.append({"campaign_id": campaign_id, "reason": f"cadence:not_due_until:{due}"})
            continue
        used_minutes = max(0, int(runtime.get("used_minutes", 0)))
        used_sources = max(0, int(runtime.get("used_sources", 0)))
        remaining_minutes = max(0, int(campaign.get("max_minutes", 0)) - used_minutes)
        remaining_sources = max(0, int(campaign.get("max_sources", 0)) - used_sources)
        eligible.append((-float(campaign.get("priority", interest.get("priority", 0.0))), campaign_id, campaign, remaining_minutes, remaining_sources))

    eligible.sort(key=lambda item: (item[0], item[1]))
    actions: list[dict[str, Any]] = []
    allocated_minutes = 0
    allocated_sources = 0
    for _, campaign_id, campaign, remaining_minutes, remaining_sources in eligible:
        if len(actions) >= min(applied["max_campaigns"], applied["max_actions"]):
            skipped.append({"campaign_id": campaign_id, "reason": "run_budget:max_actions_or_campaigns"})
            continue
        minutes = min(applied["action_minutes"], remaining_minutes, applied["max_minutes"] - allocated_minutes)
        sources = min(applied["sources_per_action"], remaining_sources, applied["max_sources"] - allocated_sources)
        if minutes <= 0 or sources <= 0:
            skipped.append({"campaign_id": campaign_id, "reason": "run_budget:exhausted"})
            continue
        action_id = stable_id("ACT", campaign_id, timestamp.isoformat(), len(actions), minutes, sources)
        action = {
            "id": action_id,
            "action_type": "external.research.plan",
            "campaign_id": campaign_id,
            "question": campaign.get("question", ""),
            "priority": float(campaign.get("priority", 0.0)),
            "budget": {"minutes": minutes, "sources": sources},
            "stop_conditions": copy.deepcopy(campaign.get("stop_conditions", [])),
            "external_work": True,
            "execution": "planned_only",
            "permission": decide_permission("external.research.plan"),
        }
        actions.append(action)
        allocated_minutes += minutes
        allocated_sources += sources
    skipped.sort(key=lambda item: (item["campaign_id"], item["reason"]))
    plan_core = {
        "schema_version": SCHEMA_VERSION,
        "kind": "bounded_schedule",
        "generated_at": timestamp.isoformat(),
        "limits": applied,
        "allocated": {
            "campaigns": len(actions),
            "actions": len(actions),
            "minutes": allocated_minutes,
            "sources": allocated_sources,
        },
        "actions": actions,
        "skipped": skipped,
        "side_effects_executed": False,
    }
    return {"plan_id": stable_id("PLAN", canonical_json(plan_core)), **plan_core}


def make_external_work_receipt(
    action: Mapping[str, Any],
    *,
    actor_id: str,
    status: str,
    evidence_refs: Sequence[str] = (),
    notes: str | None = None,
    at: str | dt.datetime | None = None,
) -> dict[str, Any]:
    """Represent an externally performed result without performing the work."""

    if status not in {"reported", "completed", "failed", "cancelled"}:
        raise RuntimeErrorBase("invalid external receipt status")
    if not action.get("external_work"):
        raise RuntimeErrorBase("external receipt requires an external_work action")
    timestamp = iso_time(at)
    receipt = {
        "schema_version": SCHEMA_VERSION,
        "receipt_id": stable_id("EXT", action.get("id"), actor_id, status, timestamp),
        "action_id": action.get("id"),
        "campaign_id": action.get("campaign_id"),
        "actor_id": actor_id,
        "status": status,
        "evidence_refs": list(dict.fromkeys(evidence_refs)),
        "notes": notes,
        "created_at": timestamp,
        "execution_performed_by_runtime": False,
        "verification_status": "unverified_report",
    }
    return receipt


class ReceiptStore:
    """Append-only, hash-chained JSONL receipt store (single-writer contract)."""

    def __init__(self, directory: Path | str):
        self.directory = Path(directory)
        self.path = self.directory / "receipts.jsonl"

    def load(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        receipts: list[dict[str, Any]] = []
        for number, line in enumerate(self.path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise RuntimeErrorBase(f"invalid receipt JSON at line {number}: {exc}") from exc
            if not isinstance(value, dict):
                raise RuntimeErrorBase(f"receipt line {number} is not an object")
            receipts.append(value)
        return receipts

    def find(self, idempotency_key: str) -> list[dict[str, Any]]:
        return [item for item in self.load() if item.get("idempotency_key") == idempotency_key]

    def append(self, receipt: Mapping[str, Any]) -> dict[str, Any]:
        self.directory.mkdir(parents=True, exist_ok=True)
        previous = self.load()
        value = copy.deepcopy(dict(receipt))
        value["prev_receipt_hash"] = previous[-1].get("receipt_hash", ZERO_HASH) if previous else ZERO_HASH
        value.pop("receipt_hash", None)
        value["receipt_hash"] = digest(value)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(canonical_json(value) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        return value

    def verify(self) -> list[str]:
        errors: list[str] = []
        previous_hash = ZERO_HASH
        for number, receipt in enumerate(self.load(), 1):
            if receipt.get("prev_receipt_hash") != previous_hash:
                errors.append(f"line {number}: broken prev_receipt_hash")
            claimed = receipt.get("receipt_hash")
            unsigned = dict(receipt)
            unsigned.pop("receipt_hash", None)
            if claimed != digest(unsigned):
                errors.append(f"line {number}: invalid receipt_hash")
            previous_hash = str(claimed)
        return errors


TERMINAL_RUN_STATES = frozenset({"completed", "dry_run", "planned", "review_required", "blocked"})


def _validate_plan_budget(plan: Mapping[str, Any]) -> None:
    actions = plan.get("actions", [])
    limits = plan.get("limits", {})
    if not isinstance(actions, list) or not isinstance(limits, dict):
        raise RuntimeErrorBase("plan actions must be a list and limits an object")
    action_ids: list[str] = []
    for item in actions:
        if not isinstance(item, dict):
            raise RuntimeErrorBase("each plan action must be an object")
        action_id = item.get("id")
        if not isinstance(action_id, str) or not action_id:
            raise RuntimeErrorBase("each plan action requires a non-empty id")
        action_ids.append(action_id)
        budget = item.get("budget", {})
        if not isinstance(budget, dict):
            raise RuntimeErrorBase(f"action {action_id}: budget must be an object")
        if any(int(budget.get(name, 0)) < 0 for name in ("minutes", "sources")):
            raise RuntimeErrorBase(f"action {action_id}: budget values must be non-negative")
    if len(set(action_ids)) != len(action_ids):
        raise RuntimeErrorBase("plan action IDs must be unique")
    for key, actual in (
        ("max_campaigns", len({item.get("campaign_id") for item in actions if item.get("campaign_id")})),
        ("max_actions", len(actions)),
        ("max_minutes", sum(int(item.get("budget", {}).get("minutes", 0)) for item in actions)),
        ("max_sources", sum(int(item.get("budget", {}).get("sources", 0)) for item in actions)),
    ):
        if key in limits and actual > int(limits[key]):
            raise RuntimeErrorBase(f"plan exceeds {key}: {actual} > {limits[key]}")


def run_plan(
    plan: Mapping[str, Any],
    *,
    dry_run: bool = True,
    store: ReceiptStore | None = None,
    handlers: Mapping[str, Callable[[Mapping[str, Any]], Any]] | None = None,
    idempotency_key: str | None = None,
    actor: Mapping[str, Any] | None = None,
    policy: Mapping[str, Any] | None = None,
    now: str | dt.datetime | None = None,
) -> dict[str, Any]:
    """Run approved internal handlers, or produce dry/planned/review receipts.

    External actions and ``planned_only`` actions never reach a handler.  A
    failed stored run may be retried: completed action IDs are recovered and
    skipped while an append-only attempt links to the failed receipt.
    """

    _validate_plan_budget(plan)
    timestamp = iso_time(now)
    plan_hash = digest(plan)
    base_key = idempotency_key or stable_id("IDEM", plan_hash)
    effective_key = stable_id("KEY", base_key, plan_hash, "dry" if dry_run else "live")
    if store:
        chain_errors = store.verify()
        if chain_errors:
            raise RuntimeErrorBase(f"receipt chain validation failed: {chain_errors[0]}")
    prior = store.find(effective_key) if store else []
    if prior and prior[-1].get("status") in TERMINAL_RUN_STATES:
        replay = copy.deepcopy(prior[-1])
        replay["replayed"] = True
        return replay
    previous = prior[-1] if prior else None
    recovered_ids = {
        item.get("action_id")
        for item in (previous or {}).get("actions", [])
        if isinstance(item, dict) and item.get("status") == "completed"
    }
    action_receipts: list[dict[str, Any]] = []
    failed = False
    for action in plan.get("actions", []):
        action_id = action.get("id")
        common = {"action_id": action_id, "campaign_id": action.get("campaign_id"), "action_type": action.get("action_type")}
        if action_id in recovered_ids:
            action_receipts.append({**common, "status": "completed", "recovered": True})
            continue
        permission = decide_permission(action, actor=actor, policy=policy)
        if permission["decision"] == "deny":
            action_receipts.append({**common, "status": "denied", "permission": permission})
            continue
        if permission["decision"] == "review":
            action_receipts.append({**common, "status": "review_required", "permission": permission})
            continue
        if action.get("external_work") or action.get("execution") == "planned_only":
            action_receipts.append({**common, "status": "planned", "permission": permission, "side_effect": False})
            continue
        if dry_run:
            action_receipts.append({**common, "status": "dry_run", "permission": permission, "side_effect": False})
            continue
        handler = (handlers or {}).get(str(action.get("action_type")))
        if handler is None:
            action_receipts.append({**common, "status": "review_required", "reason": "no registered handler"})
            continue
        try:
            outcome = handler(copy.deepcopy(action))
            action_receipts.append(
                {**common, "status": "completed", "outcome_digest": digest(outcome), "side_effect": True}
            )
        except Exception as exc:  # handler boundary must always leave a receipt
            action_receipts.append(
                {**common, "status": "failed", "error_type": type(exc).__name__, "error": str(exc), "side_effect": False}
            )
            failed = True
            break
    processed = {item.get("action_id") for item in action_receipts}
    for action in plan.get("actions", []):
        if action.get("id") not in processed:
            action_receipts.append(
                {
                    "action_id": action.get("id"),
                    "campaign_id": action.get("campaign_id"),
                    "action_type": action.get("action_type"),
                    "status": "not_started",
                }
            )
    statuses = {item["status"] for item in action_receipts}
    if failed or "failed" in statuses:
        status = "failed"
    elif "denied" in statuses:
        status = "blocked"
    elif "review_required" in statuses:
        status = "review_required"
    elif dry_run and statuses <= {"dry_run", "completed"}:
        status = "dry_run"
    elif "planned" in statuses:
        status = "planned"
    else:
        status = "completed"
    attempt = len(prior) + 1
    receipt = {
        "schema_version": SCHEMA_VERSION,
        "run_id": stable_id("RUN", effective_key, attempt, timestamp),
        "plan_id": plan.get("plan_id"),
        "plan_hash": plan_hash,
        "idempotency_key": effective_key,
        "attempt": attempt,
        "recovery_of": previous.get("run_id") if previous and previous.get("status") == "failed" else None,
        "dry_run": dry_run,
        "status": status,
        "created_at": timestamp,
        "completed_at": timestamp,
        "actions": action_receipts,
        "budget": copy.deepcopy(plan.get("allocated", {})),
        "side_effect_count": sum(1 for item in action_receipts if item.get("side_effect") is True),
    }
    return store.append(receipt) if store else receipt


def recover_run(
    plan: Mapping[str, Any],
    *,
    store: ReceiptStore,
    handlers: Mapping[str, Callable[[Mapping[str, Any]], Any]],
    idempotency_key: str | None = None,
    actor: Mapping[str, Any] | None = None,
    policy: Mapping[str, Any] | None = None,
    now: str | dt.datetime | None = None,
) -> dict[str, Any]:
    """Resume a failed live run; reject recovery of a terminal successful run."""

    plan_hash = digest(plan)
    base_key = idempotency_key or stable_id("IDEM", plan_hash)
    effective_key = stable_id("KEY", base_key, plan_hash, "live")
    prior = store.find(effective_key)
    if not prior or prior[-1].get("status") != "failed":
        raise RuntimeErrorBase("recovery requires the latest matching live receipt to be failed")
    return run_plan(
        plan,
        dry_run=False,
        store=store,
        handlers=handlers,
        idempotency_key=idempotency_key,
        actor=actor,
        policy=policy,
        now=now,
    )


def _print_json(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT, help="Living Wiki repository root")
    subparsers = parser.add_subparsers(dest="command", required=True)
    search = subparsers.add_parser("search", help="deterministic lexical retrieval")
    search.add_argument("query")
    search.add_argument("--limit", type=int, default=10)
    impact = subparsers.add_parser("impact", help="dependency and semantic impact preview")
    impact.add_argument("refs", nargs="+")
    impact.add_argument("--text", required=True)
    impact.add_argument("--limit", type=int, default=12)
    schedule = subparsers.add_parser("schedule", help="emit a bounded plan without external execution")
    schedule.add_argument("--now")
    schedule.add_argument("--max-campaigns", type=int, default=DEFAULT_LIMITS["max_campaigns"])
    schedule.add_argument("--max-actions", type=int, default=DEFAULT_LIMITS["max_actions"])
    schedule.add_argument("--max-minutes", type=int, default=DEFAULT_LIMITS["max_minutes"])
    schedule.add_argument("--max-sources", type=int, default=DEFAULT_LIMITS["max_sources"])
    permission = subparsers.add_parser("permission", help="classify an action")
    permission.add_argument("action_type")
    verify = subparsers.add_parser("verify-receipts", help="verify a receipt hash chain")
    verify.add_argument("directory", type=Path)
    validate = subparsers.add_parser("validate-record", help="validate a collaboration JSON record")
    validate.add_argument("path", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "search":
            _print_json(lexical_search(args.query, root=args.root, limit=args.limit))
        elif args.command == "impact":
            _print_json(impact_preview(args.refs, args.text, root=args.root, search_limit=args.limit))
        elif args.command == "schedule":
            _print_json(
                build_bounded_schedule(
                    root=args.root,
                    now=args.now,
                    limits={
                        "max_campaigns": args.max_campaigns,
                        "max_actions": args.max_actions,
                        "max_minutes": args.max_minutes,
                        "max_sources": args.max_sources,
                    },
                )
            )
        elif args.command == "permission":
            _print_json(decide_permission(args.action_type))
        elif args.command == "verify-receipts":
            errors = ReceiptStore(args.directory).verify()
            _print_json({"valid": not errors, "errors": errors})
            return 1 if errors else 0
        elif args.command == "validate-record":
            value = _read_json(args.path, None)
            validate_collaboration_record(value)
            _print_json({"valid": True, "id": value["id"]})
        return 0
    except RuntimeErrorBase as exc:
        print(f"runtime error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
