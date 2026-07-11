import ast
import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
from tools import memory_hygiene as hygiene
from tools import memory_feedback as feedback_schema


NOW = "2026-02-01T00:00:00+00:00"
CONFIG = {
    "name": "Fixture Wiki",
    "staleness_days": {"fast": 30, "normal": 180, "slow": 730, "timeless": None},
}


def claim(record_id="CLM-1", **changes):
    value = {
        "id": record_id,
        "created_at": "2026-01-01T00:00:00+00:00",
        "last_verified_at": None,
        "freshness": "fast",
        "confidence": {"level": "C2", "status": "supported"},
    }
    value.update(changes)
    return value


def source(record_id="SRC-1", **changes):
    value = {"id": record_id, "status": "active", "artifact": None, "source_level": "S2"}
    value.update(changes)
    return value


def feedback(record_id="FB-1", **changes):
    creation = {
        "actor_id": changes.pop("actor_id", "human:owner"),
        "created_at": changes.pop("created_at", "2026-01-20T00:00:00+00:00"),
        "task_ref": changes.pop("task_ref", f"TASK-{record_id}"),
        "targets": changes.pop("targets", ["CLM-1"]),
        "outcome": changes.pop("outcome", "helpful"),
        "rationale": changes.pop("rationale", "The cited claim answered the task."),
        "evidence_refs": changes.pop("evidence_refs", ["CLM-1"]),
    }
    try:
        value = feedback_schema.make_retrieval_feedback(**creation)
    except feedback_schema.MemoryFeedbackError:
        value = feedback_schema.make_retrieval_feedback(
            actor_id="human:owner",
            created_at="2026-01-20T00:00:00+00:00",
            task_ref=f"TASK-{record_id}",
            targets=["CLM-1"],
            outcome="helpful",
            rationale="The cited claim answered the task.",
            evidence_refs=["CLM-1"],
        )
        value.update(creation)
    status = changes.pop("status", "open")
    resolution = changes.pop("resolution", None)
    if status == "resolved" and isinstance(resolution, dict):
        value = feedback_schema.resolve_retrieval_feedback(
            value,
            actor_id=resolution["actor_id"],
            at=resolution["at"],
            rationale=resolution["rationale"],
        )
    elif status != "open" or resolution is not None:
        value["status"] = status
        value["resolution"] = resolution
    value.update(changes)
    return value


class TimeAndThresholdTests(unittest.TestCase):
    def test_z_and_offset_are_normalized_to_utc(self):
        self.assertEqual(hygiene.iso_time("2026-01-01T09:00:00+09:00"), "2026-01-01T00:00:00+00:00")
        self.assertEqual(hygiene.iso_time("2026-01-01T00:00:00Z"), "2026-01-01T00:00:00+00:00")

    def test_timezone_free_time_is_rejected(self):
        with self.assertRaises(hygiene.MemoryHygieneError):
            hygiene.parse_time("2026-01-01T00:00:00")

    def test_thresholds_allow_null_but_not_bool_negative_or_float(self):
        self.assertIsNone(hygiene.freshness_thresholds(CONFIG)["timeless"])
        for invalid in (True, -1, 1.5):
            with self.subTest(invalid=invalid):
                config = {"staleness_days": {"fast": invalid}}
                with self.assertRaises(hygiene.MemoryHygieneError):
                    hygiene.freshness_thresholds(config)

    def test_missing_threshold_object_is_rejected(self):
        with self.assertRaises(hygiene.MemoryHygieneError):
            hygiene.freshness_thresholds({})


