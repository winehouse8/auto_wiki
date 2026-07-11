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
import io
import json
import mimetypes
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse


TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))
ROOT = TOOLS_DIR.parents[0]
STATE = ROOT / "state"
RAW = ROOT / "raw" / "sources"
QUARANTINE = ROOT / "raw" / "quarantine"
WIKI = ROOT / "wiki"
REPORTS = ROOT / "reports"
EVALUATIONS = ROOT / "evaluations"
EVALUATION_REPORTS = EVALUATIONS / "reports"
OKF_BUNDLE = WIKI
ZERO_HASH = "0" * 64
SOURCE_GRANDFATHER_MANIFEST = ROOT / "migrations" / "v3.1-source-grandfather.json"
SOURCE_GRANDFATHER_MANIFEST_SHA256 = "6c7ecd0c7a99a679534de7ca265fb3254b4091720c98f168619c6cf60c792dac"

STATE_FILES: dict[str, dict[str, Any]] = {
    "actors": {"version": 1, "actors": []},
    "sources": {"version": 1, "sources": []},
    "claims": {"version": 1, "claims": []},
    "reviews": {"version": 1, "reviews": []},
    "campaigns": {"version": 1, "campaigns": []},
    "proposals": {"version": 1, "proposals": []},
    "collaborations": {"version": 1, "collaborations": []},
    "admissions": {"version": 1, "admissions": []},
    "runs": {"version": 1, "runs": []},
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


def admission_record_digest(item: dict[str, Any]) -> str:
    material = {
        key: item.get(key)
        for key in ("id", "candidate", "decision", "status", "created_by", "created_at", "policy_effect")
    }
    return digest_text(canonical_json(material))


def external_report_digest(item: dict[str, Any]) -> str:
    return digest_text(canonical_json({key: value for key, value in item.items() if key != "report_digest"}))


def admission_integrity_findings(item: dict[str, Any], *, require_digest: bool = True) -> list[str]:
    findings: list[str] = []
    candidate = item.get("candidate", {})
    decision = item.get("decision", {})
    effect = item.get("policy_effect")
    if not isinstance(candidate, dict) or not isinstance(decision, dict):
        return ["candidate and decision must be objects"]
    if item.get("status") != decision.get("decision"):
        findings.append("top-level status does not match decision.decision")
    if effect == "advisory_only":
        expected_id = stable_id("ADM", candidate.get("id"), canonical_json(decision))
    elif effect == "quarantine_only_no_source_promotion":
        assessment = decision.get("security_assessment", {})
        expected_id = stable_id(
            "ADM",
            "security",
            candidate.get("source_ref"),
            candidate.get("quarantine_artifact", {}).get("sha256"),
            canonical_json(assessment),
        )
        write_gate = assessment.get("gates", {}).get("write", {}) if isinstance(assessment, dict) else {}
        if decision.get("stage") != "write" or write_gate.get("decision") != decision.get("decision"):
            findings.append("security decision does not match the embedded write gate")
    else:
        return ["unknown policy_effect"]
    if item.get("id") != expected_id:
        findings.append("admission ID does not match canonical candidate/decision")
    recorded_digest = item.get("record_digest")
    if recorded_digest is None:
        if require_digest:
            findings.append("record_digest is missing")
    elif recorded_digest != admission_record_digest(item):
        findings.append("record_digest mismatch")
    return findings


def admission_digest_is_anchored(item: dict[str, Any]) -> bool:
    return any(
        event.get("subject") == item.get("id")
        and event.get("details", {}).get("record_digest") == item.get("record_digest")
        for event in event_lines()
    )


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
    for path in (STATE, RAW, QUARANTINE, WIKI, REPORTS, EVALUATIONS, EVALUATION_REPORTS):
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


def source_grandfather_ids() -> set[str]:
    """Load the pinned, finite v3.1 exception set for pre-admission sources."""

    if not SOURCE_GRANDFATHER_MANIFEST.is_file():
        raise WikiError("Pinned v3.1 source grandfather manifest is missing")
    if digest_file(SOURCE_GRANDFATHER_MANIFEST) != SOURCE_GRANDFATHER_MANIFEST_SHA256:
        raise WikiError("Pinned v3.1 source grandfather manifest hash drift")
    payload = load_json(SOURCE_GRANDFATHER_MANIFEST)
    ids = payload.get("source_ids", [])
    if (
        payload.get("schema_version") != "living-wiki-source-grandfather/v1"
        or not isinstance(ids, list)
        or len(ids) != payload.get("source_count")
        or len(set(ids)) != len(ids)
    ):
        raise WikiError("Pinned v3.1 source grandfather manifest schema is invalid")
    return set(ids)


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
        append_event(
            "agent:codex",
            "bootstrap",
            "wiki",
            {"harness_version": load_json(ROOT / "config" / "wiki.json").get("harness_version", "unknown")},
        )
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


def require_source_admission(
    admission_id: str | None,
    *,
    title: str,
    url: str | None,
) -> dict[str, Any]:
    """Require a positive advisory admission before the canonical writer runs."""

    if not admission_id:
        raise WikiError("New sources require --admission with an allow decision")
    admission = find(collection("admissions"), admission_id, "admission")
    integrity = admission_integrity_findings(admission)
    if integrity:
        raise WikiError(f"Source admission integrity failure: {'; '.join(integrity)}")
    if not admission_digest_is_anchored(admission):
        raise WikiError("Source admission digest is not anchored in the event chain")
    decision = admission.get("decision", {})
    expected_id = stable_id("ADM", admission.get("candidate", {}).get("id"), canonical_json(decision))
    if admission.get("id") != expected_id:
        raise WikiError(f"Source admission identity/decision integrity mismatch: {admission_id}")
    if (
        admission.get("status") != "allow"
        or decision.get("decision") != "allow"
        or admission.get("policy_effect") != "advisory_only"
    ):
        raise WikiError(f"Source admission is not an advisory allow decision: {admission_id}")
    candidate = admission.get("candidate", {})
    candidate_url = candidate.get("url")
    candidate_title = str(candidate.get("title") or "").strip().casefold()
    if url and candidate_url:
        import calibration

        try:
            if calibration.canonicalize_url(url) != calibration.canonicalize_url(candidate_url):
                raise WikiError("Source URL does not match the admitted candidate identity")
        except calibration.CalibrationError as exc:
            raise WikiError(f"Cannot verify admitted source identity: {exc}") from exc
    elif candidate_title != title.strip().casefold():
        raise WikiError("Source title does not match the admitted metadata-only candidate")
    return admission


def require_security_admission(admission_id: str | None, artifact_hash: str) -> dict[str, Any]:
    """Require a positive quarantine gate whose immutable hash matches the file."""

    if not admission_id:
        raise WikiError("File-backed sources require --security-admission with an allow decision")
    admission = find(collection("admissions"), admission_id, "security admission")
    integrity = admission_integrity_findings(admission)
    if integrity:
        raise WikiError(f"Security admission integrity failure: {'; '.join(integrity)}")
    if not admission_digest_is_anchored(admission):
        raise WikiError("Security admission digest is not anchored in the event chain")
    candidate = admission.get("candidate", {})
    decision = admission.get("decision", {})
    assessment = decision.get("security_assessment", {})
    expected_id = stable_id(
        "ADM",
        "security",
        candidate.get("source_ref"),
        candidate.get("quarantine_artifact", {}).get("sha256"),
        canonical_json(assessment),
    )
    write_gate = assessment.get("gates", {}).get("write", {}) if isinstance(assessment, dict) else {}
    if admission.get("id") != expected_id:
        raise WikiError(f"Security admission identity/assessment integrity mismatch: {admission_id}")
    if (
        admission.get("status") != "allow"
        or decision.get("decision") != "allow"
        or decision.get("stage") != "write"
        or write_gate.get("decision") != "allow"
        or admission.get("policy_effect") != "quarantine_only_no_source_promotion"
    ):
        raise WikiError(f"Security admission is not a quarantine allow decision: {admission_id}")
    artifact = candidate.get("quarantine_artifact", {})
    if artifact.get("sha256") != artifact_hash:
        raise WikiError("File hash does not match the security-admitted quarantine artifact")
    artifact_path = ROOT / str(artifact.get("path", ""))
    if not artifact_path.is_file() or digest_file(artifact_path) != artifact_hash:
        raise WikiError("Security-admitted quarantine artifact is missing or mutated")
    return admission


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
    source_admission = require_source_admission(args.admission, title=args.title, url=args.url)
    security_admission = (
        require_security_admission(args.security_admission, artifact_hash)
        if source_file and artifact_hash
        else None
    )
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
        "admission_ids": [
            source_admission["id"],
            *([security_admission["id"]] if security_admission else []),
        ],
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


def interest_seed(args: argparse.Namespace) -> None:
    """Seed due interest questions as bounded queued campaigns; execute no research."""

    require_actor(args.actor)
    if args.max_campaigns < 1:
        raise WikiError("--max-campaigns must be at least 1")
    import runtime

    try:
        now = runtime.parse_time(args.now)
    except runtime.RuntimeErrorBase as exc:
        raise WikiError(str(exc)) from exc
    config = load_json(ROOT / "config" / "interests.json")
    interests = config.get("interests", [])
    if not isinstance(interests, list):
        raise WikiError("config/interests.json must contain an interests list")
    campaigns = collection("campaigns")
    created: list[str] = []
    ordered_interests = sorted(
        (item for item in interests if isinstance(item, dict) and item.get("id")),
        key=lambda item: (-float(item.get("priority", 0.0)), str(item["id"])),
    )
    for interest in ordered_interests:
        if len(created) >= args.max_campaigns:
            break
        interest_id = str(interest["id"])
        related = [item for item in campaigns if item.get("interest_id") == interest_id]
        if any(item.get("status") in {"queued", "active"} for item in related):
            continue
        timestamps = []
        for item in related:
            value = item.get("updated_at") or item.get("created_at")
            if isinstance(value, str):
                try:
                    timestamps.append(runtime.parse_time(value))
                except runtime.RuntimeErrorBase:
                    raise WikiError(f"{item.get('id')}: invalid campaign timestamp {value}")
        cadence_days = max(0, int(interest.get("cadence_days", 0)))
        if timestamps and now < max(timestamps) + dt.timedelta(days=cadence_days):
            continue
        questions = [str(item).strip() for item in interest.get("questions", []) if str(item).strip()]
        if not questions:
            continue
        usage = {question: sum(item.get("question") == question for item in related) for question in questions}
        question = min(questions, key=lambda value: (usage[value], questions.index(value)))
        cycle_key = now.date().isoformat()
        campaign_id = stable_id("CMP", interest_id, question.casefold(), cycle_key)
        if any(item.get("id") == campaign_id for item in campaigns):
            continue
        limits = load_json(ROOT / "config" / "wiki.json").get("research_limits", {})
        item = {
            "id": campaign_id,
            "interest_id": interest_id,
            "question": question,
            "why_now": f"Interest cadence of {cadence_days} day(s) became due at {now.isoformat()}.",
            "priority": float(interest.get("priority", 0.5)),
            "status": "queued",
            "created_by": args.actor,
            "created_at": now.isoformat(),
            "cadence_days": cadence_days,
            "cycle_key": cycle_key,
            "max_sources": int(limits.get("default_max_sources_per_cycle", 12)),
            "max_minutes": int(limits.get("default_max_minutes_per_cycle", 45)),
            "required_independent_groups": int(limits.get("min_independent_source_groups", 2)),
            "stop_conditions": [
                "counter-search completed",
                f"{int(limits.get('stop_after_no_novel_claim_rounds', 2))} rounds with no novel claims",
                "budget exhausted",
            ],
            "counter_search_required": True,
            "source_ids": [],
            "claim_ids": [],
            "notes": [],
            "runtime": {"used_minutes": 0, "used_sources": 0, "met_stop_conditions": []},
        }
        campaigns.append(item)
        created.append(campaign_id)
        save_collection("campaigns", campaigns)
        append_event(
            args.actor,
            "campaign.seed",
            campaign_id,
            {"interest_id": interest_id, "cycle_key": cycle_key, "cadence_days": cadence_days},
        )
    if created:
        print("\n".join(created))
    else:
        print("No interest is due for campaign seeding.")


def render_proposal_record(item: dict[str, Any]) -> None:
    path = ROOT / "governance" / "proposals" / f"{item['id'].lower()}-{slugify(item['title'])}.md"
    reviews = item.get("approvals", [])
    review_lines = [
        f"- `{review.get('at', '-')}` — **{review.get('decision', '-')}** by "
        f"`{review.get('actor_id', '-')}`: {review.get('rationale', '-') }"
        for review in reviews
    ]
    body = f"""# {item['id']}: {item['title']}

Status: {item.get('status', 'proposed')}
Proposed by: `{item['created_by']}`
Created: {item['created_at']}

## Problem

{item['problem']}

## Proposed change

{item['proposed_change']}

## Evidence

{chr(10).join(f'- `{e}`' for e in item.get('evidence', [])) or '- 아직 연결된 근거 없음'}

## Benchmark and acceptance gate

{item['benchmark']}

## Risks

{chr(10).join(f'- {risk}' for risk in item.get('risks', [])) or '- 미기록'}

## Rollback

{item['rollback']}

## Review decisions

{chr(10).join(review_lines) or '- 아직 검토 결정 없음'}

## Implementation evidence

{f"- Release report: `{item.get('implementation_evidence', {}).get('release_report')}`" if item.get('implementation_evidence') else '- 아직 구현 완료 증거 없음'}
{f"- Component fingerprint: `{item.get('implementation_evidence', {}).get('component_fingerprint')}`" if item.get('implementation_evidence') else ''}
{f"- Production certified: `{item.get('implementation_evidence', {}).get('production_certified')}`" if item.get('implementation_evidence') else ''}
"""
    atomic_write_text(path, body)


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
    render_proposal_record(item)
    append_event(args.actor, "proposal.add", proposal_id, {"title": args.title})
    print(proposal_id)


def proposal_review(args: argparse.Namespace) -> None:
    require_actor(args.actor)
    actor = actor_record(args.actor)
    if args.decision not in {"approve", "request-changes", "reject"}:
        raise WikiError("Proposal decision must be approve, request-changes, or reject")
    if args.decision in {"approve", "reject"} and "policy-approver" not in actor.get("roles", []):
        raise WikiError("Only an actor with policy-approver role may approve or reject a harness proposal")
    proposals = collection("proposals")
    proposal = find(proposals, args.proposal, "proposal")
    review = {
        "actor_id": args.actor,
        "decision": args.decision,
        "rationale": args.rationale.strip(),
        "at": utc_now(),
    }
    signature = (review["actor_id"], review["decision"], review["rationale"])
    existing = proposal.setdefault("approvals", [])
    if any((item.get("actor_id"), item.get("decision"), item.get("rationale")) == signature for item in existing):
        print(args.proposal)
        return
    existing.append(review)
    if args.decision == "approve":
        proposal["status"] = "approved"
    elif args.decision == "request-changes":
        proposal["status"] = "changes-requested"
    else:
        proposal["status"] = "rejected"
    proposal["updated_at"] = review["at"]
    save_collection("proposals", proposals)
    render_proposal_record(proposal)
    append_event(args.actor, "proposal.review", args.proposal, {"decision": args.decision})
    print(args.proposal)


def proposal_implement(args: argparse.Namespace) -> None:
    """Close an approved RFC only after a passing, non-certifying release report."""

    require_actor(args.actor)
    actor = actor_record(args.actor)
    if not ({"maintainer", "policy-approver"} & set(actor.get("roles", []))):
        raise WikiError("Only a maintainer or policy-approver may mark an approved proposal implemented")
    report_path = Path(args.release_report).expanduser().resolve()
    report = load_json(report_path)
    if (
        report.get("release_id") != "living-wiki-v4"
        or report.get("passed") is not True
        or report.get("production_certified") is not False
    ):
        raise WikiError("Proposal implementation requires a passing truthful v4 release report")
    proposals = collection("proposals")
    proposal = find(proposals, args.proposal, "proposal")
    if proposal.get("status") == "implemented":
        print(args.proposal)
        return
    if proposal.get("status") != "approved":
        raise WikiError("Only an approved proposal can be marked implemented")
    proposal["status"] = "implemented"
    proposal["implemented_by"] = args.actor
    proposal["implemented_at"] = utc_now()
    proposal["updated_at"] = proposal["implemented_at"]
    archived_report = EVALUATION_REPORTS / f"v4-release-{report['component_fingerprint'][:16]}.json"
    if not archived_report.exists():
        atomic_write_json(archived_report, report)
    proposal["implementation_evidence"] = {
        "release_report": archived_report.relative_to(ROOT).as_posix(),
        "component_fingerprint": report["component_fingerprint"],
        "production_certified": False,
    }
    save_collection("proposals", proposals)
    render_proposal_record(proposal)
    append_event(
        args.actor,
        "proposal.implement",
        args.proposal,
        {"component_fingerprint": report["component_fingerprint"]},
    )
    print(args.proposal)


def calibration_run(args: argparse.Namespace) -> None:
    """Evaluate a frozen gold/admission fixture without changing trust levels."""

    require_actor(args.actor)
    import calibration

    fixture_path = Path(args.input).expanduser().resolve()
    fixture = calibration.load_fixture(fixture_path)
    report = calibration.build_report(fixture, small_n_threshold=args.small_n)
    output = Path(args.output).expanduser().resolve() if args.output else EVALUATION_REPORTS / "calibration-latest.json"
    atomic_write_json(output, report)
    append_event(
        args.actor,
        "calibration.evaluate",
        output.relative_to(ROOT).as_posix() if ROOT in output.parents else str(output),
        {
            "benchmark_sha256": report["benchmark_sha256"],
            "scorable": report["calibration"]["coverage"]["scorable_records"],
            "trust_policy_mutated": report["trust_policy_mutated"],
        },
    )
    print(output.relative_to(ROOT) if ROOT in output.parents else output)


def admission_check(args: argparse.Namespace) -> None:
    """Screen one source candidate and record an advisory admission decision."""

    require_actor(args.actor)
    import calibration

    candidate_path = Path(args.candidate).expanduser().resolve()
    candidate = load_json(candidate_path)
    if not isinstance(candidate, dict):
        raise WikiError("Admission candidate file must contain one JSON object")
    fixture_path = Path(args.registry_fixture).expanduser().resolve() if args.registry_fixture else None
    registry = None
    if fixture_path:
        fixture = calibration.load_fixture(fixture_path)
        registry = calibration.FixtureStatusRegistry(fixture.get("registry_entries", []))
    existing_sources = collection("sources")
    try:
        independence = calibration.cluster_independence([*existing_sources, candidate])
        decision = calibration.admission_decision(
            candidate,
            registry=registry,
            existing_sources=existing_sources,
            independence=independence,
        )
    except calibration.CalibrationError as exc:
        raise WikiError(str(exc)) from exc
    admission_id = stable_id("ADM", candidate.get("id"), canonical_json(decision))
    admissions = collection("admissions")
    if any(item.get("id") == admission_id for item in admissions):
        print(admission_id)
        return
    item = {
        "id": admission_id,
        "candidate": candidate,
        "decision": decision,
        "status": decision["decision"],
        "created_by": args.actor,
        "created_at": utc_now(),
        "policy_effect": "advisory_only",
    }
    item["record_digest"] = admission_record_digest(item)
    admissions.append(item)
    save_collection("admissions", admissions)
    append_event(
        args.actor,
        "source.admission.evaluate",
        admission_id,
        {"decision": decision["decision"], "record_digest": item["record_digest"]},
    )
    output = EVALUATION_REPORTS / f"{admission_id.lower()}.json"
    atomic_write_json(output, item)
    print(admission_id)


def admission_seal(args: argparse.Namespace) -> None:
    """Backfill or re-anchor one structurally valid admission record."""

    require_actor(args.actor)
    actor = actor_record(args.actor)
    if "maintainer" not in actor.get("roles", []):
        raise WikiError("Only a maintainer may seal an admission record")
    admissions = collection("admissions")
    item = find(admissions, args.admission, "admission")
    findings = admission_integrity_findings(item, require_digest=False)
    if findings:
        raise WikiError("Admission cannot be sealed: " + "; ".join(findings))
    item["record_digest"] = admission_record_digest(item)
    save_collection("admissions", admissions)
    append_event(
        args.actor,
        "admission.seal",
        args.admission,
        {"record_digest": item["record_digest"], "decision": item.get("status")},
    )
    print(args.admission)


def security_evaluate(args: argparse.Namespace) -> None:
    """Evaluate the frozen poisoning corpus without executing fixture content."""

    require_actor(args.actor)
    import security_gate

    corpus_path = Path(args.corpus).expanduser().resolve()
    try:
        corpus = security_gate.load_corpus(corpus_path)
        report = security_gate.evaluate_corpus(corpus)
    except (OSError, ValueError, TypeError) as exc:
        raise WikiError(f"Security corpus evaluation failed closed: {exc}") from exc
    output = Path(args.output).expanduser().resolve() if args.output else EVALUATION_REPORTS / "security-latest.json"
    atomic_write_json(output, report)
    append_event(
        args.actor,
        "security.corpus.evaluate",
        output.relative_to(ROOT).as_posix() if ROOT in output.parents else str(output),
        {
            "corpus_sha256": report["corpus_sha256"],
            "cases": report["case_count"],
            "attack_success_rate": report["metrics"]["attack_success_rate"],
            "benign_rejection_rate": report["metrics"]["benign_rejection_rate"],
            "payloads_executed": report["invariants"]["payloads_executed"],
        },
    )
    print(output.relative_to(ROOT) if ROOT in output.parents else output)


def security_screen(args: argparse.Namespace) -> None:
    """Quarantine and screen one local candidate; never promote it to a source."""

    require_actor(args.actor)
    import security_gate

    input_path = Path(args.input).expanduser().resolve()
    if not input_path.is_file():
        raise WikiError(f"Security input is not a regular file: {input_path}")
    try:
        raw = input_path.read_bytes()
        extracted = (
            Path(args.extracted_text).expanduser().resolve().read_text(encoding="utf-8")
            if args.extracted_text
            else None
        )
        assessment = security_gate.assess_content(
            raw,
            source_ref=args.source_ref,
            declared_media_type=args.media_type,
            extracted_text=extracted,
        )
    except (OSError, UnicodeError, ValueError, TypeError) as exc:
        raise WikiError(f"Security screening failed closed: {exc}") from exc

    safe_assessment = assessment.to_dict(include_normalized_text=False)
    content_hash = assessment.manifest["content_sha256"]
    suffix = input_path.suffix.lower() if re.fullmatch(r"\.[a-z0-9]{1,12}", input_path.suffix.lower()) else ".bin"
    quarantine_path = QUARANTINE / content_hash / f"artifact{suffix}"
    quarantine_path.parent.mkdir(parents=True, exist_ok=True)
    if quarantine_path.exists():
        if digest_file(quarantine_path) != content_hash:
            raise WikiError(f"Quarantine collision or mutation detected: {quarantine_path.relative_to(ROOT)}")
    else:
        shutil.copyfile(input_path, quarantine_path)
        if digest_file(quarantine_path) != content_hash:
            quarantine_path.unlink(missing_ok=True)
            raise WikiError("Quarantine copy hash mismatch")
        quarantine_path.chmod(0o444)

    admission_id = stable_id("ADM", "security", args.source_ref, content_hash, canonical_json(safe_assessment))
    admissions = collection("admissions")
    prior = next((item for item in admissions if item.get("id") == admission_id), None)
    if prior:
        print(admission_id)
        return
    decision = assessment.gates["write"]
    item = {
        "id": admission_id,
        "candidate": {
            "id": stable_id("CAND", args.source_ref, content_hash),
            "source_ref": args.source_ref,
            "quarantine_artifact": {
                "path": quarantine_path.relative_to(ROOT).as_posix(),
                "sha256": content_hash,
                "size_bytes": assessment.manifest["size_bytes"],
                "media_type": assessment.manifest["media_type"],
            },
        },
        "decision": {
            "decision": decision["decision"],
            "stage": "write",
            "reasons": decision["reason_rule_ids"],
            "security_assessment": safe_assessment,
        },
        "status": decision["decision"],
        "created_by": args.actor,
        "created_at": utc_now(),
        "policy_effect": "quarantine_only_no_source_promotion",
    }
    item["record_digest"] = admission_record_digest(item)
    admissions.append(item)
    save_collection("admissions", admissions)
    append_event(
        args.actor,
        "security.candidate.screen",
        admission_id,
        {
            "decision": decision["decision"],
            "sha256": content_hash,
            "payload_executed": False,
            "record_digest": item["record_digest"],
        },
    )
    output = EVALUATION_REPORTS / f"{admission_id.lower()}.json"
    atomic_write_json(output, item)
    print(admission_id)


def collaboration_add(args: argparse.Namespace) -> None:
    """Create one actor-neutral direction/correction/lead/objection record."""

    require_actor(args.actor)
    import runtime

    try:
        record = runtime.make_collaboration_record(
            actor_id=args.actor,
            record_kind=args.record_kind,
            intent=args.intent,
            content=args.content,
            targets=parse_csv(args.targets),
            stance=args.stance,
            status=args.status,
            supersedes=parse_csv(args.supersedes),
            metadata={"priority": args.priority},
        )
    except runtime.RuntimeErrorBase as exc:
        raise WikiError(str(exc)) from exc
    records = collection("collaborations")
    if any(item.get("id") == record["id"] for item in records):
        print(record["id"])
        return
    records.append(record)
    save_collection("collaborations", records)
    append_event(args.actor, "collaboration.add", record["id"], {"intent": args.intent, "kind": args.record_kind})
    print(record["id"])


def collaboration_transition(args: argparse.Namespace) -> None:
    require_actor(args.actor)
    import runtime

    records = collection("collaborations")
    record = find(records, args.record, "collaboration record")
    try:
        transitioned = runtime.transition_collaboration_record(
            record,
            args.status,
            actor_id=args.actor,
            reason=args.reason,
        )
    except runtime.RuntimeErrorBase as exc:
        raise WikiError(str(exc)) from exc
    records = [transitioned if item.get("id") == args.record else item for item in records]
    save_collection("collaborations", records)
    append_event(args.actor, "collaboration.transition", args.record, {"status": args.status})
    print(args.record)


def search_cmd(args: argparse.Namespace) -> None:
    import runtime

    try:
        results = runtime.lexical_search(args.query, root=ROOT, limit=args.limit)
    except runtime.RuntimeErrorBase as exc:
        raise WikiError(str(exc)) from exc
    print(json.dumps(results, ensure_ascii=False, indent=2, sort_keys=True))


def impact_cmd(args: argparse.Namespace) -> None:
    import runtime

    try:
        report = runtime.impact_preview(parse_csv(args.targets), args.text, root=ROOT, search_limit=args.limit)
    except runtime.RuntimeErrorBase as exc:
        raise WikiError(str(exc)) from exc
    if args.output:
        output = Path(args.output).expanduser().resolve()
        atomic_write_json(output, report)
        print(output.relative_to(ROOT) if ROOT in output.parents else output)
    else:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))


