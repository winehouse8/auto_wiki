#!/usr/bin/env python3
"""Deterministic, read-only release gate for the Living Wiki v4 harness.

The module deliberately does not import ``tools/wiki.py``.  Structural and
OKF validator findings are injected by the caller, while calibration,
security, runtime scenarios, and the receipt hash chain are evaluated from
plain data.  A passing report means that the bounded local harness and its
fixed regression fixtures passed; it is never a production or security
certification.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

try:  # Package import when used as ``tools.release_gate``.
    from tools import calibration, runtime, security_gate
except ImportError:  # Direct execution as ``python3 tools/release_gate.py``.
    import calibration  # type: ignore[no-redef]
    import runtime  # type: ignore[no-redef]
    import security_gate  # type: ignore[no-redef]


SCHEMA_VERSION = "living-wiki-v4-release-gate/v1"
RELEASE_ID = "living-wiki-v4"
RUNTIME_EVALUATION_TIME = "2026-07-12T00:00:00+00:00"
ZERO_HASH = "0" * 64
CALIBRATION_FIXTURE_SCHEMA = "living-wiki-calibration-fixture/v1"
SECURITY_CORPUS_SCHEMA = "living-wiki-security-corpus/v1"
RUNTIME_FIXTURE_SCHEMA = 1
# These hashes pin the RFC-69828EB38078 release fixtures.  Evolving a fixture
# requires an intentional baseline update rather than silently making a gate
# easier.  The component APIs accept an override for isolated evaluator tests;
# evaluate_repository() always supplies these release baselines.
PINNED_CALIBRATION_SHA256 = "7d3674bb803f1f23bf67c1191d3b017f3b22df1b5a2d26fe6eedda9b3726782d"
PINNED_SECURITY_SHA256 = "38c337f61795f67ee7b0893b3bb81f19ebab7368136a1657022882ae56f30eea"
PINNED_RUNTIME_SHA256 = "e5e6da8aa314d89f6e8e6f65351d105773f827b1c24dfb957c3eb5c5dd02521a"
PINNED_ROLLBACK_COMMIT = "d18213a78376c0543a0aa590a3db7fcf7022c187"


class ReleaseGateError(ValueError):
    """Raised when release-gate input cannot be evaluated safely."""


def canonical_json(value: Any, *, pretty: bool = False) -> str:
    """Serialize without timestamps, host paths, locale, or key-order drift."""

    if pretty:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value: Any) -> str:
    text = value if isinstance(value, str) else canonical_json(value)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _finding_text(value: Any) -> str:
    return value if isinstance(value, str) else canonical_json(value)


def normalize_findings(findings: Any) -> dict[str, Any]:
    """Normalize wiki validator output while preserving not-evaluated state.

    Accepted values are ``{"errors": ..., "warnings": ..., "counts": ...}``,
    the tuple returned by ``validation_findings()``, the two-item tuple
    returned by an OKF validator, or a list interpreted as errors.  ``None``
    never means success: it means the caller did not run the validator.
    """

    if findings is None:
        return {
            "evaluated": False,
            "errors": ["validator_not_evaluated"],
            "warnings": [],
            "counts": {},
        }
    evaluated = True
    counts: Mapping[str, Any] = {}
    if isinstance(findings, Mapping):
        errors = findings.get("errors", [])
        warnings = findings.get("warnings", [])
        counts_value = findings.get("counts", {})
        evaluated = findings.get("evaluated", True) is True
        if isinstance(counts_value, Mapping):
            counts = counts_value
    elif isinstance(findings, tuple):
        if len(findings) not in (2, 3):
            raise ReleaseGateError("finding tuple must contain errors, warnings, and optional counts")
        errors, warnings = findings[0], findings[1]
        if len(findings) == 3 and isinstance(findings[2], Mapping):
            counts = findings[2]
    elif isinstance(findings, Sequence) and not isinstance(findings, (str, bytes)):
        errors, warnings = findings, []
    else:
        raise ReleaseGateError("findings must be a mapping, tuple, list, or null")
    if not isinstance(errors, Sequence) or isinstance(errors, (str, bytes)):
        raise ReleaseGateError("finding errors must be a list")
    if not isinstance(warnings, Sequence) or isinstance(warnings, (str, bytes)):
        raise ReleaseGateError("finding warnings must be a list")
    normalized_errors = sorted({_finding_text(item) for item in errors})
    if not evaluated and "validator_not_evaluated" not in normalized_errors:
        normalized_errors.append("validator_not_evaluated")
        normalized_errors.sort()
    return {
        "evaluated": evaluated,
        "errors": normalized_errors,
        "warnings": sorted({_finding_text(item) for item in warnings}),
        "counts": {str(key): counts[key] for key in sorted(counts)},
    }


def evaluate_findings(name: str, findings: Any) -> dict[str, Any]:
    normalized = normalize_findings(findings)
    return {
        "name": name,
        "passed": normalized["evaluated"] and not normalized["errors"],
        **normalized,
    }


def evaluate_calibration_fixture(
    fixture: Mapping[str, Any], *, expected_benchmark_sha256: str | None = None
) -> dict[str, Any]:
    """Evaluate calibration twice and classify it as pilot regression only."""

    errors: list[str] = []
    warnings: list[str] = []
    try:
        first = calibration.build_report(fixture)
        second = calibration.build_report(fixture)
    except (calibration.CalibrationError, ValueError, TypeError, KeyError) as exc:
        return {
            "name": "calibration",
            "passed": False,
            "status": "pilot_regression_only",
            "production_calibration": False,
            "errors": [f"evaluation_failed:{type(exc).__name__}:{exc}"],
            "warnings": [],
            "summary": {},
        }

    deterministic = canonical_json(first) == canonical_json(second)
    calibration_result = first.get("calibration", {})
    coverage = calibration_result.get("coverage", {})
    interpretation = calibration_result.get("interpretation", {})
    admission = first.get("admission", {})
    total = coverage.get("total_records")
    resolved = coverage.get("resolved_gold_records")
    disputed = coverage.get("disputed_records")
    abstained = coverage.get("abstained_resolved_records")
    scorable = coverage.get("scorable_records")

    if not deterministic:
        errors.append("report_not_deterministic")
    if fixture.get("schema_version") != CALIBRATION_FIXTURE_SCHEMA:
        errors.append("unexpected_calibration_fixture_schema")
    if expected_benchmark_sha256 is not None and first.get("benchmark_sha256") != expected_benchmark_sha256:
        errors.append("calibration_fixture_hash_drift")
    if first.get("trust_policy_mutated") is not False:
        errors.append("trust_policy_mutation_not_false")
    if interpretation.get("c_levels_are_probabilities") is not False:
        errors.append("ordinal_levels_misrepresented_as_probabilities")
    if admission.get("policy_effect") != "advisory_only":
        errors.append("admission_policy_effect_not_advisory")
    integer_counts = (total, resolved, disputed, abstained, scorable)
    if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in integer_counts):
        errors.append("invalid_coverage_counts")
    else:
        if total < 1 or resolved < 1 or scorable < 1:
            errors.append("calibration_fixture_has_no_scorable_records")
        if resolved + disputed != total:
            errors.append("resolved_and_disputed_do_not_cover_fixture")
        if scorable + abstained != resolved:
            errors.append("scorable_and_abstained_do_not_cover_resolved_records")
        if total < 100:
            warnings.append("pilot_fixture_below_100_record_empirical_calibration_target")

    by_level = calibration_result.get("by_level", {})
    missing_levels = sorted(set(calibration.CLAIM_LEVELS) - set(by_level)) if isinstance(by_level, Mapping) else list(calibration.CLAIM_LEVELS)
    if missing_levels:
        errors.append("missing_ordinal_levels:" + ",".join(missing_levels))
    small_n_cells = 0
    if isinstance(by_level, Mapping):
        small_n_cells += sum(1 for value in by_level.values() if isinstance(value, Mapping) and value.get("small_n") is True)
    matrix = calibration_result.get("p_correct_given_level_domain", [])
    if isinstance(matrix, list):
        small_n_cells += sum(1 for value in matrix if isinstance(value, Mapping) and value.get("small_n") is True)

    overall = calibration_result.get("overall", {})
    return {
        "name": "calibration",
        "passed": not errors,
        "status": "pilot_regression_only",
        "production_calibration": False,
        "errors": sorted(errors),
        "warnings": sorted(warnings),
        "summary": {
            "benchmark_sha256": first.get("benchmark_sha256"),
            "report_sha256": digest(first),
            "deterministic": deterministic,
            "total_records": total,
            "resolved_gold_records": resolved,
            "disputed_records": disputed,
            "abstained_resolved_records": abstained,
            "scorable_records": scorable,
            "observed_overall_p_correct": overall.get("p_correct") if isinstance(overall, Mapping) else None,
            "small_n_cells": small_n_cells,
            "admission_counts": admission.get("counts", {}),
            "ordinal_scale_preserved": interpretation.get("c_levels_are_probabilities") is False,
            "trust_policy_mutated": first.get("trust_policy_mutated"),
        },
    }


def evaluate_security_corpus(
    corpus: Mapping[str, Any], *, expected_corpus_sha256: str | None = None
) -> dict[str, Any]:
    """Run the fixed poisoning corpus twice and enforce zero-success gates."""

    errors: list[str] = []
    warnings: list[str] = []
    try:
        first = security_gate.evaluate_corpus(corpus)
        second = security_gate.evaluate_corpus(corpus)
    except (ValueError, TypeError, KeyError) as exc:
        return {
            "name": "security",
            "passed": False,
            "status": "fixed_corpus_regression_only",
            "production_security_certified": False,
            "errors": [f"evaluation_failed:{type(exc).__name__}:{exc}"],
            "warnings": [],
            "summary": {},
        }
    deterministic = canonical_json(first) == canonical_json(second)
    metrics = first.get("metrics", {})
    invariants = first.get("invariants", {})
    if not deterministic:
        errors.append("report_not_deterministic")
    if corpus.get("schema_version") != SECURITY_CORPUS_SCHEMA:
        errors.append("unexpected_security_corpus_schema")
    if expected_corpus_sha256 is not None and first.get("corpus_sha256") != expected_corpus_sha256:
        errors.append("security_corpus_hash_drift")
    if first.get("expectation_mismatches"):
        errors.append("fixture_expectation_mismatch")
    if metrics.get("attack_cases", 0) < 1 or metrics.get("benign_cases", 0) < 1:
        errors.append("corpus_requires_attack_and_benign_controls")
    if metrics.get("attack_detection_rate") != 1.0:
        errors.append("attack_detection_rate_below_one")
    if metrics.get("attack_success_rate") != 0.0:
        errors.append("attack_success_rate_nonzero")
    if metrics.get("benign_rejection_rate") != 0.0:
        errors.append("benign_rejection_rate_nonzero")
    for field in ("payloads_executed", "network_calls", "credential_reads"):
        if invariants.get(field) != 0:
            errors.append(f"security_invariant_nonzero:{field}")
    if metrics.get("benign_review_rate", 0) > 0:
        warnings.append("benign_review_rate_nonzero_operator_cost")
    warnings.append("lexical_fixed_corpus_is_not_a_production_security_boundary")
    return {
        "name": "security",
        "passed": not errors,
        "status": "fixed_corpus_regression_only",
        "production_security_certified": False,
        "errors": sorted(errors),
        "warnings": sorted(warnings),
        "summary": {
            "corpus_id": first.get("corpus_id"),
            "corpus_sha256": first.get("corpus_sha256"),
            "report_sha256": digest(first),
            "deterministic": deterministic,
            "case_count": first.get("case_count"),
            "attack_cases": metrics.get("attack_cases"),
            "attack_detection_rate": metrics.get("attack_detection_rate"),
            "attack_success_rate": metrics.get("attack_success_rate"),
            "benign_cases": metrics.get("benign_cases"),
            "benign_rejection_rate": metrics.get("benign_rejection_rate"),
            "benign_review_rate": metrics.get("benign_review_rate"),
            "known_false_positive_cases": metrics.get("known_false_positive_cases"),
            "payloads_executed": invariants.get("payloads_executed"),
            "network_calls": invariants.get("network_calls"),
            "credential_reads": invariants.get("credential_reads"),
        },
    }


def verify_receipt_chain(receipts: Sequence[Mapping[str, Any]]) -> list[str]:
    """Verify runtime-compatible receipt hashes without reading or writing files."""

    errors: list[str] = []
    previous_hash = ZERO_HASH
    for number, receipt in enumerate(receipts, 1):
        if not isinstance(receipt, Mapping):
            errors.append(f"line {number}: receipt is not an object")
            continue
        if receipt.get("prev_receipt_hash") != previous_hash:
            errors.append(f"line {number}: broken prev_receipt_hash")
        claimed = receipt.get("receipt_hash")
        unsigned = dict(receipt)
        unsigned.pop("receipt_hash", None)
        if claimed != digest(unsigned):
            errors.append(f"line {number}: invalid receipt_hash")
        previous_hash = str(claimed)
    return errors


def _runtime_budget_errors(plan: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    limits = plan.get("limits", {})
    allocated = plan.get("allocated", {})
    if not isinstance(limits, Mapping) or not isinstance(allocated, Mapping):
        return ["schedule_missing_limits_or_allocated"]
    for limit_name, allocated_name in (
        ("max_campaigns", "campaigns"),
        ("max_actions", "actions"),
        ("max_minutes", "minutes"),
        ("max_sources", "sources"),
    ):
        try:
            if int(allocated.get(allocated_name, 0)) > int(limits.get(limit_name, 0)):
                errors.append(f"schedule_exceeds:{limit_name}")
        except (TypeError, ValueError):
            errors.append(f"invalid_schedule_budget:{limit_name}")
    return errors


def evaluate_runtime_fixture(
    fixture: Mapping[str, Any],
    receipts: Sequence[Mapping[str, Any]],
    *,
    receipt_read_errors: Sequence[str] = (),
    expected_fixture_sha256: str | None = None,
) -> dict[str, Any]:
    """Evaluate collaboration parity, permissions, schedule, and receipts."""

    errors = list(receipt_read_errors)
    fixture_sha256 = digest(fixture)
    if fixture.get("schema_version") != RUNTIME_FIXTURE_SCHEMA:
        errors.append("unexpected_runtime_fixture_schema")
    if expected_fixture_sha256 is not None and fixture_sha256 != expected_fixture_sha256:
        errors.append("runtime_fixture_hash_drift")
    warnings: list[str] = []
    permission_mismatches: list[dict[str, Any]] = []
    collaboration_errors: list[str] = []
    actor_kinds_seen: set[str] = set()
    actors = fixture.get("actors", [])
    actor_kind_by_id = {
        item.get("id"): item.get("kind")
        for item in actors
        if isinstance(item, Mapping) and isinstance(item.get("id"), str)
    } if isinstance(actors, list) else {}
    try:
        records = fixture.get("collaboration_records", [])
        if not isinstance(records, list):
            raise runtime.RuntimeErrorBase("collaboration_records must be a list")
        schemas: list[set[str]] = []
        for number, item in enumerate(records, 1):
            if not isinstance(item, Mapping):
                collaboration_errors.append(f"record {number}: not an object")
                continue
            record = runtime.make_collaboration_record(
                actor_id=str(item.get("actor_id", "")),
                record_kind=str(item.get("record_kind", "")),
                intent=str(item.get("intent", "")),
                content=str(item.get("content", "")),
                targets=item.get("targets", []),
                stance=item.get("stance"),
                created_at=RUNTIME_EVALUATION_TIME,
            )
            runtime.validate_collaboration_record(record)
            schemas.append(set(record))
            kind = actor_kind_by_id.get(record["actor_id"])
            if isinstance(kind, str):
                actor_kinds_seen.add(kind)
        if not schemas or any(schema != schemas[0] for schema in schemas[1:]):
            collaboration_errors.append("collaboration_envelope_schema_mismatch")
    except (runtime.RuntimeErrorBase, TypeError, ValueError) as exc:
        collaboration_errors.append(f"collaboration_evaluation_failed:{type(exc).__name__}:{exc}")
    if not {"human", "agent"}.issubset(actor_kinds_seen):
        collaboration_errors.append("fixture_does_not_exercise_human_and_agent_actors")

    cases = fixture.get("permission_cases", [])
    if not isinstance(cases, list) or not cases:
        errors.append("permission_cases_missing")
    else:
        for item in cases:
            if not isinstance(item, Mapping):
                permission_mismatches.append({"action_type": "<invalid>", "expected": None, "actual": "invalid"})
                continue
            actual = runtime.decide_permission(str(item.get("action_type", ""))).get("decision")
            expected = item.get("expected")
            if actual != expected:
                permission_mismatches.append(
                    {"action_type": item.get("action_type"), "expected": expected, "actual": actual}
                )

    plan: dict[str, Any] = {}
    deterministic = False
    try:
        kwargs = {
            "campaigns": fixture.get("campaigns", []),
            "interests": fixture.get("interests", []),
            "receipts": receipts,
            "now": RUNTIME_EVALUATION_TIME,
        }
        plan = runtime.build_bounded_schedule(**kwargs)
        repeated = runtime.build_bounded_schedule(**kwargs)
        deterministic = canonical_json(plan) == canonical_json(repeated)
    except (runtime.RuntimeErrorBase, TypeError, ValueError, KeyError) as exc:
        errors.append(f"schedule_evaluation_failed:{type(exc).__name__}:{exc}")
    if not deterministic:
        errors.append("schedule_not_deterministic")
    errors.extend(_runtime_budget_errors(plan))
    if plan.get("side_effects_executed") is not False:
        errors.append("schedule_side_effects_executed_not_false")
    actions = plan.get("actions", []) if isinstance(plan.get("actions"), list) else []
    for item in actions:
        if not isinstance(item, Mapping):
            errors.append("schedule_action_not_object")
            continue
        if item.get("execution") != "planned_only" or item.get("external_work") is not True:
            errors.append(f"unbounded_or_internal_schedule_action:{item.get('id')}")

    chain_errors = verify_receipt_chain(receipts)
    errors.extend(chain_errors)
    if not receipts:
        errors.append("receipt_chain_has_no_release_evidence")
    unauthorized_side_effects = 0
    for receipt in receipts:
        status = receipt.get("status")
        side_effect_count = receipt.get("side_effect_count", 0)
        if status in {"planned", "dry_run", "review_required", "blocked"}:
            try:
                unauthorized_side_effects += max(0, int(side_effect_count))
            except (TypeError, ValueError):
                unauthorized_side_effects += 1
        for action in receipt.get("actions", []) if isinstance(receipt.get("actions"), list) else []:
            if not isinstance(action, Mapping):
                continue
            if action.get("action_type") == "external.research.plan" and action.get("side_effect") is not False:
                unauthorized_side_effects += 1
            if action.get("permission", {}).get("decision") in {"deny", "review"} and action.get("side_effect") is True:
                unauthorized_side_effects += 1
    if unauthorized_side_effects:
        errors.append("unauthorized_side_effects_nonzero")
    errors.extend(permission_mismatches and ["permission_fixture_mismatch"] or [])
    errors.extend(collaboration_errors)
    warnings.append("receipt_hash_chain_is_not_a_signature_or_multi_writer_lock")
    return {
        "name": "runtime",
        "passed": not errors,
        "status": "bounded_local_runtime_regression",
        "errors": sorted(set(errors)),
        "warnings": sorted(set(warnings)),
        "summary": {
            "fixture_sha256": fixture_sha256,
            "deterministic_schedule": deterministic,
            "scheduled_actions": len(actions),
            "allocated": plan.get("allocated", {}),
            "side_effects_executed": plan.get("side_effects_executed"),
            "permission_case_count": len(cases) if isinstance(cases, list) else 0,
            "permission_mismatches": sorted(permission_mismatches, key=lambda item: canonical_json(item)),
            "collaboration_record_count": len(fixture.get("collaboration_records", [])) if isinstance(fixture.get("collaboration_records"), list) else 0,
            "actor_kinds_exercised": sorted(actor_kinds_seen),
            "receipt_count": len(receipts),
            "receipt_chain_sha256": digest(list(receipts)),
            "receipt_chain_errors": chain_errors,
            "unauthorized_side_effects": unauthorized_side_effects,
        },
    }


def evaluate_regression_result(result: Mapping[str, Any] | None) -> dict[str, Any]:
    """Validate an injected unit-test result; this module never starts a process."""

    if result is None:
        return {
            "name": "regression_tests",
            "passed": False,
            "evaluated": False,
            "errors": ["regression_tests_not_evaluated"],
            "warnings": [],
            "summary": {},
        }
    errors: list[str] = []
    count = result.get("test_count")
    if result.get("passed") is not True:
        errors.append("regression_tests_not_passed")
    if isinstance(count, bool) or not isinstance(count, int) or count < 1:
        errors.append("regression_test_count_invalid")
    for field in ("failures", "errors"):
        value = result.get(field, 0)
        if isinstance(value, bool) or not isinstance(value, int) or value != 0:
            errors.append(f"regression_{field}_nonzero_or_invalid")
    skipped = result.get("skipped", 0)
    if result.get("rollback_rehearsal_passed") is not True:
        errors.append("rollback_rehearsal_not_passed")
    if result.get("rollback_base_commit") != PINNED_ROLLBACK_COMMIT:
        errors.append("rollback_baseline_commit_mismatch")
    if result.get("rollback_live_workspace_unchanged") is not True:
        errors.append("rollback_rehearsal_mutated_live_workspace")
    warnings = ["regression_tests_include_skips"] if isinstance(skipped, int) and skipped > 0 else []
    return {
        "name": "regression_tests",
        "passed": not errors,
        "evaluated": True,
        "errors": sorted(errors),
        "warnings": warnings,
        "summary": {
            "test_count": count,
            "failures": result.get("failures", 0),
            "errors": result.get("errors", 0),
            "skipped": skipped,
            "evidence": result.get("evidence"),
            "rollback_rehearsal_passed": result.get("rollback_rehearsal_passed"),
            "rollback_evidence": result.get("rollback_evidence"),
            "rollback_base_commit": result.get("rollback_base_commit"),
            "rollback_live_workspace_unchanged": result.get("rollback_live_workspace_unchanged"),
        },
    }


def build_release_report(
    *,
    structural_findings: Any,
    okf_findings: Any,
    calibration_result: Mapping[str, Any],
    security_result: Mapping[str, Any],
    runtime_result: Mapping[str, Any],
    regression_result: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Combine evaluated components into the truthful v4 readiness report."""

    gates = [
        evaluate_findings("structural_and_ledger", structural_findings),
        evaluate_findings("okf_bundle", okf_findings),
        dict(calibration_result),
        dict(security_result),
        dict(runtime_result),
        evaluate_regression_result(regression_result),
    ]
    passed = all(gate.get("passed") is True for gate in gates)
    component_fingerprint = digest(gates)
    return {
        "schema_version": SCHEMA_VERSION,
        "release_id": RELEASE_ID,
        "passed": passed,
        "readiness": "closed_loop_harness_fixed_fixture_passed" if passed else "not_ready",
        "production_certified": False,
        "calibration_status": "pilot_regression_only",
        "security_status": "fixed_corpus_regression_only",
        "scope": "deterministic local control-plane, injected repository validators, and fixed regression fixtures",
        "component_fingerprint": component_fingerprint,
        "gates": gates,
        "claims": {
            "production_security_certified": False,
            "empirical_calibration_certified": False,
            "c_levels_are_probabilities": False,
            "external_executor_certified": False,
            "release_gate_mutated_repository": False,
        },
        "limitations": [
            "The calibration fixture is a pilot regression set, not a population-level reliability estimate.",
            "The lexical security corpus does not establish robustness to unseen or semantic attacks.",
            "Receipt hashes detect accidental mutation but provide neither signatures nor multi-writer serialization.",
            "Injected structural, OKF, and unit-test results are trusted as caller-provided observations.",
            "No live network adapter, credential broker, external executor, or publication path is certified.",
        ],
    }


