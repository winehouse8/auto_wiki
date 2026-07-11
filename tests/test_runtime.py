import copy
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location("living_wiki_runtime", ROOT / "tools" / "runtime.py")
runtime = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = runtime
SPEC.loader.exec_module(runtime)

FIXTURE = json.loads((ROOT / "evaluations" / "fixtures" / "runtime-scenarios.json").read_text(encoding="utf-8"))
NOW = "2026-07-12T00:00:00+00:00"


def document(item):
    return runtime.SearchDocument(item["doc_id"], item["text"], item["kind"])


def plan(actions, *, max_actions=10, max_minutes=100, max_sources=100):
    allocated = {
        "actions": len(actions),
        "minutes": sum(item.get("budget", {}).get("minutes", 0) for item in actions),
        "sources": sum(item.get("budget", {}).get("sources", 0) for item in actions),
    }
    return {
        "plan_id": "PLAN-TEST",
        "limits": {"max_actions": max_actions, "max_minutes": max_minutes, "max_sources": max_sources},
        "allocated": allocated,
        "actions": actions,
    }


def action(action_id, action_type="content.draft", **extra):
    return {
        "id": action_id,
        "action_type": action_type,
        "budget": {"minutes": 1, "sources": 0},
        **extra,
    }


class CollaborationRecordTests(unittest.TestCase):
    def make(self, actor_id="human:owner", **changes):
        values = {
            "actor_id": actor_id,
            "record_kind": "commitment",
            "intent": "direction",
            "content": "반증 검색을 수행한다.",
            "targets": ["CMP-1"],
            "stance": "request",
            "created_at": NOW,
        }
        values.update(changes)
        return runtime.make_collaboration_record(**values)

    def test_human_and_agent_use_identical_schema(self):
        human = self.make("human:owner")
        agent = self.make("agent:researcher")
        self.assertEqual(set(human), runtime.COLLABORATION_FIELDS)
        self.assertEqual(set(human), set(agent))
        self.assertNotEqual(human["actor_id"], agent["actor_id"])

    def test_all_record_kinds_use_same_envelope(self):
        records = [self.make(record_kind=kind) for kind in sorted(runtime.RECORD_KINDS)]
        self.assertTrue(all(set(item) == set(records[0]) for item in records))

    def test_invalid_intent_is_rejected(self):
        with self.assertRaises(runtime.RuntimeErrorBase):
            self.make(intent="command")

    def test_valid_lifecycle_transition_is_attributed(self):
        proposed = self.make()
        active = runtime.transition_collaboration_record(
            proposed, "active", actor_id="agent:researcher", reason="accepted for work", at="2026-07-12T01:00:00+00:00"
        )
        self.assertEqual(active["status"], "active")
        self.assertEqual(active["metadata"]["transitions"][0]["actor_id"], "agent:researcher")
        self.assertEqual(proposed["status"], "proposed")

    def test_terminal_lifecycle_cannot_reopen(self):
        active = runtime.transition_collaboration_record(
            self.make(), "active", actor_id="human:owner", reason="start", at="2026-07-12T01:00:00+00:00"
        )
        resolved = runtime.transition_collaboration_record(
            active, "resolved", actor_id="agent:researcher", reason="done", at="2026-07-12T02:00:00+00:00"
        )
        with self.assertRaises(runtime.RuntimeErrorBase):
            runtime.transition_collaboration_record(
                resolved, "active", actor_id="human:owner", reason="reopen", at="2026-07-12T03:00:00+00:00"
            )

    def test_lifecycle_timestamp_cannot_move_backwards(self):
        acknowledged = runtime.transition_collaboration_record(
            self.make(), "acknowledged", actor_id="human:owner", reason="seen", at="2026-07-12T02:00:00+00:00"
        )
        with self.assertRaises(runtime.RuntimeErrorBase):
            runtime.transition_collaboration_record(
                acknowledged, "active", actor_id="agent:x", reason="start", at="2026-07-12T01:00:00+00:00"
            )

    def test_fixture_records_are_valid_for_both_actor_kinds(self):
        for spec in FIXTURE["collaboration_records"]:
            record = runtime.make_collaboration_record(**spec, created_at=NOW)
            self.assertEqual(runtime.validate_collaboration_record(record), [])


