#!/usr/bin/env python3
"""Deterministic control plane for the Living Wiki.

The LLM does judgment-heavy research. This CLI owns boring invariants: IDs,
attribution, immutable artifact copies, evidence links, confidence gates,
tamper-evident events, validation, and derived dashboards.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import mimetypes
import os
import re
import shutil
import sys
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "state"
RAW = ROOT / "raw" / "sources"
WIKI = ROOT / "wiki"
REPORTS = ROOT / "reports"
EVALUATIONS = ROOT / "evaluations"
OKF_BUNDLE = WIKI
ZERO_HASH = "0" * 64

STATE_FILES: dict[str, dict[str, Any]] = {
    "actors": {"version": 1, "actors": []},
    "sources": {"version": 1, "sources": []},
    "claims": {"version": 1, "claims": []},
    "reviews": {"version": 1, "reviews": []},
    "campaigns": {"version": 1, "campaigns": []},
    "proposals": {"version": 1, "proposals": []},
}

SOURCE_LEVELS = {f"S{i}": i for i in range(5)}
CLAIM_LEVELS = {f"C{i}": i for i in range(5)}
CLAIM_KINDS = {"fact", "interpretation", "hypothesis", "prediction", "value"}
RELATIONS = {"supports", "contradicts", "contextualizes"}
SOURCE_TYPES = {
    "paper",
    "standard",
    "official-doc",
    "dataset",
    "code",
    "talk",
    "video",
    "article",
    "book",
    "note",
    "other",
}


class WikiError(RuntimeError):
    pass


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def today() -> str:
    return dt.datetime.now(dt.timezone.utc).date().isoformat()


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def digest_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def stable_id(prefix: str, *parts: Any) -> str:
    joined = "\x1f".join(str(p).strip() for p in parts)
    return f"{prefix}-{digest_text(joined)[:12].upper()}"


def slugify(value: str, limit: int = 72) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9가-힣]+", "-", value).strip("-")
    return (value[:limit].rstrip("-") or "item")


def parse_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return sorted({part.strip() for part in value.split(",") if part.strip()})


def latest_meaningful_timestamp(*groups: Iterable[dict[str, Any]]) -> str:
    candidates: list[str] = []
    for group in groups:
        for item in group:
            for key in ("updated_at", "last_verified_at", "retrieved_at", "created_at"):
                value = item.get(key)
                if isinstance(value, str) and re.match(r"^\d{4}-\d{2}-\d{2}T", value):
                    candidates.append(value)
            confidence_at = item.get("confidence", {}).get("computed_at") if isinstance(item.get("confidence"), dict) else None
            if isinstance(confidence_at, str):
                candidates.append(confidence_at)
    return max(candidates, default="2026-07-11T00:00:00+09:00")


def ensure_layout() -> None:
    for path in (STATE, RAW, WIKI, REPORTS, EVALUATIONS):
        path.mkdir(parents=True, exist_ok=True)
    for name, default in STATE_FILES.items():
        path = STATE / f"{name}.json"
        if not path.exists():
            atomic_write_json(path, default)
    events = STATE / "events.jsonl"
    if not events.exists():
        events.touch()


def load_json(path: Path, default: Any | None = None) -> Any:
    if not path.exists():
        if default is not None:
            return default
        raise WikiError(f"Missing file: {path.relative_to(ROOT)}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise WikiError(f"Invalid JSON in {path.relative_to(ROOT)}: {exc}") from exc


def atomic_write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temp, path)


def atomic_write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(value, encoding="utf-8")
    os.replace(temp, path)


def yaml_value(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    return json.dumps(value, ensure_ascii=False)


def write_okf_concept(path: Path, metadata: dict[str, Any], body: str) -> None:
    ordered = ["type", "title", "description", "resource", "tags", "timestamp"]
    keys = [key for key in ordered if key in metadata]
    keys.extend(sorted(key for key in metadata if key not in ordered))
    frontmatter = ["---"] + [f"{key}: {yaml_value(metadata[key])}" for key in keys] + ["---", ""]
    atomic_write_text(path, "\n".join(frontmatter) + body.rstrip() + "\n")


def md_cell(value: Any) -> str:
    return str(value if value is not None else "-").replace("\n", " ").replace("|", "\\|")


def actor_page_name(actor_id: str) -> str:
    return f"actor-{slugify(actor_id.replace(':', '-'))}.md"


def split_okf_frontmatter(text: str) -> tuple[dict[str, str], str, list[str]]:
    """Parse the flat OKF profile used here without making PyYAML mandatory.

    OKF permits arbitrary YAML. If PyYAML is available we use it for strict YAML
    parsing; the fallback validates top-level keys and the required scalar type,
    while tolerating indented/list continuations for portability.
    """
    errors: list[str] = []
    if not text.startswith("---\n"):
        return {}, text, ["missing YAML frontmatter at byte 0"]
    lines = text.splitlines()
    try:
        closing = lines.index("---", 1)
    except ValueError:
        return {}, text, ["unclosed YAML frontmatter"]
    raw = "\n".join(lines[1:closing])
    data: dict[str, Any] | None = None
    try:
        import yaml  # type: ignore

        loaded = yaml.safe_load(raw)
        if not isinstance(loaded, dict):
            errors.append("frontmatter must be a YAML mapping")
        else:
            data = loaded
    except ImportError:
        data = {}
        seen: set[str] = set()
        for number, line in enumerate(lines[1:closing], 2):
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            if "\t" in line:
                errors.append(f"frontmatter line {number}: tabs are not allowed in this profile")
                continue
            if line[0].isspace() or line.lstrip().startswith("- "):
                continue
            match = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*):(?:\s*(.*))?$", line)
            if not match:
                errors.append(f"frontmatter line {number}: unsupported or malformed YAML")
                continue
            key, value = match.group(1), (match.group(2) or "").strip()
            if key in seen:
                errors.append(f"frontmatter line {number}: duplicate key '{key}'")
            seen.add(key)
            data[key] = value.strip("'\"")
    except Exception as exc:
        return {}, text, [f"invalid YAML frontmatter: {exc}"]
    normalized = {str(key): value for key, value in (data or {}).items()}
    body = "\n".join(lines[closing + 1 :])
    return normalized, body, errors


def collection(name: str) -> list[dict[str, Any]]:
    ensure_layout()
    payload = load_json(STATE / f"{name}.json")
    items = payload.get(name)
    if not isinstance(items, list):
        raise WikiError(f"state/{name}.json must contain a '{name}' list")
    return items


def save_collection(name: str, items: Iterable[dict[str, Any]]) -> None:
    ordered = sorted(items, key=lambda item: item["id"])
    atomic_write_json(STATE / f"{name}.json", {"version": 1, name: ordered})


def find(items: Iterable[dict[str, Any]], item_id: str, kind: str) -> dict[str, Any]:
    for item in items:
        if item.get("id") == item_id:
            return item
    raise WikiError(f"Unknown {kind}: {item_id}")


def actor_exists(actor_id: str) -> bool:
    return any(item.get("id") == actor_id and item.get("status") == "active" for item in collection("actors"))


def actor_record(actor_id: str) -> dict[str, Any]:
    return find(collection("actors"), actor_id, "actor")


def actor_independence_group(actor: dict[str, Any]) -> str:
    return actor.get("metadata", {}).get("independence_group") or actor["id"]


def require_actor(actor_id: str) -> None:
    if not actor_exists(actor_id):
        raise WikiError(f"Unknown or inactive actor: {actor_id}")


def event_lines() -> list[dict[str, Any]]:
    ensure_layout()
    events: list[dict[str, Any]] = []
    for number, line in enumerate((STATE / "events.jsonl").read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise WikiError(f"Invalid event JSON on line {number}: {exc}") from exc
    return events


def append_event(actor: str, action: str, subject: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    events = event_lines()
    previous = events[-1].get("event_hash", ZERO_HASH) if events else ZERO_HASH
    body = {
        "id": stable_id("EVT", previous, actor, action, subject, utc_now()),
        "at": utc_now(),
        "actor": actor,
        "action": action,
        "subject": subject,
        "details": details or {},
        "prev_hash": previous,
    }
    body["event_hash"] = digest_text(canonical_json(body))
    with (STATE / "events.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(canonical_json(body) + "\n")
        fh.flush()
        os.fsync(fh.fileno())
    return body


def bootstrap(args: argparse.Namespace) -> None:
    ensure_layout()
    actors = collection("actors")
    defaults = [
        {
            "id": "human:owner",
            "kind": "human",
            "display_name": "Wiki Owner",
            "roles": ["director", "contributor", "reviewer", "policy-approver"],
            "capabilities": ["discover", "submit", "review", "direct", "approve"],
            "status": "active",
            "created_at": utc_now(),
            "metadata": {"independence_group": "human:owner"},
        },
        {
            "id": "agent:codex",
            "kind": "agent",
            "display_name": "Codex Research Maintainer",
            "roles": ["maintainer", "researcher", "contributor", "reviewer"],
            "capabilities": ["discover", "archive", "extract", "synthesize", "review", "lint", "propose"],
            "status": "active",
            "created_at": utc_now(),
            "metadata": {
                "model": "runtime-provided",
                "prompt_hash": None,
                "independence_group": "openai-codex-session",
            },
        },
    ]
    changed = False
    for default in defaults:
        if not any(a.get("id") == default["id"] for a in actors):
            actors.append(default)
            changed = True
    if changed:
        save_collection("actors", actors)
    if not event_lines():
        append_event("agent:codex", "bootstrap", "wiki", {"harness_version": "3.1.0"})
    render_all(actor="agent:codex", log=False)
    print("Living Wiki initialized.")


def actor_add(args: argparse.Namespace) -> None:
    ensure_layout()
    actors = collection("actors")
    actor_id = args.id
    if any(a.get("id") == actor_id for a in actors):
        raise WikiError(f"Actor already exists: {actor_id}")
    if args.kind not in {"human", "agent"}:
        raise WikiError("Actor kind must be human or agent")
    item = {
        "id": actor_id,
        "kind": args.kind,
        "display_name": args.name,
        "roles": parse_csv(args.roles),
        "capabilities": parse_csv(args.capabilities),
        "status": "active",
        "created_at": utc_now(),
        "metadata": json.loads(args.metadata) if args.metadata else {},
    }
    actors.append(item)
    save_collection("actors", actors)
    append_event(args.by, "actor.add", actor_id, {"kind": args.kind})
    print(actor_id)


def validate_url(url: str | None) -> None:
    if not url:
        return
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise WikiError(f"Invalid http(s) URL: {url}")


def source_add(args: argparse.Namespace) -> None:
    require_actor(args.actor)
    validate_url(args.url)
    if args.source_type not in SOURCE_TYPES:
        raise WikiError(f"Unknown source type: {args.source_type}")
    if args.level not in SOURCE_LEVELS:
        raise WikiError(f"Unknown source level: {args.level}")

    source_file = Path(args.file).expanduser().resolve() if args.file else None
    if source_file and not source_file.is_file():
        raise WikiError(f"Source artifact does not exist: {source_file}")
    artifact_hash = digest_file(source_file) if source_file else None
    identity = args.url or args.title
    source_id = stable_id("SRC", identity, artifact_hash or args.published or "metadata-only")
    sources = collection("sources")
    if any(s.get("id") == source_id for s in sources):
        print(source_id)
        return

    artifact = None
    if source_file:
        destination_dir = RAW / source_id
        destination_dir.mkdir(parents=True, exist_ok=True)
        destination = destination_dir / source_file.name
        if destination.exists() and digest_file(destination) != artifact_hash:
            raise WikiError(f"Immutable raw artifact collision: {destination.relative_to(ROOT)}")
        if not destination.exists():
            shutil.copy2(source_file, destination)
        artifact = {
            "path": destination.relative_to(ROOT).as_posix(),
            "sha256": artifact_hash,
            "bytes": destination.stat().st_size,
            "media_type": (
                "text/markdown"
                if destination.suffix.lower() in {".md", ".markdown"}
                else mimetypes.guess_type(destination.name)[0] or "application/octet-stream"
            ),
        }

    item = {
        "id": source_id,
        "title": args.title,
        "url": args.url,
        "source_type": args.source_type,
        "authors": parse_csv(args.authors),
        "publisher": args.publisher,
        "published_at": args.published,
        "retrieved_at": utc_now(),
        "publication_status": args.publication_status,
        "independence_group": args.independence_group or source_id,
        "source_level": args.level,
        "assessment": {
            "assessed_by": args.actor,
            "assessed_at": utc_now(),
            "rationale": args.rationale,
            "quality_markers": parse_csv(args.quality_markers),
            "conflicts_of_interest": parse_csv(args.conflicts),
        },
        "artifact": artifact,
        "license": args.license,
        "notes": args.notes,
        "status": "active",
    }
    sources.append(item)
    save_collection("sources", sources)
    append_event(args.actor, "source.add", source_id, {"url": args.url, "level": args.level})
    print(source_id)


def source_assess(args: argparse.Namespace) -> None:
    require_actor(args.actor)
    if args.level not in SOURCE_LEVELS:
        raise WikiError(f"Unknown source level: {args.level}")
    sources = collection("sources")
    item = find(sources, args.source, "source")
    previous = item.get("source_level", "S0")
    item["source_level"] = args.level
    item["assessment"] = {
        **item.get("assessment", {}),
        "assessed_by": args.actor,
        "assessed_at": utc_now(),
        "rationale": args.rationale,
        "quality_markers": parse_csv(args.quality_markers) or item.get("assessment", {}).get("quality_markers", []),
        "conflicts_of_interest": parse_csv(args.conflicts) or item.get("assessment", {}).get("conflicts_of_interest", []),
    }
    save_collection("sources", sources)
    append_event(args.actor, "source.assess", args.source, {"from": previous, "to": args.level})
    print(args.source)


def claim_add(args: argparse.Namespace) -> None:
    require_actor(args.actor)
    creator = actor_record(args.actor)
    if args.kind not in CLAIM_KINDS:
        raise WikiError(f"Unknown claim kind: {args.kind}")
    normalized = re.sub(r"\s+", " ", args.statement).strip()
    if len(normalized) < 8:
        raise WikiError("Claim statement is too short")
    scope = args.scope.strip() or "general"
    claim_id = stable_id("CLM", normalized.casefold(), scope.casefold())
    claims = collection("claims")
    if any(c.get("id") == claim_id for c in claims):
        print(claim_id)
        return
    item = {
        "id": claim_id,
        "statement": normalized,
        "kind": args.kind,
        "scope": scope,
        "created_by": args.actor,
        "created_by_group": actor_independence_group(creator),
        "created_at": utc_now(),
        "last_verified_at": None,
        "freshness": args.freshness,
        "valid_at": args.valid_at,
        "tags": parse_csv(args.tags),
        "evidence": [],
        "confidence": {
            "level": "C0",
            "status": "open",
            "supporting_groups": 0,
            "contradicting_groups": 0,
            "independent_reviews": 0,
            "rationale": "No linked evidence.",
        },
        "supersedes": parse_csv(args.supersedes),
        "notes": args.notes,
    }
    claims.append(item)
    save_collection("claims", claims)
    append_event(args.actor, "claim.add", claim_id, {"kind": args.kind, "scope": scope})
    print(claim_id)


def evidence_add(args: argparse.Namespace) -> None:
    require_actor(args.actor)
    if args.relation not in RELATIONS:
        raise WikiError(f"Unknown evidence relation: {args.relation}")
    if not 1 <= args.strength <= 4:
        raise WikiError("Evidence strength must be 1..4")
    claims = collection("claims")
    sources = collection("sources")
    claim = find(claims, args.claim, "claim")
    find(sources, args.source, "source")
    if not args.locator.strip():
        raise WikiError("Evidence requires an exact page/section/timestamp locator")
    edge = {
        "source_id": args.source,
        "relation": args.relation,
        "locator": args.locator.strip(),
        "strength": args.strength,
        "added_by": args.actor,
        "added_at": utc_now(),
        "note": args.note,
    }
    signature = (args.source, args.relation, args.locator.strip())
    for existing in claim.get("evidence", []):
        if (existing.get("source_id"), existing.get("relation"), existing.get("locator")) == signature:
            print(args.claim)
            return
    claim.setdefault("evidence", []).append(edge)
    claim["evidence"] = sorted(claim["evidence"], key=lambda e: (e["source_id"], e["relation"], e["locator"]))
    save_collection("claims", claims)
    append_event(args.actor, "claim.evidence.add", args.claim, {"source": args.source, "relation": args.relation})
    print(args.claim)


def review_add(args: argparse.Namespace) -> None:
    require_actor(args.actor)
    reviewer = actor_record(args.actor)
    if args.verdict not in {"supports", "contradicts", "uncertain"}:
        raise WikiError("Review verdict must be supports, contradicts, or uncertain")
    find(collection("claims"), args.claim, "claim")
    reviews = collection("reviews")
    review_id = stable_id("REV", args.claim, args.actor, args.verdict, args.rationale)
    if any(r.get("id") == review_id for r in reviews):
        print(review_id)
        return
    item = {
        "id": review_id,
        "claim_id": args.claim,
        "actor_id": args.actor,
        "reviewer_group": actor_independence_group(reviewer),
        "verdict": args.verdict,
        "adversarial": bool(args.adversarial),
        "rationale": args.rationale,
        "created_at": utc_now(),
        "status": "active",
    }
    reviews.append(item)
    save_collection("reviews", reviews)
    append_event(args.actor, "review.add", review_id, {"claim": args.claim, "verdict": args.verdict})
    print(review_id)


def calculate_confidence(claim: dict[str, Any], sources_by_id: dict[str, dict[str, Any]], reviews: list[dict[str, Any]]) -> dict[str, Any]:
    supporting: list[tuple[dict[str, Any], dict[str, Any]]] = []
    contradicting: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for edge in claim.get("evidence", []):
        source = sources_by_id.get(edge.get("source_id"))
        if not source or source.get("status") != "active":
            continue
        if edge.get("relation") == "supports":
            supporting.append((edge, source))
        elif edge.get("relation") == "contradicts":
            contradicting.append((edge, source))

    support_groups = {source.get("independence_group", source["id"]) for _, source in supporting}
    contradict_groups = {source.get("independence_group", source["id"]) for _, source in contradicting}
    high_support = [
        (edge, source)
        for edge, source in supporting
        if SOURCE_LEVELS.get(source.get("source_level", "S0"), 0) >= 3 and int(edge.get("strength", 0)) >= 3
    ]
    strong_contradiction = any(
        SOURCE_LEVELS.get(source.get("source_level", "S0"), 0) >= 3 and int(edge.get("strength", 0)) >= 3
        for edge, source in contradicting
    )
    quality_markers = {
        marker
        for _, source in supporting
        for marker in source.get("assessment", {}).get("quality_markers", [])
    }

    creator_group = claim.get("created_by_group") or claim.get("created_by")
    active_reviews = [
        review
        for review in reviews
        if review.get("claim_id") == claim["id"]
        and review.get("status") == "active"
        and (review.get("reviewer_group") or review.get("actor_id")) != creator_group
    ]
    positive_reviews = [review for review in active_reviews if review.get("verdict") == "supports"]
    adversarial_reviews = [review for review in positive_reviews if review.get("adversarial")]

    level = 0
    reasons: list[str] = []
    if supporting:
        level = 1
        reasons.append("at least one traceable supporting source")
    if high_support or len(support_groups) >= 2:
        level = 2
        reasons.append("a strong direct source or two independent source groups")
    if len(support_groups) >= 2 and high_support and positive_reviews and not strong_contradiction:
        level = 3
        reasons.append("independent corroboration and independent review")
    robust_marker = bool(quality_markers & {"peer-reviewed", "official-record", "reproduced", "standard"})
    high_source_ids = {source["id"] for _, source in high_support}
    if (
        len(support_groups) >= 2
        and len(high_source_ids) >= 2
        and len({r.get("reviewer_group") or r["actor_id"] for r in positive_reviews}) >= 2
        and adversarial_reviews
        and robust_marker
        and not strong_contradiction
    ):
        level = 4
        reasons.append("multiple high-quality sources, adversarial review, and robust validation marker")

    status = "open"
    if supporting:
        status = "supported"
    if contradicting:
        status = "contested"
    if strong_contradiction and not supporting:
        status = "refuted"

    return {
        "level": f"C{level}",
        "status": status,
        "supporting_groups": len(support_groups),
        "contradicting_groups": len(contradict_groups),
        "independent_reviews": len({r.get("reviewer_group") or r["actor_id"] for r in active_reviews}),
        "positive_independent_reviews": len({r.get("reviewer_group") or r["actor_id"] for r in positive_reviews}),
        "adversarial_reviewed": bool(adversarial_reviews),
        "strong_contradiction": strong_contradiction,
        "quality_markers": sorted(quality_markers),
        "rationale": "; ".join(reasons) if reasons else "No qualifying supporting evidence.",
        "computed_at": utc_now(),
    }


def evaluate(args: argparse.Namespace) -> None:
    require_actor(args.actor)
    claims = collection("claims")
    sources = collection("sources")
    reviews = collection("reviews")
    by_id = {source["id"]: source for source in sources}
    changed = 0
    for claim in claims:
        old = {k: v for k, v in claim.get("confidence", {}).items() if k != "computed_at"}
        new = calculate_confidence(claim, by_id, reviews)
        comparable = {k: v for k, v in new.items() if k != "computed_at"}
        if old != comparable:
            changed += 1
            claim["confidence"] = new
            claim["last_verified_at"] = utc_now()
        elif "computed_at" not in claim.get("confidence", {}):
            claim["confidence"] = new
    save_collection("claims", claims)
    render_epistemic_dashboard(claims, sources)
    if changed:
        append_event(args.actor, "claims.evaluate", "all", {"changed": changed})
    print(f"Evaluated {len(claims)} claims; {changed} changed.")


def campaign_add(args: argparse.Namespace) -> None:
    require_actor(args.actor)
    campaign_id = stable_id("CMP", args.question.casefold(), args.interest)
    campaigns = collection("campaigns")
    if any(c.get("id") == campaign_id for c in campaigns):
        print(campaign_id)
        return
    item = {
        "id": campaign_id,
        "interest_id": args.interest,
        "question": args.question.strip(),
        "why_now": args.why,
        "priority": args.priority,
        "status": "queued",
        "created_by": args.actor,
        "created_at": utc_now(),
        "max_sources": args.max_sources,
        "max_minutes": args.max_minutes,
        "required_independent_groups": args.independent_groups,
        "stop_conditions": parse_csv(args.stop) or ["two rounds with no novel claims", "budget exhausted"],
        "counter_search_required": True,
        "source_ids": [],
        "claim_ids": [],
        "notes": [],
    }
    campaigns.append(item)
    save_collection("campaigns", campaigns)
    append_event(args.actor, "campaign.add", campaign_id, {"question": args.question})
    print(campaign_id)


def campaign_update(args: argparse.Namespace) -> None:
    require_actor(args.actor)
    if args.status not in {"queued", "active", "blocked", "completed", "cancelled"}:
        raise WikiError("Invalid campaign status")
    campaigns = collection("campaigns")
    campaign = find(campaigns, args.campaign, "campaign")
    old = campaign.get("status")
    campaign["status"] = args.status
    campaign["updated_at"] = utc_now()
    if args.note:
        campaign.setdefault("notes", []).append({"at": utc_now(), "actor": args.actor, "text": args.note})
    campaign["source_ids"] = sorted(set(campaign.get("source_ids", [])) | set(parse_csv(args.sources)))
    campaign["claim_ids"] = sorted(set(campaign.get("claim_ids", [])) | set(parse_csv(args.claims)))
    save_collection("campaigns", campaigns)
    append_event(args.actor, "campaign.update", args.campaign, {"from": old, "to": args.status})
    print(args.campaign)


def next_task(args: argparse.Namespace) -> None:
    campaigns = [c for c in collection("campaigns") if c.get("status") in {"active", "queued"}]
    if not campaigns:
        print("No queued research campaign.")
        return
    campaigns.sort(key=lambda c: (c.get("status") != "active", -float(c.get("priority", 0)), c.get("created_at", "")))
    campaign = campaigns[0]
    if args.json:
        print(json.dumps(campaign, ensure_ascii=False, indent=2, sort_keys=True))
        return
    print(f"Campaign: {campaign['id']}")
    print(f"Question: {campaign['question']}")
    print(f"Budget: {campaign['max_sources']} sources / {campaign['max_minutes']} minutes")
    print(f"Independent groups required: {campaign['required_independent_groups']}")
    print("Counter-search: required")
    print("Stop: " + "; ".join(campaign.get("stop_conditions", [])))


def proposal_add(args: argparse.Namespace) -> None:
    require_actor(args.actor)
    proposal_id = stable_id("RFC", args.title.casefold(), args.problem.casefold())
    proposals = collection("proposals")
    if any(p.get("id") == proposal_id for p in proposals):
        print(proposal_id)
        return
    item = {
        "id": proposal_id,
        "title": args.title,
        "problem": args.problem,
        "proposed_change": args.change,
        "evidence": parse_csv(args.evidence),
        "benchmark": args.benchmark,
        "risks": parse_csv(args.risks),
        "rollback": args.rollback,
        "created_by": args.actor,
        "created_at": utc_now(),
        "status": "proposed",
        "approvals": [],
    }
    proposals.append(item)
    save_collection("proposals", proposals)
    path = ROOT / "governance" / "proposals" / f"{proposal_id.lower()}-{slugify(args.title)}.md"
    body = f"""# {proposal_id}: {args.title}