class StalenessTests(unittest.TestCase):
    def evaluate(self, claims, now=NOW):
        return hygiene.evaluate_staleness(
            claims, thresholds=hygiene.freshness_thresholds(CONFIG), now=now
        )

    def test_exact_threshold_is_review_due(self):
        result = self.evaluate([claim(created_at="2026-01-02T00:00:00+00:00")])
        item = result["stale_claims"][0]
        self.assertEqual(item["age_days"], 30.0)
        self.assertEqual(item["review_due_at"], NOW)
        self.assertEqual(item["severity"], "warning")
        self.assertEqual(item["meaning"], "review_due_not_falsehood")

    def test_reference_precedence_is_last_verified_then_computed_then_created(self):
        recent = claim(
            last_verified_at="2026-01-20T00:00:00+00:00",
            created_at="2020-01-01T00:00:00+00:00",
            confidence={"computed_at": "2025-01-01T00:00:00+00:00"},
        )
        computed = claim(
            "CLM-2",
            last_verified_at=None,
            created_at="2020-01-01T00:00:00+00:00",
            confidence={"computed_at": "2025-12-01T00:00:00+00:00"},
        )
        created = claim("CLM-3", created_at="2025-12-01T00:00:00+00:00", confidence={})
        result = self.evaluate([recent, computed, created])
        by_id = {item["id"]: item for item in result["stale_claims"]}
        self.assertNotIn("CLM-1", by_id)
        self.assertEqual(by_id["CLM-2"]["reference_field"], "confidence.computed_at")
        self.assertEqual(by_id["CLM-3"]["reference_field"], "created_at")

    def test_timeless_claim_is_never_stale(self):
        result = self.evaluate([claim(freshness="timeless", created_at="2000-01-01T00:00:00+00:00")])
        self.assertEqual(result["stale_claims"], [])
        self.assertEqual(result["timeless_claim_ids"], ["CLM-1"])

    def test_unknown_freshness_and_missing_time_are_unassessable(self):
        result = self.evaluate(
            [
                claim("CLM-1", freshness="weekly"),
                claim("CLM-2", created_at=None, confidence={}),
            ]
        )
        reasons = {item["id"]: item["reason"] for item in result["unassessable_claims"]}
        self.assertEqual(reasons["CLM-1"], "unconfigured_or_missing_freshness_class")
        self.assertEqual(reasons["CLM-2"], "missing_reference_timestamp")

    def test_malformed_high_precedence_time_is_not_hidden_by_fallback(self):
        value = claim(
            last_verified_at=123,
            confidence={"computed_at": "2026-01-30T00:00:00+00:00"},
        )
        result = self.evaluate([value])
        self.assertEqual(
            result["unassessable_claims"][0]["reason"],
            "invalid_or_timezone_free_reference_timestamp",
        )
        self.assertEqual(result["unassessable_claims"][0]["reference_field"], "last_verified_at")

    def test_future_reference_is_flagged_not_stale(self):
        result = self.evaluate([claim(last_verified_at="2027-01-01T00:00:00+00:00")])
        self.assertEqual(result["stale_claims"], [])
        self.assertEqual(result["future_reference_claims"][0]["id"], "CLM-1")

    def test_inactive_stale_claim_remains_visible_but_not_active_count(self):
        result = self.evaluate(
            [claim(lifecycle_status="deprecated", created_at="2025-01-01T00:00:00+00:00")]
        )
        self.assertEqual(result["stale_count"], 1)
        self.assertEqual(result["active_stale_count"], 0)
        self.assertEqual(result["stale_claims"][0]["lifecycle_status"], "deprecated")

    def test_semantics_never_calls_stale_false_or_deprecated(self):
        result = self.evaluate([claim(created_at="2025-01-01T00:00:00+00:00")])
        self.assertIn("does not mean false", result["semantics"])