def _load_json(path: Path) -> Mapping[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReleaseGateError(f"cannot load {path.name}: {exc}") from exc
    if not isinstance(value, Mapping):
        raise ReleaseGateError(f"{path.name} must contain a JSON object")
    return value


def load_receipts(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    """Read a JSONL chain fail-closed while keeping errors in the report."""

    if not path.is_file():
        return [], ["receipt_ledger_missing"]
    values: list[dict[str, Any]] = []
    errors: list[str] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        return [], [f"receipt_ledger_unreadable:{type(exc).__name__}"]
    for number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            errors.append(f"line {number}: invalid receipt JSON")
            continue
        if not isinstance(value, dict):
            errors.append(f"line {number}: receipt is not an object")
            continue
        values.append(value)
    return values, errors


def evaluate_repository(
    root: Path | str,
    *,
    structural_findings: Any,
    okf_findings: Any,
    regression_result: Mapping[str, Any] | None,
    calibration_fixture: Path | str | None = None,
    security_corpus: Path | str | None = None,
    runtime_fixture: Path | str | None = None,
    receipt_ledger: Path | str | None = None,
) -> dict[str, Any]:
    """Read repository fixtures and return a deterministic, mutation-free report."""

    base = Path(root)
    calibration_path = Path(calibration_fixture) if calibration_fixture else base / "evaluations" / "fixtures" / "calibration-gold.json"
    security_path = Path(security_corpus) if security_corpus else base / "evaluations" / "fixtures" / "security-corpus.json"
    runtime_path = Path(runtime_fixture) if runtime_fixture else base / "evaluations" / "fixtures" / "runtime-scenarios.json"
    receipts_path = Path(receipt_ledger) if receipt_ledger else base / "evaluations" / "receipts" / "receipts.jsonl"
    calibration_data = _load_json(calibration_path)
    security_data = _load_json(security_path)
    runtime_data = _load_json(runtime_path)
    receipts, receipt_errors = load_receipts(receipts_path)
    return build_release_report(
        structural_findings=structural_findings,
        okf_findings=okf_findings,
        calibration_result=evaluate_calibration_fixture(
            calibration_data, expected_benchmark_sha256=PINNED_CALIBRATION_SHA256
        ),
        security_result=evaluate_security_corpus(
            security_data, expected_corpus_sha256=PINNED_SECURITY_SHA256
        ),
        runtime_result=evaluate_runtime_fixture(
            runtime_data,
            receipts,
            receipt_read_errors=receipt_errors,
            expected_fixture_sha256=PINNED_RUNTIME_SHA256,
        ),
        regression_result=regression_result,
    )


def _optional_json(path: Path | None) -> Mapping[str, Any] | None:
    return _load_json(path) if path is not None else None


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read-only Living Wiki v4 release gate")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--structural-findings", type=Path, help="JSON object injected by tools/wiki.py validation")
    parser.add_argument("--okf-findings", type=Path, help="JSON object injected by OKF validation")
    parser.add_argument("--regression-result", type=Path, help="JSON unit-test summary; tests are not run here")
    parser.add_argument("--compact", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        report = evaluate_repository(
            args.root,
            structural_findings=_optional_json(args.structural_findings),
            okf_findings=_optional_json(args.okf_findings),
            regression_result=_optional_json(args.regression_result),
        )
    except ReleaseGateError as exc:
        sys.stderr.write(canonical_json({"error": str(exc)}) + "\n")
        return 2
    sys.stdout.write(canonical_json(report, pretty=not args.compact))
    return 0 if report["passed"] else 4


if __name__ == "__main__":
    raise SystemExit(main())
