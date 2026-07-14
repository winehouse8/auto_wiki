"""결정론적이고 읽기 전용인 Living Wiki 위생 후보 계획기.

이 모듈은 정규 상태와 비예약 OKF 문서를 전수 구조 검사한 뒤, 제한된
시드와 강한 유형 관계만 모델 의미 검토의 입력 후보로 만든다. 결과는
검토 계획일 뿐 evidence, 신뢰도, 생명주기 또는 원문을 변경하지 않는다.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict, deque
from datetime import datetime, timedelta
from itertools import combinations
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import unquote, urlsplit


RESERVED_MARKDOWN_NAMES = {"index.md", "log.md"}
REQUIRED_LIMITS = {
    "recent_documents",
    "stale_claims",
    "max_hops",
    "max_nodes",
    "max_pairs",
    "semantic_review_limit",
}
STRONG_RELATIONS = {
    "markdown_link",
    "claim_ids",
    "source_id",
    "campaign_id",
    "evidence_source",
    "supersedes",
    "campaign_membership",
}
HARD_RISK_REASONS = {
    "broken_markdown_link",
    "duplicate_source_identity",
    "inactive_lifecycle_leak",
    "invalid_frontmatter",
    "invalid_timestamp",
    "missing_claim_reference",
    "missing_source_reference",
    "missing_campaign_reference",
    "registered_contradiction",
    "unresolved_harmful_feedback",
}
SEED_REASON_ORDER = {
    reason: 0 for reason in HARD_RISK_REASONS
} | {
    "recent_document": 1,
    "review_due_claim": 2,
    "dependency_newer_than_document": 3,
}
SIGNAL_ORDER = {
    "explicit_contradiction": 0,
    "polarity_difference": 1,
    "numeric_difference": 2,
    "condition_difference": 3,
}
WEAK_TAG_STOPLIST = {
    "active",
    "admission",
    "agent",
    "allow",
    "archived",
    "article",
    "audit",
    "book",
    "campaign",
    "claim",
    "code",
    "completed",
    "contested",
    "contextualizes",
    "dataset",
    "deprecated",
    "draft",
    "fact",
    "feedback",
    "generated",
    "hypothesis",
    "implemented",
    "interpretation",
    "invalidated",
    "note",
    "official-doc",
    "open",
    "other",
    "paper",
    "prediction",
    "proposed",
    "reference",
    "reject",
    "research-campaign",
    "review",
    "resolved",
    "run",
    "source",
    "standard",
    "supported",
    "superseded",
    "talk",
    "value",
    "video",
}
MARKDOWN_LINK_RE = re.compile(r"(?<!!)\[[^\]]*\]\(([^)]+)\)")
NUMBER_RE = re.compile(r"(?<![\w.])[+-]?\d+(?:[.,]\d+)?(?:%|일|개|회|년|개월)?")
NEGATIVE_RE = re.compile(
    r"(?:하지\s*않|않(?:는|다|음)?|아니|금지|불가|없(?:다|는|음)?|\bnot\b|\bnever\b)",
    re.IGNORECASE,
)
CONDITION_RE = re.compile(r"[^,.!?\n]{0,48}(?:경우|때만|조건(?:에서|에는|이면)?)")
TOPIC_TOKEN_RE = re.compile(
    r"[0-9A-Za-z가-힣]+(?:[._/-][0-9A-Za-z가-힣]+)*"
)


class HygienePlanError(ValueError):
    """후보 계획 입력이 계약을 충족하지 않을 때 발생한다."""


def canonical_plan_bytes(plan: dict[str, Any]) -> bytes:
    """계획을 키 정렬된 canonical JSON bytes로 직렬화한다."""

    return (
        json.dumps(plan, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")


def _input_paths(root: Path) -> list[Path]:
    candidates: set[Path] = set()
    config = root / "config" / "wiki.json"
    if config.is_file():
        candidates.add(config)
    state = root / "state"
    if state.is_dir():
        candidates.update(path for path in state.rglob("*") if path.is_file())
    wiki = root / "wiki"
    if wiki.is_dir():
        candidates.update(path for path in wiki.rglob("*.md") if path.is_file())
    return sorted(candidates, key=lambda path: path.relative_to(root).as_posix())


def repository_fingerprints(root: Path | str) -> dict[str, str]:
    """후보 계획이 읽는 입력 파일의 SHA-256 지문을 정렬해 반환한다."""

    root_path = Path(root).resolve()
    return {
        path.relative_to(root_path).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in _input_paths(root_path)
    }


def _read_json(path: Path, default: Any) -> Any:
    if not path.is_file():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise HygienePlanError(f"JSON 입력을 읽을 수 없음: {path}") from exc


def _collection(root: Path, filename: str, key: str) -> list[dict[str, Any]]:
    payload = _read_json(root / "state" / filename, {key: []})
    if not isinstance(payload, dict) or not isinstance(payload.get(key, []), list):
        raise HygienePlanError(f"state/{filename}의 {key} collection이 올바르지 않음")
    return [item for item in payload.get(key, []) if isinstance(item, dict)]


def _parse_scalar(value: str) -> Any:
    value = value.strip()
    if not value:
        return None
    if value.startswith("[") and value.endswith("]"):
        body = value[1:-1].strip()
        if not body:
            return []
        return [_parse_scalar(part) for part in body.split(",")]
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    folded = value.casefold()
    if folded in {"true", "false"}:
        return folded == "true"
    if folded in {"null", "none", "~"}:
        return None
    return value


def _parse_frontmatter(text: str) -> tuple[dict[str, Any], str, bool]:
    match = re.match(r"\A---\r?\n(.*?)\r?\n---(?:\r?\n|\Z)", text, re.DOTALL)
    if not match:
        return {}, text, False
    metadata: dict[str, Any] = {}
    pending_list_key: str | None = None
    for raw_line in match.group(1).splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("-") and pending_list_key:
            current = metadata.setdefault(pending_list_key, [])
            if isinstance(current, list):
                current.append(_parse_scalar(stripped[1:].strip()))
            continue
        pending_list_key = None
        if ":" not in raw_line:
            continue
        key, raw_value = raw_line.split(":", 1)
        key = key.strip()
        if not key:
            continue
        parsed = _parse_scalar(raw_value)
        metadata[key] = parsed
        if parsed is None:
            metadata[key] = []
            pending_list_key = key
    return metadata, text[match.end() :], True


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    return []


def _parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed


def _typed(kind: str, identifier: str) -> str:
    return f"{kind}:{identifier}"


def _kind(node_id: str) -> str:
    return node_id.split(":", 1)[0]


def _validate_limits(limits: dict[str, Any]) -> dict[str, int]:
    if not isinstance(limits, dict):
        raise HygienePlanError("limits는 object여야 함")
    missing = REQUIRED_LIMITS - set(limits)
    if missing:
        raise HygienePlanError(f"누락된 위생 상한: {', '.join(sorted(missing))}")
    result: dict[str, int] = {}
    for key in REQUIRED_LIMITS:
        value = limits[key]
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise HygienePlanError(f"limits.{key}는 0 이상의 정수여야 함")
        result[key] = value
    if result["max_hops"] > 2:
        raise HygienePlanError("limits.max_hops는 2 이하여야 함")
    return {key: result[key] for key in limits if key in result}


def _document_records(root: Path) -> list[dict[str, Any]]:
    wiki = root / "wiki"
    records: list[dict[str, Any]] = []
    if not wiki.is_dir():
        return records
    for path in sorted(wiki.rglob("*.md"), key=lambda item: item.relative_to(root).as_posix()):
        if path.name in RESERVED_MARKDOWN_NAMES:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise HygienePlanError(f"Markdown 입력을 읽을 수 없음: {path}") from exc
        metadata, body, has_frontmatter = _parse_frontmatter(text)
        relative = path.relative_to(root).as_posix()
        records.append(
            {
                "id": _typed("document", relative),
                "path": path,
                "relative_path": relative,
                "metadata": metadata,
                "body": body,
                "has_frontmatter": has_frontmatter,
                "timestamp": _parse_datetime(metadata.get("timestamp")),
                "tags": sorted(set(_as_list(metadata.get("tags")))),
                "claim_ids": sorted(set(_as_list(metadata.get("claim_ids")))),
                "source_ids": sorted(
                    set(
                        _as_list(metadata.get("source_id"))
                        + _as_list(metadata.get("source_ids"))
                    )
                ),
                "campaign_ids": sorted(
                    set(
                        _as_list(metadata.get("campaign_id"))
                        + _as_list(metadata.get("campaign_ids"))
                    )
                ),
            }
        )
    return records


def _local_link_target(root: Path, source: Path, raw_target: str) -> Path | None:
    target = raw_target.strip()
    if target.startswith("<") and target.endswith(">"):
        target = target[1:-1].strip()
    else:
        title_match = re.match(r"^(\S+)(?:\s+[\"'].*[\"'])$", target)
        if title_match:
            target = title_match.group(1)
    parsed = urlsplit(target)
    if parsed.scheme or parsed.netloc or not parsed.path:
        return None
    candidate = (source.parent / unquote(parsed.path)).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    if not candidate.exists() and not candidate.suffix:
        markdown_candidate = candidate.with_suffix(".md")
        if markdown_candidate.exists():
            candidate = markdown_candidate
    return candidate


def _add_edge(
    adjacency: dict[str, set[tuple[str, str]]],
    left: str,
    right: str,
    relation: str,
) -> None:
    if not left or not right or left == right:
        return
    adjacency[left].add((right, relation))
    adjacency[right].add((left, relation))


def _claim_change_time(claim: dict[str, Any]) -> datetime | None:
    values = [
        _parse_datetime(claim.get(field))
        for field in ("content_updated_at", "updated_at", "lifecycle_updated_at", "created_at")
    ]
    known = [value for value in values if value is not None]
    return max(known) if known else None


def _reference_time(claim: dict[str, Any]) -> datetime | None:
    confidence = claim.get("confidence") if isinstance(claim.get("confidence"), dict) else {}
    candidates = (
        claim.get("last_verified_at"),
        confidence.get("computed_at"),
        claim.get("content_updated_at"),
        claim.get("updated_at"),
        claim.get("created_at"),
    )
    for candidate in candidates:
        value = _parse_datetime(candidate)
        if value is not None:
            return value
    return None


def _source_change_time(source: dict[str, Any]) -> datetime | None:
    assessment = source.get("assessment") if isinstance(source.get("assessment"), dict) else {}
    explicit = _parse_datetime(source.get("content_updated_at"))
    if explicit is not None:
        return explicit
    values = (
        source.get("created_at"),
        source.get("retrieved_at"),
        assessment.get("assessed_at"),
        source.get("lifecycle_updated_at"),
    )
    known = [parsed for value in values if (parsed := _parse_datetime(value)) is not None]
    return max(known) if known else None


def _seed_priority(item: dict[str, Any]) -> tuple[int, str]:
    reasons = item.get("reasons", [])
    priority = min((SEED_REASON_ORDER.get(reason, 9) for reason in reasons), default=9)
    return priority, item["id"]


def _negative(statement: str) -> bool:
    return bool(NEGATIVE_RE.search(statement))


def _numbers(statement: str) -> tuple[str, ...]:
    return tuple(sorted(set(NUMBER_RE.findall(statement))))


def _conditions(statement: str) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                re.sub(r"\s+", " ", match.group(0)).strip()
                for match in CONDITION_RE.finditer(statement)
            }
        )
    )


def _scopes_overlap(left: dict[str, Any], right: dict[str, Any]) -> bool:
    left_scope = str(left.get("scope", "")).strip().casefold()
    right_scope = str(right.get("scope", "")).strip().casefold()
    if not left_scope or not right_scope:
        return True
    if left_scope == right_scope or left_scope in right_scope or right_scope in left_scope:
        return True
    left_tokens = set(re.findall(r"[0-9A-Za-z가-힣]+", left_scope))
    right_tokens = set(re.findall(r"[0-9A-Za-z가-힣]+", right_scope))
    return len(left_tokens & right_tokens) >= 2


def _topic_anchor_overlap(left_statement: str, right_statement: str) -> bool:
    """넓은 tag/scope가 아닌 문장 자체의 충분한 주제 겹침을 확인한다.

    숫자·연도·버전은 충돌 신호일 수 있지만 주제 anchor로 세지 않는다.
    문장이 공유하는 서로 다른 토큰이 세 개 이상이고, 더 짧은 문장의
    주제 토큰 절반 이상이 같을 때만 휴리스틱 비교 대상으로 삼는다.
    """

    def topic_tokens(statement: str) -> set[str]:
        return {
            token
            for raw_token in TOPIC_TOKEN_RE.findall(statement.casefold())
            if len(token := raw_token.strip("._/-")) >= 2
            and not any(character.isdigit() for character in token)
        }

    left_tokens = topic_tokens(left_statement)
    right_tokens = topic_tokens(right_statement)
    if not left_tokens or not right_tokens:
        return False
    shared = left_tokens & right_tokens
    return len(shared) >= 3 and len(shared) / min(len(left_tokens), len(right_tokens)) >= 0.5


def _conflict_candidates(
    claims: list[dict[str, Any]], max_pairs: int
) -> tuple[list[dict[str, Any]], int]:
    by_id = {
        str(claim.get("id")): claim
        for claim in claims
        if isinstance(claim.get("id"), str) and claim.get("id")
    }
    signals: dict[tuple[str, str], set[str]] = defaultdict(set)
    source_relations: dict[str, dict[str, set[str]]] = defaultdict(
        lambda: {"supports": set(), "contradicts": set()}
    )
    for claim_id, claim in by_id.items():
        for edge in claim.get("evidence", []):
            if not isinstance(edge, dict):
                continue
            source_id = edge.get("source_id")
            relation = edge.get("relation")
            if source_id and relation in {"supports", "contradicts"}:
                source_relations[str(source_id)][str(relation)].add(claim_id)
    for relation_map in source_relations.values():
        for supporting in sorted(relation_map["supports"]):
            for contradicting in sorted(relation_map["contradicts"]):
                if supporting != contradicting:
                    signals[tuple(sorted((supporting, contradicting)))].add(
                        "explicit_contradiction"
                    )

    for left_id, right_id in combinations(sorted(by_id), 2):
        left = by_id[left_id]
        right = by_id[right_id]
        left_tags = set(_as_list(left.get("tags")))
        right_tags = set(_as_list(right.get("tags")))
        if not left_tags.intersection(right_tags) or not _scopes_overlap(left, right):
            continue
        left_statement = str(left.get("statement", ""))
        right_statement = str(right.get("statement", ""))
        if not left_statement or not right_statement:
            continue
        if not _topic_anchor_overlap(left_statement, right_statement):
            continue
        pair = (left_id, right_id)
        if _negative(left_statement) != _negative(right_statement):
            signals[pair].add("polarity_difference")
        left_numbers = _numbers(left_statement)
        right_numbers = _numbers(right_statement)
        if left_numbers and right_numbers and left_numbers != right_numbers:
            signals[pair].add("numeric_difference")
        left_conditions = _conditions(left_statement)
        right_conditions = _conditions(right_statement)
        if left_conditions and right_conditions and left_conditions != right_conditions:
            signals[pair].add("condition_difference")

    all_candidates = [
        {
            "claim_ids": list(pair),
            "signals": sorted(pair_signals, key=lambda value: (SIGNAL_ORDER[value], value)),
            "review_only": True,
            "automatic_actions": [],
        }
        for pair, pair_signals in signals.items()
        if pair_signals
    ]
    all_candidates.sort(
        key=lambda item: (
            min(SIGNAL_ORDER[signal] for signal in item["signals"]),
            item["claim_ids"],
        )
    )
    return all_candidates[:max_pairs], max(0, len(all_candidates) - max_pairs)


def _weak_candidates(
    documents: list[dict[str, Any]],
    adjacency: dict[str, set[tuple[str, str]]],
    max_candidates: int,
) -> tuple[list[dict[str, Any]], int]:
    tag_members: dict[str, list[str]] = defaultdict(list)
    for document in documents:
        for tag in document["tags"]:
            folded = tag.casefold()
            if folded in WEAK_TAG_STOPLIST or re.fullmatch(r"[cs][0-4]", folded):
                continue
            tag_members[tag].append(document["id"])
    pair_tags: dict[tuple[str, str], set[str]] = defaultdict(set)
    for tag in sorted(tag_members):
        members = sorted(set(tag_members[tag]))
        for left, right in combinations(members, 2):
            if any(neighbor == right for neighbor, _relation in adjacency.get(left, set())):
                continue
            pair_tags[(left, right)].add(tag)
    candidates = [
        {
            "node_ids": list(pair),
            "signals": ["shared_tag"],
            "shared_tags": sorted(tags),
            "review_only": True,
        }
        for pair, tags in sorted(pair_tags.items())
    ]
    return candidates[:max_candidates], max(0, len(candidates) - max_candidates)


def _semantic_review_queue(
    conflict_candidates: list[dict[str, Any]],
    weak_candidates: list[dict[str, Any]],
    selected_nodes: list[dict[str, Any]],
    limit: int,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for item in conflict_candidates:
        candidates.append(
            {
                "kind": "conflict_candidate",
                "claim_ids": item["claim_ids"],
                "signals": item["signals"],
                "review_only": True,
            }
        )

    def selected_priority(item: dict[str, Any]) -> tuple[int, str] | None:
        reasons = set(item.get("reasons", []))
        if reasons & HARD_RISK_REASONS:
            return 0, item["id"]
        if "review_due_claim" in reasons:
            return 1, item["id"]
        if "dependency_newer_than_document" in reasons:
            return 2, item["id"]
        if "recent_document" in reasons:
            return 3, item["id"]
        return None

    prioritized_selected = [
        (priority, item)
        for item in selected_nodes
        if (priority := selected_priority(item)) is not None
    ]
    for _priority, item in sorted(prioritized_selected, key=lambda entry: entry[0]):
        candidates.append(
            {
                "kind": "selected_node",
                "node_id": item["id"],
                "reasons": item["reasons"],
                "review_only": True,
            }
        )
    for item in weak_candidates:
        candidates.append(
            {
                "kind": "weak_relation_candidate",
                "node_ids": item["node_ids"],
                "signals": item["signals"],
                "review_only": True,
            }
        )
    return candidates[:limit]


def build_hygiene_plan(
    root: Path | str,
    *,
    now: str,
    limits: dict[str, Any],
) -> dict[str, Any]:
    """고정 시각과 명시적 상한으로 읽기 전용 위생 후보 계획을 만든다."""

    root_path = Path(root).resolve()
    now_value = _parse_datetime(now)
    if now_value is None:
        raise HygienePlanError("now는 시간대가 포함된 ISO-8601 시각이어야 함")
    normalized_limits = _validate_limits(limits)
    fingerprints = repository_fingerprints(root_path)

    config = _read_json(root_path / "config" / "wiki.json", {})
    if not isinstance(config, dict):
        raise HygienePlanError("config/wiki.json은 object여야 함")
    thresholds = config.get("staleness_days", {})
    if not isinstance(thresholds, dict):
        thresholds = {}

    claims = _collection(root_path, "claims.json", "claims")
    sources = _collection(root_path, "sources.json", "sources")
    campaigns = _collection(root_path, "campaigns.json", "campaigns")
    feedback_filename = (
        "memory_feedback.json"
        if (root_path / "state" / "memory_feedback.json").is_file()
        else "memory-feedback.json"
    )
    feedback = _collection(root_path, feedback_filename, "feedback")
    documents = _document_records(root_path)

    claim_by_id = {
        str(item["id"]): item
        for item in claims
        if isinstance(item.get("id"), str) and item.get("id")
    }
    source_by_id = {
        str(item["id"]): item
        for item in sources
        if isinstance(item.get("id"), str) and item.get("id")
    }
    campaign_by_id = {
        str(item["id"]): item
        for item in campaigns
        if isinstance(item.get("id"), str) and item.get("id")
    }
    document_by_resolved_path = {item["path"].resolve(): item for item in documents}
    node_ids = {
        *(_typed("document", item["relative_path"]) for item in documents),
        *(_typed("claim", item) for item in claim_by_id),
        *(_typed("source", item) for item in source_by_id),
        *(_typed("campaign", item) for item in campaign_by_id),
    }

    adjacency: dict[str, set[tuple[str, str]]] = defaultdict(set)
    reasons: dict[str, set[str]] = defaultdict(set)

    for document in documents:
        document_id = document["id"]
        if not document["has_frontmatter"] or not document["metadata"].get("type"):
            reasons[document_id].add("invalid_frontmatter")
        if document["timestamp"] is None:
            reasons[document_id].add("invalid_timestamp")
        for claim_id in document["claim_ids"]:
            claim_node = _typed("claim", claim_id)
            if claim_id not in claim_by_id:
                reasons[document_id].add("missing_claim_reference")
                continue
            _add_edge(adjacency, document_id, claim_node, "claim_ids")
            if str(claim_by_id[claim_id].get("lifecycle_status", "active")) != "active":
                reasons[document_id].add("inactive_lifecycle_leak")
        for source_id in document["source_ids"]:
            if source_id not in source_by_id:
                reasons[document_id].add("missing_source_reference")
                continue
            _add_edge(
                adjacency,
                document_id,
                _typed("source", source_id),
                "source_id",
            )
            source_status = source_by_id[source_id].get("lifecycle_status") or source_by_id[
                source_id
            ].get("status", "active")
            if str(source_status) != "active":
                reasons[document_id].add("inactive_lifecycle_leak")
        for campaign_id in document["campaign_ids"]:
            if campaign_id not in campaign_by_id:
                reasons[document_id].add("missing_campaign_reference")
                continue
            _add_edge(
                adjacency,
                document_id,
                _typed("campaign", campaign_id),
                "campaign_id",
            )
        for raw_target in MARKDOWN_LINK_RE.findall(document["body"]):
            target = _local_link_target(root_path, document["path"], raw_target)
            if target is None:
                continue
            if not target.exists():
                reasons[document_id].add("broken_markdown_link")
                continue
            target_document = document_by_resolved_path.get(target.resolve())
            if target_document is not None:
                _add_edge(adjacency, document_id, target_document["id"], "markdown_link")

    for claim_id, claim in claim_by_id.items():
        claim_node = _typed("claim", claim_id)
        for edge in claim.get("evidence", []):
            if not isinstance(edge, dict):
                continue
            source_id = edge.get("source_id")
            if isinstance(source_id, str) and source_id in source_by_id:
                _add_edge(
                    adjacency,
                    claim_node,
                    _typed("source", source_id),
                    "evidence_source",
                )
            if edge.get("relation") == "contradicts":
                reasons[claim_node].add("registered_contradiction")
        for superseded_id in _as_list(claim.get("supersedes")):
            if superseded_id in claim_by_id:
                _add_edge(
                    adjacency,
                    claim_node,
                    _typed("claim", superseded_id),
                    "supersedes",
                )

    for campaign_id, campaign in campaign_by_id.items():
        campaign_node = _typed("campaign", campaign_id)
        for claim_id in sorted(set(_as_list(campaign.get("claim_ids")))):
            if claim_id in claim_by_id:
                _add_edge(
                    adjacency,
                    campaign_node,
                    _typed("claim", claim_id),
                    "campaign_membership",
                )
        for source_id in sorted(set(_as_list(campaign.get("source_ids")))):
            if source_id in source_by_id:
                _add_edge(
                    adjacency,
                    campaign_node,
                    _typed("source", source_id),
                    "campaign_membership",
                )

    identities: dict[str, list[str]] = defaultdict(list)
    for source_id, source in source_by_id.items():
        identity = str(source.get("canonical_identity") or source.get("url") or "").strip()
        if identity:
            identities[identity].append(source_id)
    for duplicate_ids in identities.values():
        if len(duplicate_ids) > 1:
            for source_id in duplicate_ids:
                reasons[_typed("source", source_id)].add("duplicate_source_identity")

    for record in feedback:
        if record.get("resolved_at") or record.get("status") in {"resolved", "closed"}:
            continue
        harmful = record.get("harmful") is True or str(record.get("outcome", "")).casefold() in {
            "harmful",
            "incorrect",
            "misleading",
        }
        if not harmful:
            continue
        targets = _as_list(record.get("target_ids") or record.get("targets") or record.get("target_id"))
        for target in targets:
            if target in claim_by_id:
                reasons[_typed("claim", target)].add("unresolved_harmful_feedback")
            elif target in source_by_id:
                reasons[_typed("source", target)].add("unresolved_harmful_feedback")

    recent_candidates = [item for item in documents if item["timestamp"] is not None]
    recent_candidates.sort(
        key=lambda item: (-item["timestamp"].timestamp(), item["relative_path"])
    )
    for document in recent_candidates[: normalized_limits["recent_documents"]]:
        reasons[document["id"]].add("recent_document")

    stale_candidates: list[tuple[datetime, str]] = []
    for claim_id, claim in claim_by_id.items():
        freshness = str(claim.get("freshness", "normal"))
        threshold = thresholds.get(freshness)
        if threshold is None:
            continue
        if isinstance(threshold, bool) or not isinstance(threshold, int) or threshold < 0:
            continue
        reference = _reference_time(claim)
        if reference is None or reference > now_value:
            continue
        due_at = reference + timedelta(days=threshold)
        if now_value >= due_at:
            stale_candidates.append((due_at, claim_id))
    stale_candidates.sort(key=lambda item: (item[0], item[1]))
    for _due_at, claim_id in stale_candidates[: normalized_limits["stale_claims"]]:
        reasons[_typed("claim", claim_id)].add("review_due_claim")

    for document in documents:
        document_timestamp = document["timestamp"]
        if document_timestamp is None:
            continue
        for claim_id in document["claim_ids"]:
            claim = claim_by_id.get(claim_id)
            if claim is None:
                continue
            changed_at = _claim_change_time(claim)
            if changed_at is not None and changed_at > document_timestamp:
                reasons[document["id"]].add("dependency_newer_than_document")
        for source_id in document["source_ids"]:
            source = source_by_id.get(source_id)
            if source is None:
                continue
            changed_at = _source_change_time(source)
            if changed_at is not None and changed_at > document_timestamp:
                reasons[document["id"]].add("dependency_newer_than_document")

    seeds = [
        {
            "id": node_id,
            "kind": _kind(node_id),
            "reasons": sorted(node_reasons, key=lambda value: (SEED_REASON_ORDER.get(value, 9), value)),
        }
        for node_id, node_reasons in reasons.items()
        if node_reasons and node_id in node_ids
    ]
    seeds.sort(key=_seed_priority)

    selected: dict[str, dict[str, Any]] = {}
    queue: deque[str] = deque()
    node_limit_reached = False
    omitted_seed_ids: list[str] = []
    for seed in seeds:
        if len(selected) >= normalized_limits["max_nodes"]:
            node_limit_reached = True
            omitted_seed_ids.append(seed["id"])
            continue
        selected[seed["id"]] = {
            "id": seed["id"],
            "kind": seed["kind"],
            "reasons": seed["reasons"],
            "hop": 0,
            "selection_path": [{"node_id": seed["id"], "relation": "seed"}],
        }
        queue.append(seed["id"])

    while queue:
        current_id = queue.popleft()
        current = selected[current_id]
        if current["hop"] >= normalized_limits["max_hops"]:
            continue
        neighbors = sorted(adjacency.get(current_id, set()), key=lambda item: (item[0], item[1]))
        for neighbor_id, relation in neighbors:
            if relation not in STRONG_RELATIONS or neighbor_id in selected:
                continue
            if len(selected) >= normalized_limits["max_nodes"]:
                node_limit_reached = True
                queue.clear()
                break
            selected[neighbor_id] = {
                "id": neighbor_id,
                "kind": _kind(neighbor_id),
                "reasons": ["graph_expansion"],
                "hop": current["hop"] + 1,
                "selection_path": [
                    *current["selection_path"],
                    {"node_id": neighbor_id, "relation": relation},
                ],
            }
            queue.append(neighbor_id)

    selected_nodes = list(selected.values())
    conflict_candidates, omitted_pairs = _conflict_candidates(
        claims, normalized_limits["max_pairs"]
    )
    weak_candidates, omitted_weak = _weak_candidates(
        documents, adjacency, normalized_limits["max_pairs"]
    )
    truncations: list[dict[str, Any]] = []
    if node_limit_reached:
        truncations.append(
            {
                "code": "max_nodes_reached",
                "limit": normalized_limits["max_nodes"],
                "omitted_seed_ids": omitted_seed_ids,
            }
        )
    if omitted_pairs:
        truncations.append(
            {
                "code": "max_pairs_reached",
                "limit": normalized_limits["max_pairs"],
                "omitted": omitted_pairs,
            }
        )
    if omitted_weak:
        truncations.append(
            {
                "code": "weak_candidates_truncated",
                "limit": normalized_limits["max_pairs"],
                "omitted": omitted_weak,
            }
        )

    semantic_review_queue = _semantic_review_queue(
        conflict_candidates,
        weak_candidates,
        selected_nodes,
        normalized_limits["semantic_review_limit"],
    )
    plan = {
        "schema_version": 1,
        "now": now,
        "inputs": {
            "fingerprints": fingerprints,
            "scanned_documents": len(documents),
            "scanned_claims": len(claims),
            "scanned_sources": len(sources),
            "scanned_campaigns": len(campaigns),
        },
        "limits": normalized_limits,
        "seeds": seeds,
        "selected_nodes": selected_nodes,
        "weak_candidates": weak_candidates,
        "conflict_candidates": conflict_candidates,
        "semantic_review_queue": semantic_review_queue,
        "truncations": truncations,
        "invariants": {
            "read_only": True,
            "conflicts_are_review_only": True,
            "automatic_evidence_mutation": False,
            "automatic_trust_mutation": False,
            "automatic_lifecycle_mutation": False,
        },
    }
    if repository_fingerprints(root_path) != fingerprints:
        raise HygienePlanError("후보 계획 도중 입력이 변경되어 결과를 폐기함")
    return plan


__all__ = [
    "HygienePlanError",
    "build_hygiene_plan",
    "canonical_plan_bytes",
    "repository_fingerprints",
]