Status: proposed  
Proposed by: `{args.actor}`  
Created: {item['created_at']}

## Problem

{args.problem}

## Proposed change

{args.change}

## Evidence

{chr(10).join(f'- `{e}`' for e in item['evidence']) or '- 아직 연결된 근거 없음'}

## Benchmark and acceptance gate

{args.benchmark}

## Risks

{chr(10).join(f'- {risk}' for risk in item['risks']) or '- 미기록'}

## Rollback

{args.rollback}
"""
    atomic_write_text(path, body)
    append_event(args.actor, "proposal.add", proposal_id, {"title": args.title})
    print(proposal_id)


def verify_event_chain(errors: list[str]) -> int:
    previous = ZERO_HASH
    count = 0
    try:
        events = event_lines()
    except WikiError as exc:
        errors.append(str(exc))
        return 0
    for index, event in enumerate(events, 1):
        count += 1
        claimed = event.get("event_hash")
        body = {key: value for key, value in event.items() if key != "event_hash"}
        expected = digest_text(canonical_json(body))
        if event.get("prev_hash") != previous:
            errors.append(f"events.jsonl line {index}: broken prev_hash")
        if claimed != expected:
            errors.append(f"events.jsonl line {index}: invalid event_hash")
        previous = claimed or ZERO_HASH
    return count


def okf_validation_findings() -> tuple[list[str], list[str], int]:
    """Validate the `wiki/` directory as the OKF v0.1 bundle boundary."""
    errors: list[str] = []
    warnings: list[str] = []
    concepts = 0
    if not OKF_BUNDLE.is_dir():
        return ["bundle directory wiki/ is missing"], warnings, concepts
    for path in sorted(OKF_BUNDLE.rglob("*.md")):
        relative = path.relative_to(OKF_BUNDLE).as_posix()
        text = path.read_text(encoding="utf-8")
        if path.name in {"index.md", "log.md"}:
            if text.startswith("---\n"):
                errors.append(f"{relative}: reserved {path.name} must remain frontmatter-free in this profile")
            if path.name == "index.md":
                if not re.search(r"(?m)^#\s+\S", text):
                    errors.append(f"{relative}: index must contain at least one section heading")
            else:
                for heading in re.findall(r"(?m)^##\s+(.+?)\s*$", text):
                    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", heading):
                        errors.append(f"{relative}: log date heading is not ISO YYYY-MM-DD: {heading}")
            if "[[" in text:
                warnings.append(f"{relative}: Obsidian wikilink is not a portable OKF relationship")
            continue
        concepts += 1
        metadata, _, parse_errors = split_okf_frontmatter(text)
        errors.extend(f"{relative}: {item}" for item in parse_errors)
        type_value = metadata.get("type")
        if not isinstance(type_value, str) or not type_value.strip():
            errors.append(f"{relative}: required non-empty frontmatter key 'type' is missing")
        if "[[" in text:
            warnings.append(f"{relative}: replace Obsidian wikilinks with standard Markdown links")
    return errors, warnings, concepts


def okf_profile_findings() -> tuple[list[str], list[str]]:
    """Enforce the stricter Living Wiki producer profile on top of OKF core."""
    errors: list[str] = []
    warnings: list[str] = []
    if not OKF_BUNDLE.is_dir():
        return ["bundle directory wiki/ is missing"], warnings
    link_pattern = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")
    for path in sorted(OKF_BUNDLE.rglob("*.md")):
        relative = path.relative_to(OKF_BUNDLE).as_posix()
        text = path.read_text(encoding="utf-8")
        if path.name not in {"index.md", "log.md"}:
            metadata, _, parse_errors = split_okf_frontmatter(text)
            if parse_errors:
                continue
            for key in ("title", "description", "timestamp"):
                value = metadata.get(key)
                if not isinstance(value, str) or not value.strip():
                    errors.append(f"{relative}: Living Wiki profile requires non-empty '{key}'")
        for target in link_pattern.findall(text):
            target = target.strip().split(maxsplit=1)[0].strip("<>")
            if not target or target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            clean = target.split("#", 1)[0].split("?", 1)[0]
            resolved = (OKF_BUNDLE / clean.lstrip("/")) if clean.startswith("/") else (path.parent / clean)
            if resolved.is_dir():
                resolved = resolved / "index.md"
            try:
                resolved.resolve().relative_to(OKF_BUNDLE.resolve())
            except ValueError:
                warnings.append(f"{relative}: link leaves the portable bundle: {target}")
                continue
            if not resolved.exists():
                errors.append(f"{relative}: broken internal link: {target}")

    expected = {
        "sources": len(collection("sources")),
        "claims": len(collection("claims")),
        "actors": len(collection("actors")),
        "reviews": len(collection("reviews")),
        "campaigns": len(collection("campaigns")),
    }
    actual = {
        "sources": len(list((OKF_BUNDLE / "sources").glob("src-*.md"))),
        "claims": len(list((OKF_BUNDLE / "claims").glob("clm-*.md"))),
        "actors": len(list((OKF_BUNDLE / "actors").glob("actor-*.md"))),
        "reviews": len(list((OKF_BUNDLE / "reviews").glob("rev-*.md"))),
        "campaigns": len(list((OKF_BUNDLE / "campaigns").glob("cmp-*.md"))),
    }
    for kind in expected:
        if actual[kind] != expected[kind]:
            errors.append(f"projection parity mismatch for {kind}: state={expected[kind]} bundle={actual[kind]}")
    return errors, warnings


def okf_validate(args: argparse.Namespace) -> None:
    errors, warnings, count = okf_validation_findings()
    profile_errors, profile_warnings = okf_profile_findings()
    print(f"OKF v0.1 bundle: wiki/ ({count} concept documents)")
    for warning in warnings:
        print(f"CORE WARN: {warning}")
    for error in errors:
        print(f"CORE ERROR: {error}")
    for warning in profile_warnings:
        print(f"PROFILE WARN: {warning}")
    for error in profile_errors:
        print(f"PROFILE ERROR: {error}")
    if errors or profile_errors:
        raise WikiError(
            f"OKF validation failed with {len(errors)} core and {len(profile_errors)} profile error(s)"
        )
    print(
        f"OKF core and Living Wiki profile validation passed with "
        f"{len(warnings) + len(profile_warnings)} warning(s)."
    )


def validation_findings() -> tuple[list[str], list[str], dict[str, int]]:
    errors: list[str] = []
    warnings: list[str] = []
    try:
        actors = collection("actors")
        sources = collection("sources")
        claims = collection("claims")
        reviews = collection("reviews")
        campaigns = collection("campaigns")
    except WikiError as exc:
        return [str(exc)], [], {}

    def duplicate_ids(items: list[dict[str, Any]], label: str) -> None:
        ids = [item.get("id") for item in items]
        duplicates = sorted({item_id for item_id in ids if ids.count(item_id) > 1})
        if duplicates:
            errors.append(f"Duplicate {label} IDs: {', '.join(duplicates)}")

    duplicate_ids(actors, "actor")
    duplicate_ids(sources, "source")
    duplicate_ids(claims, "claim")
    duplicate_ids(reviews, "review")
    duplicate_ids(campaigns, "campaign")

    actor_ids = {a.get("id") for a in actors}
    source_ids = {s.get("id") for s in sources}
    claim_ids = {c.get("id") for c in claims}
    for source in sources:
        if source.get("assessment", {}).get("assessed_by") not in actor_ids:
            errors.append(f"{source.get('id')}: assessment has unknown actor")
        if source.get("source_level") not in SOURCE_LEVELS:
            errors.append(f"{source.get('id')}: invalid source level")
        artifact = source.get("artifact")
        if artifact:
            path = ROOT / artifact.get("path", "")
            if not path.is_file():
                errors.append(f"{source.get('id')}: raw artifact missing")
            elif digest_file(path) != artifact.get("sha256"):
                errors.append(f"{source.get('id')}: raw artifact hash mismatch")
        else:
            warnings.append(f"{source.get('id')}: metadata-only source; immutable snapshot absent")
        if source.get("source_level") == "S0":
            warnings.append(f"{source.get('id')}: source credibility unassessed")

    for claim in claims:
        if claim.get("created_by") not in actor_ids:
            errors.append(f"{claim.get('id')}: unknown creator")
        if claim.get("kind") not in CLAIM_KINDS:
            errors.append(f"{claim.get('id')}: invalid kind")
        if claim.get("confidence", {}).get("level") not in CLAIM_LEVELS:
            errors.append(f"{claim.get('id')}: invalid confidence level")
        for edge in claim.get("evidence", []):
            if edge.get("source_id") not in source_ids:
                errors.append(f"{claim.get('id')}: unknown source {edge.get('source_id')}")
            if edge.get("added_by") not in actor_ids:
                errors.append(f"{claim.get('id')}: evidence has unknown actor")
            if edge.get("relation") not in RELATIONS:
                errors.append(f"{claim.get('id')}: invalid evidence relation")
            if not edge.get("locator"):
                errors.append(f"{claim.get('id')}: evidence missing locator")
        if not claim.get("evidence"):
            warnings.append(f"{claim.get('id')}: no evidence")
        if claim.get("confidence", {}).get("status") == "contested":
            warnings.append(f"{claim.get('id')}: contested claim")

    for review in reviews:
        if review.get("actor_id") not in actor_ids:
            errors.append(f"{review.get('id')}: unknown reviewer")
        if review.get("claim_id") not in claim_ids:
            errors.append(f"{review.get('id')}: unknown claim")

    for campaign in campaigns:
        for source_id in campaign.get("source_ids", []):
            if source_id not in source_ids:
                errors.append(f"{campaign.get('id')}: unknown source {source_id}")
        for claim_id in campaign.get("claim_ids", []):
            if claim_id not in claim_ids:
                errors.append(f"{campaign.get('id')}: unknown claim {claim_id}")

    event_count = verify_event_chain(errors)
    okf_errors, okf_warnings, okf_count = okf_validation_findings()
    profile_errors, profile_warnings = okf_profile_findings()
    errors.extend(f"OKF: {item}" for item in okf_errors)
    warnings.extend(f"OKF: {item}" for item in okf_warnings)
    errors.extend(f"OKF profile: {item}" for item in profile_errors)
    warnings.extend(f"OKF profile: {item}" for item in profile_warnings)
    counts = {
        "actors": len(actors),
        "sources": len(sources),
        "claims": len(claims),
        "reviews": len(reviews),
        "campaigns": len(campaigns),
        "events": event_count,
        "okf_concepts": okf_count,
    }
    return errors, warnings, counts


def validate(args: argparse.Namespace) -> None:
    errors, warnings, counts = validation_findings()
    print("Counts: " + ", ".join(f"{key}={value}" for key, value in counts.items()))
    for warning in warnings:
        print(f"WARN: {warning}")
    for error in errors:
        print(f"ERROR: {error}")
    if errors:
        raise WikiError(f"Validation failed with {len(errors)} error(s)")
    print(f"Validation passed with {len(warnings)} warning(s).")


def render_epistemic_dashboard(claims: list[dict[str, Any]], sources: list[dict[str, Any]]) -> None:
    claim_rows = []
    for claim in sorted(claims, key=lambda c: (-CLAIM_LEVELS.get(c.get("confidence", {}).get("level", "C0"), 0), c["id"])):
        statement = claim.get("statement", "").replace("|", "\\|")
        confidence = claim.get("confidence", {})
        claim_rows.append(
            f"| `{claim['id']}` | {confidence.get('level', 'C0')} | {confidence.get('status', 'open')} | "
            f"{statement} | {confidence.get('supporting_groups', 0)} | {confidence.get('contradicting_groups', 0)} |"
        )
    source_rows = []
    for source in sorted(sources, key=lambda s: (-SOURCE_LEVELS.get(s.get("source_level", "S0"), 0), s["id"])):
        title = source.get("title", "").replace("|", "\\|")
        source_rows.append(
            f"| `{source['id']}` | {source.get('source_level', 'S0')} | {source.get('publication_status') or '-'} | "
            f"{title} | `{source.get('independence_group', '-')}` |"
        )
    timestamp = latest_meaningful_timestamp(claims, sources)
    body = f"""---