class RetrievalTests(unittest.TestCase):
    def setUp(self):
        self.documents = [document(item) for item in FIXTURE["search_documents"]]

    def test_bm25_ranks_relevant_document_first(self):
        results = runtime.lexical_search("주장 신뢰도 승격 독립 검토", documents=self.documents)
        self.assertEqual(results[0]["doc_id"], "claim:CLM-A")
        self.assertGreater(results[0]["score"], 0)

    def test_bm25_tie_break_is_document_id(self):
        documents = [runtime.SearchDocument("b", "same token"), runtime.SearchDocument("a", "same token")]
        results = runtime.lexical_search("same token", documents=documents)
        self.assertEqual([item["doc_id"] for item in results], ["a", "b"])

    def test_empty_or_unmatched_query_returns_nothing(self):
        self.assertEqual(runtime.lexical_search("", documents=self.documents), [])
        self.assertEqual(runtime.lexical_search("zzzz-not-present", documents=self.documents), [])

    def test_repository_corpus_includes_state_and_wiki_but_not_raw(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "state").mkdir()
            (root / "wiki").mkdir()
            (root / "raw").mkdir()
            (root / "state" / "claims.json").write_text(
                json.dumps({"claims": [{"id": "CLM-1", "statement": "state needle"}]}), encoding="utf-8"
            )
            (root / "wiki" / "page.md").write_text("wiki needle", encoding="utf-8")
            (root / "raw" / "secret.md").write_text("raw needle", encoding="utf-8")
            docs = runtime.build_search_documents(root)
            ids = {item.doc_id for item in docs}
            self.assertIn("claim:CLM-1", ids)
            self.assertIn("wiki:wiki/page.md", ids)
            self.assertFalse(any("raw" in item for item in ids))


class ImpactPreviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "state").mkdir()
        (self.root / "wiki").mkdir()
        (self.root / "state" / "claims.json").write_text(
            json.dumps(
                {
                    "claims": [
                        {
                            "id": "CLM-1",
                            "statement": "자동 승격을 허용한다.",
                            "evidence": [{"source_id": "SRC-1", "relation": "supports"}],
                            "supersedes": [],
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        (self.root / "state" / "sources.json").write_text(
            json.dumps({"sources": [{"id": "SRC-1", "title": "승격 정책"}]}), encoding="utf-8"
        )
        (self.root / "state" / "campaigns.json").write_text(
            json.dumps({"campaigns": [{"id": "CMP-1", "question": "승격", "claim_ids": ["CLM-1"], "source_ids": []}]}),
            encoding="utf-8",
        )

    def tearDown(self):
        self.temp.cleanup()

    def test_source_change_propagates_to_claim_and_campaign(self):
        preview = runtime.impact_preview(["SRC-1"], "자동 승격 근거", root=self.root)
        self.assertEqual(preview["impacted"]["claims"], ["CLM-1"])
        self.assertEqual(preview["impacted"]["campaigns"], ["CMP-1"])

    def test_campaign_target_expands_membership_dependencies(self):
        preview = runtime.impact_preview(["CMP-1"], "승격", root=self.root)
        self.assertIn("CLM-1", preview["impacted"]["claims"])
        self.assertIn("SRC-1", preview["impacted"]["sources"])

    def test_unknown_target_is_reported(self):
        preview = runtime.impact_preview(["CLM-UNKNOWN"], "승격", root=self.root)
        self.assertEqual(preview["unknown_targets"], ["CLM-UNKNOWN"])

    def test_polarity_difference_is_only_a_conflict_candidate(self):
        preview = runtime.impact_preview(["CLM-1"], "자동 승격을 허용하지 않는다", root=self.root)
        candidates = preview["semantic_conflict_candidates"]
        self.assertTrue(any("polarity_mismatch" in item["reasons"] for item in candidates))
        self.assertTrue(all(item["status"] == "candidate_requires_review" for item in candidates))


class PermissionTests(unittest.TestCase):
    def test_fixture_permission_decisions(self):
        for case in FIXTURE["permission_cases"]:
            with self.subTest(case=case):
                self.assertEqual(runtime.decide_permission(case["action_type"])["decision"], case["expected"])

    def test_actor_kind_does_not_override_high_risk_review(self):
        human = runtime.decide_permission("external.publish", actor={"id": "human:owner", "kind": "human"})
        agent = runtime.decide_permission("external.publish", actor={"id": "agent:x", "kind": "agent"})
        self.assertEqual(human["decision"], "review")
        self.assertEqual(agent["decision"], "review")
        self.assertFalse(human["actor_kind_used_for_decision"])

    def test_irreversible_allowlisted_action_is_not_auto(self):
        result = runtime.decide_permission({"action_type": "content.draft", "irreversible": True})
        self.assertEqual(result["decision"], "review")
        self.assertEqual(result["risk"], "high")

    def test_custom_policy_cannot_auto_allow_builtin_high_risk(self):
        result = runtime.decide_permission("governance.modify", policy={"auto_actions": ["governance.modify"]})
        self.assertEqual(result["decision"], "review")

    def test_high_risk_prefix_variant_cannot_be_custom_auto(self):
        action_type = "governance.modify.constitution"
        result = runtime.decide_permission(action_type, policy={"auto_actions": [action_type]})
        self.assertEqual(result["decision"], "review")

    def test_unplanned_external_variant_cannot_be_custom_auto(self):
        action_type = "external.research.perform"
        result = runtime.decide_permission(action_type, policy={"auto_actions": [action_type]})
        self.assertEqual(result["decision"], "review")


class SchedulerTests(unittest.TestCase):
    def schedule(self, **changes):
        values = {
            "campaigns": copy.deepcopy(FIXTURE["campaigns"]),
            "interests": copy.deepcopy(FIXTURE["interests"]),
            "now": NOW,
            "limits": {"max_campaigns": 1, "max_actions": 1, "max_minutes": 10, "max_sources": 1, "action_minutes": 10},
        }
        values.update(changes)
        return runtime.build_bounded_schedule(**values)

    def test_scheduler_selects_priority_first_and_honors_global_bounds(self):
        result = self.schedule()
        self.assertEqual([item["campaign_id"] for item in result["actions"]], ["CMP-HIGH"])
        self.assertEqual(result["allocated"], {"campaigns": 1, "actions": 1, "minutes": 10, "sources": 1})

    def test_scheduler_honors_met_stop_condition(self):
        result = self.schedule()
        stopped = [item for item in result["skipped"] if item["campaign_id"] == "CMP-STOPPED"]
        self.assertEqual(stopped[0]["reason"], "condition:done")

    def test_scheduler_honors_cadence_receipt(self):
        receipts = [
            {
                "status": "completed",
                "completed_at": "2026-07-11T00:00:00+00:00",
                "actions": [{"campaign_id": "CMP-HIGH", "status": "completed"}],
            }
        ]
        result = self.schedule(receipts=receipts)
        self.assertEqual(result["actions"][0]["campaign_id"], "CMP-LOW")
        reason = next(item["reason"] for item in result["skipped"] if item["campaign_id"] == "CMP-HIGH")
        self.assertTrue(reason.startswith("cadence:not_due_until:"))

    def test_dry_run_receipt_does_not_consume_cadence(self):
        receipts = [
            {
                "status": "dry_run",
                "completed_at": "2026-07-11T00:00:00+00:00",
                "actions": [{"campaign_id": "CMP-HIGH", "status": "dry_run"}],
            }
        ]
        result = self.schedule(receipts=receipts)
        self.assertEqual(result["actions"][0]["campaign_id"], "CMP-HIGH")

    def test_scheduler_honors_per_campaign_remaining_budget(self):
        campaigns = copy.deepcopy(FIXTURE["campaigns"])
        campaigns[0]["runtime"] = {"used_minutes": 57, "used_sources": 4}
        result = self.schedule(campaigns=campaigns)
        self.assertEqual(result["actions"][0]["budget"], {"minutes": 3, "sources": 1})

    def test_scheduler_only_emits_external_plans(self):
        result = self.schedule()
        selected = result["actions"][0]
        self.assertEqual(selected["execution"], "planned_only")
        self.assertTrue(selected["external_work"])
        self.assertFalse(result["side_effects_executed"])


class ReceiptTests(unittest.TestCase):
    def test_external_receipt_never_claims_runtime_execution(self):
        external = action("A", "external.research.plan", external_work=True, execution="planned_only")
        receipt = runtime.make_external_work_receipt(
            external, actor_id="human:owner", status="reported", evidence_refs=["SRC-1"], at=NOW
        )
        self.assertFalse(receipt["execution_performed_by_runtime"])
        self.assertEqual(receipt["verification_status"], "unverified_report")

    def test_external_receipt_rejects_internal_action(self):
        with self.assertRaises(runtime.RuntimeErrorBase):
            runtime.make_external_work_receipt(action("A"), actor_id="agent:x", status="completed", at=NOW)

    def test_dry_run_never_calls_handler(self):
        called = []
        receipt = runtime.run_plan(
            plan([action("A")]), dry_run=True, handlers={"content.draft": lambda item: called.append(item)}, now=NOW
        )
        self.assertEqual(receipt["status"], "dry_run")
        self.assertEqual(called, [])
        self.assertEqual(receipt["side_effect_count"], 0)

    def test_external_planned_action_never_calls_handler_even_live(self):
        called = []
        external = action("A", "external.research.plan", external_work=True, execution="planned_only")
        receipt = runtime.run_plan(
            plan([external]),
            dry_run=False,
            handlers={"external.research.plan": lambda item: called.append(item)},
            now=NOW,
        )
        self.assertEqual(receipt["status"], "planned")
        self.assertEqual(called, [])

    def test_high_risk_action_never_calls_handler(self):
        called = []
        receipt = runtime.run_plan(
            plan([action("A", "governance.modify")]),
            dry_run=False,
            handlers={"governance.modify": lambda item: called.append(item)},
            now=NOW,
        )
        self.assertEqual(receipt["status"], "review_required")
        self.assertEqual(called, [])

    def test_idempotent_terminal_run_replays_without_handler(self):
        with tempfile.TemporaryDirectory() as directory:
            store = runtime.ReceiptStore(directory)
            called = []
            work = plan([action("A")])
            first = runtime.run_plan(
                work,
                dry_run=False,
                store=store,
                handlers={"content.draft": lambda item: called.append(item) or {"ok": True}},
                now=NOW,
            )
            second = runtime.run_plan(
                work,
                dry_run=False,
                store=store,
                handlers={"content.draft": lambda item: called.append(item)},
                now="2026-07-12T01:00:00+00:00",
            )
            self.assertEqual(first["run_id"], second["run_id"])
            self.assertTrue(second["replayed"])
            self.assertEqual(len(called), 1)
            self.assertEqual(len(store.load()), 1)

    def test_receipt_chain_detects_tampering(self):
        with tempfile.TemporaryDirectory() as directory:
            store = runtime.ReceiptStore(directory)
            runtime.run_plan(plan([action("A")]), store=store, now=NOW)
            self.assertEqual(store.verify(), [])
            receipt = json.loads(store.path.read_text(encoding="utf-8"))
            receipt["status"] = "tampered"
            store.path.write_text(json.dumps(receipt) + "\n", encoding="utf-8")
            self.assertTrue(any("invalid receipt_hash" in error for error in store.verify()))

    def test_tampered_chain_blocks_a_new_run(self):
        with tempfile.TemporaryDirectory() as directory:
            store = runtime.ReceiptStore(directory)
            runtime.run_plan(plan([action("A")]), store=store, now=NOW)
            receipt = json.loads(store.path.read_text(encoding="utf-8"))
            receipt["status"] = "tampered"
            store.path.write_text(json.dumps(receipt) + "\n", encoding="utf-8")
            with self.assertRaises(runtime.RuntimeErrorBase):
                runtime.run_plan(plan([action("B")]), store=store, now="2026-07-12T01:00:00+00:00")

    def test_failed_run_recovers_without_repeating_completed_action(self):
        with tempfile.TemporaryDirectory() as directory:
            store = runtime.ReceiptStore(directory)
            work = plan([action("A"), action("B")])
            calls = []

            def first_handler(item):
                calls.append(item["id"])
                if item["id"] == "B":
                    raise ValueError("fixture failure")
                return {"ok": item["id"]}

            failed = runtime.run_plan(
                work, dry_run=False, store=store, handlers={"content.draft": first_handler}, now=NOW
            )
            self.assertEqual(failed["status"], "failed")
            recovered = runtime.recover_run(
                work,
                store=store,
                handlers={"content.draft": lambda item: calls.append(item["id"]) or {"ok": item["id"]}},
                now="2026-07-12T01:00:00+00:00",
            )
            self.assertEqual(recovered["status"], "completed")
            self.assertEqual(recovered["recovery_of"], failed["run_id"])
            self.assertEqual(calls, ["A", "B", "B"])
            recovered_a = next(item for item in recovered["actions"] if item["action_id"] == "A")
            self.assertTrue(recovered_a["recovered"])
            self.assertEqual(store.verify(), [])

    def test_plan_over_budget_is_rejected_before_handler(self):
        called = []
        with self.assertRaises(runtime.RuntimeErrorBase):
            runtime.run_plan(
                plan([action("A"), action("B")], max_actions=1),
                dry_run=False,
                handlers={"content.draft": lambda item: called.append(item)},
                now=NOW,
            )
        self.assertEqual(called, [])

    def test_duplicate_action_ids_are_rejected(self):
        with self.assertRaises(runtime.RuntimeErrorBase):
            runtime.run_plan(plan([action("A"), action("A")]), now=NOW)

    def test_negative_action_budget_is_rejected(self):
        bad = action("A")
        bad["budget"]["minutes"] = -1
        with self.assertRaises(runtime.RuntimeErrorBase):
            runtime.run_plan(plan([bad]), now=NOW)


if __name__ == "__main__":
    unittest.main()
