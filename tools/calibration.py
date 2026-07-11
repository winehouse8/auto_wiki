#!/usr/bin/env python3
"""Deterministic calibration and source-admission primitives for Living Wiki.

This module is deliberately independent of ``tools/wiki.py`` and the canonical
ledgers.  It evaluates snapshots supplied by callers; it never mutates a trust
level, source record, or Wiki page.  Python standard library only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import posixpath
import re
import sys
from abc import ABC, abstractmethod
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple
from urllib.parse import parse_qsl, quote, unquote, urlencode, urlsplit, urlunsplit


SCHEMA_VERSION = "living-wiki-calibration-report/v1"
GOLD_LABELS: Tuple[str, ...] = (
    "supported",
    "contradicted",
    "mixed",
    "insufficient",
    "obsolete",
)
CLAIM_LEVELS: Tuple[str, ...] = ("C0", "C1", "C2", "C3", "C4")
REGISTRY_STATUSES: Tuple[str, ...] = (
    "active",
    "corrected",
    "superseded",
    "retracted",
    "withdrawn",
    "unknown",
)
COUNTER_SEARCH_DIMENSIONS: Tuple[str, ...] = (
    "contradiction",
    "origin",
    "status",
)
SMALL_N_DEFAULT = 5

_DOI_RE = re.compile(r"^10\.\d{4,9}/\S+$", re.IGNORECASE)
_TRACKING_QUERY_NAMES = {
    "fbclid",
    "gclid",
    "mc_cid",
    "mc_eid",
    "ref_src",
    "ref_url",
}


class CalibrationError(ValueError):
    """Raised when a benchmark or source cannot be evaluated safely."""


def canonical_json(value: Any, *, pretty: bool = False) -> str:
    """Return stable UTF-8 JSON text without environment-dependent fields."""

    if pretty:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _rounded(value: float) -> float:
    return round(value, 6)


def _normalise_domain(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CalibrationError("gold record domain must be a non-empty string")
    return re.sub(r"\s+", "-", value.strip().casefold())


def _normalise_label(value: Any, field: str) -> str:
    if not isinstance(value, str) or value not in GOLD_LABELS:
        allowed = ", ".join(GOLD_LABELS)
        raise CalibrationError(f"{field} must be one of: {allowed}")
    return value


def wilson_interval(successes: int, total: int, z: float = 1.959963984540054) -> Optional[List[float]]:
    """Return a two-sided Wilson score interval, or ``None`` for no trials."""

    if isinstance(successes, bool) or isinstance(total, bool):
        raise CalibrationError("Wilson counts must be integers, not booleans")
    if not isinstance(successes, int) or not isinstance(total, int):
        raise CalibrationError("Wilson counts must be integers")
    if total < 0 or successes < 0 or successes > total:
        raise CalibrationError("Wilson counts require 0 <= successes <= total")
    if total == 0:
        return None
    if not isinstance(z, (int, float)) or not math.isfinite(z) or z <= 0:
        raise CalibrationError("Wilson z must be a positive finite number")
    proportion = successes / total
    z_squared = z * z
    denominator = 1.0 + z_squared / total
    centre = (proportion + z_squared / (2.0 * total)) / denominator
    margin = z * math.sqrt(
        proportion * (1.0 - proportion) / total + z_squared / (4.0 * total * total)
    ) / denominator
    return [_rounded(max(0.0, centre - margin)), _rounded(min(1.0, centre + margin))]


def resolve_gold_record(record: Mapping[str, Any]) -> Dict[str, Any]:
    """Resolve independent adjudications to a benchmark label.

    Votes are counted once per ``reviewer_group``.  Repeated identical votes
    from one group are reported and ignored.  Conflicting votes from the same
    group make the item disputed because group independence is no longer clear.
    A strict majority is required unless ``benchmark_status=disputed``.
    """

    record_id = record.get("id")
    if not isinstance(record_id, str) or not record_id.strip():
        raise CalibrationError("gold record id must be a non-empty string")
    declared_status = record.get("benchmark_status", "adjudicated")
    if declared_status not in ("adjudicated", "disputed"):
        raise CalibrationError(
            f"gold record {record_id}: benchmark_status must be adjudicated or disputed"
        )
    adjudications = record.get("adjudications")
    if not isinstance(adjudications, list) or not adjudications:
        raise CalibrationError(f"gold record {record_id}: adjudications must be a non-empty list")

    group_votes: Dict[str, str] = {}
    duplicate_votes = 0
    conflicting_groups: Set[str] = set()
    for position, vote in enumerate(adjudications):
        if not isinstance(vote, Mapping):
            raise CalibrationError(f"gold record {record_id}: adjudication {position} must be an object")
        group = vote.get("reviewer_group")
        if not isinstance(group, str) or not group.strip():
            raise CalibrationError(
                f"gold record {record_id}: adjudication {position} needs reviewer_group"
            )
        group = group.strip()
        label = _normalise_label(vote.get("label"), f"gold record {record_id} label")
        prior = group_votes.get(group)
        if prior is None:
            group_votes[group] = label
        elif prior == label:
            duplicate_votes += 1
        else:
            conflicting_groups.add(group)

    counts = Counter(
        label for group, label in group_votes.items() if group not in conflicting_groups
    )
    valid_group_count = sum(counts.values())
    ordered_counts = {label: counts.get(label, 0) for label in GOLD_LABELS}
    result: Dict[str, Any] = {
        "adjudicator_groups": len(group_votes),
        "agreement": None,
        "counts": ordered_counts,
        "duplicate_votes_ignored": duplicate_votes,
        "label": None,
        "reason": None,
        "status": "disputed",
    }

    if declared_status == "disputed":
        result["reason"] = "benchmark_marked_disputed"
        return result
    if conflicting_groups:
        result["reason"] = "conflicting_votes_within_reviewer_group"
        result["conflicting_groups"] = sorted(conflicting_groups)
        return result
    if valid_group_count < 2:
        result["reason"] = "fewer_than_two_independent_adjudicator_groups"
        return result

    ranked = sorted(counts.items(), key=lambda item: (-item[1], GOLD_LABELS.index(item[0])))
    top_label, top_count = ranked[0]
    runner_up = ranked[1][1] if len(ranked) > 1 else 0
    agreement = top_count / valid_group_count
    result["agreement"] = _rounded(agreement)
    if top_count == runner_up or top_count <= valid_group_count / 2.0:
        result["reason"] = "no_strict_majority"
        return result

    result.update(
        {
            "label": top_label,
            "reason": "strict_majority",
            "status": "resolved",
        }
    )
    return result


def _metric(successes: int, total: int, small_n_threshold: int) -> Dict[str, Any]:
    return {
        "correct": successes,
        "n": total,
        "p_correct": _rounded(successes / total) if total else None,
        "small_n": total < small_n_threshold,
        "small_n_threshold": small_n_threshold,
        "wilson_95": wilson_interval(successes, total),
    }


def calibration_report(
    records: Sequence[Mapping[str, Any]], *, small_n_threshold: int = SMALL_N_DEFAULT
) -> Dict[str, Any]:
    """Compute observational correctness by ordinal level and domain.

    ``p_correct`` is empirical performance conditional on a Wiki-assigned
    evidence-maturity level.  It is never used as, or presented as, the meaning
    of C0--C4.  Disputed gold items and abstentions remain visible in coverage
    but are excluded from accuracy denominators.
    """

    if isinstance(small_n_threshold, bool) or not isinstance(small_n_threshold, int):
        raise CalibrationError("small_n_threshold must be an integer")
    if small_n_threshold < 1:
        raise CalibrationError("small_n_threshold must be at least 1")
    if not isinstance(records, Sequence) or isinstance(records, (str, bytes)):
        raise CalibrationError("gold_records must be a list")

    seen_ids: Set[str] = set()
    resolved_rows: List[Dict[str, Any]] = []
    adjudication_rows: List[Dict[str, Any]] = []
    domains: Set[str] = set()
    disputed = 0
    abstentions = 0

    for record in records:
        if not isinstance(record, Mapping):
            raise CalibrationError("every gold record must be an object")
        record_id = record.get("id")
        if not isinstance(record_id, str) or not record_id.strip():
            raise CalibrationError("gold record id must be a non-empty string")
        if record_id in seen_ids:
            raise CalibrationError(f"duplicate gold record id: {record_id}")
        seen_ids.add(record_id)
        level = record.get("level")
        if level not in CLAIM_LEVELS:
            raise CalibrationError(
                f"gold record {record_id}: level must be one of {', '.join(CLAIM_LEVELS)}"
            )
        domain = _normalise_domain(record.get("domain"))
        domains.add(domain)
        predicted = record.get("predicted_label")
        if predicted is not None:
            predicted = _normalise_label(predicted, f"gold record {record_id} predicted_label")
        resolution = resolve_gold_record(record)
        adjudication_rows.append(
            {
                "id": record_id,
                "label": resolution["label"],
                "reason": resolution["reason"],
                "status": resolution["status"],
            }
        )
        if resolution["status"] != "resolved":
            disputed += 1
            continue
        if predicted is None:
            abstentions += 1
            continue
        resolved_rows.append(
            {
                "correct": predicted == resolution["label"],
                "domain": domain,
                "id": record_id,
                "level": level,
            }
        )

    def group_metric(rows: Iterable[Mapping[str, Any]]) -> Dict[str, Any]:
        materialized = list(rows)
        successes = sum(1 for row in materialized if row["correct"])
        return _metric(successes, len(materialized), small_n_threshold)

    by_level = {
        level: group_metric(row for row in resolved_rows if row["level"] == level)
        for level in CLAIM_LEVELS
    }
    by_domain = {
        domain: group_metric(row for row in resolved_rows if row["domain"] == domain)
        for domain in sorted(domains)
    }
    by_level_domain: List[Dict[str, Any]] = []
    for level in CLAIM_LEVELS:
        for domain in sorted(domains):
            entry = {"domain": domain, "level": level}
            entry.update(
                group_metric(
                    row
                    for row in resolved_rows
                    if row["level"] == level and row["domain"] == domain
                )
            )
            by_level_domain.append(entry)

    total = len(records)
    resolved_gold = total - disputed
    scorable = len(resolved_rows)
    return {
        "adjudication": sorted(adjudication_rows, key=lambda row: row["id"]),
        "by_domain": by_domain,
        "by_level": by_level,
        "p_correct_given_level_domain": by_level_domain,
        "overall": group_metric(resolved_rows),
        "coverage": {
            "abstained_resolved_records": abstentions,
            "disputed_records": disputed,
            "prediction_coverage_of_resolved": _rounded(scorable / resolved_gold)
            if resolved_gold
            else None,
            "resolved_gold_records": resolved_gold,
            "scorable_records": scorable,
            "total_records": total,
        },
        "interpretation": {
            "c_levels_are_probabilities": False,
            "conditional_rate_is": "observed benchmark correctness given assigned ordinal level and domain",
            "scale": "C0-C4 ordinal evidence-maturity level",
            "warning": "Never assign or promote a C-level from p_correct; use the existing trust-policy gates.",
        },
    }


def canonicalize_doi(value: str) -> str:
    """Return a lowercase DOI token without a resolver URL."""

    if not isinstance(value, str) or not value.strip():
        raise CalibrationError("DOI must be a non-empty string")
    candidate = unquote(value.strip())
    candidate = re.sub(r"^doi:\s*", "", candidate, flags=re.IGNORECASE)
    if re.match(r"^https?://", candidate, flags=re.IGNORECASE):
        parsed = urlsplit(candidate)
        if parsed.hostname and parsed.hostname.casefold() in ("doi.org", "dx.doi.org", "www.doi.org"):
            candidate = parsed.path.lstrip("/")
        else:
            raise CalibrationError("DOI URL must use doi.org")
    candidate = candidate.strip().rstrip(".,;)").casefold()
    if not _DOI_RE.match(candidate) or any(character.isspace() for character in candidate):
        raise CalibrationError(f"invalid DOI: {value}")
    return candidate


def _normalise_path(path: str) -> str:
    if not path or path == "/":
        return ""
    had_trailing_slash = path.endswith("/")
    path = re.sub(r"/{2,}", "/", path)
    normalised = posixpath.normpath(path)
    if not normalised.startswith("/"):
        normalised = "/" + normalised
    if had_trailing_slash and normalised != "/":
        normalised = normalised.rstrip("/")
    # Encode Unicode deterministically while preserving existing URL delimiters.
    return quote(unquote(normalised), safe="/%:@!$&'()*+,;=-._~")


def canonicalize_url(value: str) -> str:
    """Canonicalize an HTTP(S) URL for duplicate detection.

    Fragments and well-known tracking parameters are dropped.  Semantic query
    parameters are sorted and retained; this function intentionally does not
    perform network redirects or claim two different hosts are equivalent.
    """

    if not isinstance(value, str) or not value.strip():
        raise CalibrationError("URL must be a non-empty string")
    candidate = value.strip()
    if candidate.startswith("//"):
        candidate = "https:" + candidate
    parsed = urlsplit(candidate)
    if parsed.scheme.casefold() not in ("http", "https") or not parsed.hostname:
        raise CalibrationError(f"URL must be absolute HTTP(S): {value}")
    if parsed.username is not None or parsed.password is not None:
        raise CalibrationError("URLs containing credentials are not admissible")
    scheme = parsed.scheme.casefold()
    host = parsed.hostname.casefold().rstrip(".")
    try:
        host = host.encode("idna").decode("ascii")
    except UnicodeError as exc:
        raise CalibrationError(f"invalid URL hostname: {value}") from exc
    port = parsed.port
    if port is not None and not ((scheme == "http" and port == 80) or (scheme == "https" and port == 443)):
        host = f"{host}:{port}"
    query_items = []
    for key, item_value in parse_qsl(parsed.query, keep_blank_values=True):
        folded = key.casefold()
        if folded.startswith("utm_") or folded in _TRACKING_QUERY_NAMES:
            continue
        query_items.append((key, item_value))
    query_items.sort(key=lambda item: (item[0], item[1]))
    query = urlencode(query_items, doseq=True)
    return urlunsplit((scheme, host, _normalise_path(parsed.path), query, ""))


def canonicalize_repository(value: str) -> str:
    """Return the HTTPS root URL for a GitHub/GitLab/Bitbucket repository."""

    if not isinstance(value, str) or not value.strip():
        raise CalibrationError("repository must be a non-empty string")
    candidate = value.strip()
    scp_match = re.match(r"^git@([^:]+):(.+)$", candidate)
    if scp_match:
        candidate = f"https://{scp_match.group(1)}/{scp_match.group(2)}"
    elif re.match(r"^[\w.-]+/[\w.-]+(?:\.git)?$", candidate):
        candidate = "https://github.com/" + candidate
    elif re.match(r"^(?:www\.)?(?:github|gitlab|bitbucket)\.com/", candidate, re.IGNORECASE):
        candidate = "https://" + candidate
    if candidate.startswith("ssh://git@"):
        candidate = "https://" + candidate[len("ssh://git@") :]
    parsed = urlsplit(candidate)
    host = (parsed.hostname or "").casefold()
    if host.startswith("www."):
        host = host[4:]
    if host not in ("github.com", "gitlab.com", "bitbucket.org"):
        raise CalibrationError("repository host must be GitHub, GitLab, or Bitbucket")
    parts = [part for part in parsed.path.split("/") if part]
    if host == "gitlab.com" and "-" in parts:
        parts = parts[: parts.index("-")]
    elif host in ("github.com", "bitbucket.org"):
        parts = parts[:2]
    if len(parts) < 2:
        raise CalibrationError("repository URL must include owner/group and repository")
    parts[-1] = re.sub(r"\.git$", "", parts[-1], flags=re.IGNORECASE)
    if not parts[-1]:
        raise CalibrationError("repository name cannot be empty")
    # Hosted repositories on these services are case-insensitive for identity.
    path = "/".join(part.casefold() for part in parts)
    return f"https://{host}/{path}"


def canonical_registry_identifier(value: str) -> str:
    """Normalize a fixture-registry identifier with an explicit namespace."""

    if not isinstance(value, str) or ":" not in value:
        raise CalibrationError("registry identifier needs doi:, url:, or repository: prefix")
    namespace, payload = value.split(":", 1)
    namespace = namespace.casefold().strip()
    if namespace == "doi":
        return "doi:" + canonicalize_doi(payload)
    if namespace == "url":
        return "url:" + canonicalize_url(payload)
    if namespace in ("repo", "repository"):
        return "repository:" + canonicalize_repository(payload)
    if namespace == "sha256":
        digest = payload.strip().casefold()
        if not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise CalibrationError("sha256 registry identifier must contain 64 hex characters")
        return "sha256:" + digest
    raise CalibrationError(f"unsupported registry identifier namespace: {namespace}")


def source_identity_keys(source: Mapping[str, Any]) -> List[str]:
    """Return all strong, canonical identity keys present on a source record."""

    keys: Set[str] = set()
    if source.get("doi"):
        keys.add("doi:" + canonicalize_doi(source["doi"]))
    if source.get("repository"):
        keys.add("repository:" + canonicalize_repository(source["repository"]))
    if source.get("url"):
        url = canonicalize_url(source["url"])
        keys.add("url:" + url)
        parsed = urlsplit(url)
        if parsed.hostname in ("doi.org", "dx.doi.org", "www.doi.org"):
            keys.add("doi:" + canonicalize_doi(url))
        parsed_host = parsed.hostname.casefold() if parsed.hostname else ""
        if parsed_host.startswith("www."):
            parsed_host = parsed_host[4:]
        if parsed_host in ("github.com", "gitlab.com", "bitbucket.org"):
            try:
                keys.add("repository:" + canonicalize_repository(url))
            except CalibrationError:
                pass
    digest = source.get("content_sha256")
    if digest:
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", digest):
            raise CalibrationError("content_sha256 must contain exactly 64 hexadecimal characters")
        keys.add("sha256:" + digest.casefold())
    return sorted(keys)


class _UnionFind:
    def __init__(self, values: Iterable[str]) -> None:
        self.parent = {value: value for value in values}

    def find(self, value: str) -> str:
        while self.parent[value] != value:
            self.parent[value] = self.parent[self.parent[value]]
            value = self.parent[value]
        return value

    def union(self, left: str, right: str) -> None:
        root_left, root_right = self.find(left), self.find(right)
        if root_left == root_right:
            return
        if root_left < root_right:
            self.parent[root_right] = root_left
        else:
            self.parent[root_left] = root_right


def _normalise_title(value: Any) -> Optional[str]:
    if not isinstance(value, str) or not value.strip():
        return None
    return re.sub(r"[^\w]+", " ", value.casefold(), flags=re.UNICODE).strip()


def cluster_independence(sources: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    """Cluster exact duplicates and explicitly derived sources.

    This is a conservative heuristic: publisher or author overlap alone never
    merges sources.  It is an origin/dependency hint, not an automatic change to
    canonical ``independence_group`` values.
    """

    if not isinstance(sources, Sequence) or isinstance(sources, (str, bytes)):
        raise CalibrationError("sources must be a list")
    by_id: Dict[str, Mapping[str, Any]] = {}
    for source in sources:
        if not isinstance(source, Mapping):
            raise CalibrationError("every source must be an object")
        source_id = source.get("id")
        if not isinstance(source_id, str) or not source_id.strip():
            raise CalibrationError("source id must be a non-empty string")
        if source_id in by_id:
            raise CalibrationError(f"duplicate source id: {source_id}")
        by_id[source_id] = source

    union = _UnionFind(by_id)
    links: List[Dict[str, str]] = []
    identity_errors: List[Dict[str, str]] = []

    def connect(left: str, right: str, reason: str) -> None:
        if left == right:
            return
        first, second = sorted((left, right))
        union.union(first, second)
        links.append({"left": first, "reason": reason, "right": second})

    key_owner: Dict[str, str] = {}
    origin_owner: Dict[str, str] = {}
    fingerprint_owner: Dict[str, str] = {}
    for source_id in sorted(by_id):
        source = by_id[source_id]
        try:
            identity_keys = source_identity_keys(source)
        except (CalibrationError, ValueError) as exc:
            identity_keys = []
            identity_errors.append({"error": str(exc), "source_id": source_id})
        for key in identity_keys:
            if key in key_owner:
                connect(source_id, key_owner[key], "shared_identity:" + key)
            else:
                key_owner[key] = source_id

        derived_values = source.get("derived_from", [])
        if isinstance(derived_values, str):
            derived_values = [derived_values]
        if not isinstance(derived_values, list):
            raise CalibrationError(f"source {source_id}: derived_from must be a string or list")
        for parent in derived_values:
            if not isinstance(parent, str):
                raise CalibrationError(f"source {source_id}: derived_from values must be strings")
            if parent in by_id:
                connect(source_id, parent, "explicit_derived_from")

        origin_url = source.get("origin_url")
        if origin_url:
            origin_key = canonicalize_url(origin_url)
            if origin_key in origin_owner:
                connect(source_id, origin_owner[origin_key], "shared_origin_url:" + origin_key)
            else:
                origin_owner[origin_key] = source_id

        title = _normalise_title(source.get("title"))
        published_at = source.get("published_at")
        quoted_origin = source.get("quoted_origin")
        if title and published_at and quoted_origin:
            fingerprint = canonical_json(
                [title, str(published_at), str(quoted_origin).strip().casefold()]
            )
            if fingerprint in fingerprint_owner:
                connect(source_id, fingerprint_owner[fingerprint], "derived_fingerprint")
            else:
                fingerprint_owner[fingerprint] = source_id

    groups: Dict[str, List[str]] = defaultdict(list)
    for source_id in sorted(by_id):
        groups[union.find(source_id)].append(source_id)
    clusters: List[Dict[str, Any]] = []
    membership: Dict[str, str] = {}
    for members in sorted(groups.values(), key=lambda item: item[0]):
        digest = hashlib.sha256("\n".join(members).encode("utf-8")).hexdigest()[:12].upper()
        cluster_id = "IC-" + digest
        member_set = set(members)
        cluster_links = sorted(
            (
                link
                for link in links
                if link["left"] in member_set and link["right"] in member_set
            ),
            key=lambda link: (link["left"], link["right"], link["reason"]),
        )
        clusters.append(
            {
                "cluster_id": cluster_id,
                "links": cluster_links,
                "members": members,
            }
        )
        for source_id in members:
            membership[source_id] = cluster_id
    return {
        "cluster_count": len(clusters),
        "clusters": clusters,
        "identity_errors": sorted(identity_errors, key=lambda item: (item["source_id"], item["error"])),
        "membership": membership,
        "source_count": len(by_id),
        "warning": "Heuristic origin clusters require human review before changing canonical independence_group.",
    }


class StatusRegistryAdapter(ABC):
    """Read-only interface for publication/retraction status registries."""

    name = "abstract-status-registry"

    @abstractmethod
    def lookup(self, source: Mapping[str, Any]) -> Dict[str, Any]:
        """Return a serializable status finding for ``source``."""


class FixtureStatusRegistry(StatusRegistryAdapter):
    """Offline, deterministic registry used by tests and fixed benchmarks."""

    name = "offline-fixture-registry"

    def __init__(self, entries: Sequence[Mapping[str, Any]]) -> None:
        if not isinstance(entries, Sequence) or isinstance(entries, (str, bytes)):
            raise CalibrationError("registry_entries must be a list")
        self._entries: Dict[str, Dict[str, Any]] = {}
        for entry in entries:
            if not isinstance(entry, Mapping):
                raise CalibrationError("registry entry must be an object")
            identifier = canonical_registry_identifier(entry.get("identifier"))
            status = entry.get("status")
            if status not in REGISTRY_STATUSES:
                raise CalibrationError(
                    f"registry status for {identifier} must be one of {', '.join(REGISTRY_STATUSES)}"
                )
            finding = {
                "detail": entry.get("detail"),
                "identifier": identifier,
                "status": status,
            }
            prior = self._entries.get(identifier)
            if prior is not None and prior != finding:
                raise CalibrationError(f"conflicting fixture registry entries: {identifier}")
            self._entries[identifier] = finding

    def lookup(self, source: Mapping[str, Any]) -> Dict[str, Any]:
        matches = [self._entries[key] for key in source_identity_keys(source) if key in self._entries]
        if not matches:
            return {
                "adapter": self.name,
                "matches": [],
                "status": "not_found",
            }
        severity = {
            "retracted": 6,
            "withdrawn": 5,
            "superseded": 4,
            "corrected": 3,
            "unknown": 2,
            "active": 1,
        }
        matches = sorted(matches, key=lambda item: item["identifier"])
        status = max(matches, key=lambda item: severity[item["status"]])["status"]
        return {
            "adapter": self.name,
            "matches": matches,
            "status": status,
        }


def counter_search_coverage(
    counter_search: Any,
    *,
    required_dimensions: Sequence[str] = COUNTER_SEARCH_DIMENSIONS,
) -> Dict[str, Any]:
    """Measure completed counter-search dimensions without judging conclusions."""

    required = sorted(set(required_dimensions))
    if not required:
        raise CalibrationError("required counter-search dimensions cannot be empty")
    if not isinstance(counter_search, Mapping):
        counter_search = {}
    checks = counter_search.get("checks", [])
    if not isinstance(checks, list):
        raise CalibrationError("counter_search.checks must be a list")
    completed: Set[str] = set()
    for position, check in enumerate(checks):
        if isinstance(check, str):
            dimension, complete = check, True
        elif isinstance(check, Mapping):
            dimension = check.get("dimension")
            complete = check.get("completed", True)
        else:
            raise CalibrationError(f"counter-search check {position} must be a string or object")
        if not isinstance(dimension, str):
            raise CalibrationError(f"counter-search check {position} needs dimension")
        if complete is True and dimension in required:
            completed.add(dimension)
    missing = sorted(set(required) - completed)
    return {
        "completed": sorted(completed),
        "coverage": _rounded(len(completed) / len(required)),
        "missing": missing,
        "required": required,
    }


def _source_validation(source: Mapping[str, Any]) -> Tuple[List[str], List[str]]:
    errors: List[str] = []
    keys: List[str] = []
    try:
        keys = source_identity_keys(source)
    except (CalibrationError, ValueError) as exc:
        errors.append(str(exc))
    if not keys:
        errors.append("no canonical URL, DOI, repository, or content hash")
    return keys, sorted(set(errors))


def admission_decision(
    candidate: Mapping[str, Any],
    *,
    registry: Optional[StatusRegistryAdapter] = None,
    existing_sources: Sequence[Mapping[str, Any]] = (),
    independence: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Return ``allow``, ``review``, or ``reject`` without mutating state."""

    candidate_id = candidate.get("id")
    if not isinstance(candidate_id, str) or not candidate_id.strip():
        raise CalibrationError("admission candidate id must be a non-empty string")
    canonical_keys, validation_errors = _source_validation(candidate)
    reject_reasons: List[Dict[str, str]] = [
        {"code": "invalid_identifier", "detail": detail} for detail in validation_errors
    ]
    review_reasons: List[Dict[str, str]] = []

    coverage = counter_search_coverage(candidate.get("counter_search"))
    if coverage["missing"]:
        review_reasons.append(
            {
                "code": "counter_search_incomplete",
                "detail": "missing: " + ", ".join(coverage["missing"]),
            }
        )
    if candidate.get("provenance_verified") is not True:
        review_reasons.append(
            {
                "code": "provenance_unverified",
                "detail": "provenance_verified must be explicitly true",
            }
        )

    if validation_errors:
        finding = {"adapter": getattr(registry, "name", None), "matches": [], "status": "not_checked_invalid"}
    elif registry is None:
        finding = {"adapter": None, "matches": [], "status": "not_checked"}
    else:
        finding = registry.lookup(candidate)
    status = finding["status"]
    if status in ("retracted", "withdrawn"):
        reject_reasons.append(
            {
                "code": "registry_terminal_status",
                "detail": status,
            }
        )
    elif status in ("corrected", "superseded", "unknown"):
        review_reasons.append(
            {
                "code": "registry_requires_review",
                "detail": status,
            }
        )
    elif candidate.get("registry_required") is True and status in ("not_checked", "not_found"):
        review_reasons.append(
            {
                "code": "required_registry_status_missing",
                "detail": status,
            }
        )

    existing_key_owner: Dict[str, str] = {}
    for source in existing_sources:
        source_id = source.get("id")
        if not isinstance(source_id, str):
            raise CalibrationError("existing source id must be a string")
        for key in source_identity_keys(source):
            existing_key_owner.setdefault(key, source_id)
    duplicate_ids = sorted({existing_key_owner[key] for key in canonical_keys if key in existing_key_owner})
    if duplicate_ids:
        review_reasons.append(
            {
                "code": "duplicate_existing_source",
                "detail": ", ".join(duplicate_ids),
            }
        )

    cluster_id = None
    cluster_members: List[str] = []
    if independence:
        membership = independence.get("membership", {})
        cluster_id = membership.get(candidate_id)
        for cluster in independence.get("clusters", []):
            if cluster.get("cluster_id") == cluster_id:
                cluster_members = list(cluster.get("members", []))
                break
        other_members = sorted(member for member in cluster_members if member != candidate_id)
        if other_members and not duplicate_ids:
            review_reasons.append(
                {
                    "code": "derived_independence_collision",
                    "detail": ", ".join(other_members),
                }
            )

    if candidate.get("unresolved_strong_contradiction") is True:
        review_reasons.append(
            {
                "code": "unresolved_strong_contradiction",
                "detail": "candidate requires contradiction adjudication",
            }
        )

    reject_reasons = sorted(reject_reasons, key=lambda item: (item["code"], item["detail"]))
    review_reasons = sorted(review_reasons, key=lambda item: (item["code"], item["detail"]))
    if reject_reasons:
        decision = "reject"
        reasons = reject_reasons + review_reasons
    elif review_reasons:
        decision = "review"
        reasons = review_reasons
    else:
        decision = "allow"
        reasons = [
            {
                "code": "minimum_gate_satisfied",
                "detail": "identity, provenance, status policy, and counter-search checks passed",
            }
        ]
    return {
        "candidate_id": candidate_id,
        "canonical_identifiers": canonical_keys,
        "counter_search": coverage,
        "decision": decision,
        "independence_cluster": {
            "cluster_id": cluster_id,
            "members": cluster_members,
        },
        "reasons": reasons,
        "registry": finding,
    }