type: Epistemic Dashboard
title: Epistemic dashboard
description: Claim and source evidence-maturity levels derived from the canonical ledger.
tags: [trust, provenance, claims]
timestamp: '{timestamp}'
generated: true
---

<!-- AUTOGENERATED by tools/wiki.py. Do not edit manually. -->
# Epistemic dashboard

신뢰 레벨은 진실 확률이 아니라 현재 증거 성숙도의 파생 표시다. 상세 근거는 `state/claims.json`과 `state/sources.json`을 확인한다.

## Claims

| ID | Level | Status | Statement | Supporting groups | Contradicting groups |
|---|---:|---|---|---:|---:|
""" + ("\n".join(claim_rows) if claim_rows else "| - | - | - | 아직 등록된 주장 없음 | - | - |") + """

## Sources

| ID | Level | Publication status | Title | Independence group |
|---|---:|---|---|---|
""" + ("\n".join(source_rows) if source_rows else "| - | - | - | 아직 등록된 출처 없음 | - |") + "\n"
    atomic_write_text(WIKI / "epistemic-dashboard.md", body)


def render_index(claims: list[dict[str, Any]], sources: list[dict[str, Any]], campaigns: list[dict[str, Any]]) -> None:
    timestamp = latest_meaningful_timestamp(claims, sources, campaigns)
    body = f"""<!-- AUTOGENERATED by tools/wiki.py. Do not edit manually. -->