def run_plan_cmd(args: argparse.Namespace) -> None:
    """Create and receipt a bounded plan; never perform external research."""

    require_actor(args.actor)
    import runtime

    prior_runs = collection("runs")
    prior_receipts = [item.get("receipt", {}) for item in prior_runs if isinstance(item.get("receipt"), dict)]
    limits = {
        "max_campaigns": args.max_campaigns,
        "max_actions": args.max_actions,
        "max_minutes": args.max_minutes,
        "max_sources": args.max_sources,
        "action_minutes": args.action_minutes,
        "sources_per_action": args.sources_per_action,
    }
    try:
        plan = runtime.build_bounded_schedule(root=ROOT, receipts=prior_receipts, limits=limits, now=args.now)
        store = runtime.ReceiptStore(EVALUATIONS / "receipts")
        receipt = runtime.run_plan(
            plan,
            dry_run=True,
            store=store,
            idempotency_key=args.idempotency_key,
            actor=actor_record(args.actor),
            now=args.now,
        )
    except runtime.RuntimeErrorBase as exc:
        raise WikiError(str(exc)) from exc
    run_id = receipt["run_id"]
    if not any(item.get("id") == run_id for item in prior_runs):
        prior_runs.append(
            {
                "id": run_id,
                "actor_id": args.actor,
                "created_at": receipt["created_at"],
                "status": receipt["status"],
                "plan": plan,
                "receipt": receipt,
                "external_receipts": [],
            }
        )
        save_collection("runs", prior_runs)
        append_event(
            args.actor,
            "runtime.plan",
            run_id,
            {"actions": len(plan["actions"]), "status": receipt["status"], "side_effect_count": receipt["side_effect_count"]},
        )
    output = EVALUATION_REPORTS / f"{run_id.lower()}.json"
    atomic_write_json(output, {"plan": plan, "receipt": receipt})
    print(run_id)