class LifecycleAndPreservationTests(unittest.TestCase):
    def test_canonical_lifecycle_status_has_precedence(self):
        item = claim(
            lifecycle_status="invalidated",
            lifecycle={"status": "archived"},
            status="deprecated",
        )
        self.assertEqual(hygiene.lifecycle_status(item, kind="claim"), "invalidated")

    def test_legacy_nested_and_source_status_are_tolerated(self):
        self.assertEqual(
            hygiene.lifecycle_status(claim(lifecycle={"status": "archived"}), kind="claim"),
            "archived",
        )
        self.assertEqual(hygiene.lifecycle_status(source(status="deprecated"), kind="source"), "deprecated")

    def test_confidence_status_is_not_lifecycle(self):
        item = claim(confidence={"status": "refuted"})
        self.assertEqual(hygiene.lifecycle_status(item, kind="claim"), "active")

    def test_invalid_lifecycle_is_rejected(self):
        with self.assertRaises(hygiene.MemoryHygieneError):
            hygiene.lifecycle_status(claim(lifecycle_status="deleted"), kind="claim")

    def test_inactive_counts_replacements_and_missing_supersession(self):
        result = hygiene.evaluate_lifecycle(
            [
                claim("CLM-A", lifecycle_status="active"),
                claim("CLM-B", lifecycle_status="superseded", replaced_by="CLM-C"),
                claim("CLM-C", lifecycle_status="archived"),
                claim("CLM-D", lifecycle_status="superseded"),
            ],
            [source("SRC-A", lifecycle_status="invalidated")],
        )
        self.assertEqual(result["claims"]["inactive_count"], 3)
        by_id = {item["id"]: item for item in result["claims"]["inactive_claims"]}
        self.assertEqual(by_id["CLM-B"]["replacement_ids"], ["CLM-C"])
        self.assertEqual(
            result["claims"]["issues"],
            [{"id": "CLM-D", "reason": "superseded_missing_replaced_by"}],
        )
        self.assertEqual(result["sources"]["counts"]["invalidated"], 1)

    def test_metadata_only_requires_path_and_hash(self):
        result = hygiene.evaluate_sources(
            [
                source("SRC-1"),
                source("SRC-2", artifact={}),
                source("SRC-3", artifact={"path": "raw/a"}),
                source("SRC-4", artifact={"path": "raw/b", "sha256": "abc"}),
            ]
        )
        self.assertEqual(result["metadata_only_count"], 3)
        self.assertEqual(
            [item["id"] for item in result["metadata_only_sources"]],
            ["SRC-1", "SRC-2", "SRC-3"],
        )
        self.assertEqual(result["artifact_backed_count"], 1)
        self.assertIn("not a source credibility", result["semantics"])


class FeedbackTests(unittest.TestCase):
    def evaluate(self, records=None):
        payload = None if records is None else {"version": 1, "feedback": records}
        return hygiene.evaluate_feedback(payload, known_target_ids={"CLM-1", "SRC-1", "CLM-2"})

    def test_missing_optional_ledger_is_empty(self):
        result = self.evaluate()
        self.assertFalse(result["present"])
        self.assertEqual(result["feedback_count"], 0)
        self.assertEqual(
            result["outcome_counts"],
            {"harmful": 0, "helpful": 0, "irrelevant": 0, "unknown": 0},
        )

    def test_outcomes_and_open_concerning_targets_are_counted(self):
        records = [
            feedback("FB-1", outcome="helpful", targets=["CLM-1"]),
            feedback("FB-2", outcome="harmful", targets=["CLM-1", "SRC-1"]),
            feedback("FB-3", outcome="irrelevant", targets=["CLM-2"]),
            feedback("FB-4", outcome="unknown", targets=["CLM-2"]),
        ]
        result = self.evaluate(records)
        self.assertEqual(
            result["outcome_counts"],
            {"harmful": 1, "helpful": 1, "irrelevant": 1, "unknown": 1},
        )
        self.assertEqual(result["unresolved_concerning_count"], 2)
        self.assertEqual(
            result["unresolved_harmful_or_irrelevant_target_ids"],
            ["CLM-1", "CLM-2", "SRC-1"],
        )

    def test_resolved_status_requires_attributed_resolution(self):
        with self.assertRaises(hygiene.MemoryHygieneError):
            self.evaluate([feedback(outcome="harmful", status="resolved", resolution=None)])

    def test_open_status_rejects_resolution_object(self):
        with self.assertRaises(hygiene.MemoryHygieneError):
            self.evaluate(
                [
                    feedback(
                        outcome="irrelevant",
                        status="open",
                        resolution={
                            "actor_id": "human:owner",
                            "at": "2026-01-21T00:00:00+00:00",
                            "rationale": "Draft resolution only.",
                        },
                    )
                ]
            )

    def test_duplicate_target_input_is_normalized_before_canonical_storage(self):
        result = self.evaluate(
            [feedback(outcome="harmful", targets=["CLM-1", "CLM-1", "CLM-UNKNOWN"])]
        )
        self.assertEqual(
            result["unresolved_concerning_feedback"][0]["target_ids"],
            ["CLM-1", "CLM-UNKNOWN"],
        )
        self.assertEqual(result["unknown_target_ids"], ["CLM-UNKNOWN"])

    def test_feedback_without_target_fails_canonical_schema(self):
        with self.assertRaises(hygiene.MemoryHygieneError):
            self.evaluate([feedback(outcome="harmful", targets=[])])

    def test_raw_query_task_ref_rationale_and_evidence_are_not_projected(self):
        secret = "private-rationale-token-0b4cb2e1"
        item = feedback(
            rationale=secret,
            evidence_refs=["EVT-0b4cb2e1"],
            outcome="harmful",
        )
        serialized = hygiene.canonical_json(self.evaluate([item]))
        self.assertNotIn(secret, serialized)
        self.assertIn("Only feedback IDs", serialized)

    def test_trust_or_automatic_effect_is_rejected(self):
        for changes in ({"trust_effect": "promote"}, {"automatic_action": True}):
            with self.subTest(changes=changes):
                with self.assertRaises(hygiene.MemoryHygieneError):
                    self.evaluate([feedback(**changes)])

    def test_invalid_outcome_status_targets_and_time_are_rejected(self):
        cases = [
            {"outcome": "bad"},
            {"status": "closed"},
            {"targets": "CLM-1"},
            {"created_at": "2026-01-01"},
        ]
        for changes in cases:
            with self.subTest(changes=changes):
                with self.assertRaises(hygiene.MemoryHygieneError):
                    self.evaluate([feedback(**changes)])

    def test_unknown_digest_field_is_rejected(self):
        with self.assertRaises(hygiene.MemoryHygieneError):
            self.evaluate([feedback(digest="abc123")])