def build_report(fixture: Mapping[str, Any], *, small_n_threshold: int = SMALL_N_DEFAULT) -> Dict[str, Any]:
    """Build the complete deterministic fixture report."""

    if not isinstance(fixture, Mapping):
        raise CalibrationError("fixture root must be an object")
    records = fixture.get("gold_records", [])
    sources = fixture.get("sources", [])
    candidates = fixture.get("admission_candidates", [])
    entries = fixture.get("registry_entries", [])
    if not isinstance(sources, list) or not isinstance(candidates, list):
        raise CalibrationError("sources and admission_candidates must be lists")
    combined = list(sources) + list(candidates)
    independence = cluster_independence(combined)
    registry = FixtureStatusRegistry(entries)
    decisions = [
        admission_decision(
            candidate,
            registry=registry,
            existing_sources=sources,
            independence=independence,
        )
        for candidate in sorted(candidates, key=lambda item: item.get("id", ""))
    ]
    digest = hashlib.sha256(canonical_json(fixture).encode("utf-8")).hexdigest()
    return {
        "admission": {
            "counts": {
                decision: sum(1 for row in decisions if row["decision"] == decision)
                for decision in ("allow", "review", "reject")
            },
            "decisions": decisions,
            "policy_effect": "advisory_only",
        },
        "benchmark_sha256": digest,
        "calibration": calibration_report(records, small_n_threshold=small_n_threshold),
        "independence": independence,
        "schema_version": SCHEMA_VERSION,
        "trust_policy_mutated": False,
    }