# Living Wiki index

Knowledge state timestamp: {timestamp}

## Start here

* [Overview](overview.md) - 현재 연구 범위와 구조.
* [Synthesis](synthesis.md) - 현재의 종합 관점.
* [Epistemic dashboard](epistemic-dashboard.md) - 주장·출처 신뢰 상태.
* [Open questions](open-questions.md) - 미해결 질문.
* [Contradictions](contradictions.md) - 충돌과 반증.
* [Current position](perspectives/self-evolving-wiki-position.md) - 위키가 현재 채택한 관점과 반증 조건.
* [OKF profile](okf-profile.md) - 이 bundle의 OKF v0.1 확장 규약.
* [Claims](claims/index.md) - atomic claim과 exact evidence projection.
* [Actors](actors/index.md) - 사람과 Agent contributor registry.
* [Campaigns](campaigns/index.md) - bounded autonomous research queue.
* [Trust policy](trust/index.md) - S0-S4/C0-C4 producer profile.
* [Governance](governance/index.md) - 헌장과 결정 기록.

## State

- Sources: {len(sources)}
- Claims: {len(claims)}
- Research campaigns: {len(campaigns)}
- Active/queued campaigns: {sum(c.get('status') in {'active', 'queued'} for c in campaigns)}

## Source pages