class ReportTests(unittest.TestCase):
    def inputs(self):
        return {
            "config": copy.deepcopy(CONFIG),
            "claims": [claim(created_at="2025-01-01T00:00:00+00:00")],
            "sources": [source()],
            "feedback": {"version": 1, "feedback": [feedback(outcome="harmful")]},
            "now": NOW,
        }

    def test_report_is_deterministic_and_caller_timed(self):
        first = hygiene.build_report(**self.inputs())
        second = hygiene.build_report(**self.inputs())
        self.assertEqual(hygiene.canonical_json(first), hygiene.canonical_json(second))
        self.assertEqual(first["as_of"], NOW)
        self.assertNotIn("generated_at", first)

    def test_report_does_not_mutate_inputs(self):
        values = self.inputs()
        before = copy.deepcopy(values)
        hygiene.build_report(**values)
        self.assertEqual(values, before)

    def test_report_invariants_forbid_trust_status_and_deletion_effects(self):
        report = hygiene.build_report(**self.inputs())
        self.assertTrue(report["invariants"]["read_only"])
        for field in (
            "trust_mutated",
            "lifecycle_mutated",
            "status_mutated",
            "content_deleted",
            "staleness_changes_truth_value",
            "staleness_changes_confidence",
            "feedback_changes_ranking_or_trust",
            "host_paths_included",
            "wall_clock_used",
        ):
            self.assertFalse(report["invariants"][field])

    def test_duplicate_claim_or_source_ids_fail_closed(self):
        with self.assertRaises(hygiene.MemoryHygieneError):
            hygiene.build_report(
                config=CONFIG, claims=[claim(), claim()], sources=[], now=NOW
            )
        with self.assertRaises(hygiene.MemoryHygieneError):
            hygiene.build_report(
                config=CONFIG, claims=[], sources=[source(), source()], now=NOW
            )

    def test_input_fingerprint_changes_with_input(self):
        first = hygiene.build_report(**self.inputs())
        values = self.inputs()
        values["claims"][0]["freshness"] = "normal"
        second = hygiene.build_report(**values)
        self.assertNotEqual(
            first["input_fingerprints"]["claims_sha256"],
            second["input_fingerprints"]["claims_sha256"],
        )


class RepositoryAndCliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "config").mkdir()
        (self.root / "state").mkdir()
        (self.root / "config" / "wiki.json").write_text(json.dumps(CONFIG), encoding="utf-8")
        (self.root / "state" / "claims.json").write_text(
            json.dumps({"version": 1, "claims": [claim()]}), encoding="utf-8"
        )
        (self.root / "state" / "sources.json").write_text(
            json.dumps({"version": 1, "sources": [source()]}), encoding="utf-8"
        )

    def tearDown(self):
        self.temp.cleanup()

    def test_missing_feedback_is_empty_and_not_created(self):
        path = self.root / "state" / "memory_feedback.json"
        report = hygiene.evaluate_repository(self.root, now=NOW)
        self.assertFalse(report["feedback"]["present"])
        self.assertFalse(path.exists())

    def test_canonical_underscore_feedback_file_is_read(self):
        path = self.root / "state" / "memory_feedback.json"
        path.write_text(
            json.dumps({"version": 1, "feedback": [feedback(outcome="irrelevant")]}),
            encoding="utf-8",
        )
        report = hygiene.evaluate_repository(self.root, now=NOW)
        self.assertTrue(report["feedback"]["present"])
        self.assertEqual(report["feedback"]["outcome_counts"]["irrelevant"], 1)

    def test_report_contains_no_root_path(self):
        report = hygiene.evaluate_repository(self.root, now=NOW)
        self.assertNotIn(str(self.root.resolve()), hygiene.canonical_json(report))

    def test_read_only_evaluation_leaves_all_input_bytes_unchanged(self):
        files = sorted(path for path in self.root.rglob("*") if path.is_file())
        before = {path: path.read_bytes() for path in files}
        hygiene.evaluate_repository(self.root, now=NOW)
        after = {path: path.read_bytes() for path in files}
        self.assertEqual(before, after)
        self.assertEqual(files, sorted(path for path in self.root.rglob("*") if path.is_file()))

    def test_missing_required_input_error_does_not_leak_host_path(self):
        (self.root / "state" / "claims.json").unlink()
        with self.assertRaises(hygiene.MemoryHygieneError) as caught:
            hygiene.evaluate_repository(self.root, now=NOW)
        self.assertEqual(str(caught.exception), "missing required input: state/claims.json")
        self.assertNotIn(str(self.root), str(caught.exception))

    def test_cli_is_byte_deterministic(self):
        command = [
            sys.executable,
            str(ROOT / "tools" / "memory_hygiene.py"),
            "--root",
            str(self.root),
            "--now",
            NOW,
            "--compact",
        ]
        first = subprocess.run(command, capture_output=True, text=True, check=False)
        second = subprocess.run(command, capture_output=True, text=True, check=False)
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(first.stdout, second.stdout)
        self.assertEqual(json.loads(first.stdout)["as_of"], NOW)

    def test_cli_requires_explicit_timezone_aware_now(self):
        base = [
            sys.executable,
            str(ROOT / "tools" / "memory_hygiene.py"),
            "--root",
            str(self.root),
        ]
        missing = subprocess.run(base, capture_output=True, text=True, check=False)
        self.assertEqual(missing.returncode, 2)
        naive = subprocess.run(
            [*base, "--now", "2026-02-01T00:00:00", "--compact"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(naive.returncode, 2)
        self.assertIn("explicit UTC offset", json.loads(naive.stderr)["error"])

    def test_module_imports_no_network_or_process_capability_and_uses_no_wall_clock(self):
        path = ROOT / "tools" / "memory_hygiene.py"
        text = path.read_text(encoding="utf-8")
        tree = ast.parse(text)
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        self.assertTrue({"socket", "urllib", "requests", "subprocess"}.isdisjoint(imported))
        self.assertNotIn("datetime.now", text)
        self.assertNotIn("utcnow(", text)


if __name__ == "__main__":
    unittest.main()
