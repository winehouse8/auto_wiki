#!/usr/bin/env python3
"""Deterministic control plane for the Living Wiki.

The LLM does judgment-heavy research. This CLI owns boring invariants: IDs,
attribution, immutable artifact copies, evidence links, confidence gates,
tamper-evident events, validation, and derived dashboards.
"""

from __future__ import annotations

import argparse
import copy
import datetime as dt
import hashlib
import io
import json
import mimetypes
import os
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


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
MEMORY_FEEDBACK_FIXTURE = EVALUATIONS / "fixtures" / "memory-feedback-scenarios.json"
MEMORY_FEEDBACK_FIXTURE_SHA256 = "f68d52d6d5544e8763b365c9952f425e6a3636f6ecd92fbe15dd57be179902c9"

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
    "memory_feedback": {"version": 1, "feedback": []},
}

COLLECTION_KEYS = {"memory_feedback": "feedback"}

SOURCE_LEVELS = {f"S{i}": i for i in range(5)}
CLAIM_LEVELS = {f"C{i}": i for i in range(5)}
CLAIM_KINDS = {"fact", "interpretation", "hypothesis", "prediction", "value"}
RELATIONS = {"supports", "contradicts", "contextualizes"}
LIFECYCLE_STATUSES = {"active", "deprecated", "superseded", "invalidated", "archived"}
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
RESEARCH_PORTFOLIO_SCHEMA_VERSION = "living-wiki-research-portfolio/v1"
PROJECT_STATUSES = {"active", "paused", "archived"}


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


STRICT_QUARANTINE_PROFILE = "strict-local-custody"
PUBLIC_QUARANTINE_PROFILE = "public-clean-clone"


def quarantine_anchor_is_valid(
    admission: dict[str, Any],
    event: dict[str, Any],
) -> bool:
    """격리 admission을 사건 원장의 정확한 보안 판정과 연결한다."""

    if not isinstance(admission, dict) or not isinstance(event, dict):
        return False
    candidate = admission.get("candidate", {})
    artifact = candidate.get("quarantine_artifact", {}) if isinstance(candidate, dict) else {}
    details = event.get("details", {})
    if not isinstance(artifact, dict) or not isinstance(details, dict):
        return False
    return bool(
        event.get("action") == "security.candidate.screen"
        and event.get("actor") == admission.get("created_by")
        and event.get("subject") == admission.get("id")
        and details.get("record_digest") == admission.get("record_digest")
        and details.get("sha256") == artifact.get("sha256")
        and details.get("decision") == admission.get("status")
        and details.get("payload_executed") is False
    )