"""
    pages = sorted((WIKI / "sources").glob("*.md"))
    body += "\n".join(f"* [{page.stem}](sources/{page.name})" for page in pages if page.name not in {"index.md", "log.md"}) or "* 아직 없음"
    body += "\n\n## Concept pages\n\n"
    pages = sorted((WIKI / "concepts").glob("*.md"))
    body += "\n".join(f"* [{page.stem}](concepts/{page.name})" for page in pages if page.name not in {"index.md", "log.md"}) or "* 아직 없음"
    body += "\n"
    atomic_write_text(WIKI / "index.md", body)


def render_okf_state_projection() -> None:
    actors = collection("actors")
    sources = collection("sources")
    claims = collection("claims")
    reviews = collection("reviews")
    campaigns = collection("campaigns")
    source_by_id = {source["id"]: source for source in sources}
    claims_by_source: dict[str, list[str]] = {}
    for claim in claims:
        for evidence in claim.get("evidence", []):
            claims_by_source.setdefault(evidence.get("source_id", ""), []).append(claim["id"])

    for actor in actors:
        metadata = {
            "type": "Actor",
            "title": actor.get("display_name") or actor["id"],
            "description": f"{actor.get('kind', 'unknown')} contributor {actor['id']} in the Living Wiki.",
            "tags": ["actor", actor.get("kind", "unknown"), *actor.get("roles", [])],
            "timestamp": actor.get("created_at") or "2026-07-11T00:00:00+09:00",
            "actor_id": actor["id"],
            "generated": True,
        }
        body = f"""<!-- AUTOGENERATED from state/actors.json. -->
