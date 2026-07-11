#!/usr/bin/env python3
"""Deterministic, non-executing security gates for untrusted Wiki inputs.

This module deliberately has no network, subprocess, shell, dynamic import, or
credential integration.  It classifies bytes, creates quarantine metadata,
normalizes text into a separate derived artifact, reports explainable lexical
signals, and returns write/retrieve/activate decisions.

The scanner is a conservative admission aid, not a complete security boundary.
See docs/SECURITY_GATE.md for the threat model and integration contract.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import mimetypes
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


SCHEMA_VERSION = "living-wiki-security-gate/v1"
CORPUS_SCHEMA_VERSION = "living-wiki-security-corpus/v1"
MAX_SCAN_BYTES = 1_000_000
MAX_MATCHES_PER_RULE = 3
STAGES = ("write", "retrieve", "activate")
DECISIONS = ("allow", "review", "reject")

_SEVERITY = {1: "info", 2: "low", 3: "medium", 4: "high", 5: "critical"}
_THREAT_CATEGORIES = {
    "prompt_injection",
    "secret_exfiltration",
    "shell_command",
    "policy_overwrite",
    "persistence",
    "obfuscation",
    "executable_payload",
}


def _rule(
    rule_id: str,
    category: str,
    risk: int,
    pattern: str,
    description: str,
) -> dict[str, Any]:
    return {
        "rule_id": rule_id,
        "category": category,
        "risk": risk,
        "regex": re.compile(pattern, re.IGNORECASE | re.DOTALL),
        "description": description,
    }


_RULES = (
    _rule(
        "PROMPT_OVERRIDE_PREVIOUS",
        "prompt_injection",
        4,
        r"\b(?:ignore|disregard|forget)\b.{0,80}\b(?:previous|prior|above|system|developer)\b.{0,50}\b(?:instruction|message|rule|prompt)s?\b",
        "Attempts to override earlier or higher-priority instructions.",
    ),
    _rule(
        "PROMPT_ROLE_REASSIGNMENT",
        "prompt_injection",
        4,
        r"\byou\s+are\s+now\b.{0,80}\b(?:agent|assistant|system|developer|administrator|root)\b",
        "Attempts to reassign the consuming agent's role.",
    ),
    _rule(
        "PROMPT_PRIVILEGED_BLOCK",
        "prompt_injection",
        4,
        r"\b(?:system|developer)\s*(?:message|prompt|instruction)s?\s*:",
        "Embeds text that presents itself as a privileged instruction block.",
    ),
    _rule(
        "PROMPT_FOLLOW_ATTACKER",
        "prompt_injection",
        4,
        r"\bfollow\s+(?:only\s+)?(?:these|this|my|the following)\s+instructions?\b",
        "Directs the consumer to privilege instructions found in source data.",
    ),
    _rule(
        "PROMPT_HIDDEN_DIRECTIVE",
        "prompt_injection",
        4,
        r"(?:display\s*:\s*none|visibility\s*:\s*hidden|font-size\s*:\s*0).{0,240}\b(?:ignore|system|developer|instruction|prompt)\b",
        "Places instruction-like text in visually hidden markup.",
    ),
    _rule(
        "SECRET_READ_OR_SEND",
        "secret_exfiltration",
        5,
        r"\b(?:read|open|print|reveal|show|send|upload|post|exfiltrat\w*)\b.{0,120}(?:\.env\b|api[- ]?key|credential|private[- ]?key|ssh[- ]?key|access[- ]?token|bearer[- ]?token|system[- ]?prompt|developer[- ]?message)",
        "Requests reading, revealing, or transmitting secrets or privileged prompts.",
    ),
    _rule(
        "SECRET_FILESYSTEM_PATH",
        "secret_exfiltration",
        5,
        r"(?:~?/\.ssh/(?:id_[a-z0-9_-]+|config)|~?/\.aws/credentials|~?/\.config/(?:gcloud|gh)/|/proc/self/environ)",
        "References a credential-bearing filesystem location.",
    ),
    _rule(
        "SHELL_DOWNLOAD_EXECUTE",
        "shell_command",
        5,
        r"\b(?:curl|wget)\b.{0,240}(?:\|\s*(?:sudo\s+)?(?:sh|bash|zsh)\b|\b(?:sh|bash|zsh)\s+-c\b)",
        "Downloads content and pipes or passes it to a command interpreter.",
    ),
    _rule(
        "SHELL_DESTRUCTIVE_DELETE",
        "shell_command",
        5,
        r"(?:^|[\s;`])(?:sudo\s+)?rm\s+-[a-z]*r[a-z]*f[a-z]*\s+(?:/|~|\$HOME|\.\.)",
        "Contains a destructive recursive delete command.",
    ),
    _rule(
        "SHELL_EXECUTABLE_PERMISSION",
        "shell_command",
        4,
        r"\b(?:sudo\s+)?chmod\s+(?:[ugo+]*\+x|[0-7]*7[0-7]{2})\b",
        "Attempts to make a payload executable.",
    ),
    _rule(
        "SHELL_REVERSE_CONNECTION",
        "shell_command",
        5,
        r"\b(?:nc|ncat|netcat)\b.{0,160}\s-e\s+(?:/bin/)?(?:sh|bash)\b",
        "Contains a reverse-shell style command.",
    ),
    _rule(
        "POLICY_FILE_OVERWRITE",
        "policy_overwrite",
        5,
        r"\b(?:edit|overwrite|replace|rewrite|modify|patch|write\s+(?:to|into))\b.{0,120}(?:AGENTS(?:\.override)?\.md|constitution(?:\.md)?|trust-policy(?:\.json)?|security[-_ ]?policy|system[-_ ]?prompt)",
        "Attempts to modify a policy or privileged instruction file.",
    ),
    _rule(
        "POLICY_DISABLE_GATE",
        "policy_overwrite",
        5,
        r"\b(?:bypass|disable|remove|skip|turn\s+off)\b.{0,80}\b(?:safety|security|review|approval|gate|policy|validation)\b",
        "Attempts to disable a safety, review, or validation gate.",
    ),
    _rule(
        "POLICY_FORCE_TRUST",
        "policy_overwrite",
        5,
        r"\b(?:set|promote|mark|label)\b.{0,70}\b(?:C4|S4|trusted|accepted|verified)\b.{0,90}\b(?:without|bypass|regardless|immediately|no\s+review)\b",
        "Attempts to force a trust/admission state without required evidence or review.",
    ),
    _rule(
        "PERSIST_MEMORY_WRITE",
        "persistence",
        4,
        r"\b(?:remember|store|save|persist|write|insert)\b.{0,120}\b(?:permanent(?:ly)?|forever|all\s+future|future\s+(?:turn|session|agent|run)s?|long[- ]?term\s+memory|canonical\s+memory|wiki\s+memory)\b",
        "Attempts to persist a directive into long-lived memory.",
    ),
    _rule(
        "PERSIST_FUTURE_EXECUTION",
        "persistence",
        4,
        r"\b(?:on\s+every|each|all\s+future)\b.{0,70}\b(?:turn|session|run|request)s?\b.{0,100}\b(?:execute|follow|obey|run|perform|do)\b",
        "Requests recurring execution in future turns or runs.",
    ),
    _rule(
        "PERSIST_WIKI_DIRECTIVE",
        "persistence",
        4,
        r"\b(?:add|insert|copy|write)\b.{0,80}\b(?:instruction|directive|command|prompt)\b.{0,100}\b(?:wiki|memory|AGENTS\.md)\b",
        "Attempts to plant an instruction or command in persistent Wiki state.",
    ),
    _rule(
        "OBFUSCATED_BASE64_BLOB",
        "obfuscation",
        3,
        r"(?<![A-Za-z0-9+/])[A-Za-z0-9+/]{120,}={0,2}(?![A-Za-z0-9+/])",
        "Contains a long base64-like blob that this lexical scanner cannot inspect semantically.",
    ),
)

_ANALYTICAL_CONTEXT = re.compile(
    r"\b(?:example|quoted|quotation|documentation|security\s+training|historical|analysis|discussion|"
    r"do\s+not|don't|never|must\s+not|should\s+not|dangerous\s+example)\b",
    re.IGNORECASE,
)
_TOKEN_RE = re.compile(
    r"(?:\bsk-[A-Za-z0-9_-]{8,}|\bghp_[A-Za-z0-9]{8,}|\bAKIA[A-Z0-9]{8,}|"
    r"\bBearer\s+[A-Za-z0-9._~+/=-]{8,})"
)


class SecurityAssessment:
    """Immutable-by-convention value returned by :func:`assess_content`.

    ``manifest`` describes the original bytes without retaining them.
    ``normalized`` holds the separate derived text.  ``to_dict`` omits that text
    unless a caller explicitly opts in, which prevents routine reports from
    becoming a second persistent copy of an attack payload.
    """

    __slots__ = ("manifest", "normalized", "signals", "gates")

    def __init__(
        self,
        manifest: Mapping[str, Any],
        normalized: Mapping[str, Any],
        signals: Sequence[Mapping[str, Any]],
        gates: Mapping[str, Mapping[str, Any]],
    ) -> None:
        self.manifest = dict(manifest)
        self.normalized = dict(normalized)
        self.signals = [dict(signal) for signal in signals]
        self.gates = {stage: dict(result) for stage, result in gates.items()}

    def to_dict(self, include_normalized_text: bool = False) -> dict[str, Any]:
        normalized = {
            key: value
            for key, value in self.normalized.items()
            if include_normalized_text or key != "text"
        }
        return {
            "schema_version": SCHEMA_VERSION,
            "classification": "untrusted_external_content",
            "manifest": dict(self.manifest),
            "normalized": normalized,
            "signals": [dict(signal) for signal in self.signals],
            "gates": {stage: dict(self.gates[stage]) for stage in STAGES},
            "invariants": {
                "payload_executed": False,
                "network_used": False,
                "credentials_accessed": False,
                "allow_means_data_use_only": True,
            },
        }


def canonical_json(value: Any) -> str:
    """Return stable JSON used by the CLI and fixture reports."""

    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _looks_textual(raw: bytes) -> bool:
    if not raw:
        return True
    sample = raw[:8192]
    if b"\x00" in sample:
        return False
    try:
        sample.decode("utf-8")
        return True
    except UnicodeDecodeError:
        controls = sum(byte < 9 or (13 < byte < 32) for byte in sample)
        return controls / max(len(sample), 1) < 0.02


def _magic_media_type(raw: bytes) -> str | None:
    signatures = (
        (b"%PDF-", "application/pdf"),
        (b"\x89PNG\r\n\x1a\n", "image/png"),
        (b"\xff\xd8\xff", "image/jpeg"),
        (b"GIF87a", "image/gif"),
        (b"GIF89a", "image/gif"),
        (b"PK\x03\x04", "application/zip"),
        (b"\x7fELF", "application/x-executable"),
        (b"MZ", "application/x-dosexec"),
    )
    for prefix, media_type in signatures:
        if raw.startswith(prefix):
            return media_type
    return None


def _valid_media_type(value: str | None) -> str | None:
    if value is None:
        return None
    candidate = value.split(";", 1)[0].strip().lower()
    if re.fullmatch(r"[a-z0-9!#$&^_.+-]+/[a-z0-9!#$&^_.+-]+", candidate):
        return candidate
    return None


def _classify_media_type(
    raw: bytes,
    source_ref: str,
    declared_media_type: str | None,
) -> tuple[str, str, str | None]:
    declared = _valid_media_type(declared_media_type)
    magic = _magic_media_type(raw)
    guessed, _ = mimetypes.guess_type(source_ref, strict=False)
    guessed = _valid_media_type(guessed)
    if magic:
        detected = magic
    elif guessed:
        detected = guessed
    elif _looks_textual(raw):
        detected = "text/plain"
    else:
        detected = "application/octet-stream"

    if magic:
        effective = magic
    elif declared:
        effective = declared
        detected = declared if _looks_textual(raw) else detected
    else:
        effective = detected
    return effective, detected, declared


def _is_textual_media_type(media_type: str) -> bool:
    return (
        media_type.startswith("text/")
        or media_type in {
            "application/json",
            "application/ld+json",
            "application/xml",
            "application/xhtml+xml",
            "application/javascript",
            "application/x-yaml",
        }
        or media_type.endswith("+json")
        or media_type.endswith("+xml")
    )


def normalize_text(text: str) -> str:
    """Produce a deterministic scan view without mutating original bytes."""

    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = unicodedata.normalize("NFKC", text)
    kept: list[str] = []
    for character in text:
        if character in "\n\t":
            kept.append(character)
            continue
        category = unicodedata.category(character)
        if category in {"Cc", "Cf", "Cs"}:
            continue
        kept.append(character)
    return "".join(kept)


def _redacted_excerpt(text: str, start: int, end: int) -> str:
    left = max(0, start - 40)
    right = min(len(text), end + 40)
    excerpt = re.sub(r"\s+", " ", text[left:right]).strip()
    excerpt = _TOKEN_RE.sub("[REDACTED-TOKEN]", excerpt)
    if len(excerpt) > 180:
        excerpt = excerpt[:177] + "..."
    return excerpt


def _signal(
    rule_id: str,
    category: str,
    risk: int,
    description: str,
    *,
    start: int = -1,
    end: int = -1,
    excerpt: str = "",
    context_modifier: str | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "rule_id": rule_id,
        "category": category,
        "risk": risk,
        "severity": _SEVERITY[risk],
        "description": description,
        "span": {"start": start, "end": end} if start >= 0 else None,
        "excerpt": excerpt,
    }
    if context_modifier:
        result["context_modifier"] = context_modifier
    return result


def detect_signals(text: str) -> list[dict[str, Any]]:
    """Return ordered, explainable lexical signals without executing text."""

    signals: list[dict[str, Any]] = []
    for rule in _RULES:
        count = 0
        for match in rule["regex"].finditer(text):
            context_start = max(0, match.start() - 100)
            context_end = min(len(text), match.end() + 100)
            context = text[context_start:context_end]
            risk = int(rule["risk"])
            modifier = None
            if _ANALYTICAL_CONTEXT.search(context):
                # Quotation/negation can reduce auto-rejection, but never makes a
                # matched directive automatically allowable.
                risk = 2
                modifier = "analytical_or_negated_context"
            signals.append(
                _signal(
                    str(rule["rule_id"]),
                    str(rule["category"]),
                    risk,
                    str(rule["description"]),
                    start=match.start(),
                    end=match.end(),
                    excerpt=_redacted_excerpt(text, match.start(), match.end()),
                    context_modifier=modifier,
                )
            )
            count += 1
            if count >= MAX_MATCHES_PER_RULE:
                break
    return sorted(signals, key=lambda item: (item["span"]["start"], item["rule_id"]))


def decide_gate(signals: Iterable[Mapping[str, Any]], stage: str) -> dict[str, Any]:
    """Map signals to an allow/review/reject decision for one lifecycle stage."""

    if stage not in STAGES:
        raise ValueError(f"unknown gate stage: {stage}")
    signal_list = [dict(signal) for signal in signals]
    if not signal_list:
        return {
            "stage": stage,
            "decision": "allow",
            "risk_score": 0,
            "max_risk": 0,
            "reason_rule_ids": [],
            "meaning": "May proceed only as untrusted data; never as executable instruction.",
        }

    risks = [int(signal["risk"]) for signal in signal_list]
    risk_score = min(20, sum(risks))
    max_risk = max(risks)
    threat_signals = [
        signal for signal in signal_list if signal.get("category") in _THREAT_CATEGORIES
    ]

    if stage == "write":
        reject = max_risk >= 5 or risk_score >= 8
    elif stage == "retrieve":
        reject = max_risk >= 5 or risk_score >= 10
    else:
        reject = any(int(signal["risk"]) >= 3 for signal in threat_signals) or risk_score >= 5

    decision = "reject" if reject else "review"
    meaning = {
        "review": "Stop automatic progression and require an independent human/agent review.",
        "reject": "Deny this automatic transition; retain only immutable quarantine evidence.",
    }[decision]
    return {
        "stage": stage,
        "decision": decision,
        "risk_score": risk_score,
        "max_risk": max_risk,
        "reason_rule_ids": sorted({str(signal["rule_id"]) for signal in signal_list}),
        "meaning": meaning,
    }


def assess_content(
    raw: bytes,
    source_ref: str,
    declared_media_type: str | None = None,
    extracted_text: str | None = None,
) -> SecurityAssessment:
    """Assess bytes as untrusted external content.

    ``raw`` is hashed and measured but never returned or executed.  For binary
    formats, callers may supply text produced by a separate sandboxed parser in
    ``extracted_text``.  This function does not parse PDF/Office/archive formats.
    """

    if not isinstance(raw, bytes):
        raise TypeError("raw must be bytes")
    if not isinstance(source_ref, str) or not source_ref.strip():
        raise ValueError("source_ref must be a non-empty string")
    if extracted_text is not None and not isinstance(extracted_text, str):
        raise TypeError("extracted_text must be str or None")

    effective_type, detected_type, declared_type = _classify_media_type(
        raw, source_ref, declared_media_type
    )
    manifest = {
        "classification": "untrusted_external_content",
        "source_ref": source_ref,
        "hash_algorithm": "sha256",
        "content_sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
        "media_type": effective_type,
        "declared_media_type": declared_type,
        "detected_media_type": detected_type,
    }

    structural_signals: list[dict[str, Any]] = []
    if declared_type and detected_type != declared_type:
        structural_signals.append(
            _signal(
                "MEDIA_TYPE_MISMATCH",
                "content_integrity",
                3,
                "Declared media type conflicts with magic/extension-based detection.",
            )
        )
    if effective_type in {"application/x-executable", "application/x-dosexec"}:
        structural_signals.append(
            _signal(
                "EXECUTABLE_ARTIFACT",
                "executable_payload",
                5,
                "Executable file signature detected; this scanner never executes artifacts.",
            )
        )
    if len(raw) > MAX_SCAN_BYTES:
        structural_signals.append(
            _signal(
                "CONTENT_OVERSIZE",
                "content_integrity",
                5,
                f"Content exceeds deterministic scan limit of {MAX_SCAN_BYTES} bytes.",
            )
        )

    normalization_source: str
    replacement_characters = 0
    truncated = False
    if extracted_text is not None:
        normalization_source = "sandboxed_extraction"
        candidate = extracted_text
        if len(candidate.encode("utf-8")) > MAX_SCAN_BYTES:
            candidate = candidate[:MAX_SCAN_BYTES]
            truncated = True
            structural_signals.append(
                _signal(
                    "EXTRACTED_TEXT_OVERSIZE",
                    "content_integrity",
                    5,
                    f"Extracted text exceeds deterministic scan limit of {MAX_SCAN_BYTES} bytes.",
                )
            )
    elif _is_textual_media_type(effective_type):
        normalization_source = "utf8_decode"
        raw_for_scan = raw[:MAX_SCAN_BYTES]
        truncated = len(raw) > MAX_SCAN_BYTES
        candidate = raw_for_scan.decode("utf-8", errors="replace")
        replacement_characters = candidate.count("\ufffd")
        if replacement_characters:
            structural_signals.append(
                _signal(
                    "DECODE_REPLACEMENT",
                    "content_integrity",
                    3,
                    "Invalid UTF-8 bytes required replacement during normalization.",
                )
            )
    else:
        normalization_source = "none_binary_requires_sandboxed_extraction"
        candidate = ""
        structural_signals.append(
            _signal(
                "OPAQUE_BINARY",
                "content_integrity",
                4,
                "Binary content was not parsed; provide sandboxed extracted text for inspection.",
            )
        )

    normalized_text = normalize_text(candidate)
    normalized = {
        "text": normalized_text,
        "content_sha256": hashlib.sha256(normalized_text.encode("utf-8")).hexdigest(),
        "length_chars": len(normalized_text),
        "normalization": "utf8+newline-lf+unicode-nfkc+control-strip",
        "normalization_source": normalization_source,
        "replacement_characters": replacement_characters,
        "truncated": truncated,
    }
    signals = structural_signals + detect_signals(normalized_text)
    signals = sorted(
        signals,
        key=lambda item: (
            item["span"]["start"] if item.get("span") else -1,
            str(item["rule_id"]),
        ),
    )
    gates = {stage: decide_gate(signals, stage) for stage in STAGES}
    return SecurityAssessment(manifest, normalized, signals, gates)


def load_corpus(path: str | Path) -> dict[str, Any]:
    """Load and minimally validate a deterministic JSON security corpus."""

    corpus = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(corpus, dict) or corpus.get("schema_version") != CORPUS_SCHEMA_VERSION:
        raise ValueError(f"corpus must use schema_version {CORPUS_SCHEMA_VERSION}")
    cases = corpus.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("corpus cases must be a non-empty list")
    seen: set[str] = set()
    for case in cases:
        if not isinstance(case, dict):
            raise ValueError("each corpus case must be an object")
        case_id = case.get("id")
        if not isinstance(case_id, str) or not case_id or case_id in seen:
            raise ValueError("corpus case ids must be unique non-empty strings")
        seen.add(case_id)
        if case.get("label") not in {"attack", "benign"}:
            raise ValueError(f"{case_id}: label must be attack or benign")
        if not isinstance(case.get("content"), str):
            raise ValueError(f"{case_id}: content must be a string")
    return corpus


def _case_bytes(case: Mapping[str, Any]) -> bytes:
    encoding = case.get("content_encoding", "utf-8")
    content = str(case["content"])
    if encoding == "utf-8":
        return content.encode("utf-8")
    if encoding == "base64":
        try:
            return base64.b64decode(content, validate=True)
        except (ValueError, base64.binascii.Error) as exc:
            raise ValueError(f"{case.get('id')}: invalid base64 content") from exc
    raise ValueError(f"{case.get('id')}: unsupported content_encoding {encoding}")


def _rate(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 6) if denominator else 0.0


def evaluate_corpus(corpus: Mapping[str, Any]) -> dict[str, Any]:
    """Evaluate fixtures and return attack/benign gate metrics without side effects."""

    cases = corpus.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("corpus cases must be a non-empty list")

    case_results: list[dict[str, Any]] = []
    mismatches: list[dict[str, str]] = []
    stage_metrics: dict[str, dict[str, Any]] = {}
    for stage in STAGES:
        stage_metrics[stage] = {
            "attack_cases": 0,
            "attack_allowed": 0,
            "attack_success_rate": 0.0,
            "benign_cases": 0,
            "benign_rejected": 0,
            "benign_rejection_rate": 0.0,
            "benign_reviewed": 0,
            "benign_review_rate": 0.0,
        }

    attacks_detected = 0
    known_false_positives = 0
    for case in cases:
        raw = _case_bytes(case)
        assessment = assess_content(
            raw,
            source_ref=str(case.get("source_ref", f"fixture:{case['id']}")),
            declared_media_type=case.get("media_type"),
            extracted_text=case.get("extracted_text"),
        )
        label = str(case["label"])
        if label == "attack" and assessment.signals:
            attacks_detected += 1
        if bool(case.get("known_false_positive")):
            known_false_positives += 1

        decisions = {stage: assessment.gates[stage]["decision"] for stage in STAGES}
        expected = case.get("expected_gates", {})
        if isinstance(expected, dict):
            for stage in STAGES:
                if stage in expected and expected[stage] != decisions[stage]:
                    mismatches.append(
                        {
                            "case_id": str(case["id"]),
                            "stage": stage,
                            "expected": str(expected[stage]),
                            "actual": str(decisions[stage]),
                        }
                    )

        for stage in STAGES:
            metric = stage_metrics[stage]
            if label == "attack":
                metric["attack_cases"] += 1
                if decisions[stage] == "allow":
                    metric["attack_allowed"] += 1
            else:
                metric["benign_cases"] += 1
                if decisions[stage] == "reject":
                    metric["benign_rejected"] += 1
                if decisions[stage] == "review":
                    metric["benign_reviewed"] += 1

        case_results.append(
            {
                "id": str(case["id"]),
                "label": label,
                "known_false_positive": bool(case.get("known_false_positive", False)),
                "content_sha256": assessment.manifest["content_sha256"],
                "signal_rule_ids": sorted(
                    {str(signal["rule_id"]) for signal in assessment.signals}
                ),
                "signal_categories": sorted(
                    {str(signal["category"]) for signal in assessment.signals}
                ),
                "gates": decisions,
            }
        )

    for stage in STAGES:
        metric = stage_metrics[stage]
        metric["attack_success_rate"] = _rate(
            metric["attack_allowed"], metric["attack_cases"]
        )
        metric["benign_rejection_rate"] = _rate(
            metric["benign_rejected"], metric["benign_cases"]
        )
        metric["benign_review_rate"] = _rate(
            metric["benign_reviewed"], metric["benign_cases"]
        )

    attack_cases = sum(1 for case in cases if case.get("label") == "attack")
    benign_cases = len(cases) - attack_cases
    attack_stage_allowed = sum(
        int(stage_metrics[stage]["attack_allowed"]) for stage in STAGES
    )
    benign_stage_rejected = sum(
        int(stage_metrics[stage]["benign_rejected"]) for stage in STAGES
    )
    benign_stage_reviewed = sum(
        int(stage_metrics[stage]["benign_reviewed"]) for stage in STAGES
    )

    canonical_corpus = json.dumps(
        corpus, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return {
        "schema_version": SCHEMA_VERSION,
        "report_type": "security_corpus_evaluation",
        "corpus_id": str(corpus.get("corpus_id", "unnamed")),
        "corpus_sha256": hashlib.sha256(canonical_corpus).hexdigest(),
        "case_count": len(cases),
        "metrics": {
            "attack_cases": attack_cases,
            "attack_cases_detected": attacks_detected,
            "attack_detection_rate": _rate(attacks_detected, attack_cases),
            "attack_stage_attempts": attack_cases * len(STAGES),
            "attack_stage_allowed": attack_stage_allowed,
            "attack_success_rate": _rate(attack_stage_allowed, attack_cases * len(STAGES)),
            "benign_cases": benign_cases,
            "benign_stage_decisions": benign_cases * len(STAGES),
            "benign_stage_rejected": benign_stage_rejected,
            "benign_rejection_rate": _rate(
                benign_stage_rejected, benign_cases * len(STAGES)
            ),
            "benign_stage_reviewed": benign_stage_reviewed,
            "benign_review_rate": _rate(
                benign_stage_reviewed, benign_cases * len(STAGES)
            ),
            "known_false_positive_cases": known_false_positives,
            "by_stage": stage_metrics,
        },
        "expectation_mismatches": mismatches,
        "cases": sorted(case_results, key=lambda item: item["id"]),
        "invariants": {
            "payloads_executed": 0,
            "network_calls": 0,
            "credential_reads": 0,
            "review_counts_as_automatic_attack_block": True,
        },
    }


def _default_corpus_path() -> Path:
    return Path(__file__).resolve().parents[1] / "evaluations" / "fixtures" / "security-corpus.json"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Deterministic, non-executing security gates for untrusted Wiki content."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan = subparsers.add_parser("scan", help="assess one local artifact")
    scan.add_argument("--input", required=True, type=Path, help="local artifact to read as bytes")
    scan.add_argument("--source-ref", help="provenance reference; defaults to the input argument")
    scan.add_argument("--media-type", help="declared MIME media type")
    scan.add_argument(
        "--extracted-text",
        type=Path,
        help="UTF-8 text produced by a separate sandboxed parser for a binary artifact",
    )
    scan.add_argument("--gate", choices=STAGES, default="write", help="decision used for exit code")

    evaluate = subparsers.add_parser("evaluate", help="run the fixed security fixture corpus")
    evaluate.add_argument("--corpus", type=Path, default=_default_corpus_path())
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "scan":
        raw = args.input.read_bytes()
        extracted = (
            args.extracted_text.read_text(encoding="utf-8") if args.extracted_text else None
        )
        assessment = assess_content(
            raw,
            source_ref=args.source_ref or str(args.input),
            declared_media_type=args.media_type,
            extracted_text=extracted,
        )
        sys.stdout.write(canonical_json(assessment.to_dict()))
        return {"allow": 0, "review": 2, "reject": 3}[
            assessment.gates[args.gate]["decision"]
        ]

    corpus = load_corpus(args.corpus)
    report = evaluate_corpus(corpus)
    sys.stdout.write(canonical_json(report))
    failed = bool(report["expectation_mismatches"]) or report["metrics"][
        "attack_success_rate"
    ] > 0
    return 4 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