def portable_quarantine_metadata(
    admission: dict[str, Any],
    distribution_policy: dict[str, Any],
    *,
    validation_profile: str,
    anchor_verified: bool,
) -> bool:
    """public Git에 payload 없이 보존할 격리 기록의 엄격한 메타데이터 계약."""

    expected_policy = {
        "mode": "local-only-metadata-in-git",
        "path": "raw/quarantine",
        "public_repository": "winehouse8/auto_wiki",
        "missing_artifact_policy": "anchored-content-addressed-admission-only",
        "default_validation_profile": STRICT_QUARANTINE_PROFILE,
        "portable_validation_profile": PUBLIC_QUARANTINE_PROFILE,
    }
    if distribution_policy != expected_policy:
        return False
    if validation_profile != PUBLIC_QUARANTINE_PROFILE or not anchor_verified:
        return False
    if admission_integrity_findings(admission):
        return False
    if admission.get("policy_effect") != "quarantine_only_no_source_promotion":
        return False
    decision = admission.get("decision", {})
    if (
        not isinstance(decision, dict)
        or admission.get("status") != decision.get("decision")
        or decision.get("stage") != "write"
    ):
        return False
    assessment = decision.get("security_assessment", {})
    invariants = assessment.get("invariants", {}) if isinstance(assessment, dict) else {}
    manifest = assessment.get("manifest", {}) if isinstance(assessment, dict) else {}
    if (
        not isinstance(assessment, dict)
        or assessment.get("schema_version") != "living-wiki-security-gate/v1"
        or assessment.get("classification") != "untrusted_external_content"
        or not isinstance(invariants, dict)
        or invariants.get("allow_means_data_use_only") is not True
        or invariants.get("credentials_accessed") is not False
        or invariants.get("network_used") is not False
        or invariants.get("payload_executed") is not False
        or not isinstance(manifest, dict)
        or manifest.get("classification") != "untrusted_external_content"
    ):
        return False
    candidate = admission.get("candidate", {})
    if not isinstance(candidate, dict):
        return False
    artifact = candidate.get("quarantine_artifact", {})
    if not isinstance(artifact, dict):
        return False
    sha256 = str(artifact.get("sha256", ""))
    path = str(artifact.get("path", ""))
    match = re.fullmatch(
        r"raw/quarantine/([0-9a-f]{64})/artifact(?:\.[A-Za-z0-9._-]+)?",
        path,
    )
    size = artifact.get("size_bytes")
    media_type = artifact.get("media_type")
    return bool(
        match
        and match.group(1) == sha256
        and re.fullmatch(r"[0-9a-f]{64}", sha256)
        and isinstance(size, int)
        and not isinstance(size, bool)
        and size >= 0
        and isinstance(media_type, str)
        and bool(media_type.strip())
        and manifest.get("content_sha256") == sha256
        and manifest.get("size_bytes") == size
        and manifest.get("media_type") == media_type
        and manifest.get("source_ref") == candidate.get("source_ref")
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
            for key in (
                "updated_at",
                "lifecycle_updated_at",
                "last_verified_at",
                "retrieved_at",
                "created_at",
            ):
                value = item.get(key)
                if isinstance(value, str) and re.match(r"^\d{4}-\d{2}-\d{2}T", value):
                    candidates.append(value)
            confidence_at = item.get("confidence", {}).get("computed_at") if isinstance(item.get("confidence"), dict) else None
            if isinstance(confidence_at, str):
                candidates.append(confidence_at)
            resolution_at = item.get("resolution", {}).get("at") if isinstance(item.get("resolution"), dict) else None
            if isinstance(resolution_at, str):
                candidates.append(resolution_at)
    return max(candidates, default="2026-07-11T00:00:00+09:00")


def record_latest_timestamp(*values: Any) -> str:
    timestamps: list[tuple[dt.datetime, str]] = []
    for value in values:
        parsed = parse_timezone_aware_iso8601(value)
        if parsed is not None and isinstance(value, str):
            timestamps.append((parsed, value))
    return max(timestamps, default=(dt.datetime.min.replace(tzinfo=dt.timezone.utc), "2026-07-11T00:00:00+09:00"))[1]


def parse_timezone_aware_iso8601(value: Any) -> dt.datetime | None:
    """Return a comparable aware datetime for the portable temporal profile."""

    if isinstance(value, dt.datetime):
        parsed = value
    elif isinstance(value, str) and re.match(r"^\d{4}-\d{2}-\d{2}T", value):
        normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
        try:
            parsed = dt.datetime.fromisoformat(normalized)
        except ValueError:
            return None
    else:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed


def claim_semantic_timestamp(claim: dict[str, Any]) -> Any:
    """Project an explicit semantic timestamp, with a conservative legacy fallback."""

    if claim.get("content_updated_at") is not None:
        return claim["content_updated_at"]
    confidence = claim.get("confidence") if isinstance(claim.get("confidence"), dict) else {}
    evidence_times = [
        edge.get("added_at")
        for edge in claim.get("evidence", [])
        if isinstance(edge, dict)
    ]
    return record_latest_timestamp(
        claim.get("created_at"),
        *evidence_times,
        confidence.get("computed_at"),
        claim.get("lifecycle_updated_at"),
    )


def source_semantic_timestamp(source: dict[str, Any]) -> Any:
    """Project an explicit semantic timestamp without inventing source creation."""

    if source.get("content_updated_at") is not None:
        return source["content_updated_at"]
    assessment = source.get("assessment") if isinstance(source.get("assessment"), dict) else {}
    return record_latest_timestamp(
        source.get("created_at"),
        source.get("retrieved_at"),
        assessment.get("assessed_at"),
        source.get("lifecycle_updated_at"),
    )


def project_known_fields(metadata: dict[str, Any], values: dict[str, Any], fields: Iterable[str]) -> None:
    """Copy only canonical values that are actually known; never synthesize them."""

    for field in fields:
        if values.get(field) is not None:
            metadata[field] = values[field]


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
    key = COLLECTION_KEYS.get(name, name)
    items = payload.get(key)
    if not isinstance(items, list):
        raise WikiError(f"state/{name}.json must contain a '{key}' list")
    return items


def save_collection(name: str, items: Iterable[dict[str, Any]]) -> None:
    ordered = sorted(items, key=lambda item: item["id"])
    key = COLLECTION_KEYS.get(name, name)
    atomic_write_json(STATE / f"{name}.json", {"version": 1, key: ordered})


def lifecycle_status(record: dict[str, Any], *, kind: str) -> str:
    """Return the additive knowledge lifecycle without confusing claim confidence."""

    value = record.get("lifecycle_status")
    if value is None and kind == "source":
        value = record.get("status")
    return str(value or "active")


def find(items: Iterable[dict[str, Any]], item_id: str, kind: str) -> dict[str, Any]:
    for item in items:
        if item.get("id") == item_id:
            return item
    raise WikiError(f"Unknown {kind}: {item_id}")


def research_portfolio_config() -> tuple[dict[str, Any], dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    """프로젝트와 관심사 참조를 하나의 fail-closed 포트폴리오로 읽는다."""

    payload = load_json(ROOT / "config" / "interests.json")
    if not isinstance(payload, dict):
        raise WikiError("config/interests.json must be an object")
    if payload.get("schema_version") != RESEARCH_PORTFOLIO_SCHEMA_VERSION:
        raise WikiError(
            f"config/interests.json schema_version must be {RESEARCH_PORTFOLIO_SCHEMA_VERSION}"
        )
    projects = payload.get("projects")
    interests = payload.get("interests")
    if not isinstance(projects, list) or not projects:
        raise WikiError("config/interests.json must contain a non-empty projects list")
    if not isinstance(interests, list):
        raise WikiError("config/interests.json must contain an interests list")

    project_by_id: dict[str, dict[str, Any]] = {}
    for project in projects:
        if not isinstance(project, dict):
            raise WikiError("each research project must be an object")
        project_id = project.get("id")
        if not isinstance(project_id, str) or re.fullmatch(
            r"PRJ-[A-Z0-9]+(?:-[A-Z0-9]+)*",
            project_id,
        ) is None:
            raise WikiError(
                "each research project id must match PRJ-[A-Z0-9]+(?:-[A-Z0-9]+)*"
            )
        if project_id in project_by_id:
            raise WikiError(f"duplicate research project id: {project_id}")
        if not isinstance(project.get("name"), str) or not project["name"].strip():
            raise WikiError(f"{project_id}: project name must be non-empty")
        if project.get("status") not in PROJECT_STATUSES:
            raise WikiError(f"{project_id}: invalid project status")
        project_by_id[project_id] = project

    interest_by_id: dict[str, dict[str, Any]] = {}
    for interest in interests:
        if not isinstance(interest, dict):
            raise WikiError("each research interest must be an object")
        interest_id = interest.get("id")
        if not isinstance(interest_id, str) or not interest_id:
            raise WikiError("each research interest id must be a non-empty string")
        if interest_id in interest_by_id:
            raise WikiError(f"duplicate research interest id: {interest_id}")
        project_id = interest.get("project_id")
        if not isinstance(project_id, str) or not project_id:
            raise WikiError(f"{interest_id}: project_id must be a non-empty string")
        if project_id not in project_by_id:
            raise WikiError(f"{interest_id}: unknown project_id {project_id}")
        research_brief = interest.get("research_brief", {})
        if not isinstance(research_brief, dict):
            raise WikiError(f"{interest_id}: research_brief must be an object")
        interest_by_id[interest_id] = interest
    return payload, project_by_id, interest_by_id


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

    recorded_at = utc_now()
    item = {
        "id": source_id,
        "title": args.title,
        "url": args.url,
        "source_type": args.source_type,
        "authors": parse_csv(args.authors),
        "publisher": args.publisher,
        "published_at": args.published,
        "created_at": recorded_at,
        "content_updated_at": recorded_at,
        "retrieved_at": recorded_at,
        "publication_status": args.publication_status,
        "independence_group": args.independence_group or source_id,
        "source_level": args.level,
        "assessment": {
            "assessed_by": args.actor,
            "assessed_at": recorded_at,
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
        "lifecycle_status": "active",
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
    assessed_at = utc_now()
    item["source_level"] = args.level
    item["content_updated_at"] = assessed_at
    item["assessment"] = {
        **item.get("assessment", {}),
        "assessed_by": args.actor,
        "assessed_at": assessed_at,
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
    scope = args.scope.strip() or "일반"
    claim_id = stable_id("CLM", normalized.casefold(), scope.casefold())
    claims = collection("claims")
    if any(c.get("id") == claim_id for c in claims):
        print(claim_id)
        return
    created_at = utc_now()
    item = {
        "id": claim_id,
        "statement": normalized,
        "kind": args.kind,
        "scope": scope,
        "created_by": args.actor,
        "created_by_group": actor_independence_group(creator),
        "created_at": created_at,
        "content_updated_at": created_at,
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
            "rationale": "연결된 증거가 없음.",
        },
        "supersedes": parse_csv(args.supersedes),
        "notes": args.notes,
        "lifecycle_status": "active",
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
    added_at = utc_now()
    edge = {
        "source_id": args.source,
        "relation": args.relation,
        "locator": args.locator.strip(),
        "strength": args.strength,
        "added_by": args.actor,
        "added_at": added_at,
        "note": args.note,
    }
    signature = (args.source, args.relation, args.locator.strip())
    for existing in claim.get("evidence", []):
        if (existing.get("source_id"), existing.get("relation"), existing.get("locator")) == signature:
            print(args.claim)
            return
    claim.setdefault("evidence", []).append(edge)
    claim["evidence"] = sorted(claim["evidence"], key=lambda e: (e["source_id"], e["relation"], e["locator"]))
    claim["content_updated_at"] = added_at
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
        if (
            not source
            or source.get("status", "active") != "active"
            or lifecycle_status(source, kind="source") != "active"
        ):
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
        reasons.append("추적 가능한 지지 출처가 하나 이상 있음")
    if high_support or len(support_groups) >= 2:
        level = 2
        reasons.append("강한 직접 출처가 있거나 독립 출처 그룹이 둘 이상임")
    if len(support_groups) >= 2 and high_support and positive_reviews and not strong_contradiction:
        level = 3
        reasons.append("독립 교차확인과 독립 검토를 충족함")
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
        reasons.append("고품질 출처 다수, 적대적 검토와 견고한 검증 표지를 충족함")

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
        "rationale": "; ".join(reasons) if reasons else "조건을 충족하는 지지 증거가 없음.",
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
        elif "computed_at" not in claim.get("confidence", {}):
            claim["confidence"] = new
    save_collection("claims", claims)
    render_epistemic_dashboard(claims, sources)
    if changed:
        append_event(args.actor, "claims.evaluate", "all", {"changed": changed})
    print(f"Evaluated {len(claims)} claims; {changed} changed.")


def campaign_add(args: argparse.Namespace) -> None:
    require_actor(args.actor)
    _, _, interest_by_id = research_portfolio_config()
    interest = interest_by_id.get(args.interest)
    if interest is None:
        raise WikiError(f"Unknown research interest: {args.interest}")
    campaign_id = stable_id("CMP", args.question.casefold(), args.interest)
    campaigns = collection("campaigns")
    if any(c.get("id") == campaign_id for c in campaigns):
        print(campaign_id)
        return
    item = {
        "id": campaign_id,
        "project_id": interest["project_id"],
        "interest_id": args.interest,
        "research_brief": copy.deepcopy(interest.get("research_brief", {})),
        "question": args.question.strip(),
        "why_now": args.why,
        "priority": args.priority,
        "status": "queued",
        "created_by": args.actor,
        "created_at": utc_now(),
        "max_sources": args.max_sources,
        "max_minutes": args.max_minutes,
        "required_independent_groups": args.independent_groups,
        "stop_conditions": parse_csv(args.stop) or ["새 주장이 없는 상태가 두 회차 지속됨", "예산 소진"],
        "counter_search_required": True,
        "source_ids": [],
        "claim_ids": [],
        "notes": [],
    }
    campaigns.append(item)
    save_collection("campaigns", campaigns)
    append_event(
        args.actor,
        "campaign.add",
        campaign_id,
        {"question": args.question, "project_id": interest["project_id"]},
    )
    print(campaign_id)


def campaign_project_backfill(args: argparse.Namespace) -> None:
    """기존 캠페인에 관심사가 가리키는 프로젝트를 한 번만 분류한다."""

    require_actor(args.actor)
    _, project_by_id, interest_by_id = research_portfolio_config()
    campaigns = collection("campaigns")
    changed: list[tuple[str, str, str]] = []
    for campaign in campaigns:
        campaign_id = str(campaign.get("id", ""))
        interest_id = campaign.get("interest_id")
        interest = interest_by_id.get(interest_id)
        if interest is None:
            raise WikiError(f"{campaign_id}: unknown interest_id {interest_id}")
        expected = str(interest["project_id"])
        current = campaign.get("project_id")
        if current is not None and current not in project_by_id:
            raise WikiError(f"{campaign_id}: unknown project_id {current}")
        if current is None:
            campaign["project_id"] = expected
            changed.append((campaign_id, str(interest_id), expected))
    if changed:
        save_collection("campaigns", campaigns)
        for campaign_id, interest_id, project_id in changed:
            append_event(
                args.actor,
                "campaign.project.assign",
                campaign_id,
                {
                    "interest_id": interest_id,
                    "project_id": project_id,
                    "migration": "research-project-portfolio/v1",
                },
            )
    print(f"프로젝트를 분류한 캠페인: {len(changed)}개")


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
    config, project_by_id, interest_by_id = research_portfolio_config()
    interests = list(interest_by_id.values())
    wiki_config = load_json(ROOT / "config" / "wiki.json")
    timezone_name = wiki_config.get("timezone")
    if not isinstance(timezone_name, str) or not timezone_name.strip():
        raise WikiError("config/wiki.json timezone must be a non-empty IANA timezone")
    schedule = config.get("schedule", {})
    if schedule is None:
        schedule = {}
    if not isinstance(schedule, dict):
        raise WikiError("config/interests.json schedule must be an object")
    configured_schedule_timezone = schedule.get("timezone")
    if configured_schedule_timezone not in (None, timezone_name):
        raise WikiError("interest schedule timezone must match config/wiki.json timezone")
    try:
        local_zone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        raise WikiError("config/wiki.json timezone is not available") from None
    local_date = now.astimezone(local_zone).date()
    cycle_key = local_date.isoformat()
    daily_limit = schedule.get("max_campaigns_per_local_day", 1)
    if isinstance(daily_limit, bool) or not isinstance(daily_limit, int) or daily_limit < 1:
        raise WikiError("schedule.max_campaigns_per_local_day must be a positive integer")
    campaigns = collection("campaigns")
    created: list[str] = []

    existing_local_cycles = sum(
        1
        for item in campaigns
        if item.get("cycle_key") == cycle_key
    )
    available_slots = min(args.max_campaigns, daily_limit - existing_local_cycles)
    if available_slots <= 0:
        print("No interest is due for campaign seeding.")
        return

    def parsed_timestamp(value: Any) -> dt.datetime | None:
        if not isinstance(value, str):
            return None
        try:
            return runtime.parse_time(value)
        except runtime.RuntimeErrorBase as exc:
            raise WikiError(f"invalid campaign timestamp {value}") from exc

    due_interests: list[
        tuple[tuple[Any, ...], dict[str, Any], list[dict[str, Any]], dt.datetime | None, dt.datetime | None]
    ] = []
    for interest in interests:
        if interest.get("status", "active") != "active":
            continue
        if project_by_id[str(interest["project_id"])].get("status") != "active":
            continue
        interest_id = str(interest["id"])
        related = [item for item in campaigns if item.get("interest_id") == interest_id]
        if any(item.get("status") in {"queued", "active"} for item in related):
            continue
        attempts = [
            value
            for item in related
            if (value := parsed_timestamp(item.get("created_at"))) is not None
        ]
        successes = [
            value
            for item in related
            if item.get("status") == "completed"
            and (
                value := parsed_timestamp(item.get("updated_at") or item.get("created_at"))
            )
            is not None
        ]
        last_attempt = max(attempts) if attempts else None
        last_success = max(successes) if successes else None
        cadence_days = max(0, int(interest.get("cadence_days", 0)))
        if last_success is not None:
            next_local_date = last_success.astimezone(local_zone).date() + dt.timedelta(
                days=cadence_days
            )
            if local_date < next_local_date:
                continue
        questions = [str(item).strip() for item in interest.get("questions", []) if str(item).strip()]
        if not questions:
            continue
        brief = interest.get("research_brief", {})
        if not isinstance(brief, dict):
            raise WikiError(f"{interest_id}: research_brief must be an object")
        fairness_key = (
            0 if last_attempt is None else 1,
            last_attempt or dt.datetime.min.replace(tzinfo=dt.timezone.utc),
            0 if last_success is None else 1,
            last_success or dt.datetime.min.replace(tzinfo=dt.timezone.utc),
            -float(interest.get("priority", 0.0)),
            interest_id,
        )
        due_interests.append(
            (fairness_key, interest, related, last_attempt, last_success)
        )

    due_interests.sort(key=lambda item: item[0])
    for _, interest, related, last_attempt, last_success in due_interests:
        if len(created) >= available_slots:
            break
        interest_id = str(interest["id"])
        cadence_days = max(0, int(interest.get("cadence_days", 0)))
        questions = [str(item).strip() for item in interest.get("questions", []) if str(item).strip()]
        completed_related = [item for item in related if item.get("status") == "completed"]
        usage = {
            question: sum(item.get("question") == question for item in completed_related)
            for question in questions
        }
        question = min(questions, key=lambda value: (usage[value], questions.index(value)))
        campaign_id = stable_id("CMP", interest_id, question.casefold(), cycle_key)
        if any(item.get("id") == campaign_id for item in campaigns):
            continue
        limits = load_json(ROOT / "config" / "wiki.json").get("research_limits", {})
        item = {
            "id": campaign_id,
            "project_id": str(interest["project_id"]),
            "interest_id": interest_id,
            "question": question,
            "why_now": f"{cadence_days}일 연구 주기가 {now.isoformat()}에 도래함.",
            "priority": float(interest.get("priority", 0.5)),
            "status": "queued",
            "created_by": args.actor,
            "created_at": now.isoformat(),
            "cadence_days": cadence_days,
            "cycle_key": cycle_key,
            "schedule_timezone": timezone_name,
            "research_brief": copy.deepcopy(interest.get("research_brief", {})),
            "selection": {
                "policy_version": "fair-interest-portfolio/v1",
                "local_date": cycle_key,
                "timezone": timezone_name,
                "last_attempt_at": last_attempt.isoformat() if last_attempt else None,
                "last_success_at": last_success.isoformat() if last_success else None,
                "priority": float(interest.get("priority", 0.5)),
                "completed_question_count": usage[question],
            },
            "max_sources": int(limits.get("default_max_sources_per_cycle", 12)),
            "max_minutes": int(limits.get("default_max_minutes_per_cycle", 45)),
            "required_independent_groups": int(limits.get("min_independent_source_groups", 2)),
            "stop_conditions": [
                "반증 검색 완료",
                f"새 주장이 없는 상태가 {int(limits.get('stop_after_no_novel_claim_rounds', 2))}회 지속됨",
                "예산 소진",
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
            {
                "interest_id": interest_id,
                "project_id": str(interest["project_id"]),
                "cycle_key": cycle_key,
                "cadence_days": cadence_days,
                "schedule_timezone": timezone_name,
                "selection_policy": "fair-interest-portfolio/v1",
                "last_attempt_at": last_attempt.isoformat() if last_attempt else None,
                "last_success_at": last_success.isoformat() if last_success else None,
                "completed_question_count": usage[question],
            },
        )
    if created:
        print("\n".join(created))
    else:
        print("No interest is due for campaign seeding.")


def render_proposal_record(item: dict[str, Any]) -> None:
    proposal_folder = ROOT / "governance" / "proposals"
    existing_paths = sorted(proposal_folder.glob(f"{item['id'].lower()}-*.md"))
    if len(existing_paths) > 1:
        raise WikiError(f"{item['id']}: 같은 RFC를 가리키는 제안 문서가 여러 개임")
    path = existing_paths[0] if existing_paths else proposal_folder / f"{item['id'].lower()}-{slugify(item['title'])}.md"
    reviews = item.get("approvals", [])
    review_lines = [
        f"- `{review.get('at', '-')}` — **{review.get('decision', '-')}** / "
        f"검토자 `{review.get('actor_id', '-')}`: {review.get('rationale', '-') }"
        for review in reviews
    ]
    body = f"""<!-- state/proposals.json에서 자동 생성함. -->
# {item['id']}: 하네스 제안 — {item['title']}

상태: `{item.get('status', 'proposed')}`
제안자: `{item['created_by']}`
생성 시각: {item['created_at']}

## 문제

기록된 문제: {item['problem']}

## 제안 변경

기록된 변경안: {item['proposed_change']}

## 근거

{chr(10).join(f'- `{e}`' for e in item.get('evidence', [])) or '- 아직 연결된 근거 없음'}

## 벤치마크와 수용 게이트

기록된 수용 기준: {item['benchmark']}

## 위험

{chr(10).join(f'- 기록된 위험: {risk}' for risk in item.get('risks', [])) or '- 미기록'}

## 롤백

기록된 롤백: {item['rollback']}

## 검토 결정

{chr(10).join(review_lines) or '- 아직 검토 결정 없음'}

## 구현 근거

{f"- 릴리스 보고서: `{item.get('implementation_evidence', {}).get('release_report')}`" if item.get('implementation_evidence') else '- 아직 구현 완료 근거 없음'}
{f"- 구성요소 지문: `{item.get('implementation_evidence', {}).get('component_fingerprint')}`" if item.get('implementation_evidence') else ''}
{f"- 운영 환경 인증: `{item.get('implementation_evidence', {}).get('production_certified')}`" if item.get('implementation_evidence') else ''}
"""
    atomic_write_text(path, body)


def validate_proposal_evidence_ids(evidence_ids: list[str]) -> list[str]:
    """제안 근거가 현재 원장의 claim ID만 참조하는지 쓰기 전에 확인한다."""

    known_claim_ids = {item.get("id") for item in collection("claims")}
    unknown = sorted({item for item in evidence_ids if item not in known_claim_ids})
    if unknown:
        raise WikiError(
            "제안 근거는 기존 claim ID만 사용할 수 있음: " + ", ".join(unknown)
        )
    return sorted(set(evidence_ids))


def proposal_add(args: argparse.Namespace) -> None:
    require_actor(args.actor)
    evidence_ids = validate_proposal_evidence_ids(parse_csv(args.evidence))
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
        "evidence": evidence_ids,
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
    """Close or reseal an RFC only after a passing, anchored release report."""

    require_actor(args.actor)
    actor = actor_record(args.actor)
    if not ({"maintainer", "policy-approver"} & set(actor.get("roles", []))):
        raise WikiError("Only a maintainer or policy-approver may mark an approved proposal implemented")
    proposals = collection("proposals")
    proposal = find(proposals, args.proposal, "proposal")
    already_implemented = proposal.get("status") == "implemented"
    if proposal.get("status") not in {"approved", "implemented"}:
        raise WikiError("Only an approved or already implemented proposal can bind release evidence")
    report_path = Path(args.release_report).expanduser().resolve()
    try:
        report_path.relative_to(EVALUATION_REPORTS.resolve())
    except ValueError as exc:
        raise WikiError("Release report must be inside evaluations/reports") from exc
    report = load_json(report_path)
    expected_component = digest_text(canonical_json(report.get("gates", [])))
    expected_report_digest = digest_text(
        canonical_json({key: value for key, value in report.items() if key != "report_digest"})
    )
    gate_records = [gate for gate in report.get("gates", []) if isinstance(gate, dict)]
    gate_names = [gate.get("name") for gate in gate_records]
    gates_by_name = {
        gate.get("name"): gate
        for gate in gate_records
        if isinstance(gate, dict) and isinstance(gate.get("name"), str)
    }
    mandatory_gate_names = {
        "structural_and_ledger",
        "okf_bundle",
        "calibration",
        "security",
        "runtime",
        "regression_tests",
        "memory_feedback_lifecycle_hygiene",
        "korean_documentation_contract",
    }
    current_harness_manifest = harness_component_manifest()
    current_harness_digest = digest_text(canonical_json(current_harness_manifest))
    if (
        report.get("release_id") != "living-wiki-v4"
        or report.get("passed") is not True
        or report.get("production_certified") is not False
        or report.get("harness_version") != load_json(ROOT / "config" / "wiki.json").get("harness_version")
        or report.get("component_fingerprint") != expected_component
        or report.get("report_digest") != expected_report_digest
        or report.get("harness_manifest_sha256") != current_harness_digest
        or report.get("harness_file_count") != len(current_harness_manifest)
        or len(gate_names) != len(set(gate_names))
        or any(
            not isinstance(gates_by_name.get(name), dict)
            or gates_by_name[name].get("passed") is not True
            for name in mandatory_gate_names
        )
    ):
        raise WikiError("Proposal implementation requires a fresh, integrity-checked v4.2 release report")
    approval_times = [
        item.get("at")
        for item in proposal.get("approvals", [])
        if item.get("decision") == "approve" and isinstance(item.get("at"), str)
    ]
    approved_at = max(approval_times, default=proposal.get("created_at", ""))
    anchored = any(
        event.get("action") == "release.evaluate"
        and event.get("subject") == "living-wiki-v4"
        and event.get("details", {}).get("component_fingerprint") == report.get("component_fingerprint")
        and event.get("details", {}).get("report_digest") == report.get("report_digest")
        and str(event.get("at", "")) >= str(approved_at)
        for event in event_lines()
    )
    if not anchored:
        raise WikiError("Release report is not anchored by a post-approval release event")
    archived_report = EVALUATION_REPORTS / f"v4-release-{report['component_fingerprint'][:16]}.json"
    if not archived_report.exists():
        atomic_write_json(archived_report, report)
    evidence = {
        "release_report": archived_report.relative_to(ROOT).as_posix(),
        "component_fingerprint": report["component_fingerprint"],
        "production_certified": False,
    }
    if already_implemented and proposal.get("implementation_evidence") == evidence:
        print(args.proposal)
        return
    now = utc_now()
    proposal["status"] = "implemented"
    if not already_implemented:
        proposal["implemented_by"] = args.actor
        proposal["implemented_at"] = now
    else:
        proposal["revalidated_by"] = args.actor
        proposal["revalidated_at"] = now
    proposal["updated_at"] = now
    proposal["implementation_evidence"] = evidence
    save_collection("proposals", proposals)
    render_proposal_record(proposal)
    append_event(
        args.actor,
        "proposal.implementation.reseal" if already_implemented else "proposal.implement",
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


def _reference_exists(reference: str, known_ids: set[str]) -> bool:
    if reference in known_ids:
        return True
    if not reference.startswith("wiki/"):
        return False
    candidate = (ROOT / reference).resolve()
    try:
        candidate.relative_to(WIKI.resolve())
    except ValueError:
        return False
    return candidate.is_file()


def _known_reference_ids() -> set[str]:
    names = (
        "actors",
        "sources",
        "claims",
        "reviews",
        "campaigns",
        "proposals",
        "collaborations",
        "admissions",
        "runs",
        "memory_feedback",
    )
    identifiers = {str(item["id"]) for name in names for item in collection(name) if item.get("id")}
    identifiers.update(str(event["id"]) for event in event_lines() if event.get("id"))
    return identifiers


def memory_feedback_add(args: argparse.Namespace) -> None:
    """Record a retrieval outcome without granting it any automatic trust effect."""

    require_actor(args.actor)
    import memory_feedback

    targets = parse_csv(args.targets)
    evidence_refs = parse_csv(args.evidence_refs)
    known_ids = _known_reference_ids()
    target_ids = {
        *(str(item["id"]) for item in collection("claims")),
        *(str(item["id"]) for item in collection("sources")),
    }
    unknown_targets = sorted(
        reference for reference in targets if not _reference_exists(reference, target_ids)
    )
    unknown_evidence = sorted(
        reference for reference in evidence_refs if not _reference_exists(reference, known_ids)
    )
    unknown = [*unknown_targets, *unknown_evidence]
    if unknown:
        raise WikiError("Unknown feedback reference(s): " + ", ".join(unknown))
    try:
        record = memory_feedback.make_retrieval_feedback(
            actor_id=args.actor,
            targets=targets,
            outcome=args.outcome,
            task_ref=args.task_ref,
            rationale=args.rationale,
            evidence_refs=evidence_refs,
            created_at=args.at or utc_now(),
        )
    except memory_feedback.MemoryFeedbackError as exc:
        raise WikiError(str(exc)) from exc
    records = collection("memory_feedback")
    prior = next((item for item in records if item.get("id") == record["id"]), None)
    if prior is not None:
        try:
            memory_feedback.validate_retrieval_feedback(prior)
        except memory_feedback.MemoryFeedbackError as exc:
            raise WikiError(f"Existing feedback is invalid: {exc}") from exc
        print(record["id"])
        return
    records.append(record)
    save_collection("memory_feedback", records)
    append_event(
        args.actor,
        "memory.feedback.add",
        record["id"],
        {
            "identity_digest": memory_feedback.feedback_digest(record),
            "state_digest": memory_feedback.feedback_state_digest(record),
            "trust_effect": "none",
            "automatic_action": False,
        },
    )
    print(record["id"])


def memory_feedback_resolve(args: argparse.Namespace) -> None:
    require_actor(args.actor)
    import memory_feedback

    records = collection("memory_feedback")
    record = find(records, args.feedback, "memory feedback")
    try:
        resolved = memory_feedback.resolve_retrieval_feedback(
            record,
            actor_id=args.actor,
            rationale=args.rationale,
            at=args.at or utc_now(),
        )
    except memory_feedback.MemoryFeedbackError as exc:
        raise WikiError(str(exc)) from exc
    if resolved == record:
        print(args.feedback)
        return
    records = [resolved if item.get("id") == args.feedback else item for item in records]
    save_collection("memory_feedback", records)
    append_event(
        args.actor,
        "memory.feedback.resolve",
        args.feedback,
        {
            "state_digest": memory_feedback.feedback_state_digest(resolved),
            "trust_effect": "none",
            "automatic_action": False,
        },
    )
    print(args.feedback)


def knowledge_lifecycle(args: argparse.Namespace) -> None:
    """Apply one attributed, non-destructive source/claim lifecycle transition."""

    require_actor(args.actor)
    actor = actor_record(args.actor)
    if not ({"maintainer", "policy-approver"} & set(actor.get("roles", []))):
        raise WikiError("Knowledge lifecycle transitions require maintainer or policy-approver role")
    import memory_feedback

    collection_name = "claims" if args.kind == "claim" else "sources"
    records = collection(collection_name)
    subject = find(records, args.id, args.kind)
    if args.replacement:
        replacement = find(records, args.replacement, f"replacement {args.kind}")
        if lifecycle_status(replacement, kind=args.kind) != "active":
            raise WikiError("Replacement must have active lifecycle status")
    try:
        updated, transition = memory_feedback.transition_lifecycle(
            subject,
            to_status=args.status,
            actor_id=args.actor,
            reason=args.reason,
            replacement_ref=args.replacement,
            created_at=args.at or utc_now(),
        )
    except memory_feedback.MemoryFeedbackError as exc:
        raise WikiError(str(exc)) from exc
    records = [updated if item.get("id") == args.id else item for item in records]
    save_collection(collection_name, records)
    append_event(
        args.actor,
        "knowledge.lifecycle.transition",
        transition["id"],
        {
            "kind": args.kind,
            "target": args.id,
            "from": transition["from_status"],
            "to": transition["to_status"],
            "replacement": transition["replacement_ref"],
            "transition_digest": memory_feedback.lifecycle_transition_digest(transition),
            "automatic_action": False,
            "destructive_action": False,
        },
    )
    print(transition["id"])


def memory_hygiene_cmd(args: argparse.Namespace) -> None:
    """Print a fixed-time, read-only memory hygiene observation."""

    import memory_hygiene

    try:
        report = memory_hygiene.evaluate_repository(ROOT, now=args.now)
    except memory_hygiene.MemoryHygieneError as exc:
        raise WikiError(str(exc)) from exc
    print(memory_hygiene.canonical_json(report, pretty=not args.compact), end="")


def hygiene_plan_cmd(args: argparse.Namespace) -> None:
    """Print a bounded, deterministic, read-only semantic hygiene plan."""

    import wiki_hygiene

    config = load_json(ROOT / "config" / "wiki.json")
    limits = config.get("hygiene_selection") if isinstance(config, dict) else None
    if not isinstance(limits, dict):
        raise WikiError("config/wiki.json에 hygiene_selection 설정이 필요함")
    try:
        plan = wiki_hygiene.build_hygiene_plan(ROOT, now=args.now, limits=limits)
    except wiki_hygiene.HygienePlanError as exc:
        raise WikiError(str(exc)) from exc
    if args.pretty:
        print(json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        sys.stdout.write(wiki_hygiene.canonical_plan_bytes(plan).decode("utf-8"))


def search_cmd(args: argparse.Namespace) -> None:
    import runtime

    try:
        results = runtime.lexical_search(
            args.query,
            root=ROOT,
            limit=args.limit,
            include_inactive=args.include_inactive,
        )
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
    inactive = [
        item.get("id")
        for kind, items in (("claim", collection("claims")), ("source", collection("sources")))
        for item in items
        if lifecycle_status(item, kind=kind) != "active"
    ]
    if inactive:
        result = {
            "passed": False,
            "base_commit": base_commit,
            "live_workspace_unchanged": True,
            "commands_passed": 0,
            "evidence": digest_text(canonical_json(sorted(inactive))),
            "error": (
                "v3.1 rollback would lose inactive lifecycle semantics; an explicit "
                "migration or v4.1-compatible rollback reader is required"
            ),
        }
        atomic_write_json(EVALUATION_REPORTS / "rollback-rehearsal-latest.json", result)
        return result
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


def _memory_control_release_gate() -> dict[str, Any]:
    """Exercise pinned memory controls and the bounded v4.2 hygiene planner."""

    import memory_feedback
    import memory_hygiene
    import wiki_hygiene

    errors: list[str] = []
    warnings = ["memory feedback is selectively observed diagnostic data, not epistemic ground truth"]
    summary: dict[str, Any] = {}
    try:
        fixture_hash = digest_file(MEMORY_FEEDBACK_FIXTURE)
        if fixture_hash != MEMORY_FEEDBACK_FIXTURE_SHA256:
            errors.append("memory_feedback_fixture_hash_drift")
        fixture = load_json(MEMORY_FEEDBACK_FIXTURE)
        if fixture.get("version") != 1:
            errors.append("unexpected_memory_feedback_fixture_version")
        records = [memory_feedback.make_retrieval_feedback(**item) for item in fixture.get("feedback_inputs", [])]
        aggregate = memory_feedback.aggregate_feedback_report(
            [*records, *records[:1]],
            generated_at="2026-07-12T03:00:00+00:00",
        )
        expected = fixture.get("expected_aggregate", {})
        for field in (
            "input_records",
            "unique_records",
            "duplicate_records",
            "outcome_counts",
            "status_counts",
            "evidence",
        ):
            if aggregate.get(field) != expected.get(field):
                errors.append(f"memory_feedback_aggregate_mismatch:{field}")
        for scenario in fixture.get("lifecycle_scenarios", []):
            subject = scenario["subject"]
            updated, transition = memory_feedback.transition_lifecycle(
                subject,
                to_status=scenario["to_status"],
                actor_id=scenario["actor_id"],
                reason=scenario["reason"],
                replacement_ref=scenario.get("replacement_ref"),
                created_at=scenario["created_at"],
            )
            if transition.get("automatic_action") is not False or transition.get("destructive_action") is not False:
                errors.append("lifecycle_transition_is_automatic_or_destructive")
            for protected in ("confidence", "source_level", "statement", "title"):
                if protected in subject and updated.get(protected) != subject.get(protected):
                    errors.append(f"lifecycle_mutated_protected_field:{protected}")
        first = memory_hygiene.evaluate_repository(
            ROOT,
            now="2026-08-11T00:00:00+00:00",
        )
        second = memory_hygiene.evaluate_repository(
            ROOT,
            now="2026-08-11T00:00:00+00:00",
        )
        deterministic = memory_hygiene.canonical_json(first) == memory_hygiene.canonical_json(second)
        if not deterministic:
            errors.append("memory_hygiene_report_not_deterministic")
        required_false = (
            "trust_mutated",
            "lifecycle_mutated",
            "status_mutated",
            "content_deleted",
            "feedback_changes_ranking_or_trust",
            "wall_clock_used",
        )
        if first.get("invariants", {}).get("read_only") is not True:
            errors.append("memory_hygiene_not_read_only")
        for field in required_false:
            if first.get("invariants", {}).get(field) is not False:
                errors.append(f"memory_hygiene_invariant_failed:{field}")
        hygiene_limits = load_json(ROOT / "config" / "wiki.json").get("hygiene_selection")
        if not isinstance(hygiene_limits, dict):
            errors.append("hygiene_selection_config_missing")
            hygiene_limits = {}
        hygiene_before = wiki_hygiene.repository_fingerprints(ROOT)
        hygiene_first = wiki_hygiene.build_hygiene_plan(
            ROOT,
            now="2026-08-11T00:00:00+00:00",
            limits=hygiene_limits,
        )
        hygiene_second = wiki_hygiene.build_hygiene_plan(
            ROOT,
            now="2026-08-11T00:00:00+00:00",
            limits=hygiene_limits,
        )
        hygiene_after = wiki_hygiene.repository_fingerprints(ROOT)
        hygiene_bytes = wiki_hygiene.canonical_plan_bytes(hygiene_first)
        if hygiene_bytes != wiki_hygiene.canonical_plan_bytes(hygiene_second):
            errors.append("bounded_hygiene_plan_not_deterministic")
        if hygiene_before != hygiene_after:
            errors.append("bounded_hygiene_plan_not_read_only")
        if len(hygiene_first.get("selected_nodes", [])) > int(hygiene_limits.get("max_nodes", -1)):
            errors.append("bounded_hygiene_node_limit_exceeded")
        if len(hygiene_first.get("conflict_candidates", [])) > int(hygiene_limits.get("max_pairs", -1)):
            errors.append("bounded_hygiene_pair_limit_exceeded")
        if len(hygiene_first.get("semantic_review_queue", [])) > int(
            hygiene_limits.get("semantic_review_limit", -1)
        ):
            errors.append("bounded_hygiene_review_limit_exceeded")
        if any(
            int(node.get("hop", 0)) > int(hygiene_limits.get("max_hops", -1))
            for node in hygiene_first.get("selected_nodes", [])
        ):
            errors.append("bounded_hygiene_hop_limit_exceeded")
        expected_hygiene_invariants = {
            "read_only": True,
            "conflicts_are_review_only": True,
            "automatic_evidence_mutation": False,
            "automatic_trust_mutation": False,
            "automatic_lifecycle_mutation": False,
        }
        if hygiene_first.get("invariants") != expected_hygiene_invariants:
            errors.append("bounded_hygiene_safety_invariant_failed")
        harness_manifest = harness_component_manifest()
        summary = {
            "fixture_sha256": fixture_hash,
            "aggregate_report_digest": aggregate.get("report_digest"),
            "hygiene_report_sha256": digest_text(memory_hygiene.canonical_json(first)),
            "deterministic": deterministic,
            "feedback_records": first.get("summary", {}).get("feedback"),
            "active_stale_claims": first.get("summary", {}).get("active_stale_claims"),
            "metadata_only_sources": first.get("summary", {}).get("metadata_only_sources"),
            "bounded_hygiene_plan_sha256": digest_text(hygiene_bytes.decode("utf-8")),
            "bounded_hygiene_seeds": len(hygiene_first.get("seeds", [])),
            "bounded_hygiene_selected_nodes": len(hygiene_first.get("selected_nodes", [])),
            "bounded_hygiene_conflict_candidates": len(
                hygiene_first.get("conflict_candidates", [])
            ),
            "bounded_hygiene_review_queue": len(hygiene_first.get("semantic_review_queue", [])),
            "automatic_action": False,
            "trust_effect": "none",
            "content_deleted": False,
            "harness_file_count": len(harness_manifest),
            "harness_manifest_sha256": digest_text(canonical_json(harness_manifest)),
        }
    except (
        OSError,
        KeyError,
        TypeError,
        WikiError,
        memory_feedback.MemoryFeedbackError,
        memory_hygiene.MemoryHygieneError,
        wiki_hygiene.HygienePlanError,
    ) as exc:
        errors.append(f"memory_control_evaluation_failed:{type(exc).__name__}:{exc}")
    return {
        "name": "memory_feedback_lifecycle_hygiene",
        "passed": not errors,
        "status": "fixed_fixture_and_bounded_live_read_only_observation",
        "production_memory_certified": False,
        "errors": sorted(set(errors)),
        "warnings": warnings,
        "summary": summary,
    }


def _korean_documentation_release_gate() -> dict[str, Any]:
    """한국어 문서 계약을 독립 릴리스 게이트로 평가한다."""

    import korean_docs

    findings = [
        item
        for item in korean_docs.validate_repository(ROOT)
        if not item.startswith("evaluations/reports/v4-release-report.md:")
    ]
    return {
        "name": "korean_documentation_contract",
        "passed": not findings,
        "status": "한국어 문서 계약 통과" if not findings else "한국어 문서 계약 위반",
        "errors": findings,
        "warnings": [],
        "summary": {
            "spec_id": "SPEC-KO-DOCS-001",
            "finding_count": len(findings),
        },
    }


def _release_report_markdown(report: dict[str, Any]) -> str:
    gate_rows = [
        f"| `{gate.get('name', '-')}` | {'통과' if gate.get('passed') else '실패'} | "
        f"{len(gate.get('errors', []))} | {len(gate.get('warnings', []))} |"
        for gate in report.get("gates", [])
    ]
    quarantine = report.get("quarantine_validation", {})
    return f"""# Living Wiki v4 릴리스 보고서

- 결과: **{'통과' if report.get('passed') else '실패'}**
- 준비 상태: `{report.get('readiness')}`
- 운영 환경 인증: **{str(report.get('production_certified')).lower()}**
- 보정: `{report.get('calibration_status')}`
- 보안: `{report.get('security_status')}`
- 메모리 위생: `{report.get('memory_hygiene_status')}`
- 범위 제한 후보 계획: `{report.get('bounded_hygiene_status')}`
- 격리 검증 프로필: `{quarantine.get('profile', '-')}`
- 격리 payload bytes 검증: **{str(quarantine.get('quarantine_payload_verified')).lower()}** (전체 {quarantine.get('total', 0)}개, 실제 확인 {quarantine.get('present', 0)}개, 누락 {quarantine.get('missing', 0)}개)
- 하네스 버전: `{report.get('harness_version')}`
- 하네스 명세표: `{report.get('harness_manifest_sha256')}` (파일 {report.get('harness_file_count')}개)
- 구성요소 지문: `{report.get('component_fingerprint')}`
- 보고서 다이제스트: `{report.get('report_digest')}`

| 게이트 | 결과 | 오류 | 경고 |
|---|---|---:|---:|
{chr(10).join(gate_rows)}

## 해석

이 판정은 로컬 제어 계층과 고정 fixture의 회귀 통과를 뜻한다. 장기 경험적 보정, 아직 보지 못한 의미 공격, 실제 외부 실행기와 자격증명·공개 경로는 인증하지 않는다.
"""


def harness_component_manifest() -> dict[str, str]:
    """Hash release-relevant harness inputs without mutable state or generated views."""

    files: list[Path] = []
    for folder in (
        "tools",
        "tests",
        "config",
        "prompts",
        "docs",
        "evolution",
        "skills",
        "wiki/specs",
    ):
        base = ROOT / folder
        if base.is_dir():
            files.extend(path for path in base.rglob("*") if path.is_file())
    files.extend(
        path
        for path in (
            ROOT / "AGENTS.md",
            ROOT / "README.md",
            ROOT / "pyproject.toml",
            ROOT / "governance" / "constitution.md",
            ROOT / "governance" / "decision-log.md",
        )
        if path.is_file()
    )
    manifest: dict[str, str] = {}
    for path in sorted(set(files), key=lambda item: item.as_posix()):
        if "__pycache__" in path.parts or path.name.endswith((".pyc", ".tmp")):
            continue
        manifest[path.relative_to(ROOT).as_posix()] = digest_file(path)
    return manifest


def release_check(args: argparse.Namespace) -> None:
    """Orchestrate validators, tests, and fixed fixtures into a truthful v4 gate."""

    require_actor(args.actor)
    if getattr(args, "check_only", False):
        _release_check_in_shadow(args)
        return
    import release_gate
    import korean_docs

    # 릴리스 검사는 현재 템플릿에서 파생 뷰를 먼저 다시 만들어 stale 산출물 우회를 막는다.
    render_all(args.actor, log=False)
    structural = validation_findings(quarantine_profile=args.quarantine_profile)
    structural_counts = structural[2]
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
    memory_gate = _memory_control_release_gate()
    korean_documentation_gate = _korean_documentation_release_gate()
    report["gates"].extend([memory_gate, korean_documentation_gate])
    report["harness_version"] = load_json(ROOT / "config" / "wiki.json").get("harness_version")
    report["memory_hygiene_status"] = memory_gate["status"]
    report["bounded_hygiene_status"] = (
        "결정론적·읽기 전용·예산 제한 통과"
        if memory_gate.get("passed")
        else "후보 계획 게이트 실패"
    )
    report["harness_manifest_sha256"] = memory_gate.get("summary", {}).get("harness_manifest_sha256")
    report["harness_file_count"] = memory_gate.get("summary", {}).get("harness_file_count")
    quarantine_missing = structural_counts.get("quarantine_artifacts_missing", 0)
    report["quarantine_validation"] = {
        "profile": args.quarantine_profile,
        "total": structural_counts.get("quarantine_artifacts_total", 0),
        "present": structural_counts.get("quarantine_artifacts_present", 0),
        "missing": quarantine_missing,
        "quarantine_payload_verified": quarantine_missing == 0,
    }
    report["scope"] += ", fixed memory controls and bounded fixed-time hygiene candidate routing"
    report.setdefault("claims", {})["production_memory_certified"] = False
    report.setdefault("limitations", []).append(
        "Memory feedback is selection-biased diagnostic data; the fixed fixture and hygiene report do not certify production memory quality."
    )
    if quarantine_missing:
        report.setdefault("limitations", []).append(
            "The public-clean-clone profile validated anchored admission metadata, not the bytes of missing local quarantine payloads."
        )
    report["passed"] = all(gate.get("passed") is True for gate in report["gates"])
    report["readiness"] = (
        "closed_loop_harness_fixed_fixture_passed" if report["passed"] else "not_ready"
    )
    report["component_fingerprint"] = release_gate.digest(report["gates"])
    prospective_markdown = _release_report_markdown(report)
    markdown_findings = korean_docs.validate_markdown_text(
        ROOT,
        Path("evaluations/reports/v4-release-report.md"),
        prospective_markdown,
    )
    if markdown_findings:
        korean_documentation_gate["errors"] = sorted(
            set(korean_documentation_gate.get("errors", [])) | set(markdown_findings)
        )
        korean_documentation_gate["passed"] = False
        korean_documentation_gate["status"] = "한국어 문서 계약 위반"
        korean_documentation_gate["summary"]["finding_count"] = len(
            korean_documentation_gate["errors"]
        )
        report["passed"] = False
        report["readiness"] = "not_ready"
        report["component_fingerprint"] = release_gate.digest(report["gates"])
    report["report_digest"] = digest_text(canonical_json(report))
    markdown = _release_report_markdown(report)
    final_markdown_findings = korean_docs.validate_markdown_text(
        ROOT,
        Path("evaluations/reports/v4-release-report.md"),
        markdown,
    )
    if final_markdown_findings:
        raise WikiError(
            "릴리스 보고서 Markdown이 한국어 문서 계약을 통과하지 못함: "
            + "; ".join(final_markdown_findings[:3])
        )
    json_path = EVALUATION_REPORTS / "v4-release-report.json"
    atomic_write_json(json_path, report)
    archived_json_path = EVALUATION_REPORTS / f"v4-release-{report['component_fingerprint'][:16]}.json"
    if archived_json_path.exists() and load_json(archived_json_path) != report:
        raise WikiError("Content-addressed release report collision")
    if not archived_json_path.exists():
        atomic_write_json(archived_json_path, report)
    atomic_write_text(EVALUATION_REPORTS / "v4-release-report.md", markdown)
    if not args.no_log:
        append_event(
            args.actor,
            "release.evaluate",
            "living-wiki-v4",
            {
                "passed": report["passed"],
                "component_fingerprint": report["component_fingerprint"],
                "production_certified": False,
                "test_count": regression["test_count"],
                "report_digest": report["report_digest"],
            },
        )
    print(json_path.relative_to(ROOT))
    if not report["passed"]:
        raise WikiError("Living Wiki v4 release gate did not pass")


def _safe_git_paths(*, include_untracked: bool) -> list[str]:
    command = ["git", "ls-files", "-z"]
    if include_untracked:
        command = ["git", "ls-files", "--others", "--exclude-standard", "-z", "--"]
    result = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise WikiError("check-only 작업 사본 경로를 Git에서 읽지 못함")
    values = result.stdout.split("\0")
    if values[-1] != "":
        raise WikiError("check-only Git NUL 경로 출력이 잘못됨")
    paths: list[str] = []
    for value in values[:-1]:
        candidate = Path(value)
        if (
            not value
            or candidate.is_absolute()
            or ".." in candidate.parts
            or candidate.parts[0] in {".git", "auth"}
        ):
            raise WikiError("check-only에 안전하지 않은 Git 경로가 포함됨")
        paths.append(candidate.as_posix())
    return sorted(set(paths))


def _overlay_regular_path(source: Path, destination: Path) -> None:
    if not source.exists() and not source.is_symlink():
        if destination.is_dir() and not destination.is_symlink():
            shutil.rmtree(destination)
        elif destination.exists() or destination.is_symlink():
            destination.unlink()
        return
    metadata = source.lstat()
    if not stat.S_ISREG(metadata.st_mode):
        raise WikiError(f"check-only는 regular file만 복제함: {source.relative_to(ROOT)}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and destination.is_dir():
        shutil.rmtree(destination)
    shutil.copy2(source, destination, follow_symlinks=False)


def _copy_local_quarantine_to_shadow(shadow: Path) -> None:
    if not QUARANTINE.exists():
        return
    for source in sorted(QUARANTINE.rglob("*"), key=lambda item: item.as_posix()):
        if source.is_dir() and not source.is_symlink():
            continue
        if source.is_symlink() or not source.is_file():
            raise WikiError("check-only 격리 원문에는 symlink나 irregular file을 허용하지 않음")
        relative = source.relative_to(ROOT)
        _overlay_regular_path(source, shadow / relative)


def _release_check_in_shadow(args: argparse.Namespace) -> None:
    """현재 변경을 임시 detached worktree에서 검사하고 원본에는 쓰지 않는다."""

    tracked = _safe_git_paths(include_untracked=False)
    untracked = _safe_git_paths(include_untracked=True)
    with tempfile.TemporaryDirectory(prefix="wiki-release-check-") as temporary:
        shadow = Path(temporary) / "worktree"
        add = subprocess.run(
            ("git", "worktree", "add", "--detach", str(shadow), "HEAD"),
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        if add.returncode != 0:
            raise WikiError("check-only 임시 Git worktree를 만들지 못함")
        try:
            for relative in tracked:
                _overlay_regular_path(ROOT / relative, shadow / relative)
            for relative in untracked:
                _overlay_regular_path(ROOT / relative, shadow / relative)
            if args.quarantine_profile == STRICT_QUARANTINE_PROFILE:
                _copy_local_quarantine_to_shadow(shadow)
            command = [
                sys.executable,
                "tools/wiki.py",
                "release-check",
                "--actor",
                args.actor,
                "--test-timeout",
                str(args.test_timeout),
                "--quarantine-profile",
                args.quarantine_profile,
                "--no-log",
            ]
            environment = dict(os.environ)
            environment.pop("GH_TOKEN", None)
            result = subprocess.run(
                command,
                cwd=shadow,
                env=environment,
                text=True,
                capture_output=True,
                check=False,
            )
            if result.stdout:
                sys.stdout.write(result.stdout)
            if result.stderr:
                sys.stderr.write(result.stderr)
            if result.returncode != 0:
                raise WikiError("check-only 임시 작업 사본의 릴리스 게이트가 실패함")
        finally:
            subprocess.run(
                ("git", "worktree", "remove", "--force", str(shadow)),
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )


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
            parsed_times: dict[str, dt.datetime] = {}
            for key in (
                "timestamp",
                "created_at",
                "content_updated_at",
                "last_verified_at",
                "retrieved_at",
                "assessed_at",
                "lifecycle_updated_at",
                "rendered_at",
            ):
                if key not in metadata:
                    continue
                parsed = parse_timezone_aware_iso8601(metadata.get(key))
                if parsed is None:
                    errors.append(f"{relative}: '{key}' must be a timezone-aware ISO-8601 timestamp")
                else:
                    parsed_times[key] = parsed
            if (
                "created_at" in parsed_times
                and "timestamp" in parsed_times
                and parsed_times["created_at"] > parsed_times["timestamp"]
            ):
                errors.append(f"{relative}: 'created_at' must not be later than 'timestamp'")
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
        "feedback": len(collection("memory_feedback")),
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
        "feedback": len(list((OKF_BUNDLE / "feedback").glob("mfb-*.md"))),
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


def validation_findings(
    *,
    quarantine_profile: str = STRICT_QUARANTINE_PROFILE,
) -> tuple[list[str], list[str], dict[str, int]]:
    errors: list[str] = []
    warnings: list[str] = []
    if quarantine_profile not in {
        STRICT_QUARANTINE_PROFILE,
        PUBLIC_QUARANTINE_PROFILE,
    }:
        return [f"알 수 없는 격리 검증 프로필: {quarantine_profile}"], [], {}
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
        feedback_records = collection("memory_feedback")
    except WikiError as exc:
        return [str(exc)], [], {}
    try:
        grandfathered_source_ids = source_grandfather_ids()
    except WikiError as exc:
        return [str(exc)], [], {}
    try:
        quarantine_distribution = load_json(ROOT / "config" / "wiki.json").get(
            "quarantine_distribution", {}
        )
    except (OSError, json.JSONDecodeError, WikiError) as exc:
        return [f"격리 원문 배포 정책을 읽지 못함: {exc}"], [], {}
    try:
        _, project_by_id, interest_by_id = research_portfolio_config()
    except (OSError, json.JSONDecodeError, WikiError) as exc:
        errors.append(f"연구 프로젝트 설정을 읽지 못함: {exc}")
        project_by_id = {}
        interest_by_id = {}

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
    duplicate_ids(feedback_records, "memory feedback")

    actor_ids = {a.get("id") for a in actors}
    source_ids = {s.get("id") for s in sources}
    claim_ids = {c.get("id") for c in claims}
    campaign_ids = {c.get("id") for c in campaigns}
    feedback_ids = {item.get("id") for item in feedback_records}
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
            warnings.append(f"{source.get('id')}: 메타데이터 전용 출처이며 불변 원문 스냅샷이 없음")
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
            f"출처 {legacy_source_count}개는 v4 입수 심사 적용 이전 자료이며 고정된 기존 예외로 유지됨"
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
            warnings.append(f"{claim.get('id')}: 이의가 제기된 주장")

    try:
        import memory_feedback
    except ImportError as exc:
        errors.append(f"memory feedback validation unavailable: {exc}")
    else:
        try:
            memory_feedback.validate_feedback_collection(
                load_json(STATE / "memory_feedback.json")
            )
        except (memory_feedback.MemoryFeedbackError, WikiError) as exc:
            errors.append(f"memory feedback ledger invalid: {exc}")

        known_reference_ids = {
            *actor_ids,
            *source_ids,
            *claim_ids,
            *campaign_ids,
            *feedback_ids,
            *(item.get("id") for item in reviews),
            *(item.get("id") for item in proposals),
            *(item.get("id") for item in collaborations),
            *(item.get("id") for item in admissions),
            *(item.get("id") for item in runs),
            *(item.get("id") for item in ledger_events),
        }
        known_reference_ids.discard(None)
        feedback_target_ids = {str(item) for item in {*source_ids, *claim_ids} if item is not None}
        for record in feedback_records:
            if record.get("actor_id") not in actor_ids:
                errors.append(f"{record.get('id')}: unknown feedback actor")
            resolution = record.get("resolution")
            if isinstance(resolution, dict) and resolution.get("actor_id") not in actor_ids:
                errors.append(f"{record.get('id')}: unknown feedback resolution actor")
            for reference in record.get("targets", []):
                if not _reference_exists(str(reference), feedback_target_ids):
                    errors.append(f"{record.get('id')}: unknown feedback target {reference}")
            for reference in record.get("evidence_refs", []):
                if not _reference_exists(str(reference), {str(item) for item in known_reference_ids}):
                    errors.append(f"{record.get('id')}: unknown feedback evidence reference {reference}")
            try:
                state_digest = memory_feedback.feedback_state_digest(record)
            except memory_feedback.MemoryFeedbackError:
                continue
            if not any(
                event.get("subject") == record.get("id")
                and event.get("details", {}).get("state_digest") == state_digest
                for event in ledger_events
            ):
                errors.append(f"{record.get('id')}: current feedback state digest is not anchored")

        def validate_lifecycle_records(items: list[dict[str, Any]], kind: str) -> None:
            item_ids = {item.get("id") for item in items}
            for item in items:
                item_id = item.get("id")
                status_value = lifecycle_status(item, kind=kind)
                if status_value not in LIFECYCLE_STATUSES:
                    errors.append(f"{item_id}: invalid lifecycle status {status_value}")
                    continue
                history = item.get("lifecycle_history", [])
                if not isinstance(history, list):
                    errors.append(f"{item_id}: lifecycle_history must be a list")
                    continue
                if not history:
                    if status_value != "active":
                        errors.append(f"{item_id}: inactive lifecycle lacks transition history")
                    if any(
                        key in item
                        for key in ("lifecycle_reason", "lifecycle_updated_at", "lifecycle_updated_by", "replaced_by")
                    ):
                        errors.append(f"{item_id}: lifecycle projection fields lack transition history")
                    continue
                projection: dict[str, Any] = {
                    "id": item_id,
                    "lifecycle_status": "active",
                    "lifecycle_history": [],
                }
                previous_at: str | None = None
                failed = False
                for transition in history:
                    try:
                        memory_feedback.validate_lifecycle_transition(transition)
                        normalized_at = memory_feedback.normalize_timestamp(transition["created_at"])
                        if previous_at is not None and normalized_at < previous_at:
                            raise memory_feedback.MemoryFeedbackError(
                                "lifecycle history timestamps must be monotonic"
                            )
                        previous_at = normalized_at
                        if transition.get("actor_id") not in actor_ids:
                            raise memory_feedback.MemoryFeedbackError(
                                f"unknown transition actor {transition.get('actor_id')}"
                            )
                        replacement = transition.get("replacement_ref")
                        if replacement is not None and replacement not in item_ids:
                            raise memory_feedback.MemoryFeedbackError(
                                f"unknown same-kind replacement {replacement}"
                            )
                        transition_digest = memory_feedback.lifecycle_transition_digest(transition)
                        if not any(
                            event.get("subject") == transition.get("id")
                            and event.get("details", {}).get("transition_digest") == transition_digest
                            for event in ledger_events
                        ):
                            raise memory_feedback.MemoryFeedbackError(
                                f"transition {transition.get('id')} is not anchored"
                            )
                        projection = memory_feedback.apply_lifecycle_transition(projection, transition)
                    except memory_feedback.MemoryFeedbackError as exc:
                        errors.append(f"{item_id}: invalid lifecycle history: {exc}")
                        failed = True
                        break
                if failed:
                    continue
                for field in (
                    "lifecycle_status",
                    "lifecycle_reason",
                    "lifecycle_updated_at",
                    "lifecycle_updated_by",
                    "replaced_by",
                    "lifecycle_history",
                ):
                    if projection.get(field) != item.get(field):
                        errors.append(f"{item_id}: lifecycle projection mismatch for {field}")

        validate_lifecycle_records(claims, "claim")
        validate_lifecycle_records(sources, "source")

        lifecycle_transition_ids = {
            transition.get("id")
            for item in [*claims, *sources]
            for transition in item.get("lifecycle_history", [])
            if isinstance(transition, dict)
        }
        for event in ledger_events:
            action = event.get("action")
            subject = event.get("subject")
            if action in {"memory.feedback.add", "memory.feedback.resolve"} and subject not in feedback_ids:
                errors.append(f"{event.get('id')}: orphan memory feedback event for {subject}")
            if action == "knowledge.lifecycle.transition" and subject not in lifecycle_transition_ids:
                errors.append(f"{event.get('id')}: orphan lifecycle event for {subject}")

    for review in reviews:
        if review.get("actor_id") not in actor_ids:
            errors.append(f"{review.get('id')}: unknown reviewer")
        if review.get("claim_id") not in claim_ids:
            errors.append(f"{review.get('id')}: unknown claim")

    for campaign in campaigns:
        project_id = campaign.get("project_id")
        interest_id = campaign.get("interest_id")
        if project_id not in project_by_id:
            errors.append(f"{campaign.get('id')}: unknown or missing project_id {project_id}")
        interest = interest_by_id.get(interest_id)
        if interest is None:
            errors.append(f"{campaign.get('id')}: unknown interest_id {interest_id}")
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

    quarantine_artifacts_total = 0
    quarantine_artifacts_present = 0
    quarantine_artifacts_missing = 0
    for admission in admissions:
        if admission.get("created_by") not in actor_ids:
            errors.append(f"{admission.get('id')}: unknown admission actor")
        if admission.get("status") not in {"allow", "review", "reject"}:
            errors.append(f"{admission.get('id')}: invalid admission status")
        if admission.get("policy_effect") not in {"advisory_only", "quarantine_only_no_source_promotion"}:
            errors.append(f"{admission.get('id')}: admission may not mutate trust or promote a source")
        for finding in admission_integrity_findings(admission):
            errors.append(f"{admission.get('id')}: {finding}")
        digest_anchored = bool(admission.get("record_digest")) and any(
            event.get("subject") == admission.get("id")
            and event.get("details", {}).get("record_digest") == admission.get("record_digest")
            for event in ledger_events
        )
        if admission.get("record_digest") and not digest_anchored:
            errors.append(f"{admission.get('id')}: admission digest is not anchored in the event chain")
        assessment = admission.get("decision", {}).get("security_assessment")
        if isinstance(assessment, dict):
            quarantine_artifacts_total += 1
            invariants = assessment.get("invariants", {})
            if invariants.get("payload_executed") is not False:
                errors.append(f"{admission.get('id')}: security assessment lacks no-execution invariant")
            artifact = admission.get("candidate", {}).get("quarantine_artifact", {})
            artifact_path = ROOT / str(artifact.get("path", ""))
            if artifact_path.is_symlink():
                errors.append(f"{admission.get('id')}: quarantine artifact may not be a symbolic link")
            elif not artifact_path.is_file():
                quarantine_artifacts_missing += 1
                anchor_verified = any(
                    quarantine_anchor_is_valid(admission, event)
                    for event in ledger_events
                )
                if portable_quarantine_metadata(
                    admission,
                    quarantine_distribution,
                    validation_profile=quarantine_profile,
                    anchor_verified=anchor_verified,
                ):
                    warnings.append(
                        f"{admission.get('id')}: 로컬 전용 격리 원문은 public Git에 배포하지 않으며 content-addressed 입수 메타데이터와 사건 anchor만 검증함"
                    )
                else:
                    errors.append(f"{admission.get('id')}: quarantine artifact missing")
            elif digest_file(artifact_path) != artifact.get("sha256"):
                quarantine_artifacts_present += 1
                errors.append(f"{admission.get('id')}: quarantine artifact hash mismatch")
            else:
                quarantine_artifacts_present += 1

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
        "projects": len(project_by_id),
        "proposals": len(proposals),
        "collaborations": len(collaborations),
        "admissions": len(admissions),
        "runs": len(runs),
        "memory_feedback": len(feedback_records),
        "events": event_count,
        "okf_concepts": okf_count,
        "quarantine_artifacts_total": quarantine_artifacts_total,
        "quarantine_artifacts_present": quarantine_artifacts_present,
        "quarantine_artifacts_missing": quarantine_artifacts_missing,
    }
    return errors, warnings, counts


def validate(args: argparse.Namespace) -> None:
    errors, warnings, counts = validation_findings(
        quarantine_profile=args.quarantine_profile
    )
    missing = counts.get("quarantine_artifacts_missing", 0)
    print(f"격리 검증 프로필: {args.quarantine_profile}")
    print(f"quarantine_payload_verified={str(missing == 0).lower()}")
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
            f"| `{claim['id']}` | {confidence.get('level', 'C0')} | {confidence.get('status', 'open')} | {lifecycle_status(claim, kind='claim')} | "
            f"{statement} | {confidence.get('supporting_groups', 0)} | {confidence.get('contradicting_groups', 0)} |"
        )
    source_rows = []
    for source in sorted(sources, key=lambda s: (-SOURCE_LEVELS.get(s.get("source_level", "S0"), 0), s["id"])):
        title = source.get("title", "").replace("|", "\\|")
        source_rows.append(
            f"| `{source['id']}` | {source.get('source_level', 'S0')} | {lifecycle_status(source, kind='source')} | {source.get('publication_status') or '-'} | "
            f"{title} | `{source.get('independence_group', '-')}` |"
        )
    timestamp = latest_meaningful_timestamp(claims, sources)
    body = f"""---
type: Epistemic Dashboard
title: 인식론 대시보드
description: 정규 원장에서 파생한 주장·출처의 증거 성숙도 현황.
tags: [trust, provenance, claims]
timestamp: '{timestamp}'
generated: true
---

<!-- tools/wiki.py가 자동 생성함. 직접 수정하지 마세요. -->
# 인식론 대시보드

신뢰 레벨은 진실 확률이 아니라 현재 증거 성숙도의 파생 표시다. 상세 근거는 `state/claims.json`과 `state/sources.json`을 확인한다.

## 주장

| ID | 레벨 | 증거 상태 | 생명주기 | 주장 | 지지 그룹 | 반박 그룹 |
|---|---:|---|---|---|---:|---:|
""" + ("\n".join(claim_rows) if claim_rows else "| - | - | - | - | 아직 등록된 주장 없음 | - | - |") + """

## 출처

| ID | 레벨 | 생명주기 | 출판 상태 | 원제 | 독립성 그룹 |
|---|---:|---|---|---|---|
""" + ("\n".join(source_rows) if source_rows else "| - | - | - | - | 아직 등록된 출처 없음 | - |") + "\n"
    atomic_write_text(WIKI / "epistemic-dashboard.md", body)


def render_index(
    claims: list[dict[str, Any]],
    sources: list[dict[str, Any]],
    campaigns: list[dict[str, Any]],
    feedback_records: list[dict[str, Any]] | None = None,
) -> None:
    feedback_records = feedback_records or []
    _, project_by_id, _ = research_portfolio_config()
    timestamp = latest_meaningful_timestamp(claims, sources, campaigns, feedback_records)
    body = f"""<!-- tools/wiki.py가 자동 생성함. 직접 수정하지 마세요. -->
# Living Wiki 색인

지식 상태 시각: {timestamp}

## 시작하기

* [개요](overview.md) - 현재 연구 범위와 구조.
* [종합](synthesis.md) - 현재의 종합 관점.
* [인식론 대시보드](epistemic-dashboard.md) - 주장·출처 신뢰 상태.
* [열린 질문](open-questions.md) - 미해결 질문.
* [모순](contradictions.md) - 충돌과 반증.
* [현재 관점](perspectives/self-evolving-wiki-position.md) - 위키가 현재 채택한 관점과 반증 조건.
* [OKF 프로필](okf-profile.md) - 이 bundle의 OKF v0.1 확장 규약.
* [주장](claims/index.md) - 원자적 주장과 정확한 근거 투영.
* [행위자](actors/index.md) - 사람과 Agent 기여자 등록부.
* [협업](collaborations/index.md) - 행위자 중립의 방향·단서·교정·이의 원장.
* [연구 프로젝트](projects/index.md) - 두 연구 축의 관심사·캠페인·실행·공유 근거 탐색.
* [캠페인](campaigns/index.md) - 범위가 제한된 자율 연구 대기열.
* [입수 판정](admissions/index.md) - 자동 승격 없는 출처·보안 입수 판정.
* [실행 기록](runs/index.md) - 제한된 계획과 귀속된 외부 작업 기록.
* [메모리 피드백](feedback/index.md) - 자동 신뢰 효과가 없는 최소 개인정보 검색 결과.
* [신뢰 정책](trust/index.md) - S0-S4/C0-C4 생산자 프로필.
* [거버넌스](governance/index.md) - 헌장과 결정 기록.

## 상태

- 출처: {len(sources)}
- 주장: {len(claims)}
- 연구 캠페인: {len(campaigns)}
- 활성·대기 캠페인: {sum(c.get('status') in {'active', 'queued'} for c in campaigns)}
- 메모리 피드백 기록: {len(feedback_records)}

## 연구 프로젝트

{chr(10).join(f"* [{project['name']}](projects/{project_id.lower()}.md) - {project.get('description', '')}" for project_id, project in sorted(project_by_id.items()))}

## 출처 문서

"""
    pages = sorted((WIKI / "sources").glob("*.md"))
    body += "\n".join(f"* [{page.stem}](sources/{page.name})" for page in pages if page.name not in {"index.md", "log.md"}) or "* 아직 없음"
    body += "\n\n## 개념 문서\n\n"
    pages = sorted((WIKI / "concepts").glob("*.md"))
    body += "\n".join(f"* [{page.stem}](concepts/{page.name})" for page in pages if page.name not in {"index.md", "log.md"}) or "* 아직 없음"
    body += "\n"
    atomic_write_text(WIKI / "index.md", body)


def render_project_views() -> None:
    """프로젝트별 탐색 뷰를 만들되 claim/source 정규 객체는 복제하지 않는다."""

    _, project_by_id, interest_by_id = research_portfolio_config()
    campaigns = collection("campaigns")
    runs = collection("runs")
    folder = WIKI / "projects"
    folder.mkdir(parents=True, exist_ok=True)
    expected_paths = {folder / f"{project_id.lower()}.md" for project_id in project_by_id}

    for campaign in campaigns:
        campaign_id = str(campaign.get("id", ""))
        project_id = campaign.get("project_id")
        if project_id not in project_by_id:
            raise WikiError(f"{campaign_id}: unknown or missing project_id {project_id}")

    for project_id, project in sorted(project_by_id.items()):
        project_interests = [
            item for item in interest_by_id.values() if item.get("project_id") == project_id
        ]
        project_campaigns = [
            item for item in campaigns if item.get("project_id") == project_id
        ]
        project_campaign_ids = {str(item["id"]) for item in project_campaigns}
        project_runs: list[dict[str, Any]] = []
        evidence_refs: set[str] = set()
        for run in runs:
            actions = run.get("plan", {}).get("actions", [])
            related_action_ids = {
                str(action.get("id"))
                for action in actions
                if action.get("campaign_id") in project_campaign_ids
            }
            if not related_action_ids:
                continue
            project_runs.append(run)
            for report in run.get("external_receipts", []):
                if report.get("action_id") in related_action_ids:
                    evidence_refs.update(str(item) for item in report.get("evidence_refs", []))

        claim_ids = sorted(
            {
                str(claim_id)
                for campaign in project_campaigns
                for claim_id in campaign.get("claim_ids", [])
            }
        )
        source_ids = sorted(
            {
                str(source_id)
                for campaign in project_campaigns
                for source_id in campaign.get("source_ids", [])
            }
        )
        timestamp = record_latest_timestamp(
            project.get("updated_at"),
            project.get("created_at"),
            *(item.get("updated_at") for item in project_interests),
            *(item.get("created_at") for item in project_interests),
            *(item.get("updated_at") for item in project_campaigns),
            *(item.get("created_at") for item in project_campaigns),
            *(item.get("updated_at") for item in project_runs),
            *(item.get("created_at") for item in project_runs),
            *(item.get("plan", {}).get("generated_at") for item in project_runs),
            *(
                receipt.get("usage_accounted_at") or receipt.get("created_at")
                for item in project_runs
                for receipt in item.get("external_receipts", [])
            ),
            "2026-07-15T00:00:00+09:00",
        )
        body = f"""<!-- config/interests.json과 정규 상태에서 자동 생성함. -->
# {project['name']}

> {project.get('description', '')}

## 프로젝트 목표

{project.get('objective') or '목표 기록 없음.'}

| 항목 | 값 |
|---|---|
| 프로젝트 ID | `{project_id}` |
| 상태 | **{project.get('status', '-')}** |
| 관심사 수 | {len(project_interests)} |
| 캠페인 수 | {len(project_campaigns)} |
| 실행 수 | {len(project_runs)} |

## 관심사

{chr(10).join(f"- `{item['id']}` — {item.get('name', '이름 없음')} / 상태 `{item.get('status', 'active')}`" for item in sorted(project_interests, key=lambda value: value['id'])) or '- 아직 없음'}

## 캠페인

{chr(10).join(f"- [{item['id']}](../campaigns/{item['id'].lower()}.md) — {item.get('question', '')} / 상태 `{item.get('status', '-')}`" for item in sorted(project_campaigns, key=lambda value: value['id'])) or '- 아직 없음'}

## 실행

{chr(10).join(f"- [{item['id']}](../runs/{item['id'].lower()}.md) — 상태 `{item.get('status', '-')}`" for item in sorted(project_runs, key=lambda value: value['id'])) or '- 아직 없음'}

## 공유 근거

출처와 주장은 프로젝트별 사본이 아니라 전역 canonical 원장을 공유한다. 아래 링크가 여러 프로젝트에 나타나도 독립 증거가 늘어난 것으로 세지 않는다.

### 주장

{chr(10).join(f'- [{item}](../claims/{item.lower()}.md)' for item in claim_ids) or '- 아직 없음'}

### 출처

{chr(10).join(f'- [{item}](../sources/{item.lower()}.md)' for item in source_ids) or '- 아직 없음'}

### 실행 보고 근거 참조

{chr(10).join(f'- `{item}`' for item in sorted(evidence_refs)) or '- 아직 없음'}
"""
        write_okf_concept(
            folder / f"{project_id.lower()}.md",
            {
                "type": "Research Project",
                "title": project["name"],
                "description": project.get("description", ""),
                "tags": ["research-project", project.get("status", "unknown")],
                "timestamp": timestamp,
                "project_id": project_id,
                "generated": True,
            },
            body,
        )

    for path in sorted(folder.glob("prj-*.md")):
        if path in expected_paths:
            continue
        text = path.read_text(encoding="utf-8")
        if "config/interests.json과 정규 상태에서 자동 생성함" not in text:
            raise WikiError(f"생성 문서가 아닌 프로젝트 페이지를 자동 삭제할 수 없음: {path}")
        path.unlink()

    entries = [
        f"* [{project['name']}]({project_id.lower()}.md) - {project.get('description', '')}"
        for project_id, project in sorted(project_by_id.items())
    ]
    atomic_write_text(folder / "index.md", "# 연구 프로젝트\n\n" + "\n".join(entries) + "\n")


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
    feedback_records = collection("memory_feedback")
    source_by_id = {source["id"]: source for source in sources}
    campaign_by_id = {campaign["id"]: campaign for campaign in campaigns}
    project_ids_by_claim: dict[str, set[str]] = {}
    project_ids_by_source: dict[str, set[str]] = {}
    for campaign in campaigns:
        project_id = campaign.get("project_id")
        if not isinstance(project_id, str) or not project_id:
            continue
        for claim_id in campaign.get("claim_ids", []):
            project_ids_by_claim.setdefault(str(claim_id), set()).add(project_id)
        for source_id in campaign.get("source_ids", []):
            project_ids_by_source.setdefault(str(source_id), set()).add(project_id)
    claims_by_source: dict[str, list[str]] = {}
    for claim in claims:
        for evidence in claim.get("evidence", []):
            claims_by_source.setdefault(evidence.get("source_id", ""), []).append(claim["id"])

    for actor in actors:
        metadata = {
            "type": "Actor",
            "title": f"행위자 {actor['id']}",
            "description": f"Living Wiki 기여자 {actor['id']}의 행위자·역할 기록.",
            "tags": ["actor", actor.get("kind", "unknown"), *actor.get("roles", [])],
            "timestamp": actor.get("created_at") or "2026-07-11T00:00:00+09:00",
            "actor_id": actor["id"],
            "generated": True,
        }
        body = f"""<!-- state/actors.json에서 자동 생성함. -->
# 행위자 — {actor.get('display_name') or actor['id']}

| 항목 | 값 |
|---|---|
| 정규 행위자 ID | `{actor['id']}` |
| 종류 | `{actor.get('kind', '-')}` |
| 상태 | `{actor.get('status', '-')}` |
| 독립성 그룹 | `{actor_independence_group(actor)}` |

## 역할

{chr(10).join(f'- `{role}`' for role in actor.get('roles', [])) or '- 없음'}

## 기능

{chr(10).join(f'- `{capability}`' for capability in actor.get('capabilities', [])) or '- 없음'}

이 문서는 신원과 운영 역할을 기록한다. 행위자 종류 자체는 주장의 사실성을 높이거나 낮추지 않는다.
"""
        write_okf_concept(WIKI / "actors" / actor_page_name(actor["id"]), metadata, body)

    for source in sources:
        assessment = source.get("assessment", {})
        rationale = re.sub(r"\s+", " ", str(assessment.get("rationale") or "아직 평가하지 않은 출처."))
        source_lifecycle = lifecycle_status(source, kind="source")
        metadata: dict[str, Any] = {
            "type": "Reference",
            "title": source.get("title") or source["id"],
            "description": f"출처 {source['id']}의 범위 한정 평가와 보존 정보. 현재 레벨은 {source.get('source_level', 'S0')}.",
            "tags": ["source", source.get("source_type", "unknown"), source.get("source_level", "S0"), source_lifecycle],
            "timestamp": source_semantic_timestamp(source),
            "source_id": source["id"],
            "source_level": source.get("source_level", "S0"),
            "lifecycle_status": source_lifecycle,
            "generated": True,
        }
        related_project_ids = sorted(project_ids_by_source.get(source["id"], set()))
        if related_project_ids:
            metadata["project_ids"] = related_project_ids
        source_times = {
            "created_at": source.get("created_at"),
            "retrieved_at": source.get("retrieved_at"),
            "assessed_at": assessment.get("assessed_at"),
            "lifecycle_updated_at": source.get("lifecycle_updated_at"),
        }
        project_known_fields(
            metadata,
            source_times,
            ("created_at", "retrieved_at", "assessed_at", "lifecycle_updated_at"),
        )
        if source.get("url"):
            metadata["resource"] = source["url"]
        artifact = source.get("artifact") or {}
        body = f"""<!-- state/sources.json에서 자동 생성함. -->
# {source.get('title') or source['id']}

## 출처 식별 정보

| 항목 | 값 |
|---|---|
| 정규 출처 ID | `{source['id']}` |
| 유형 | `{source.get('source_type', '-')}` |
| 저자 | {md_cell(', '.join(source.get('authors', [])) or '-')} |
| 발행자 | {md_cell(source.get('publisher'))} |
| 출판 상태 | {md_cell(source.get('publication_status'))} |
| 게시 시각 | {md_cell(source.get('published_at'))} |
| 검색 시각 | {md_cell(source.get('retrieved_at'))} |
| 독립성 그룹 | `{source.get('independence_group', source['id'])}` |
| 라이선스 | {md_cell(source.get('license'))} |
| 생명주기 | **{source_lifecycle}** |
| 생명주기 사유 | {md_cell(source.get('lifecycle_reason'))} |
| 대체 출처 | {md_cell(source.get('replaced_by'))} |

## 범위 한정 평가

- 레벨: **{source.get('source_level', 'S0')}**
- 기록된 평가 근거: {rationale}
- 품질 표지: {', '.join(f'`{item}`' for item in assessment.get('quality_markers', [])) or '없음'}
- 이해관계 충돌: {', '.join(f'`{item}`' for item in assessment.get('conflicts_of_interest', [])) or '기록 없음'}

## 보존 원문

- bundle 밖 경로: `{artifact.get('path', '메타데이터 전용')}`
- SHA-256: `{artifact.get('sha256', '없음')}`
- 미디어 유형: `{artifact.get('media_type', '없음')}`

## 이 출처를 사용하는 주장

{chr(10).join(f'- [{claim_id}](../claims/{claim_id.lower()}.md)' for claim_id in sorted(set(claims_by_source.get(source['id'], [])))) or '- 없음'}

## 관련 연구 프로젝트

{chr(10).join(f'- 연구 프로젝트: [{project_id}](../projects/{project_id.lower()}.md)' for project_id in related_project_ids) or '- 공통·제어면 지식'}
"""
        if source.get("url"):
            body += f"\n# 인용\n\n[1] [{source.get('title') or source['id']}]({source['url']})\n"
        write_okf_concept(WIKI / "sources" / f"{source['id'].lower()}.md", metadata, body)

    for claim in claims:
        confidence = claim.get("confidence", {})
        claim_lifecycle = lifecycle_status(claim, kind="claim")
        creator_path = f"../actors/{actor_page_name(claim.get('created_by', 'unknown'))}"
        metadata = {
            "type": "Claim",
            "title": claim["id"],
            "description": f"주장 {claim['id']}의 범위·생명주기·증거 성숙도 기록.",
            "tags": ["claim", claim.get("kind", "unknown"), confidence.get("level", "C0"), confidence.get("status", "open"), claim_lifecycle],
            "timestamp": claim_semantic_timestamp(claim),
            "claim_id": claim["id"],
            "lifecycle_status": claim_lifecycle,
            "generated": True,
        }
        related_project_ids = sorted(project_ids_by_claim.get(claim["id"], set()))
        if related_project_ids:
            metadata["project_ids"] = related_project_ids
        project_known_fields(
            metadata,
            claim,
            ("created_at", "last_verified_at", "freshness", "lifecycle_updated_at"),
        )
        evidence_rows: list[str] = []
        citations: list[str] = []
        citation_seen: set[str] = set()
        for evidence in claim.get("evidence", []):
            source_id = evidence.get("source_id", "")
            source = source_by_id.get(source_id, {})
            source_title = source.get("title") or source_id
            evidence_rows.append(
                f"| `{evidence.get('relation', '-')}` | [출처 {md_cell(source_id)}](../sources/{source_id.lower()}.md) | "
                f"`{md_cell(evidence.get('locator'))}` | {evidence.get('strength', '-')} | `{evidence.get('added_by', '-')}` |"
            )
            url = source.get("url")
            if url and url not in citation_seen:
                citation_seen.add(url)
                citations.append(f"[{len(citations) + 1}] [{source_title}]({url})")
        body = f"""<!-- state/claims.json에서 자동 생성함. -->
# {claim['id']}

> 기록된 주장: {claim.get('statement', '')}

## 범위와 생명주기

| 항목 | 값 |
|---|---|
| 종류 | `{claim.get('kind', '-')}` |
| 범위 | {md_cell(claim.get('scope'))} |
| 유효 시점 | {md_cell(claim.get('valid_at'))} |
| 최신성 분류 | `{claim.get('freshness', '-')}` |
| 생명주기 | **{claim_lifecycle}** |
| 생명주기 사유 | {md_cell(claim.get('lifecycle_reason'))} |
| 대체 주장 | {md_cell(claim.get('replaced_by'))} |
| 생성자 | [{claim.get('created_by', '-')}]({creator_path}) |
| 생성 시각 | `{claim.get('created_at', '-')}` |
| 마지막 검증 | `{claim.get('last_verified_at') or '검증되지 않음'}` |

## 관련 연구 프로젝트

{chr(10).join(f'- 연구 프로젝트: [{project_id}](../projects/{project_id.lower()}.md)' for project_id in related_project_ids) or '- 공통·제어면 지식'}

## 증거 성숙도

| 항목 | 값 |
|---|---|
| 표시 레벨 | **{confidence.get('level', 'C0')}** |
| 상태 | **{confidence.get('status', 'open')}** |
| 지지 독립성 그룹 | {confidence.get('supporting_groups', 0)} |
| 반박 독립성 그룹 | {confidence.get('contradicting_groups', 0)} |
| 독립 검토자 그룹 | {confidence.get('independent_reviews', 0)} |
| 강한 미해결 반증 | {confidence.get('strong_contradiction', False)} |

평가 근거: {confidence.get('rationale', '평가하지 않음.')}

## 증거 연결

| 관계 | 출처 | 정확한 원문 위치 | 강도 | 추가한 행위자 |
|---|---|---|---:|---|
{chr(10).join(evidence_rows) or '| - | - | - | - | - |'}
"""
        if citations:
            body += "\n# 인용\n\n" + "\n".join(citations) + "\n"
        write_okf_concept(WIKI / "claims" / f"{claim['id'].lower()}.md", metadata, body)

    for review in reviews:
        claim_id = review.get("claim_id", "")
        actor_id = review.get("actor_id", "")
        metadata = {
            "type": "Review",
            "title": review["id"],
            "description": f"주장 {claim_id}에 대해 {actor_id}가 남긴 검토 기록.",
            "tags": ["review", review.get("verdict", "unknown"), "adversarial" if review.get("adversarial") else "standard"],
            "timestamp": review.get("created_at") or "2026-07-11T00:00:00+09:00",
            "review_id": review["id"],
            "generated": True,
        }
        body = f"""<!-- state/reviews.json에서 자동 생성함. -->
# {review['id']}

- 주장: [{claim_id}](../claims/{claim_id.lower()}.md)
- 검토자: [{actor_id}](../actors/{actor_page_name(actor_id)})
- 검토자 독립성 그룹: `{review.get('reviewer_group', actor_id)}`
- 판정: **{review.get('verdict', '-')}**
- 적대적 검토: `{review.get('adversarial', False)}`
- 상태: `{review.get('status', '-')}`

## 근거

기록된 검토 근거: {review.get('rationale') or '근거 기록 없음.'}
"""
        write_okf_concept(WIKI / "reviews" / f"{review['id'].lower()}.md", metadata, body)

    for campaign in campaigns:
        project_id = campaign.get("project_id")
        metadata = {
            "type": "Research Campaign",
            "title": campaign["id"],
            "description": f"연구 캠페인 {campaign['id']}의 질문·예산·종료 조건 기록.",
            "tags": ["research-campaign", campaign.get("status", "unknown"), campaign.get("interest_id", "unknown")],
            "timestamp": campaign.get("updated_at") or campaign.get("created_at") or "2026-07-11T00:00:00+09:00",
            "campaign_id": campaign["id"],
            "project_id": project_id,
            "generated": True,
        }
        source_links = [f"[{item}](../sources/{item.lower()}.md)" for item in campaign.get("source_ids", [])]
        claim_links = [f"[{item}](../claims/{item.lower()}.md)" for item in campaign.get("claim_ids", [])]
        body = f"""<!-- state/campaigns.json에서 자동 생성함. -->
# {campaign['id']}

> 연구 질문: {campaign.get('question', '')}

## 제어 정보

| 항목 | 값 |
|---|---|
| 상태 | **{campaign.get('status', '-')}** |
| 프로젝트 | {f'[{project_id}](../projects/{str(project_id).lower()}.md)' if project_id else '-'} |
| 관심사 | `{campaign.get('interest_id', '-')}` |
| 우선순위 | {campaign.get('priority', '-')} |
| 생성자 | [{campaign.get('created_by', '-')}](../actors/{actor_page_name(campaign.get('created_by', 'unknown'))}) |
| 최대 출처 수 | {campaign.get('max_sources', '-')} |
| 최대 시간(분) | {campaign.get('max_minutes', '-')} |
| 필요한 독립 그룹 수 | {campaign.get('required_independent_groups', '-')} |
| 반증 검색 필수 | {campaign.get('counter_search_required', False)} |

지금 수행하는 이유: {campaign.get('why_now') or '-'}

## 종료 조건

{chr(10).join(f'- 기록된 조건: {item}' for item in campaign.get('stop_conditions', [])) or '- 없음'}

## 출처

{chr(10).join(f'- {item}' for item in source_links) or '- 아직 없음'}

## 주장

{chr(10).join(f'- {item}' for item in claim_links) or '- 아직 없음'}
"""
        write_okf_concept(WIKI / "campaigns" / f"{campaign['id'].lower()}.md", metadata, body)

    for proposal in proposals:
        metadata = {
            "type": "Harness Proposal",
            "title": f"{proposal['id']}: 하네스 제안",
            "description": f"하네스 제안 {proposal['id']}의 문제·변경·검토·구현 근거.",
            "tags": ["governance", "harness-proposal", proposal.get("status", "proposed")],
            "timestamp": proposal.get("updated_at") or proposal.get("created_at") or "2026-07-11T00:00:00+09:00",
            "proposal_id": proposal["id"],
            "lifecycle_status": proposal.get("status", "proposed"),
            "generated": True,
        }
        reviews = proposal.get("approvals", [])
        body = f"""<!-- state/proposals.json에서 자동 생성함. -->
# {proposal['id']}: 하네스 제안 — {proposal.get('title', '')}

- 상태: **{proposal.get('status', 'proposed')}**
- 제안자: [{proposal.get('created_by', '-')}](../actors/{actor_page_name(proposal.get('created_by', 'unknown'))})
- 생성 시각: `{proposal.get('created_at', '-')}`

## 문제

기록된 문제: {proposal.get('problem', '-')}

## 제안 변경

기록된 변경안: {proposal.get('proposed_change', '-')}

## 근거 주장

{chr(10).join(f'- [{claim_id}](../claims/{claim_id.lower()}.md)' for claim_id in proposal.get('evidence', [])) or '- 없음'}

## 수용 게이트

기록된 수용 기준: {proposal.get('benchmark', '-')}

## 위험

{chr(10).join(f'- 기록된 위험: {risk}' for risk in proposal.get('risks', [])) or '- 없음'}

## 롤백

기록된 롤백: {proposal.get('rollback', '-')}

## 검토 결정

{chr(10).join(f"- **{item.get('decision', '-')}** / 검토자 `{item.get('actor_id', '-')}` / 시각 `{item.get('at', '-')}` — 기록된 사유: {item.get('rationale', '-')}" for item in reviews) or '- 없음'}

## 구현 근거

{f"- 릴리스 보고서: `{proposal.get('implementation_evidence', {}).get('release_report')}`" if proposal.get('implementation_evidence') else '- 아직 구현되지 않음.'}
{f"- 구성요소 지문: `{proposal.get('implementation_evidence', {}).get('component_fingerprint')}`" if proposal.get('implementation_evidence') else ''}
{f"- 운영 환경 인증: `{proposal.get('implementation_evidence', {}).get('production_certified')}`" if proposal.get('implementation_evidence') else ''}
"""
        write_okf_concept(WIKI / "governance" / f"{proposal['id'].lower()}.md", metadata, body)

    for record in collaborations:
        transitions = record.get("metadata", {}).get("transitions", [])
        body = f"""<!-- state/collaborations.json에서 자동 생성함. -->
# {record['id']}

> 기록된 협업 내용: {record.get('content', '')}

| 항목 | 값 |
|---|---|
| 행위자 | [{record.get('actor_id', '-')}](../actors/{actor_page_name(record.get('actor_id', 'unknown'))}) |
| 기록 종류 | `{record.get('record_kind', '-')}` |
| 의도 | `{record.get('intent', '-')}` |
| 입장 | `{record.get('stance') or '-'}` |
| 상태 | **{record.get('status', '-')}** |
| 생성 시각 | `{record.get('created_at', '-')}` |
| 갱신 시각 | `{record.get('updated_at', '-')}` |

## 대상

{chr(10).join(f'- `{target}`' for target in record.get('targets', [])) or '- 없음'}

## 전이 이력

{chr(10).join(f"- `{item.get('at', '-')}` — `{item.get('from', '-')}` → `{item.get('to', '-')}` / 처리자 `{item.get('actor_id', '-')}`: 기록된 사유 {item.get('reason', '-')}" for item in transitions) or '- 없음'}
"""
        write_okf_concept(
            WIKI / "collaborations" / f"{record['id'].lower()}.md",
            {
                "type": "Collaboration Record",
                "title": record["id"],
                "description": f"협업 기록 {record['id']}의 방향·기여·검토와 전이 이력.",
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
        body = f"""<!-- state/admissions.json에서 자동 생성함. 신뢰하지 않는 payload 본문은 의도적으로 제외함. -->
# {admission['id']}

| 항목 | 값 |
|---|---|
| 후보 | `{candidate.get('id', '-')}` |
| 출처 참조 | {md_cell(source_ref or source_url)} |
| 판정 | **{admission.get('status', '-')}** |
| 정책 효과 | `{admission.get('policy_effect', '-')}` |
| 평가자 | [{admission.get('created_by', '-')}](../actors/{actor_page_name(admission.get('created_by', 'unknown'))}) |
| 평가 시각 | `{admission.get('created_at', '-')}` |

## 설명 가능한 사유

{chr(10).join(f'- `{code}`' for code in reason_codes) or '- 차단 사유 기록 없음.'}

## 격리 명세표

- bundle 밖 경로: `{artifact.get('path', '해당 없음')}`
- SHA-256: `{artifact.get('sha256', '해당 없음')}`
- 크기: `{artifact.get('size_bytes', '해당 없음')}` 바이트
- 미디어 유형: `{artifact.get('media_type', '해당 없음')}`

이 후보는 정규 출처로 자동 승격되지 않았고, 이 판정은 C0–C4를 변경하지 않았다.
"""
        if citation_url:
            body += f"\n# 인용\n\n[1] [후보 출처]({citation_url})\n"
        write_okf_concept(
            WIKI / "admissions" / f"{admission['id'].lower()}.md",
            {
                "type": "Admission Decision",
                "title": admission["id"],
                "description": f"자동 신뢰 변경이 없는 출처·보안 입수 판정 {admission['id']} 기록.",
                "tags": ["admission", admission.get("status", "unknown"), "audit"],
                "timestamp": admission.get("created_at") or "2026-07-11T00:00:00+09:00",
                "lifecycle_status": admission.get("status", "unknown"),
                "generated": True,
            },
            body,
        )

    for run in runs:
        action_rows = []
        run_project_ids: set[str] = set()
        for action in run.get("plan", {}).get("actions", []):
            budget = action.get("budget", {})
            action_campaign = campaign_by_id.get(action.get("campaign_id"), {})
            project_id = action_campaign.get("project_id")
            project_cell = (
                f"[{project_id}](../projects/{str(project_id).lower()}.md)"
                if project_id
                else "-"
            )
            if project_id:
                run_project_ids.add(str(project_id))
            action_rows.append(
                f"| `{action.get('id', '-')}` | {project_cell} | `{action.get('campaign_id', '-')}` | `{action.get('execution', '-')}` | "
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
        body = f"""<!-- state/runs.json에서 자동 생성함. -->
# {run['id']}

- 상태: **{run.get('status', '-')}**
- 계획자: [{run.get('actor_id', '-')}](../actors/{actor_page_name(run.get('actor_id', 'unknown'))})
- 생성 시각: `{run.get('created_at', '-')}`
- 계획 ID: `{run.get('plan', {}).get('plan_id', '-')}`
- 계획 영수증 해시: `{receipt.get('receipt_hash', '-')}`
- 실행환경 부작용 수: **{receipt.get('side_effect_count', '-')}**

## 계획 전용 작업

| 작업 | 프로젝트 | 캠페인 | 실행 방식 | 시간(분) | 출처 수 |
|---|---|---|---|---:|---:|
{chr(10).join(action_rows) or '| - | - | - | - | - | - |'}

## 귀속된 외부 작업 보고

| 영수증 | 작업 | 상태 | 행위자 | 사용 시간(분) | 사용 출처 수 |
|---|---|---|---|---:|---:|
{chr(10).join(report_rows) or '| - | - | - | - | - | - |'}

실행환경은 외부 작업을 계획만 했다. 보고된 실행은 별도 행위자에게 귀속되며, 근거를 검토하기 전에는 검증되지 않은 상태로 남는다.
"""
        write_okf_concept(
            WIKI / "runs" / f"{run['id'].lower()}.md",
            {
                "type": "Runtime Receipt",
                "title": run["id"],
                "description": "범위가 제한된 연구 계획과 귀속된 외부 작업 영수증. 실행환경은 외부 작업을 수행하지 않는다.",
                "tags": ["runtime", "receipt", run.get("status", "unknown")],
                "timestamp": run.get("updated_at") or run.get("created_at") or "2026-07-11T00:00:00+09:00",
                "lifecycle_status": run.get("status", "unknown"),
                "project_ids": sorted(run_project_ids),
                "generated": True,
            },
            body,
        )

    def feedback_reference_link(reference: str) -> str:
        if reference.startswith("CLM-"):
            return f"[{reference}](../claims/{reference.lower()}.md)"
        if reference.startswith("SRC-"):
            return f"[{reference}](../sources/{reference.lower()}.md)"
        if reference.startswith("wiki/"):
            return f"[{reference}](../{reference.removeprefix('wiki/')})"
        return f"`{reference}`"

    for feedback in feedback_records:
        targets = [feedback_reference_link(str(item)) for item in feedback.get("targets", [])]
        evidence_refs = [feedback_reference_link(str(item)) for item in feedback.get("evidence_refs", [])]
        resolution = feedback.get("resolution") if isinstance(feedback.get("resolution"), dict) else {}
        body = f"""<!-- state/memory_feedback.json에서 자동 생성한 개인정보 최소 투영. -->
# {feedback['id']}

| 항목 | 값 |
|---|---|
| 행위자 | [{feedback.get('actor_id', '-')}](../actors/{actor_page_name(feedback.get('actor_id', 'unknown'))}) |
| 결과 | **{feedback.get('outcome', '-')}** |
| 상태 | **{feedback.get('status', '-')}** |
| 생성 시각 | `{feedback.get('created_at', '-')}` |
| 신뢰 효과 | `{feedback.get('trust_effect', '-')}` |
| 자동 작업 | `{feedback.get('automatic_action', '-')}` |
| 해결자 | {feedback_reference_link(str(resolution.get('actor_id')) ) if resolution else '-'} |
| 해결 시각 | `{resolution.get('at', '-') if resolution else '-'}` |

## 대상

{chr(10).join(f'- {item}' for item in targets) or '- 없음'}

## 근거 참조

{chr(10).join(f'- {item}' for item in evidence_refs) or '- 없음'}

자유 형식 사유, 작업 참조와 해결 사유는 제어 영역에 남기며 이 이동 가능한 투영에서는 의도적으로 제외한다. 피드백은 진단용이며 순위, C-level, S-level, 생명주기를 자동 변경하거나 내용을 삭제할 수 없다.
"""
        write_okf_concept(
            WIKI / "feedback" / f"{feedback['id'].lower()}.md",
            {
                "type": "Memory Feedback",
                "title": feedback["id"],
                "description": "자동 신뢰 변경이나 삭제 효과가 없는 개인정보 최소 검색 결과.",
                "tags": ["memory-feedback", feedback.get("outcome", "unknown"), feedback.get("status", "open")],
                "timestamp": resolution.get("at") or feedback.get("created_at") or "2026-07-11T00:00:00+09:00",
                "lifecycle_status": feedback.get("status", "open"),
                "generated": True,
            },
            body,
        )

    trust = load_json(ROOT / "config" / "trust-policy.json")
    source_rows = "\n".join(f"| {level} | {md_cell(text)} |" for level, text in trust.get("source_levels", {}).items())
    claim_rows = "\n".join(f"| {level} | {md_cell(text)} |" for level, text in trust.get("claim_levels", {}).items())
    trust_body = f"""<!-- config/trust-policy.json에서 자동 생성함. -->
# Living Wiki 신뢰 정책

이 문서는 Living Wiki 생산자 프로필이며 OKF 핵심 신뢰 스키마가 아니다.

## 출처 레벨

| 레벨 | 의미 |
|---|---|
{source_rows}

## 주장 레벨

| 레벨 | 의미 |
|---|---|
{claim_rows}

## 핵심 원칙

{trust.get('principle', '')}
"""
    write_okf_concept(
        WIKI / "trust" / "trust-policy.md",
        {
            "type": "Trust Policy",
            "title": "Living Wiki 신뢰 정책",
            "description": "생산자가 정의한 S0-S4 출처 및 C0-C4 주장 증거 성숙도 프로필.",
            "tags": ["trust", "claims", "sources", "producer-extension"],
            "timestamp": "2026-07-11T00:00:00+09:00",
            "generated": True,
        },
        trust_body,
    )

    for filename, type_name, title, description in [
        ("constitution.md", "Governance Policy", "Living Wiki 헌장", "행위자 동등성, 인식론 규칙, 권한 경계와 자기진화 정책."),
        ("decision-log.md", "Governance Decision Register", "Living Wiki 결정 기록", "아키텍처 결정과 명시적인 근거."),
    ]:
        canonical = ROOT / "governance" / filename
        body = "<!-- governance/%s에서 자동 생성한 투영. -->\n" % filename + canonical.read_text(encoding="utf-8")
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
        ("sources", "출처"),
        ("concepts", "개념"),
        ("perspectives", "관점"),
        ("claims", "주장"),
        ("actors", "행위자"),
        ("reviews", "검토"),
        ("projects", "연구 프로젝트"),
        ("campaigns", "연구 캠페인"),
        ("collaborations", "협업 기록"),
        ("admissions", "입수 판정"),
        ("runs", "실행 기록"),
        ("feedback", "메모리 피드백"),
        ("trust", "신뢰 정책"),
        ("governance", "거버넌스"),
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
        body = f"# {heading}\n\n" + ("\n".join(entries) if entries else "* 아직 문서 없음.") + "\n"
        atomic_write_text(folder / "index.md", body)


def render_okf_log() -> None:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for event in reversed(event_lines()):
        date = str(event.get("at", ""))[:10]
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
            grouped.setdefault(date, []).append(event)
    lines = ["# Living Wiki 갱신 기록", ""]
    for date in sorted(grouped, reverse=True):
        lines.extend([f"## {date}"])
        for event in grouped[date]:
            lines.append(
                f"* **{event.get('action', '갱신')}**: `{event.get('subject', '-')}` / 처리자 `{event.get('actor', '-')}`."
            )
        lines.append("")
    atomic_write_text(WIKI / "log.md", "\n".join(lines).rstrip() + "\n")


def render_all(actor: str, log: bool = True) -> None:
    claims = collection("claims")
    sources = collection("sources")
    campaigns = collection("campaigns")
    feedback_records = collection("memory_feedback")
    render_epistemic_dashboard(claims, sources)
    render_okf_state_projection()
    render_project_views()
    for proposal in collection("proposals"):
        render_proposal_record(proposal)
    render_index(claims, sources, campaigns, feedback_records)
    render_okf_subindexes()
    if log:
        append_event(
            actor,
            "wiki.render",
            "derived-views",
            {"sources": len(sources), "claims": len(claims), "memory_feedback": len(feedback_records)},
        )
    render_okf_log()


def render_cmd(args: argparse.Namespace) -> None:
    require_actor(args.actor)
    render_all(args.actor, log=not args.no_log)
    print("OKF bundle 색인·기록·인식론 대시보드를 렌더링함")


def language_validate(args: argparse.Namespace) -> None:
    import korean_docs

    findings = korean_docs.validate_repository(ROOT)
    for finding in findings:
        print(f"오류: {finding}")
    if findings:
        raise WikiError(f"한국어 문서 검사에서 {len(findings)}건을 발견함")
    print("한국어 문서 검사 통과")


def lint(args: argparse.Namespace) -> None:
    require_actor(args.actor)
    errors, warnings, counts = validation_findings(
        quarantine_profile=args.quarantine_profile
    )
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
                extra.append(f"{claim['id']}: 여러 지지 출처가 하나의 독립성 그룹으로 합쳐짐")
        if claim.get("confidence", {}).get("level") in {"C3", "C4"} and not claim.get("last_verified_at"):
            errors.append(f"{claim['id']}: promoted claim lacks last_verified_at")
    report = f"""# Wiki lint 보고서 — {today()}

## 요약

- 오류: {len(errors)}
- 경고: {len(warnings)}
- 인식론 발견: {len(extra)}
- 격리 검증 프로필: `{args.quarantine_profile}`
- 격리 payload bytes 검증: **{str(counts.get('quarantine_artifacts_missing', 0) == 0).lower()}**
- 개수: 행위자={counts.get('actors', 0)}, 출처={counts.get('sources', 0)}, 주장={counts.get('claims', 0)}, 검토={counts.get('reviews', 0)}, 캠페인={counts.get('campaigns', 0)}, 제안={counts.get('proposals', 0)}, 협업={counts.get('collaborations', 0)}, 입수 판정={counts.get('admissions', 0)}, 실행 기록={counts.get('runs', 0)}, 메모리 피드백={counts.get('memory_feedback', 0)}, 사건={counts.get('events', 0)}, OKF 문서={counts.get('okf_concepts', 0)}

## 오류

{chr(10).join(f'- 기록된 오류: {item}' for item in errors) or '- 없음'}

## 경고

{chr(10).join(f'- 기록된 경고: {item}' for item in warnings) or '- 없음'}

## 인식론 발견

{chr(10).join(f'- 기록된 발견: {item}' for item in extra) or '- 없음'}

## 해석

경고는 자동 삭제나 자동 강등 명령이 아니다. 담당 actor가 원문과 scope를 확인한 뒤 evidence, status, freshness를 갱신해야 한다.
"""
    check_only = bool(getattr(args, "check_only", False))
    if not check_only:
        atomic_write_text(REPORTS / "latest-lint.md", report)
    if not check_only and not args.no_log:
        append_event(
            args.actor,
            "wiki.lint",
            "all",
            {
                "errors": len(errors),
                "warnings": len(warnings),
                "findings": len(extra),
                "quarantine_profile": args.quarantine_profile,
                "quarantine_payload_verified": counts.get("quarantine_artifacts_missing", 0) == 0,
                "quarantine_missing": counts.get("quarantine_artifacts_missing", 0),
            },
        )
    if check_only:
        print(f"Wiki lint 검사 완료 ({len(errors)} errors, {len(warnings) + len(extra)} warnings/findings)")
    else:
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
    feedback_records = collection("memory_feedback")
    events = event_lines()
    levels = {level: 0 for level in CLAIM_LEVELS}
    for claim in claims:
        levels[claim.get("confidence", {}).get("level", "C0")] += 1
    version = load_json(ROOT / "config" / "wiki.json").get("harness_version", "unknown")
    print(f"Living Wiki {version}")
    print(f"Actors: {len(actors)} | Sources: {len(sources)} | Claims: {len(claims)} | Events: {len(events)}")
    print(
        f"Reviews: {len(reviews)} | Collaborations: {len(collaborations)} | "
        f"Admissions: {len(admissions)} | Runs: {len(runs)} | Memory feedback: {len(feedback_records)}"
    )
    inactive_claims = sum(lifecycle_status(item, kind="claim") != "active" for item in claims)
    inactive_sources = sum(lifecycle_status(item, kind="source") != "active" for item in sources)
    unresolved_feedback = sum(item.get("status") != "resolved" for item in feedback_records)
    print(
        f"Inactive lifecycle: claims={inactive_claims} sources={inactive_sources} | "
        f"Unresolved feedback={unresolved_feedback}"
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
    p.add_argument("--scope", default="일반")
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

    p = sub.add_parser(
        "campaign-project-backfill",
        help="관심사 레지스트리를 기준으로 기존 캠페인 프로젝트를 멱등 분류",
    )
    p.add_argument("--actor", default="agent:codex")
    p.set_defaults(func=campaign_project_backfill)

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
    p.add_argument("--evidence", help="쉼표로 구분한 기존 CLM-* 근거 ID")
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

    p = sub.add_parser("memory-feedback-add", help="record an audit-only retrieval outcome")
    p.add_argument("--actor", default="agent:codex")
    p.add_argument("--task-ref", required=True, help="opaque task identifier; never paste the raw query")
    p.add_argument("--targets", required=True, help="comma-separated claim/source/wiki references")
    p.add_argument("--outcome", required=True, choices=["helpful", "harmful", "irrelevant", "unknown"])
    p.add_argument("--rationale", required=True)
    p.add_argument("--evidence-refs")
    p.add_argument("--at", help="explicit timezone-aware timestamp for replayable writes")
    p.set_defaults(func=memory_feedback_add)

    p = sub.add_parser("memory-feedback-resolve", help="resolve one feedback observation with attribution")
    p.add_argument("--actor", default="agent:codex")
    p.add_argument("--feedback", required=True)
    p.add_argument("--rationale", required=True)
    p.add_argument("--at", help="explicit timezone-aware timestamp for replayable writes")
    p.set_defaults(func=memory_feedback_resolve)

    p = sub.add_parser("knowledge-lifecycle", help="transition claim/source lifecycle without deletion")
    p.add_argument("--actor", default="agent:codex")
    p.add_argument("--kind", required=True, choices=["claim", "source"])
    p.add_argument("--id", required=True)
    p.add_argument("--status", required=True, choices=sorted(LIFECYCLE_STATUSES))
    p.add_argument("--reason", required=True)
    p.add_argument("--replacement", help="same-kind active replacement; required for superseded")
    p.add_argument("--at", help="explicit timezone-aware timestamp for replayable writes")
    p.set_defaults(func=knowledge_lifecycle)

    p = sub.add_parser("memory-hygiene", help="print a deterministic read-only staleness/lifecycle report")
    p.add_argument("--now", required=True, help="explicit timezone-aware evaluation time")
    p.add_argument("--compact", action="store_true")
    p.set_defaults(func=memory_hygiene_cmd)

    p = sub.add_parser("hygiene-plan", help="범위가 제한된 읽기 전용 위생 후보 계획 출력")
    p.add_argument("--now", required=True, help="시간대가 포함된 고정 평가 시각")
    p.add_argument("--pretty", action="store_true", help="사람이 읽기 쉬운 들여쓰기 JSON 출력")
    p.set_defaults(func=hygiene_plan_cmd)

    p = sub.add_parser("search", help="run deterministic lexical retrieval across canonical state and wiki")
    p.add_argument("query")
    p.add_argument("--limit", type=int, default=10)
    p.add_argument("--include-inactive", action="store_true", help="include deprecated/superseded/invalidated/archived records")
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
    p.add_argument(
        "--quarantine-profile",
        choices=[STRICT_QUARANTINE_PROFILE, PUBLIC_QUARANTINE_PROFILE],
        default=STRICT_QUARANTINE_PROFILE,
        help="격리 원문 검증 프로필. 로컬 보관은 strict가 기본값이다.",
    )
    p.add_argument("--no-log", action="store_true", help="publish 재검증에서 중복 사건을 남기지 않음")
    p.add_argument(
        "--check-only",
        action="store_true",
        help="현재 변경을 임시 Git worktree에서 검사하고 원본 작업 사본을 바꾸지 않음",
    )
    p.set_defaults(func=release_check)

    p = sub.add_parser("render", help="regenerate deterministic human-readable views")
    p.add_argument("--actor", default="agent:codex")
    p.add_argument("--no-log", action="store_true", help="pure/idempotence-check export without a new event")
    p.set_defaults(func=render_cmd)

    p = sub.add_parser("language-validate", help="사람이 읽는 문서의 한국어 기본 계약 검사")
    p.set_defaults(func=language_validate)

    p = sub.add_parser("lint", help="run structural and epistemic health checks")
    p.add_argument("--actor", default="agent:codex")
    p.add_argument(
        "--quarantine-profile",
        choices=[STRICT_QUARANTINE_PROFILE, PUBLIC_QUARANTINE_PROFILE],
        default=STRICT_QUARANTINE_PROFILE,
        help="격리 원문 검증 프로필. 공개 clean clone만 portable 값을 사용한다.",
    )
    p.add_argument("--no-log", action="store_true", help="publish 재검증에서 중복 사건을 남기지 않음")
    p.add_argument(
        "--check-only",
        action="store_true",
        help="판정만 수행하고 보고서와 사건 원장을 쓰지 않음",
    )
    p.set_defaults(func=lint)

    p = sub.add_parser("validate", help="validate references, hashes, schemas, and event chain")
    p.add_argument(
        "--quarantine-profile",
        choices=[STRICT_QUARANTINE_PROFILE, PUBLIC_QUARANTINE_PROFILE],
        default=STRICT_QUARANTINE_PROFILE,
        help="격리 원문 검증 프로필. 공개 clean clone만 portable 값을 사용한다.",
    )
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