# {actor.get('display_name') or actor['id']}

| Field | Value |
|---|---|
| Canonical actor ID | `{actor['id']}` |
| Kind | `{actor.get('kind', '-')}` |
| Status | `{actor.get('status', '-')}` |
| Independence group | `{actor_independence_group(actor)}` |

## Roles

{chr(10).join(f'- `{role}`' for role in actor.get('roles', [])) or '- None'}

## Capabilities

{chr(10).join(f'- `{capability}`' for capability in actor.get('capabilities', [])) or '- None'}

This document records identity and operating role. Actor kind does not itself increase or decrease claim truth.
"""
        write_okf_concept(WIKI / "actors" / actor_page_name(actor["id"]), metadata, body)

    for source in sources:
        assessment = source.get("assessment", {})
        rationale = re.sub(r"\s+", " ", str(assessment.get("rationale") or "Unassessed source."))
        metadata: dict[str, Any] = {
            "type": "Reference",
            "title": source.get("title") or source["id"],
            "description": f"{source.get('source_type', 'unknown')} source {source['id']} assessed {source.get('source_level', 'S0')}.",
            "tags": ["source", source.get("source_type", "unknown"), source.get("source_level", "S0")],
            "timestamp": assessment.get("assessed_at") or source.get("retrieved_at") or "2026-07-11T00:00:00+09:00",
            "source_id": source["id"],
            "source_level": source.get("source_level", "S0"),
            "generated": True,
        }
        if source.get("url"):
            metadata["resource"] = source["url"]
        artifact = source.get("artifact") or {}
        body = f"""<!-- AUTOGENERATED from state/sources.json. -->
# {source.get('title') or source['id']}

## Source identity

| Field | Value |
|---|---|
| Canonical source ID | `{source['id']}` |
| Type | `{source.get('source_type', '-')}` |
| Authors | {md_cell(', '.join(source.get('authors', [])) or '-')} |
| Publisher | {md_cell(source.get('publisher'))} |
| Publication status | {md_cell(source.get('publication_status'))} |
| Published | {md_cell(source.get('published_at'))} |
| Retrieved | {md_cell(source.get('retrieved_at'))} |
| Independence group | `{source.get('independence_group', source['id'])}` |
| License | {md_cell(source.get('license'))} |

## Scoped assessment

- Level: **{source.get('source_level', 'S0')}**
- Rationale: {rationale}
- Quality markers: {', '.join(f'`{item}`' for item in assessment.get('quality_markers', [])) or 'None'}
- Conflicts of interest: {', '.join(f'`{item}`' for item in assessment.get('conflicts_of_interest', [])) or 'None recorded'}

## Preserved artifact

- Path outside bundle: `{artifact.get('path', 'metadata-only')}`
- SHA-256: `{artifact.get('sha256', 'not available')}`
- Media type: `{artifact.get('media_type', 'not available')}`

## Claims using this source

{chr(10).join(f'- [{claim_id}](../claims/{claim_id.lower()}.md)' for claim_id in sorted(set(claims_by_source.get(source['id'], [])))) or '- None'}
"""
        if source.get("url"):
            body += f"\n# Citations\n\n[1] [{source.get('title') or source['id']}]({source['url']})\n"
        write_okf_concept(WIKI / "sources" / f"{source['id'].lower()}.md", metadata, body)

    for claim in claims:
        confidence = claim.get("confidence", {})
        creator_path = f"../actors/{actor_page_name(claim.get('created_by', 'unknown'))}"
        metadata = {
            "type": "Claim",
            "title": claim["id"],
            "description": claim.get("statement", "")[:300],
            "tags": ["claim", claim.get("kind", "unknown"), confidence.get("level", "C0"), confidence.get("status", "open")],
            "timestamp": claim.get("last_verified_at") or claim.get("created_at") or "2026-07-11T00:00:00+09:00",
            "claim_id": claim["id"],
            "generated": True,
        }
        evidence_rows: list[str] = []
        citations: list[str] = []
        citation_seen: set[str] = set()
        for evidence in claim.get("evidence", []):
            source_id = evidence.get("source_id", "")
            source = source_by_id.get(source_id, {})
            source_title = source.get("title") or source_id
            evidence_rows.append(
                f"| {evidence.get('relation', '-')} | [{md_cell(source_title)}](../sources/{source_id.lower()}.md) | "
                f"{md_cell(evidence.get('locator'))} | {evidence.get('strength', '-')} | `{evidence.get('added_by', '-')}` |"
            )
            url = source.get("url")
            if url and url not in citation_seen:
                citation_seen.add(url)
                citations.append(f"[{len(citations) + 1}] [{source_title}]({url})")
        body = f"""<!-- AUTOGENERATED from state/claims.json. -->
# {claim['id']}

> {claim.get('statement', '')}

## Scope and lifecycle

| Field | Value |
|---|---|
| Kind | `{claim.get('kind', '-')}` |
| Scope | {md_cell(claim.get('scope'))} |
| Valid at | {md_cell(claim.get('valid_at'))} |
| Freshness class | `{claim.get('freshness', '-')}` |
| Created by | [{claim.get('created_by', '-')}]({creator_path}) |
| Created at | `{claim.get('created_at', '-')}` |
| Last verified | `{claim.get('last_verified_at') or 'not verified'}` |

## Evidence maturity

| Field | Value |
|---|---|
| Display level | **{confidence.get('level', 'C0')}** |
| Status | **{confidence.get('status', 'open')}** |
| Supporting independence groups | {confidence.get('supporting_groups', 0)} |
| Contradicting independence groups | {confidence.get('contradicting_groups', 0)} |
| Independent reviewer groups | {confidence.get('independent_reviews', 0)} |
| Strong unresolved contradiction | {confidence.get('strong_contradiction', False)} |

Rationale: {confidence.get('rationale', 'Not evaluated.')}

## Evidence edges

| Relation | Source | Exact locator | Strength | Added by |
|---|---|---|---:|---|
{chr(10).join(evidence_rows) or '| - | - | - | - | - |'}
"""
        if citations:
            body += "\n# Citations\n\n" + "\n".join(citations) + "\n"
        write_okf_concept(WIKI / "claims" / f"{claim['id'].lower()}.md", metadata, body)

    for review in reviews:
        claim_id = review.get("claim_id", "")
        actor_id = review.get("actor_id", "")
        metadata = {
            "type": "Review",
            "title": review["id"],
            "description": f"{review.get('verdict', 'unknown')} review of {claim_id} by {actor_id}.",
            "tags": ["review", review.get("verdict", "unknown"), "adversarial" if review.get("adversarial") else "standard"],
            "timestamp": review.get("created_at") or "2026-07-11T00:00:00+09:00",
            "review_id": review["id"],
            "generated": True,
        }
        body = f"""<!-- AUTOGENERATED from state/reviews.json. -->
# {review['id']}

- Claim: [{claim_id}](../claims/{claim_id.lower()}.md)
- Reviewer: [{actor_id}](../actors/{actor_page_name(actor_id)})
- Reviewer independence group: `{review.get('reviewer_group', actor_id)}`
- Verdict: **{review.get('verdict', '-')}**
- Adversarial: `{review.get('adversarial', False)}`
- Status: `{review.get('status', '-')}`

## Rationale