def run_action_report(args: argparse.Namespace) -> None:
    """Attach an attributed report for externally performed work to a planned action."""

    require_actor(args.actor)
    import runtime

    runs = collection("runs")
    run = find(runs, args.run, "run")
    actions = run.get("plan", {}).get("actions", [])
    action = next((item for item in actions if item.get("id") == args.action), None)
    if action is None:
        raise WikiError(f"Unknown action in run {args.run}: {args.action}")
    existing = run.setdefault("external_receipts", [])
    completed = next(
        (item for item in existing if item.get("action_id") == args.action and item.get("status") == "completed"),
        None,
    )
    budget = action.get("budget", {})
    used_minutes = int(budget.get("minutes", 0) if args.used_minutes is None else args.used_minutes)
    used_sources = int(budget.get("sources", 0) if args.used_sources is None else args.used_sources)
    if used_minutes < 0 or used_sources < 0:
        raise WikiError("Reported usage must be non-negative")
    if used_minutes > int(budget.get("minutes", 0)) or used_sources > int(budget.get("sources", 0)):
        raise WikiError("Reported usage cannot exceed the planned action budget")
    if completed and args.status == "completed":
        changed = False
        if not completed.get("usage_accounted_at"):
            campaigns = collection("campaigns")
            campaign = find(campaigns, action.get("campaign_id"), "campaign")
            campaign_runtime = campaign.setdefault("runtime", {})
            next_minutes = int(campaign_runtime.get("used_minutes", 0)) + used_minutes
            next_sources = int(campaign_runtime.get("used_sources", 0)) + used_sources
            if next_minutes > int(campaign.get("max_minutes", 0)) or next_sources > int(campaign.get("max_sources", 0)):
                raise WikiError("Completed work usage would exceed the campaign budget")
            completed["usage"] = {"minutes": used_minutes, "sources": used_sources}
            completed["usage_accounted_at"] = utc_now()
            campaign_runtime.update(
                {"used_minutes": next_minutes, "used_sources": next_sources, "last_run_at": completed["created_at"]}
            )
            campaign["updated_at"] = completed["usage_accounted_at"]
            save_collection("campaigns", campaigns)
            save_collection("runs", runs)
            append_event(
                args.actor,
                "runtime.usage.backfill",
                completed["receipt_id"],
                {"run": args.run, "usage": completed["usage"]},
            )
            changed = True
        if not completed.get("report_digest"):
            completed["report_digest"] = external_report_digest(completed)
            run["status"] = "reported-complete"
            run["updated_at"] = utc_now()
            save_collection("runs", runs)
            append_event(
                args.actor,
                "runtime.action.seal",
                completed["receipt_id"],
                {"run": args.run, "report_digest": completed["report_digest"]},
            )
            changed = True
        if changed:
            save_collection("runs", runs)
        print(completed["receipt_id"])
        return
    try:
        report = runtime.make_external_work_receipt(
            action,
            actor_id=args.actor,
            status=args.status,
            evidence_refs=parse_csv(args.evidence),
            notes=args.notes,
        )
    except runtime.RuntimeErrorBase as exc:
        raise WikiError(str(exc)) from exc
    report["usage"] = {"minutes": used_minutes, "sources": used_sources}
    if any(item.get("receipt_id") == report["receipt_id"] for item in existing):
        print(report["receipt_id"])
        return
    existing.append(report)
    run["updated_at"] = report["created_at"]
    expected_actions = {item.get("id") for item in actions}
    reported_actions = {item.get("action_id") for item in existing}
    if expected_actions and expected_actions <= reported_actions:
        run["status"] = "reported-complete" if all(item.get("status") == "completed" for item in existing) else "closed-with-findings"
    if args.status == "completed":
        campaigns = collection("campaigns")
        campaign = find(campaigns, action.get("campaign_id"), "campaign")
        campaign_runtime = campaign.setdefault("runtime", {})
        next_minutes = int(campaign_runtime.get("used_minutes", 0)) + used_minutes
        next_sources = int(campaign_runtime.get("used_sources", 0)) + used_sources
        if next_minutes > int(campaign.get("max_minutes", 0)) or next_sources > int(campaign.get("max_sources", 0)):
            raise WikiError("Completed work usage would exceed the campaign budget")
        campaign_runtime["used_minutes"] = next_minutes
        campaign_runtime["used_sources"] = next_sources
        campaign_runtime["last_run_at"] = report["created_at"]
        report["usage_accounted_at"] = report["created_at"]
        campaign["updated_at"] = report["created_at"]
        save_collection("campaigns", campaigns)
    report["report_digest"] = external_report_digest(report)
    save_collection("runs", runs)
    append_event(
        args.actor,
        "runtime.action.report",
        report["receipt_id"],
        {
            "run": args.run,
            "status": args.status,
            "usage": report["usage"],
            "report_digest": report["report_digest"],
            "verification_status": report.get("verification_status"),
        },
    )
    print(report["receipt_id"])