def load_fixture(path: Path) -> Mapping[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CalibrationError(f"cannot load fixture {path}: {exc}") from exc
    if not isinstance(value, Mapping):
        raise CalibrationError("fixture root must be a JSON object")
    return value


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Living Wiki ordinal calibration and source-admission evaluator"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    report = subparsers.add_parser("report", help="emit deterministic JSON for a fixture")
    report.add_argument("--input", required=True, type=Path, help="fixture JSON path")
    report.add_argument("--small-n", default=SMALL_N_DEFAULT, type=int)
    report.add_argument("--compact", action="store_true", help="emit single-line canonical JSON")
    canonical = subparsers.add_parser("canonicalize", help="canonicalize one identifier")
    canonical.add_argument("kind", choices=("doi", "url", "repository"))
    canonical.add_argument("value")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "canonicalize":
            functions = {
                "doi": canonicalize_doi,
                "url": canonicalize_url,
                "repository": canonicalize_repository,
            }
            payload = {"canonical": functions[args.kind](args.value), "kind": args.kind}
        else:
            payload = build_report(load_fixture(args.input), small_n_threshold=args.small_n)
        sys.stdout.write(canonical_json(payload, pretty=not getattr(args, "compact", False)))
        return 0
    except (CalibrationError, ValueError) as exc:
        sys.stderr.write(canonical_json({"error": str(exc)}, pretty=False) + "\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
