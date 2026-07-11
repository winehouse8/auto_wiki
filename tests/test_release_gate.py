import ast
import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
from tools import release_gate


CALIBRATION = json.loads(
    (ROOT / "evaluations" / "fixtures" / "calibration-gold.json").read_text(encoding="utf-8")
)
SECURITY = json.loads(
    (ROOT / "evaluations" / "fixtures" / "security-corpus.json").read_text(encoding="utf-8")
)
RUNTIME = json.loads(
    (ROOT / "evaluations" / "fixtures" / "runtime-scenarios.json").read_text(encoding="utf-8")
)


def regression(passed=True, count=129):
    return {
        "passed": passed,
        "test_count": count,
        "failures": 0,
        "errors": 0,
        "skipped": 0,
        "rollback_rehearsal_passed": True,
        "rollback_evidence": "fixture-rollback-evidence",
        "rollback_base_commit": release_gate.PINNED_ROLLBACK_COMMIT,
        "rollback_live_workspace_unchanged": True,
    }


def receipt(status="planned", side_effect_count=0):
    value = {
        "schema_version": 1,
        "run_id": "RUN-TEST",
        "status": status,
        "side_effect_count": side_effect_count,
        "actions": [
            {
                "action_id": "ACT-TEST",
                "action_type": "external.research.plan",
                "status": "planned",
                "side_effect": False,
                "permission": {"decision": "auto"},
            }
        ],
        "prev_receipt_hash": release_gate.ZERO_HASH,
    }
    value["receipt_hash"] = release_gate.digest(value)
    return value


def component(name):
    return {"name": name, "passed": True, "errors": [], "warnings": [], "summary": {}}


class FindingTests(unittest.TestCase):
    def test_none_is_not_silently_clean(self):
        result = release_gate.normalize_findings(None)
        self.assertFalse(result["evaluated"])
        self.assertIn("validator_not_evaluated", result["errors"])

    def test_wiki_tuple_and_mapping_are_normalized_deterministically(self):
        tuple_result = release_gate.normalize_findings((["b", "a", "a"], ["w"], {"z": 1, "a": 2}))
        mapping_result = release_gate.normalize_findings(
            {"warnings": ["w"], "counts": {"a": 2, "z": 1}, "errors": ["a", "b"]}
        )
        self.assertEqual(tuple_result, mapping_result)
        self.assertEqual(tuple_result["errors"], ["a", "b"])

    def test_injected_validator_error_fails_component(self):
        result = release_gate.evaluate_findings("structural", (["broken chain"], []))
        self.assertFalse(result["passed"])


class CalibrationReleaseTests(unittest.TestCase):
    def test_fixed_calibration_passes_only_as_pilot(self):
        result = release_gate.evaluate_calibration_fixture(CALIBRATION)
        self.assertTrue(result["passed"])
        self.assertEqual(result["status"], "pilot_regression_only")
        self.assertFalse(result["production_calibration"])
        self.assertFalse(result["summary"]["trust_policy_mutated"])
        self.assertEqual(result["summary"]["total_records"], 15)
        self.assertIn("pilot_fixture_below_100_record_empirical_calibration_target", result["warnings"])

    def test_calibration_report_is_byte_deterministic(self):
        first = release_gate.evaluate_calibration_fixture(CALIBRATION)
        second = release_gate.evaluate_calibration_fixture(copy.deepcopy(CALIBRATION))
        self.assertEqual(release_gate.canonical_json(first), release_gate.canonical_json(second))

    def test_empty_calibration_fails_closed(self):
        value = copy.deepcopy(CALIBRATION)
        value["gold_records"] = []
        result = release_gate.evaluate_calibration_fixture(value)
        self.assertFalse(result["passed"])

    def test_release_baseline_rejects_calibration_fixture_drift(self):
        value = copy.deepcopy(CALIBRATION)
        value["gold_records"][0]["domain"] = "easier-replacement"
        result = release_gate.evaluate_calibration_fixture(
            value, expected_benchmark_sha256=release_gate.PINNED_CALIBRATION_SHA256
        )
        self.assertFalse(result["passed"])
        self.assertIn("calibration_fixture_hash_drift", result["errors"])