def _run_regression_suite(timeout_seconds: int) -> dict[str, Any]:
    """Run the repository suite and return a normalized, auditable observation."""

    command = [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"]
    try:
        completed = subprocess.run(
            command,
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        output = (exc.stdout or "") + "\n" + (exc.stderr or "")
        atomic_write_text(EVALUATION_REPORTS / "unit-test-latest.log", output)
        return {
            "passed": False,
            "test_count": 0,
            "failures": 0,
            "errors": 1,
            "skipped": 0,
            "evidence": "unit-test-timeout",
        }
    output = completed.stdout + completed.stderr
    atomic_write_text(EVALUATION_REPORTS / "unit-test-latest.log", output)
    match = re.search(r"Ran\s+(\d+)\s+tests?\s+in\s+", output)
    test_count = int(match.group(1)) if match else 0
    failures_match = re.search(r"failures=(\d+)", output)
    errors_match = re.search(r"errors=(\d+)", output)
    skipped_match = re.search(r"skipped=(\d+)", output)
    stable_lines = sorted(
        line.strip()
        for line in output.splitlines()
        if re.match(r"^test_.*\.\.\.\s+(?:ok|skipped|FAIL|ERROR)$", line.strip())
    )
    result = {
        "passed": completed.returncode == 0 and test_count > 0,
        "test_count": test_count,
        "failures": int(failures_match.group(1)) if failures_match else 0,
        "errors": int(errors_match.group(1)) if errors_match else (0 if completed.returncode == 0 else 1),
        "skipped": int(skipped_match.group(1)) if skipped_match else 0,
        "evidence": digest_text("\n".join(stable_lines)),
    }
    atomic_write_json(EVALUATION_REPORTS / "unit-test-latest.json", result)
    return result


def _run_rollback_rehearsal(timeout_seconds: int) -> dict[str, Any]:
    """Exercise committed v3.1 against current core state in an isolated tree."""

    base_commit = "d18213a78376c0543a0aa590a3db7fcf7022c187"
    live_paths = [STATE / "events.jsonl", WIKI / "index.md", ROOT / "config" / "wiki.json"]
    before = {path.relative_to(ROOT).as_posix(): digest_file(path) for path in live_paths}
    command_outputs: list[str] = []
    try:
        archive = subprocess.run(
            ["git", "archive", "--format=tar", base_commit],
            cwd=ROOT,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
        if archive.returncode != 0:
            raise WikiError("Cannot export the committed v3.1 rollback baseline")
        with tempfile.TemporaryDirectory(prefix="living-wiki-rollback-") as directory:
            target = Path(directory)
            with tarfile.open(fileobj=io.BytesIO(archive.stdout), mode="r:") as bundle:
                for member in bundle.getmembers():
                    member_path = Path(member.name)
                    if member_path.is_absolute() or ".." in member_path.parts:
                        raise WikiError("Unsafe path in local rollback archive")
                if sys.version_info >= (3, 12):
                    bundle.extractall(target, filter="data")
                else:
                    bundle.extractall(target)
            for name in ("actors", "sources", "claims", "reviews", "campaigns", "proposals"):
                shutil.copy2(STATE / f"{name}.json", target / "state" / f"{name}.json")
            shutil.copy2(STATE / "events.jsonl", target / "state" / "events.jsonl")
            if (ROOT / "raw").exists():
                shutil.copytree(ROOT / "raw", target / "raw", dirs_exist_ok=True)
            for arguments in (
                ["tools/wiki.py", "render", "--actor", "agent:codex", "--no-log"],
                ["tools/wiki.py", "validate"],
                ["tools/wiki.py", "okf-validate"],
            ):
                completed = subprocess.run(
                    [sys.executable, *arguments],
                    cwd=target,
                    capture_output=True,
                    text=True,
                    timeout=timeout_seconds,
                    check=False,
                )
                command_outputs.append(completed.stdout + completed.stderr)
                if completed.returncode != 0:
                    raise WikiError(f"Rollback rehearsal command failed: {' '.join(arguments)}")
    except (OSError, subprocess.TimeoutExpired, tarfile.TarError, WikiError) as exc:
        result = {
            "passed": False,
            "base_commit": base_commit,
            "live_workspace_unchanged": False,
            "commands_passed": len(command_outputs),
            "evidence": digest_text("\n".join(command_outputs) + f"\n{type(exc).__name__}"),
            "error": str(exc),
        }
        atomic_write_json(EVALUATION_REPORTS / "rollback-rehearsal-latest.json", result)
        return result
    after = {path.relative_to(ROOT).as_posix(): digest_file(path) for path in live_paths}
    result = {
        "passed": before == after and len(command_outputs) == 3,
        "base_commit": base_commit,
        "live_workspace_unchanged": before == after,
        "commands_passed": len(command_outputs),
        "evidence": digest_text("\n".join(command_outputs)),
        "error": None,
    }
    atomic_write_json(EVALUATION_REPORTS / "rollback-rehearsal-latest.json", result)
    return result


def release_check(args: argparse.Namespace) -> None:
    """Orchestrate validators, tests, and fixed fixtures into a truthful v4 gate."""

    require_actor(args.actor)
    import release_gate

    structural = validation_findings()
    core_errors, core_warnings, _ = okf_validation_findings()
    profile_errors, profile_warnings = okf_profile_findings()
    okf = (
        [*core_errors, *[f"profile: {item}" for item in profile_errors]],
        [*core_warnings, *[f"profile: {item}" for item in profile_warnings]],
    )
    regression = _run_regression_suite(args.test_timeout)
    rollback = _run_rollback_rehearsal(args.test_timeout)
    regression["rollback_rehearsal_passed"] = rollback["passed"]
    regression["rollback_evidence"] = rollback["evidence"]
    regression["rollback_base_commit"] = rollback["base_commit"]
    regression["rollback_live_workspace_unchanged"] = rollback["live_workspace_unchanged"]
    try:
        report = release_gate.evaluate_repository(
            ROOT,
            structural_findings=structural,
            okf_findings=okf,
            regression_result=regression,
        )
    except release_gate.ReleaseGateError as exc:
        raise WikiError(f"Release gate failed closed: {exc}") from exc
    json_path = EVALUATION_REPORTS / "v4-release-report.json"
    atomic_write_json(json_path, report)
    archived_json_path = EVALUATION_REPORTS / f"v4-release-{report['component_fingerprint'][:16]}.json"
    if archived_json_path.exists() and load_json(archived_json_path) != report:
        raise WikiError("Content-addressed release report collision")
    if not archived_json_path.exists():
        atomic_write_json(archived_json_path, report)
    gate_rows = [
        f"| {gate.get('name', '-')} | {'PASS' if gate.get('passed') else 'FAIL'} | "
        f"{len(gate.get('errors', []))} | {len(gate.get('warnings', []))} |"
        for gate in report.get("gates", [])
    ]
    markdown = f"""# Living Wiki v4 release report

- Result: **{'PASS' if report.get('passed') else 'FAIL'}**
- Readiness: `{report.get('readiness')}`
- Production certified: **{str(report.get('production_certified')).lower()}**
- Calibration: `{report.get('calibration_status')}`
- Security: `{report.get('security_status')}`
- Component fingerprint: `{report.get('component_fingerprint')}`

| Gate | Result | Errors | Warnings |
|---|---|---:|---:|
{chr(10).join(gate_rows)}

## Interpretation

이 판정은 로컬 control plane과 고정 fixture의 회귀 통과를 뜻한다. 장기 empirical calibration, 보지 못한 semantic attack, live external executor, credential/publication 경로를 인증하지 않는다.
"""
    atomic_write_text(EVALUATION_REPORTS / "v4-release-report.md", markdown)
    append_event(
        args.actor,
        "release.evaluate",
        "living-wiki-v4",
        {
            "passed": report["passed"],
            "component_fingerprint": report["component_fingerprint"],
            "production_certified": False,
            "test_count": regression["test_count"],
        },
    )
    print(json_path.relative_to(ROOT))
    if not report["passed"]:
        raise WikiError("Living Wiki v4 release gate did not pass")


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
        "proposals": len(collection("proposals")),
        "collaborations": len(collection("collaborations")),
        "admissions": len(collection("admissions")),
        "runs": len(collection("runs")),
    }
    actual = {
        "sources": len(list((OKF_BUNDLE / "sources").glob("src-*.md"))),
        "claims": len(list((OKF_BUNDLE / "claims").glob("clm-*.md"))),
        "actors": len(list((OKF_BUNDLE / "actors").glob("actor-*.md"))),
        "reviews": len(list((OKF_BUNDLE / "reviews").glob("rev-*.md"))),
        "campaigns": len(list((OKF_BUNDLE / "campaigns").glob("cmp-*.md"))),
        "proposals": len(list((OKF_BUNDLE / "governance").glob("rfc-*.md"))),
        "collaborations": len(list((OKF_BUNDLE / "collaborations").glob("col-*.md"))),
        "admissions": len(list((OKF_BUNDLE / "admissions").glob("adm-*.md"))),
        "runs": len(list((OKF_BUNDLE / "runs").glob("run-*.md"))),
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
        proposals = collection("proposals")
        collaborations = collection("collaborations")
        admissions = collection("admissions")
        runs = collection("runs")
    except WikiError as exc:
        return [str(exc)], [], {}
    try:
        grandfathered_source_ids = source_grandfather_ids()
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
    duplicate_ids(proposals, "proposal")
    duplicate_ids(collaborations, "collaboration")
    duplicate_ids(admissions, "admission")
    duplicate_ids(runs, "run")

    actor_ids = {a.get("id") for a in actors}
    source_ids = {s.get("id") for s in sources}
    claim_ids = {c.get("id") for c in claims}
    campaign_ids = {c.get("id") for c in campaigns}
    admission_by_id = {item.get("id"): item for item in admissions}
    try:
        ledger_events = event_lines()
    except WikiError as exc:
        errors.append(str(exc))
        ledger_events = []
    legacy_source_count = 0
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
        admission_ids = source.get("admission_ids", [])
        if not admission_ids:
            if source.get("id") in grandfathered_source_ids:
                legacy_source_count += 1
            else:
                errors.append(f"{source.get('id')}: non-grandfathered source lacks admission_ids")
        else:
            linked_admissions = []
            for admission_id in admission_ids:
                admission = admission_by_id.get(admission_id)
                if admission is None:
                    errors.append(f"{source.get('id')}: unknown admission {admission_id}")
                else:
                    linked_admissions.append(admission)
            if not any(
                item.get("status") == "allow" and item.get("policy_effect") == "advisory_only"
                for item in linked_admissions
            ):
                errors.append(f"{source.get('id')}: no allowing source-admission gate")
            if artifact and not any(
                item.get("status") == "allow" and item.get("policy_effect") == "quarantine_only_no_source_promotion"
                for item in linked_admissions
            ):
                errors.append(f"{source.get('id')}: file-backed source lacks an allowing security admission")
        if source.get("source_level") == "S0":
            warnings.append(f"{source.get('id')}: source credibility unassessed")

    if legacy_source_count:
        warnings.append(
            f"{legacy_source_count} source(s) predate v4 admission enforcement and remain grandfathered"
        )
    missing_grandfathered = sorted(grandfathered_source_ids - source_ids)
    if missing_grandfathered:
        errors.append(
            "Pinned grandfathered source(s) missing from the ledger: " + ", ".join(missing_grandfathered)
        )

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

    for proposal in proposals:
        if proposal.get("created_by") not in actor_ids:
            errors.append(f"{proposal.get('id')}: unknown proposal creator")
        if proposal.get("status") not in {"proposed", "approved", "changes-requested", "rejected", "implemented", "superseded"}:
            errors.append(f"{proposal.get('id')}: invalid proposal status")
        for evidence_id in proposal.get("evidence", []):
            if evidence_id not in claim_ids:
                errors.append(f"{proposal.get('id')}: unknown evidence claim {evidence_id}")
        for decision in proposal.get("approvals", []):
            if decision.get("actor_id") not in actor_ids:
                errors.append(f"{proposal.get('id')}: review has unknown actor")
            if decision.get("decision") not in {"approve", "request-changes", "reject"}:
                errors.append(f"{proposal.get('id')}: invalid proposal review decision")
        if proposal.get("status") == "implemented":
            evidence = proposal.get("implementation_evidence", {})
            report_path = ROOT / str(evidence.get("release_report", ""))
            if not report_path.is_file():
                errors.append(f"{proposal.get('id')}: implemented proposal lacks release report")
            else:
                release_report = load_json(report_path)
                if release_report.get("passed") is not True:
                    errors.append(f"{proposal.get('id')}: implementation release report did not pass")
                if release_report.get("component_fingerprint") != evidence.get("component_fingerprint"):
                    errors.append(f"{proposal.get('id')}: implementation fingerprint mismatch")
                if release_report.get("production_certified") is not False:
                    errors.append(f"{proposal.get('id')}: implementation evidence misstates certification")

    try:
        import runtime
    except ImportError as exc:
        errors.append(f"runtime validation unavailable: {exc}")
    else:
        try:
            collaboration_ids = {item.get("id") for item in collaborations}
            for record in collaborations:
                try:
                    runtime.validate_collaboration_record(record)
                except runtime.RuntimeErrorBase as exc:
                    errors.append(f"{record.get('id')}: invalid collaboration record: {exc}")
                if record.get("actor_id") not in actor_ids:
                    errors.append(f"{record.get('id')}: unknown collaboration actor")
                for superseded in record.get("supersedes", []):
                    if superseded not in collaboration_ids:
                        errors.append(f"{record.get('id')}: unknown superseded collaboration {superseded}")

            receipt_store = runtime.ReceiptStore(EVALUATIONS / "receipts")
            errors.extend(f"runtime receipt chain: {item}" for item in receipt_store.verify())
        except (runtime.RuntimeErrorBase, OSError) as exc:
            errors.append(f"runtime validation failed closed: {exc}")

    for admission in admissions:
        if admission.get("created_by") not in actor_ids:
            errors.append(f"{admission.get('id')}: unknown admission actor")
        if admission.get("status") not in {"allow", "review", "reject"}:
            errors.append(f"{admission.get('id')}: invalid admission status")
        if admission.get("policy_effect") not in {"advisory_only", "quarantine_only_no_source_promotion"}:
            errors.append(f"{admission.get('id')}: admission may not mutate trust or promote a source")
        for finding in admission_integrity_findings(admission):
            errors.append(f"{admission.get('id')}: {finding}")
        if admission.get("record_digest") and not any(
            event.get("subject") == admission.get("id")
            and event.get("details", {}).get("record_digest") == admission.get("record_digest")
            for event in ledger_events
        ):
            errors.append(f"{admission.get('id')}: admission digest is not anchored in the event chain")
        assessment = admission.get("decision", {}).get("security_assessment")
        if isinstance(assessment, dict):
            invariants = assessment.get("invariants", {})
            if invariants.get("payload_executed") is not False:
                errors.append(f"{admission.get('id')}: security assessment lacks no-execution invariant")
            artifact = admission.get("candidate", {}).get("quarantine_artifact", {})
            artifact_path = ROOT / str(artifact.get("path", ""))
            if not artifact_path.is_file():
                errors.append(f"{admission.get('id')}: quarantine artifact missing")
            elif digest_file(artifact_path) != artifact.get("sha256"):
                errors.append(f"{admission.get('id')}: quarantine artifact hash mismatch")

    for run in runs:
        if run.get("actor_id") not in actor_ids:
            errors.append(f"{run.get('id')}: unknown run actor")
        plan = run.get("plan", {})
        receipt = run.get("receipt", {})
        if run.get("status") not in {"planned", "dry_run", "review_required", "blocked", "reported-complete", "closed-with-findings"}:
            errors.append(f"{run.get('id')}: invalid run lifecycle status {run.get('status')}")
        if plan.get("side_effects_executed") is not False:
            errors.append(f"{run.get('id')}: plan must not execute side effects")
        if int(receipt.get("side_effect_count", -1)) != 0:
            errors.append(f"{run.get('id')}: external planning receipt recorded a side effect")
        action_by_id = {item.get("id"): item for item in plan.get("actions", []) if isinstance(item, dict)}
        for action in action_by_id.values():
            if action.get("campaign_id") not in campaign_ids:
                errors.append(f"{run.get('id')}: action has unknown campaign {action.get('campaign_id')}")
            if action.get("external_work") is not True or action.get("execution") != "planned_only":
                errors.append(f"{run.get('id')}: external research action is not planned-only")
        for report in run.get("external_receipts", []):
            action = action_by_id.get(report.get("action_id"))
            if action is None:
                errors.append(f"{run.get('id')}: external report has unknown action {report.get('action_id')}")
                continue
            if report.get("actor_id") not in actor_ids:
                errors.append(f"{run.get('id')}: external report has unknown actor")
            if report.get("execution_performed_by_runtime") is not False:
                errors.append(f"{run.get('id')}: runtime claimed external execution")
            if report.get("verification_status") != "unverified_report":
                errors.append(f"{run.get('id')}: external result must retain explicit verification status")
            if report.get("report_digest") != external_report_digest(report):
                errors.append(f"{run.get('id')}: external report digest mismatch")
            elif not any(
                event.get("subject") == report.get("receipt_id")
                and event.get("details", {}).get("report_digest") == report.get("report_digest")
                for event in ledger_events
            ):
                errors.append(f"{run.get('id')}: external report digest is not anchored in the event chain")
            usage = report.get("usage")
            if report.get("status") == "completed" and not isinstance(usage, dict):
                errors.append(f"{run.get('id')}: completed external report lacks usage accounting")
            if report.get("status") == "completed" and isinstance(usage, dict):
                budget = action.get("budget", {})
                if int(usage.get("minutes", -1)) > int(budget.get("minutes", 0)):
                    errors.append(f"{run.get('id')}: reported minutes exceed action budget")
                if int(usage.get("sources", -1)) > int(budget.get("sources", 0)):
                    errors.append(f"{run.get('id')}: reported sources exceed action budget")
                if not report.get("usage_accounted_at"):
                    errors.append(f"{run.get('id')}: completed external report usage was not applied to campaign runtime")

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
        "proposals": len(proposals),
        "collaborations": len(collaborations),
        "admissions": len(admissions),
        "runs": len(runs),
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
* [Collaboration](collaborations/index.md) - actor-neutral direction, lead, correction, objection ledger.
* [Campaigns](campaigns/index.md) - bounded autonomous research queue.
* [Admissions](admissions/index.md) - source/security admission decisions without automatic promotion.
* [Runs](runs/index.md) - bounded plans and attributed external-work receipts.
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
    proposals = collection("proposals")
    collaborations = collection("collaborations")
    admissions = collection("admissions")
    runs = collection("runs")
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

    for proposal in proposals:
        metadata = {
            "type": "Harness Proposal",
            "title": f"{proposal['id']}: {proposal.get('title', '')}",
            "description": proposal.get("problem", "")[:300],
            "tags": ["governance", "harness-proposal", proposal.get("status", "proposed")],
            "timestamp": proposal.get("updated_at") or proposal.get("created_at") or "2026-07-11T00:00:00+09:00",
            "proposal_id": proposal["id"],
            "lifecycle_status": proposal.get("status", "proposed"),
            "generated": True,
        }
        reviews = proposal.get("approvals", [])
        body = f"""<!-- AUTOGENERATED from state/proposals.json. -->
# {proposal['id']}: {proposal.get('title', '')}

- Status: **{proposal.get('status', 'proposed')}**
- Proposed by: [{proposal.get('created_by', '-')}](../actors/{actor_page_name(proposal.get('created_by', 'unknown'))})
- Created: `{proposal.get('created_at', '-')}`

## Problem

{proposal.get('problem', '-')}

## Proposed change

{proposal.get('proposed_change', '-')}

## Evidence claims

{chr(10).join(f'- [{claim_id}](../claims/{claim_id.lower()}.md)' for claim_id in proposal.get('evidence', [])) or '- None'}

## Acceptance gate

{proposal.get('benchmark', '-')}

## Risks

{chr(10).join(f'- {risk}' for risk in proposal.get('risks', [])) or '- None'}

## Rollback

{proposal.get('rollback', '-')}

## Review decisions

{chr(10).join(f"- **{item.get('decision', '-')}** by `{item.get('actor_id', '-')}` at `{item.get('at', '-')}` — {item.get('rationale', '-')}" for item in reviews) or '- None'}

## Implementation evidence

{f"- Release report: `{proposal.get('implementation_evidence', {}).get('release_report')}`" if proposal.get('implementation_evidence') else '- Not implemented yet.'}
{f"- Component fingerprint: `{proposal.get('implementation_evidence', {}).get('component_fingerprint')}`" if proposal.get('implementation_evidence') else ''}
{f"- Production certified: `{proposal.get('implementation_evidence', {}).get('production_certified')}`" if proposal.get('implementation_evidence') else ''}
"""
        write_okf_concept(WIKI / "governance" / f"{proposal['id'].lower()}.md", metadata, body)

    for record in collaborations:
        transitions = record.get("metadata", {}).get("transitions", [])
        body = f"""<!-- AUTOGENERATED from state/collaborations.json. -->
# {record['id']}

> {record.get('content', '')}

| Field | Value |
|---|---|
| Actor | [{record.get('actor_id', '-')}](../actors/{actor_page_name(record.get('actor_id', 'unknown'))}) |
| Record kind | `{record.get('record_kind', '-')}` |
| Intent | `{record.get('intent', '-')}` |
| Stance | `{record.get('stance') or '-'}` |
| Status | **{record.get('status', '-')}** |
| Created | `{record.get('created_at', '-')}` |
| Updated | `{record.get('updated_at', '-')}` |

## Targets

{chr(10).join(f'- `{target}`' for target in record.get('targets', [])) or '- None'}

## Transition history

{chr(10).join(f"- `{item.get('at', '-')}` — `{item.get('from', '-')}` → `{item.get('to', '-')}` by `{item.get('actor_id', '-')}`: {item.get('reason', '-')}" for item in transitions) or '- None'}
"""
        write_okf_concept(
            WIKI / "collaborations" / f"{record['id'].lower()}.md",
            {
                "type": "Collaboration Record",
                "title": record["id"],
                "description": record.get("content", "")[:300],
                "tags": ["collaboration", record.get("record_kind", "unknown"), record.get("intent", "unknown"), record.get("status", "unknown")],
                "timestamp": record.get("updated_at") or record.get("created_at") or "2026-07-11T00:00:00+09:00",
                "lifecycle_status": record.get("status", "unknown"),
                "generated": True,
            },
            body,
        )

    for admission in admissions:
        candidate = admission.get("candidate", {})
        decision = admission.get("decision", {})
        reason_items = decision.get("reasons", [])
        reason_codes = []
        for reason in reason_items:
            reason_codes.append(str(reason.get("code")) if isinstance(reason, dict) else str(reason))
        security_assessment = decision.get("security_assessment", {})
        if isinstance(security_assessment, dict):
            reason_codes.extend(
                str(item.get("rule_id"))
                for item in security_assessment.get("signals", [])
                if isinstance(item, dict) and item.get("rule_id")
            )
        reason_codes = sorted(set(filter(None, reason_codes)))
        artifact = candidate.get("quarantine_artifact", {})
        source_url = candidate.get("url")
        source_ref = candidate.get("source_ref")
        citation_url = source_url or (source_ref if isinstance(source_ref, str) and source_ref.startswith(("https://", "http://")) else None)
        body = f"""<!-- AUTOGENERATED from state/admissions.json; untrusted payload text is intentionally omitted. -->
# {admission['id']}

| Field | Value |
|---|---|
| Candidate | `{candidate.get('id', '-')}` |
| Source reference | {md_cell(source_ref or source_url)} |
| Decision | **{admission.get('status', '-')}** |
| Policy effect | `{admission.get('policy_effect', '-')}` |
| Evaluated by | [{admission.get('created_by', '-')}](../actors/{actor_page_name(admission.get('created_by', 'unknown'))}) |
| Evaluated at | `{admission.get('created_at', '-')}` |

## Explainable reasons

{chr(10).join(f'- `{code}`' for code in reason_codes) or '- No blocking reason recorded.'}

## Quarantine manifest

- Path outside bundle: `{artifact.get('path', 'not applicable')}`
- SHA-256: `{artifact.get('sha256', 'not applicable')}`
- Size: `{artifact.get('size_bytes', 'not applicable')}` bytes
- Media type: `{artifact.get('media_type', 'not applicable')}`

The candidate was not automatically promoted to a canonical source and this decision did not mutate C0–C4.
"""
        if citation_url:
            body += f"\n# Citations\n\n[1] [Candidate source]({citation_url})\n"
        write_okf_concept(
            WIKI / "admissions" / f"{admission['id'].lower()}.md",
            {
                "type": "Admission Decision",
                "title": admission["id"],
                "description": f"Source/security admission decision {admission.get('status', 'unknown')} with no automatic trust mutation.",
                "tags": ["admission", admission.get("status", "unknown"), "audit"],
                "timestamp": admission.get("created_at") or "2026-07-11T00:00:00+09:00",
                "lifecycle_status": admission.get("status", "unknown"),
                "generated": True,
            },
            body,
        )

    for run in runs:
        action_rows = []
        for action in run.get("plan", {}).get("actions", []):
            budget = action.get("budget", {})
            action_rows.append(
                f"| `{action.get('id', '-')}` | `{action.get('campaign_id', '-')}` | `{action.get('execution', '-')}` | "
                f"{budget.get('minutes', 0)} | {budget.get('sources', 0)} |"
            )
        report_rows = []
        for report in run.get("external_receipts", []):
            usage = report.get("usage", {})
            report_rows.append(
                f"| `{report.get('receipt_id', '-')}` | `{report.get('action_id', '-')}` | {report.get('status', '-')} | "
                f"`{report.get('actor_id', '-')}` | {usage.get('minutes', '-')} | {usage.get('sources', '-')} |"
            )
        receipt = run.get("receipt", {})
        body = f"""<!-- AUTOGENERATED from state/runs.json. -->
# {run['id']}

- Status: **{run.get('status', '-')}**
- Planned by: [{run.get('actor_id', '-')}](../actors/{actor_page_name(run.get('actor_id', 'unknown'))})
- Created: `{run.get('created_at', '-')}`
- Plan ID: `{run.get('plan', {}).get('plan_id', '-')}`
- Planning receipt hash: `{receipt.get('receipt_hash', '-')}`
- Runtime side-effect count: **{receipt.get('side_effect_count', '-')}**

## Planned-only actions

| Action | Campaign | Execution | Minutes | Sources |
|---|---|---|---:|---:|
{chr(10).join(action_rows) or '| - | - | - | - | - |'}

## Attributed external reports

| Receipt | Action | Status | Actor | Used minutes | Used sources |
|---|---|---|---|---:|---:|
{chr(10).join(report_rows) or '| - | - | - | - | - | - |'}

The runtime only planned external work. Any reported execution is attributed separately and remains unverified unless its evidence is reviewed.
"""
        write_okf_concept(
            WIKI / "runs" / f"{run['id'].lower()}.md",
            {
                "type": "Runtime Receipt",
                "title": run["id"],
                "description": "Bounded research plan and attributed external-work receipts; runtime executes no external action.",
                "tags": ["runtime", "receipt", run.get("status", "unknown")],
                "timestamp": run.get("updated_at") or run.get("created_at") or "2026-07-11T00:00:00+09:00",
                "lifecycle_status": run.get("status", "unknown"),
                "generated": True,
            },
            body,
        )

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
        ("collaborations", "Collaboration Records"),
        ("admissions", "Admission Decisions"),
        ("runs", "Runtime Receipts"),
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
            "migrations",
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
    reviews = collection("reviews")
    collaborations = collection("collaborations")
    admissions = collection("admissions")
    runs = collection("runs")
    events = event_lines()
    levels = {level: 0 for level in CLAIM_LEVELS}
    for claim in claims:
        levels[claim.get("confidence", {}).get("level", "C0")] += 1
    version = load_json(ROOT / "config" / "wiki.json").get("harness_version", "unknown")
    print(f"Living Wiki {version}")
    print(f"Actors: {len(actors)} | Sources: {len(sources)} | Claims: {len(claims)} | Events: {len(events)}")
    print(
        f"Reviews: {len(reviews)} | Collaborations: {len(collaborations)} | "
        f"Admissions: {len(admissions)} | Runs: {len(runs)}"
    )
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
    p.add_argument("--admission", required=True, help="allow decision from admission-check")
    p.add_argument("--security-admission", help="matching allow decision from security-screen; required with --file")
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

    p = sub.add_parser("interest-seed", help="queue cadence-due interest questions without executing research")
    p.add_argument("--actor", default="agent:codex")
    p.add_argument("--now", help="fixed ISO-8601 evaluation time for deterministic scheduling")
    p.add_argument("--max-campaigns", type=int, default=1)
    p.set_defaults(func=interest_seed)

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

    p = sub.add_parser("proposal-review", help="record an attributed approval or objection to a harness proposal")
    p.add_argument("--actor", required=True)
    p.add_argument("--proposal", required=True)
    p.add_argument("--decision", required=True, choices=["approve", "request-changes", "reject"])
    p.add_argument("--rationale", required=True)
    p.set_defaults(func=proposal_review)

    p = sub.add_parser("proposal-implement", help="mark an approved RFC implemented after a passing release gate")
    p.add_argument("--actor", default="agent:codex")
    p.add_argument("--proposal", required=True)
    p.add_argument("--release-report", default=str(EVALUATION_REPORTS / "v4-release-report.json"))
    p.set_defaults(func=proposal_implement)

    p = sub.add_parser("calibration-run", help="evaluate a frozen ordinal-calibration and admission fixture")
    p.add_argument("--actor", default="agent:codex")
    p.add_argument("--input", default=str(EVALUATIONS / "fixtures" / "calibration-gold.json"))
    p.add_argument("--output")
    p.add_argument("--small-n", type=int, default=5)
    p.set_defaults(func=calibration_run)

    p = sub.add_parser("admission-check", help="record an advisory source-admission decision for one JSON candidate")
    p.add_argument("--actor", default="agent:codex")
    p.add_argument("--candidate", required=True)
    p.add_argument("--registry-fixture")
    p.set_defaults(func=admission_check)

    p = sub.add_parser("admission-seal", help="anchor a structurally valid admission digest in the event chain")
    p.add_argument("--actor", default="agent:codex")
    p.add_argument("--admission", required=True)
    p.set_defaults(func=admission_seal)

    p = sub.add_parser("security-evaluate", help="run the fixed non-executing poisoning/security corpus")
    p.add_argument("--actor", default="agent:codex")
    p.add_argument("--corpus", default=str(EVALUATIONS / "fixtures" / "security-corpus.json"))
    p.add_argument("--output")
    p.set_defaults(func=security_evaluate)

    p = sub.add_parser("security-screen", help="quarantine and screen one local candidate without source promotion")
    p.add_argument("--actor", default="agent:codex")
    p.add_argument("--input", required=True)
    p.add_argument("--source-ref", required=True)
    p.add_argument("--media-type")
    p.add_argument("--extracted-text", help="UTF-8 output from a separately sandboxed binary parser")
    p.set_defaults(func=security_screen)

    p = sub.add_parser("collaboration-add", help="record an actor-neutral direction, correction, lead, or objection")
    p.add_argument("--actor", required=True)
    p.add_argument("--record-kind", required=True, choices=["commitment", "contribution", "review"])
    p.add_argument("--intent", required=True, choices=["direction", "correction", "lead", "objection"])
    p.add_argument("--content", required=True)
    p.add_argument("--targets", required=True, help="comma-separated claim/source/campaign/wiki references")
    p.add_argument("--stance")
    p.add_argument("--status", default="proposed", choices=["draft", "proposed", "acknowledged", "active"])
    p.add_argument("--supersedes")
    p.add_argument("--priority", type=float, default=0.5)
    p.set_defaults(func=collaboration_add)

    p = sub.add_parser("collaboration-transition", help="transition a collaboration record with attribution")
    p.add_argument("--actor", required=True)
    p.add_argument("--record", required=True)
    p.add_argument("--status", required=True, choices=["proposed", "acknowledged", "active", "resolved", "withdrawn", "rejected", "superseded"])
    p.add_argument("--reason", required=True)
    p.set_defaults(func=collaboration_transition)

    p = sub.add_parser("search", help="run deterministic lexical retrieval across canonical state and wiki")
    p.add_argument("query")
    p.add_argument("--limit", type=int, default=10)
    p.set_defaults(func=search_cmd)

    p = sub.add_parser("impact", help="preview dependency impact and possible semantic conflicts")
    p.add_argument("--targets", required=True, help="comma-separated claim/source/campaign references")
    p.add_argument("--text", required=True)
    p.add_argument("--limit", type=int, default=12)
    p.add_argument("--output")
    p.set_defaults(func=impact_cmd)

    p = sub.add_parser("run-plan", help="create a bounded, hash-receipted external research plan without executing it")
    p.add_argument("--actor", default="agent:codex")
    p.add_argument("--now")
    p.add_argument("--idempotency-key")
    p.add_argument("--max-campaigns", type=int, default=1)
    p.add_argument("--max-actions", type=int, default=1)
    p.add_argument("--max-minutes", type=int, default=45)
    p.add_argument("--max-sources", type=int, default=3)
    p.add_argument("--action-minutes", type=int, default=15)
    p.add_argument("--sources-per-action", type=int, default=1)
    p.set_defaults(func=run_plan_cmd)

    p = sub.add_parser("run-action-report", help="attach an attributed report to one externally performed planned action")
    p.add_argument("--actor", required=True)
    p.add_argument("--run", required=True)
    p.add_argument("--action", required=True)
    p.add_argument("--status", required=True, choices=["reported", "completed", "failed", "cancelled"])
    p.add_argument("--evidence")
    p.add_argument("--notes")
    p.add_argument("--used-minutes", type=int, help="actual minutes, bounded by the action allocation")
    p.add_argument("--used-sources", type=int, help="actual source count, bounded by the action allocation")
    p.set_defaults(func=run_action_report)

    p = sub.add_parser("release-check", help="run the integrated v4 structural, fixture, receipt, and regression gates")
    p.add_argument("--actor", default="agent:codex")
    p.add_argument("--test-timeout", type=int, default=300)
    p.set_defaults(func=release_check)

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