{review.get('rationale') or 'No rationale recorded.'}
"""
        write_okf_concept(WIKI / "reviews" / f"{review['id'].lower()}.md", metadata, body)

    for campaign in campaigns:
        metadata = {
            "type": "Research Campaign",
            "title": campaign["id"],
            "description": campaign.get("question", "")[:300],
            "tags": ["research-campaign", campaign.get("status", "unknown"), campaign.get("interest_id", "unknown")],
            "timestamp": campaign.get("updated_at") or campaign.get("created_at") or "2026-07-11T00:00:00+09:00",
            "campaign_id": campaign["id"],
            "generated": True,
        }
        source_links = [f"[{item}](../sources/{item.lower()}.md)" for item in campaign.get("source_ids", [])]
        claim_links = [f"[{item}](../claims/{item.lower()}.md)" for item in campaign.get("claim_ids", [])]
        body = f"""<!-- AUTOGENERATED from state/campaigns.json. -->
# {campaign['id']}

> {campaign.get('question', '')}

## Control

| Field | Value |
|---|---|
| Status | **{campaign.get('status', '-')}** |
| Interest | `{campaign.get('interest_id', '-')}` |
| Priority | {campaign.get('priority', '-')} |
| Created by | [{campaign.get('created_by', '-')}](../actors/{actor_page_name(campaign.get('created_by', 'unknown'))}) |
| Max sources | {campaign.get('max_sources', '-')} |
| Max minutes | {campaign.get('max_minutes', '-')} |
| Required independent groups | {campaign.get('required_independent_groups', '-')} |
| Counter-search required | {campaign.get('counter_search_required', False)} |

Why now: {campaign.get('why_now') or '-'}

## Stop conditions

{chr(10).join(f'- {item}' for item in campaign.get('stop_conditions', [])) or '- None'}

## Sources

{chr(10).join(f'- {item}' for item in source_links) or '- None yet'}

## Claims

{chr(10).join(f'- {item}' for item in claim_links) or '- None yet'}
"""
        write_okf_concept(WIKI / "campaigns" / f"{campaign['id'].lower()}.md", metadata, body)

    trust = load_json(ROOT / "config" / "trust-policy.json")
    source_rows = "\n".join(f"| {level} | {md_cell(text)} |" for level, text in trust.get("source_levels", {}).items())
    claim_rows = "\n".join(f"| {level} | {md_cell(text)} |" for level, text in trust.get("claim_levels", {}).items())
    trust_body = f"""<!-- AUTOGENERATED from config/trust-policy.json. -->
# Living Wiki trust policy

This is a Living Wiki producer profile, not an OKF core trust schema.

## Source levels

| Level | Meaning |
|---|---|
{source_rows}

## Claim levels

| Level | Meaning |
|---|---|
{claim_rows}

## Hard principle

{trust.get('principle', '')}
"""
    write_okf_concept(
        WIKI / "trust" / "trust-policy.md",
        {
            "type": "Trust Policy",
            "title": "Living Wiki trust policy",
            "description": "Producer-defined S0-S4 source and C0-C4 claim evidence-maturity profile.",
            "tags": ["trust", "claims", "sources", "producer-extension"],
            "timestamp": "2026-07-11T00:00:00+09:00",
            "generated": True,
        },
        trust_body,
    )

    for filename, type_name, title, description in [
        ("constitution.md", "Governance Policy", "Living Wiki constitution", "Actor parity, epistemic rules, authority boundaries, and self-evolution policy."),
        ("decision-log.md", "Governance Decision Register", "Living Wiki decision log", "Architectural decisions and their explicit rationale."),
    ]:
        canonical = ROOT / "governance" / filename
        body = "<!-- AUTOGENERATED projection of governance/%s. -->\n" % filename + canonical.read_text(encoding="utf-8")
        write_okf_concept(
            WIKI / "governance" / filename,
            {
                "type": type_name,
                "title": title,
                "description": description,
                "tags": ["governance", "living-wiki"],
                "timestamp": "2026-07-11T00:00:00+09:00",
                "generated": True,
            },
            body,
        )


def render_okf_subindexes() -> None:
    for folder_name, heading in [
        ("sources", "References"),
        ("concepts", "Concepts"),
        ("perspectives", "Perspectives"),
        ("claims", "Claims"),
        ("actors", "Actors"),
        ("reviews", "Reviews"),
        ("campaigns", "Research Campaigns"),
        ("trust", "Trust Policies"),
        ("governance", "Governance"),
    ]:
        folder = WIKI / folder_name
        folder.mkdir(parents=True, exist_ok=True)
        entries: list[str] = []
        for path in sorted(folder.glob("*.md")):
            if path.name in {"index.md", "log.md"}:
                continue
            metadata, _, _ = split_okf_frontmatter(path.read_text(encoding="utf-8"))
            title = str(metadata.get("title") or path.stem)
            description = str(metadata.get("description") or "")
            suffix = f" - {description}" if description else ""
            entries.append(f"* [{title}]({path.name}){suffix}")
        body = f"# {heading}\n\n" + ("\n".join(entries) if entries else "* No concepts yet.") + "\n"
        atomic_write_text(folder / "index.md", body)


def render_okf_log() -> None:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for event in reversed(event_lines()):
        date = str(event.get("at", ""))[:10]
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
            grouped.setdefault(date, []).append(event)
    lines = ["# Living Wiki update log", ""]
    for date in sorted(grouped, reverse=True):
        lines.extend([f"## {date}"])
        for event in grouped[date]:
            lines.append(
                f"* **{event.get('action', 'Update')}**: `{event.get('subject', '-')}` by `{event.get('actor', '-')}`."
            )
        lines.append("")
    atomic_write_text(WIKI / "log.md", "\n".join(lines).rstrip() + "\n")


def render_all(actor: str, log: bool = True) -> None:
    claims = collection("claims")
    sources = collection("sources")
    campaigns = collection("campaigns")
    render_epistemic_dashboard(claims, sources)
    render_okf_state_projection()
    render_index(claims, sources, campaigns)
    render_okf_subindexes()
    if log:
        append_event(actor, "wiki.render", "derived-views", {"sources": len(sources), "claims": len(claims)})
    render_okf_log()


def render_cmd(args: argparse.Namespace) -> None:
    require_actor(args.actor)
    render_all(args.actor, log=not args.no_log)
    print("Rendered the OKF bundle indexes, log, and epistemic dashboard")


def lint(args: argparse.Namespace) -> None:
    require_actor(args.actor)
    errors, warnings, counts = validation_findings()
    claims = collection("claims")
    sources = collection("sources")
    source_by_id = {source["id"]: source for source in sources}
    extra: list[str] = []
    for claim in claims:
        support_sources = [
            source_by_id[e["source_id"]]
            for e in claim.get("evidence", [])
            if e.get("relation") == "supports" and e.get("source_id") in source_by_id
        ]
        if len(support_sources) > 1:
            groups = {source.get("independence_group", source["id"]) for source in support_sources}
            if len(groups) == 1:
                extra.append(f"{claim['id']}: multiple supporting sources collapse to one independence group")
        if claim.get("confidence", {}).get("level") in {"C3", "C4"} and not claim.get("last_verified_at"):
            errors.append(f"{claim['id']}: promoted claim lacks last_verified_at")
    report = f"""# Wiki lint report — {today()}

## Summary

- Errors: {len(errors)}
- Warnings: {len(warnings)}
- Epistemic findings: {len(extra)}
- Counts: {', '.join(f'{k}={v}' for k, v in counts.items())}

## Errors

{chr(10).join(f'- {item}' for item in errors) or '- None'}

## Warnings

{chr(10).join(f'- {item}' for item in warnings) or '- None'}

## Epistemic findings

{chr(10).join(f'- {item}' for item in extra) or '- None'}

## Interpretation