class SecurityReleaseTests(unittest.TestCase):
    def test_fixed_security_corpus_has_zero_success_and_rejection(self):
        result = release_gate.evaluate_security_corpus(SECURITY)
        self.assertTrue(result["passed"])
        self.assertFalse(result["production_security_certified"])
        self.assertEqual(result["summary"]["attack_success_rate"], 0.0)
        self.assertEqual(result["summary"]["benign_rejection_rate"], 0.0)
        self.assertEqual(result["summary"]["payloads_executed"], 0)

    def test_security_report_is_deterministic(self):
        first = release_gate.evaluate_security_corpus(SECURITY)
        second = release_gate.evaluate_security_corpus(copy.deepcopy(SECURITY))
        self.assertEqual(release_gate.canonical_json(first), release_gate.canonical_json(second))

    def test_expected_gate_tamper_fails(self):
        value = copy.deepcopy(SECURITY)
        value["cases"][0]["expected_gates"]["write"] = "allow"
        result = release_gate.evaluate_security_corpus(value)
        self.assertFalse(result["passed"])
        self.assertIn("fixture_expectation_mismatch", result["errors"])

    def test_release_baseline_rejects_security_corpus_drift(self):
        value = copy.deepcopy(SECURITY)
        value["description"] = "changed without baseline review"
        result = release_gate.evaluate_security_corpus(
            value, expected_corpus_sha256=release_gate.PINNED_SECURITY_SHA256
        )
        self.assertFalse(result["passed"])
        self.assertIn("security_corpus_hash_drift", result["errors"])


class RuntimeReleaseTests(unittest.TestCase):
    def test_receipt_chain_detects_payload_tamper(self):
        valid = receipt()
        self.assertEqual(release_gate.verify_receipt_chain([valid]), [])
        tampered = copy.deepcopy(valid)
        tampered["side_effect_count"] = 1
        self.assertIn("line 1: invalid receipt_hash", release_gate.verify_receipt_chain([tampered]))

    def test_runtime_fixture_checks_parity_permissions_budget_and_receipt(self):
        result = release_gate.evaluate_runtime_fixture(RUNTIME, [receipt()])
        self.assertTrue(result["passed"], result["errors"])
        self.assertEqual(result["summary"]["actor_kinds_exercised"], ["agent", "human"])
        self.assertEqual(result["summary"]["permission_mismatches"], [])
        self.assertFalse(result["summary"]["side_effects_executed"])
        self.assertEqual(result["summary"]["unauthorized_side_effects"], 0)

    def test_empty_receipt_chain_is_not_release_evidence(self):
        result = release_gate.evaluate_runtime_fixture(RUNTIME, [])
        self.assertFalse(result["passed"])
        self.assertIn("receipt_chain_has_no_release_evidence", result["errors"])

    def test_planned_receipt_with_side_effect_fails(self):
        unsafe = receipt(side_effect_count=1)
        result = release_gate.evaluate_runtime_fixture(RUNTIME, [unsafe])
        self.assertFalse(result["passed"])
        self.assertIn("unauthorized_side_effects_nonzero", result["errors"])

    def test_release_baseline_rejects_runtime_fixture_drift(self):
        value = copy.deepcopy(RUNTIME)
        value["permission_cases"] = value["permission_cases"][:-1]
        result = release_gate.evaluate_runtime_fixture(
            value,
            [receipt()],
            expected_fixture_sha256=release_gate.PINNED_RUNTIME_SHA256,
        )
        self.assertFalse(result["passed"])
        self.assertIn("runtime_fixture_hash_drift", result["errors"])


class CombinedReportTests(unittest.TestCase):
    def inputs(self):
        return {
            "structural_findings": ([], [], {"events": 10}),
            "okf_findings": ([], []),
            "calibration_result": release_gate.evaluate_calibration_fixture(CALIBRATION),
            "security_result": release_gate.evaluate_security_corpus(SECURITY),
            "runtime_result": release_gate.evaluate_runtime_fixture(RUNTIME, [receipt()]),
            "regression_result": regression(),
        }

    def test_all_gates_pass_without_claiming_production_certification(self):
        report = release_gate.build_release_report(**self.inputs())
        self.assertTrue(report["passed"])
        self.assertEqual(report["readiness"], "closed_loop_harness_fixed_fixture_passed")
        self.assertFalse(report["production_certified"])
        self.assertFalse(report["claims"]["production_security_certified"])
        self.assertFalse(report["claims"]["empirical_calibration_certified"])
        self.assertFalse(report["claims"]["c_levels_are_probabilities"])

    def test_missing_regression_evidence_fails(self):
        values = self.inputs()
        values["regression_result"] = None
        report = release_gate.build_release_report(**values)
        self.assertFalse(report["passed"])
        gate = next(item for item in report["gates"] if item["name"] == "regression_tests")
        self.assertFalse(gate["evaluated"])

    def test_failed_rollback_rehearsal_fails_release(self):
        values = self.inputs()
        values["regression_result"] = regression()
        values["regression_result"]["rollback_rehearsal_passed"] = False
        report = release_gate.build_release_report(**values)
        self.assertFalse(report["passed"])
        gate = next(item for item in report["gates"] if item["name"] == "regression_tests")
        self.assertIn("rollback_rehearsal_not_passed", gate["errors"])

    def test_rollback_baseline_commit_drift_fails_release(self):
        values = self.inputs()
        values["regression_result"] = regression()
        values["regression_result"]["rollback_base_commit"] = "0" * 40
        report = release_gate.build_release_report(**values)
        self.assertFalse(report["passed"])
        gate = next(item for item in report["gates"] if item["name"] == "regression_tests")
        self.assertIn("rollback_baseline_commit_mismatch", gate["errors"])

    def test_structural_error_fails_entire_report(self):
        values = self.inputs()
        values["structural_findings"] = (["event chain invalid"], [], {})
        self.assertFalse(release_gate.build_release_report(**values)["passed"])

    def test_report_is_deterministic_and_has_no_timestamp(self):
        first = release_gate.canonical_json(release_gate.build_release_report(**self.inputs()))
        second = release_gate.canonical_json(release_gate.build_release_report(**self.inputs()))
        self.assertEqual(first, second)
        self.assertNotIn("generated_at", first)
        self.assertNotIn(str(ROOT.resolve()), first)


class RepositoryAndCliTests(unittest.TestCase):
    def test_current_repository_fixtures_can_be_evaluated_read_only(self):
        kwargs = {
            "structural_findings": ([], [], {}),
            "okf_findings": ([], []),
            "regression_result": regression(),
        }
        first = release_gate.evaluate_repository(ROOT, **kwargs)
        second = release_gate.evaluate_repository(ROOT, **kwargs)
        self.assertTrue(first["passed"])
        self.assertEqual(release_gate.canonical_json(first), release_gate.canonical_json(second))

    def test_cli_requires_injected_findings_and_test_result(self):
        completed = subprocess.run(
            [sys.executable, str(ROOT / "tools" / "release_gate.py"), "--root", str(ROOT), "--compact"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 4)
        report = json.loads(completed.stdout)
        self.assertFalse(report["passed"])
        self.assertFalse(report["production_certified"])

    def test_cli_passes_with_explicit_injected_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            structural = base / "structural.json"
            okf = base / "okf.json"
            tests = base / "tests.json"
            structural.write_text(json.dumps({"errors": [], "warnings": [], "counts": {}}), encoding="utf-8")
            okf.write_text(json.dumps({"errors": [], "warnings": []}), encoding="utf-8")
            tests.write_text(json.dumps(regression()), encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "tools" / "release_gate.py"),
                    "--root",
                    str(ROOT),
                    "--structural-findings",
                    str(structural),
                    "--okf-findings",
                    str(okf),
                    "--regression-result",
                    str(tests),
                    "--compact",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertTrue(json.loads(completed.stdout)["passed"])

    def test_module_has_no_network_or_process_import(self):
        tree = ast.parse((ROOT / "tools" / "release_gate.py").read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        self.assertTrue({"socket", "urllib", "requests", "subprocess"}.isdisjoint(imported))


if __name__ == "__main__":
    unittest.main()