경고는 자동 삭제나 자동 강등 명령이 아니다. 담당 actor가 원문과 scope를 확인한 뒤 evidence, status, freshness를 갱신해야 한다.
"""
    atomic_write_text(REPORTS / "latest-lint.md", report)
    append_event(args.actor, "wiki.lint", "all", {"errors": len(errors), "warnings": len(warnings), "findings": len(extra)})
    print(f"Wrote reports/latest-lint.md ({len(errors)} errors, {len(warnings) + len(extra)} warnings/findings)")
    if errors:
        raise WikiError("Lint found structural errors")


def snapshot(args: argparse.Namespace) -> None:
    require_actor(args.actor)
    manifest: dict[str, str] = {}
    roots = [
        ROOT / name
        for name in (
            "config",
            "state",
            "raw",
            "wiki",
            "research",
            "governance",
            "evolution",
            "evaluations",
            "reports",
            "prompts",
            "scripts",
            "tools",
            "tests",
            "docs",
        )
    ]
    for base in roots:
        if not base.exists():
            continue
        for path in sorted(base.rglob("*")):
            if (EVALUATIONS / "snapshots") in path.parents:
                continue
            if path.is_file() and not path.name.endswith(".tmp") and "__pycache__" not in path.parts:
                manifest[path.relative_to(ROOT).as_posix()] = digest_file(path)
    for name in ("README.md", "AGENTS.md", "pyproject.toml", ".gitignore"):
        path = ROOT / name
        if path.is_file():
            manifest[name] = digest_file(path)
    snapshot_id = stable_id("SNP", canonical_json(manifest))
    payload = {
        "id": snapshot_id,
        "created_at": utc_now(),
        "created_by": args.actor,
        "harness_version": load_json(ROOT / "config" / "wiki.json").get("harness_version"),
        "files": manifest,
        "root_hash": digest_text(canonical_json(manifest)),
    }
    path = EVALUATIONS / "snapshots" / f"{snapshot_id}.json"
    atomic_write_json(path, payload)
    append_event(args.actor, "snapshot.create", snapshot_id, {"files": len(manifest), "root_hash": payload["root_hash"]})
    print(path.relative_to(ROOT))


def status(args: argparse.Namespace) -> None:
    ensure_layout()
    actors = collection("actors")
    sources = collection("sources")
    claims = collection("claims")
    campaigns = collection("campaigns")
    events = event_lines()
    levels = {level: 0 for level in CLAIM_LEVELS}
    for claim in claims:
        levels[claim.get("confidence", {}).get("level", "C0")] += 1
    version = load_json(ROOT / "config" / "wiki.json").get("harness_version", "unknown")
    print(f"Living Wiki {version}")
    print(f"Actors: {len(actors)} | Sources: {len(sources)} | Claims: {len(claims)} | Events: {len(events)}")
    print("Claim levels: " + " ".join(f"{level}={count}" for level, count in levels.items()))
    print("Campaigns: " + ", ".join(f"{state}={sum(c.get('status') == state for c in campaigns)}" for state in ["active", "queued", "blocked", "completed"]))
    if events:
        print(f"Last event: {events[-1]['at']} {events[-1]['action']} {events[-1]['subject']}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Living Wiki deterministic control plane")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("bootstrap", help="create state files and default human/agent actors")
    p.set_defaults(func=bootstrap)

    p = sub.add_parser("actor-add", help="register a human or agent contributor")
    p.add_argument("--id", required=True)
    p.add_argument("--kind", required=True, choices=["human", "agent"])
    p.add_argument("--name", required=True)
    p.add_argument("--roles", default="contributor")
    p.add_argument("--capabilities", default="submit,review")
    p.add_argument("--metadata")
    p.add_argument("--by", default="human:owner")
    p.set_defaults(func=actor_add)

    p = sub.add_parser("source-add", help="register source metadata and optionally preserve an immutable file")
    p.add_argument("--actor", default="agent:codex")
    p.add_argument("--title", required=True)
    p.add_argument("--url")
    p.add_argument("--file")
    p.add_argument("--source-type", required=True, choices=sorted(SOURCE_TYPES))
    p.add_argument("--authors")
    p.add_argument("--publisher")
    p.add_argument("--published")
    p.add_argument("--publication-status", default="unknown")
    p.add_argument("--independence-group")
    p.add_argument("--level", default="S0", choices=sorted(SOURCE_LEVELS))
    p.add_argument("--rationale", required=True)
    p.add_argument("--quality-markers")
    p.add_argument("--conflicts")
    p.add_argument("--license")
    p.add_argument("--notes")
    p.set_defaults(func=source_add)

    p = sub.add_parser("source-assess", help="revise a scoped source assessment")
    p.add_argument("--actor", default="agent:codex")
    p.add_argument("--source", required=True)
    p.add_argument("--level", required=True, choices=sorted(SOURCE_LEVELS))
    p.add_argument("--rationale", required=True)
    p.add_argument("--quality-markers")
    p.add_argument("--conflicts")
    p.set_defaults(func=source_assess)

    p = sub.add_parser("claim-add", help="create an atomic claim")
    p.add_argument("--actor", default="agent:codex")
    p.add_argument("--statement", required=True)
    p.add_argument("--kind", required=True, choices=sorted(CLAIM_KINDS))
    p.add_argument("--scope", default="general")
    p.add_argument("--freshness", default="normal", choices=["fast", "normal", "slow", "timeless"])
    p.add_argument("--valid-at")
    p.add_argument("--tags")
    p.add_argument("--supersedes")
    p.add_argument("--notes")
    p.set_defaults(func=claim_add)

    p = sub.add_parser("evidence-add", help="link a claim to an exact source location")
    p.add_argument("--actor", default="agent:codex")
    p.add_argument("--claim", required=True)
    p.add_argument("--source", required=True)
    p.add_argument("--relation", required=True, choices=sorted(RELATIONS))
    p.add_argument("--locator", required=True)
    p.add_argument("--strength", type=int, default=2)
    p.add_argument("--note")
    p.set_defaults(func=evidence_add)

    p = sub.add_parser("review-add", help="record an attributed claim review")
    p.add_argument("--actor", required=True)
    p.add_argument("--claim", required=True)
    p.add_argument("--verdict", required=True, choices=["supports", "contradicts", "uncertain"])
    p.add_argument("--adversarial", action="store_true")
    p.add_argument("--rationale", required=True)
    p.set_defaults(func=review_add)

    p = sub.add_parser("evaluate", help="recompute claim evidence maturity levels")
    p.add_argument("--actor", default="agent:codex")
    p.set_defaults(func=evaluate)

    p = sub.add_parser("campaign-add", help="queue a bounded autonomous research campaign")
    p.add_argument("--actor", default="human:owner")
    p.add_argument("--interest", required=True)
    p.add_argument("--question", required=True)
    p.add_argument("--why", required=True)
    p.add_argument("--priority", type=float, default=0.5)
    p.add_argument("--max-sources", type=int, default=12)
    p.add_argument("--max-minutes", type=int, default=45)
    p.add_argument("--independent-groups", type=int, default=2)
    p.add_argument("--stop")
    p.set_defaults(func=campaign_add)

    p = sub.add_parser("campaign-update", help="update campaign state and attach outputs")
    p.add_argument("--actor", default="agent:codex")
    p.add_argument("--campaign", required=True)
    p.add_argument("--status", required=True)
    p.add_argument("--sources")
    p.add_argument("--claims")
    p.add_argument("--note")
    p.set_defaults(func=campaign_update)

    p = sub.add_parser("next-task", help="show the highest-priority research campaign")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=next_task)

    p = sub.add_parser("proposal-add", help="propose, but do not auto-apply, a harness change")
    p.add_argument("--actor", default="agent:codex")
    p.add_argument("--title", required=True)
    p.add_argument("--problem", required=True)
    p.add_argument("--change", required=True)
    p.add_argument("--evidence")
    p.add_argument("--benchmark", required=True)
    p.add_argument("--risks")
    p.add_argument("--rollback", required=True)
    p.set_defaults(func=proposal_add)

    p = sub.add_parser("render", help="regenerate deterministic human-readable views")
    p.add_argument("--actor", default="agent:codex")
    p.add_argument("--no-log", action="store_true", help="pure/idempotence-check export without a new event")
    p.set_defaults(func=render_cmd)

    p = sub.add_parser("lint", help="run structural and epistemic health checks")
    p.add_argument("--actor", default="agent:codex")
    p.set_defaults(func=lint)

    p = sub.add_parser("validate", help="validate references, hashes, schemas, and event chain")
    p.set_defaults(func=validate)

    p = sub.add_parser("okf-validate", help="validate wiki/ against the pinned OKF v0.1 profile")
    p.set_defaults(func=okf_validate)

    p = sub.add_parser("snapshot", help="write a content-addressed evaluation snapshot")
    p.add_argument("--actor", default="agent:codex")
    p.set_defaults(func=snapshot)

    p = sub.add_parser("status", help="show a compact wiki status")
    p.set_defaults(func=status)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.func(args)
        return 0
    except WikiError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
