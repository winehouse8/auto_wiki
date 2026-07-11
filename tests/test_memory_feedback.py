import copy
import importlib.util
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location("living_wiki_memory_feedback", ROOT / "tools" / "memory_feedback.py")
memory = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = memory
SPEC.loader.exec_module(memory)

FIXTURE = json.loads(
    (ROOT / "evaluations" / "fixtures" / "memory-feedback-scenarios.json").read_text(encoding="utf-8")
)
NOW = "2026-07-12T03:00:00+00:00"


class FeedbackSchemaTests(unittest.TestCase):
    def make(self, **changes):
        values = copy.deepcopy(FIXTURE["feedback_inputs"][0])
        values.update(changes)
        return memory.make_retrieval_feedback(**values)

    def test_stable_id_and_digest_ignore_input_set_order(self):
        first = self.make()
        second = self.make(
            targets=list(reversed(FIXTURE["feedback_inputs"][0]["targets"])),
            evidence_refs=list(reversed(FIXTURE["feedback_inputs"][0]["evidence_refs"])),
        )
        self.assertEqual(first, second)
        self.assertEqual(memory.feedback_digest(first), memory.feedback_digest(second))

    def test_timestamp_is_normalized_to_utc(self):
        record = self.make(created_at="2026-07-12T10:00:00+09:00")
        self.assertEqual(record["created_at"], "2026-07-12T01:00:00+00:00")

    def test_record_has_only_canonical_fields_and_safety_constants(self):
        record = self.make()
        self.assertEqual(set(record), memory.FEEDBACK_FIELDS)
        self.assertEqual(record["trust_effect"], "none")
        self.assertIs(record["automatic_action"], False)
        self.assertEqual(record["status"], "open")

    def test_no_raw_query_or_content_field_is_stored(self):
        record = self.make(task_ref="task:opaque-9f7c")
        self.assertNotIn("query", record)
        self.assertNotIn("raw_query", record)
        self.assertNotIn("content", record)
        self.assertNotIn("?", record["task_ref"])

    def test_task_ref_must_be_opaque_not_raw_text(self):
        with self.assertRaises(memory.MemoryFeedbackError):
            self.make(task_ref="what did the user ask for?")

    def test_all_outcomes_are_supported(self):
        for outcome in sorted(memory.FEEDBACK_OUTCOMES):
            with self.subTest(outcome=outcome):
                record = self.make(outcome=outcome)
                self.assertEqual(memory.validate_retrieval_feedback(record), [])

    def test_unknown_outcome_fails(self):
        with self.assertRaises(memory.MemoryFeedbackError):
            self.make(outcome="promote")

    def test_empty_targets_fail(self):
        with self.assertRaises(memory.MemoryFeedbackError):
            self.make(targets=[])

    def test_duplicate_target_input_is_normalized_not_counted_twice(self):
        record = self.make(targets=["CLM-A", "CLM-A"])
        self.assertEqual(record["targets"], ["CLM-A"])

    def test_malformed_actor_fails(self):
        with self.assertRaises(memory.MemoryFeedbackError):
            self.make(actor_id="human owner with spaces")

    def test_naive_timestamp_fails(self):
        with self.assertRaises(memory.MemoryFeedbackError):
            self.make(created_at="2026-07-12T01:00:00")

    def test_unknown_fields_fail_including_query_rank_delete_and_promotion(self):
        for field in FIXTURE["invalid_field_examples"]:
            with self.subTest(field=field):
                record = self.make()
                record[field] = "malicious-or-unsupported"
                with self.assertRaises(memory.MemoryFeedbackError):
                    memory.validate_retrieval_feedback(record)

    def test_trust_promotion_cannot_be_encoded(self):
        record = self.make()
        record["trust_effect"] = "promote:C4"
        with self.assertRaises(memory.MemoryFeedbackError):
            memory.validate_retrieval_feedback(record)

    def test_automatic_action_cannot_be_true_or_integer_zero(self):
        for value in (True, 0, "false"):
            with self.subTest(value=value):
                record = self.make()
                record["automatic_action"] = value
                with self.assertRaises(memory.MemoryFeedbackError):
                    memory.validate_retrieval_feedback(record)

    def test_id_tamper_is_detected(self):
        record = self.make()
        record["id"] = "MFB-000000000000"
        with self.assertRaises(memory.MemoryFeedbackError):
            memory.validate_retrieval_feedback(record)

    def test_missing_field_fails(self):
        record = self.make()
        record.pop("rationale")
        with self.assertRaises(memory.MemoryFeedbackError):
            memory.validate_retrieval_feedback(record)


class FeedbackResolutionAndCollectionTests(unittest.TestCase):
    def setUp(self):
        self.open = memory.make_retrieval_feedback(**FIXTURE["feedback_inputs"][0])

    def test_resolution_is_non_destructive_and_attributed(self):
        before = copy.deepcopy(self.open)
        resolved = memory.resolve_retrieval_feedback(
            self.open,
            actor_id="human:reviewer",
            rationale="Reviewed the task receipt and closed the diagnostic item.",
            at="2026-07-12T02:00:00+00:00",
        )
        self.assertEqual(self.open, before)
        self.assertEqual(resolved["id"], self.open["id"])
        self.assertEqual(resolved["outcome"], self.open["outcome"])
        self.assertEqual(resolved["resolution"]["actor_id"], "human:reviewer")
        self.assertEqual(resolved["trust_effect"], "none")
        self.assertFalse(resolved["automatic_action"])

    def test_resolved_status_requires_resolution(self):
        record = copy.deepcopy(self.open)
        record["status"] = "resolved"
        with self.assertRaises(memory.MemoryFeedbackError):
            memory.validate_retrieval_feedback(record)

    def test_open_status_rejects_resolution(self):
        record = copy.deepcopy(self.open)
        record["resolution"] = {"actor_id": "human:x", "at": NOW, "rationale": "not closed"}
        with self.assertRaises(memory.MemoryFeedbackError):
            memory.validate_retrieval_feedback(record)

    def test_resolution_unknown_field_fails(self):
        resolved = memory.resolve_retrieval_feedback(
            self.open, actor_id="human:x", rationale="done", at="2026-07-12T02:00:00+00:00"
        )
        resolved["resolution"]["delete"] = True
        with self.assertRaises(memory.MemoryFeedbackError):
            memory.validate_retrieval_feedback(resolved)

    def test_resolution_cannot_precede_feedback(self):
        with self.assertRaises(memory.MemoryFeedbackError):
            memory.resolve_retrieval_feedback(
                self.open, actor_id="human:x", rationale="too early", at="2026-07-12T00:59:59+00:00"
            )

    def test_same_resolution_is_idempotent(self):
        resolved = memory.resolve_retrieval_feedback(
            self.open, actor_id="human:x", rationale="done", at="2026-07-12T02:00:00+00:00"
        )
        again = memory.resolve_retrieval_feedback(
            resolved, actor_id="human:x", rationale="done", at="2026-07-12T02:00:00+00:00"
        )
        self.assertEqual(resolved, again)

    def test_resolved_record_cannot_be_silently_rewritten(self):
        resolved = memory.resolve_retrieval_feedback(
            self.open, actor_id="human:x", rationale="done", at="2026-07-12T02:00:00+00:00"
        )
        with self.assertRaises(memory.MemoryFeedbackError):
            memory.resolve_retrieval_feedback(
                resolved, actor_id="agent:x", rationale="different", at="2026-07-12T02:01:00+00:00"
            )

    def test_exact_duplicates_are_removed(self):
        deduped = memory.deduplicate_feedback([self.open, copy.deepcopy(self.open)])
        self.assertEqual(deduped, [self.open])

    def test_open_and_resolved_duplicate_merge_monotonically(self):
        resolved = memory.resolve_retrieval_feedback(
            self.open, actor_id="human:x", rationale="done", at="2026-07-12T02:00:00+00:00"
        )
        deduped = memory.deduplicate_feedback([resolved, self.open])
        self.assertEqual(len(deduped), 1)
        self.assertEqual(deduped[0]["status"], "resolved")

    def test_conflicting_resolutions_fail_dedupe(self):
        one = memory.resolve_retrieval_feedback(
            self.open, actor_id="human:x", rationale="one", at="2026-07-12T02:00:00+00:00"
        )
        two = memory.resolve_retrieval_feedback(
            self.open, actor_id="human:y", rationale="two", at="2026-07-12T02:00:00+00:00"
        )
        with self.assertRaises(memory.MemoryFeedbackError):
            memory.deduplicate_feedback([one, two])

    def test_collection_has_exact_canonical_shape(self):
        payload = memory.make_feedback_collection([self.open, copy.deepcopy(self.open)])
        self.assertEqual(set(payload), {"version", "feedback"})
        self.assertEqual(payload["version"], 1)
        self.assertEqual(payload["feedback"], [self.open])
        self.assertEqual(memory.validate_feedback_collection(payload), [])

    def test_collection_unknown_field_and_duplicate_id_fail(self):
        with self.assertRaises(memory.MemoryFeedbackError):
            memory.validate_feedback_collection({"version": 1, "feedback": [], "delete": True})
        with self.assertRaises(memory.MemoryFeedbackError):
            memory.validate_feedback_collection({"version": 1, "feedback": [self.open, self.open]})


class AggregateTests(unittest.TestCase):
    def records(self):
        records = [memory.make_retrieval_feedback(**item) for item in FIXTURE["feedback_inputs"]]
        return records + [copy.deepcopy(records[0])]

    def test_fixture_aggregate_counts(self):
        report = memory.aggregate_feedback_report(self.records(), generated_at=NOW)
        for key, expected in FIXTURE["expected_aggregate"].items():
            self.assertEqual(report[key], expected)

    def test_report_is_byte_deterministic_across_input_order(self):
        records = self.records()
        first = memory.aggregate_feedback_report(records, generated_at=NOW)
        second = memory.aggregate_feedback_report(list(reversed(records)), generated_at=NOW)
        self.assertEqual(first, second)
        self.assertEqual(memory.render_feedback_report(first), memory.render_feedback_report(second))

    def test_report_has_no_trust_or_automatic_consequence(self):
        report = memory.aggregate_feedback_report(self.records(), generated_at=NOW)
        encoded = memory.render_feedback_report(report).decode("utf-8")
        self.assertEqual(report["trust_effect"], "none")
        self.assertIs(report["automatic_action"], False)
        for forbidden in ("promotion", "rank_delta", "delete_action"):
            self.assertNotIn(forbidden, encoded)

    def test_report_digest_tamper_is_detected(self):
        report = memory.aggregate_feedback_report(self.records(), generated_at=NOW)
        report["outcome_counts"]["helpful"] = 99
        with self.assertRaises(memory.MemoryFeedbackError):
            memory.render_feedback_report(report)

    def test_target_rows_are_sorted_and_keep_unresolved_count(self):
        report = memory.aggregate_feedback_report(self.records(), generated_at=NOW)
        refs = [item["target_ref"] for item in report["targets"]]
        self.assertEqual(refs, sorted(refs))
        self.assertTrue(all(item["unresolved"] == item["total"] for item in report["targets"]))


class LifecycleTests(unittest.TestCase):
    def subject(self):
        return {
            "id": "CLM-OLD",
            "statement": "A version-sensitive statement.",
            "confidence": {"level": "C2", "status": "supported"},
            "source_level": "S3",
        }

    def test_default_absent_status_is_active_and_original_is_unchanged(self):
        original = self.subject()
        before = copy.deepcopy(original)
        updated, transition = memory.transition_lifecycle(
            original,
            to_status="deprecated",
            actor_id="human:owner",
            reason="A newer validity check is required.",
            created_at=NOW,
        )
        self.assertEqual(original, before)
        self.assertEqual(transition["from_status"], "active")
        self.assertEqual(updated["lifecycle_status"], "deprecated")

    def test_transition_is_stable_and_attributed(self):
        args = {
            "target_ref": "CLM-A",
            "from_status": "active",
            "to_status": "deprecated",
            "actor_id": "agent:reviewer",
            "reason": "Version is stale.",
            "created_at": NOW,
        }
        one = memory.make_lifecycle_transition(**args)
        two = memory.make_lifecycle_transition(**args)
        self.assertEqual(one, two)
        self.assertEqual(one["actor_id"], "agent:reviewer")
        self.assertEqual(memory.lifecycle_transition_digest(one), memory.lifecycle_transition_digest(two))

    def test_transition_never_encodes_deletion_or_automatic_action(self):
        transition = memory.make_lifecycle_transition(
            target_ref="CLM-A",
            from_status="active",
            to_status="invalidated",
            actor_id="human:x",
            reason="Contradicted by a primary record.",
            created_at=NOW,
        )
        self.assertIs(transition["automatic_action"], False)
        self.assertIs(transition["destructive_action"], False)
        self.assertNotIn("delete", transition)
        self.assertNotIn("trust_effect", transition)

    def test_automatic_or_destructive_transition_fails(self):
        base = memory.make_lifecycle_transition(
            target_ref="CLM-A",
            from_status="active",
            to_status="archived",
            actor_id="human:x",
            reason="No longer in active scope.",
            created_at=NOW,
        )
        for field in ("automatic_action", "destructive_action"):
            with self.subTest(field=field):
                changed = copy.deepcopy(base)
                changed[field] = True
                with self.assertRaises(memory.MemoryFeedbackError):
                    memory.validate_lifecycle_transition(changed)

    def test_superseded_requires_distinct_replacement(self):
        with self.assertRaises(memory.MemoryFeedbackError):
            memory.make_lifecycle_transition(
                target_ref="CLM-A",
                from_status="active",
                to_status="superseded",
                actor_id="human:x",
                reason="Replacement exists.",
                created_at=NOW,
            )
        with self.assertRaises(memory.MemoryFeedbackError):
            memory.make_lifecycle_transition(
                target_ref="CLM-A",
                from_status="active",
                to_status="superseded",
                actor_id="human:x",
                reason="Self replacement is invalid.",
                replacement_ref="CLM-A",
                created_at=NOW,
            )

    def test_replacement_is_rejected_for_non_superseded_status(self):
        with self.assertRaises(memory.MemoryFeedbackError):
            memory.make_lifecycle_transition(
                target_ref="CLM-A",
                from_status="active",
                to_status="deprecated",
                actor_id="human:x",
                reason="Stale.",
                replacement_ref="CLM-B",
                created_at=NOW,
            )

    def test_superseded_projection_records_replacement_prior_state_and_actor(self):
        updated, transition = memory.transition_lifecycle(
            self.subject(),
            to_status="superseded",
            actor_id="human:owner",
            reason="CLM-NEW narrows the valid period.",
            replacement_ref="CLM-NEW",
            created_at=NOW,
        )
        self.assertEqual(updated["replaced_by"], "CLM-NEW")
        self.assertEqual(updated["lifecycle_updated_by"], "human:owner")
        self.assertEqual(updated["lifecycle_history"][0]["from_status"], "active")
        self.assertEqual(updated["lifecycle_history"][0], transition)

    def test_apply_preserves_all_non_lifecycle_data_and_trust(self):
        subject = self.subject()
        updated, _ = memory.transition_lifecycle(
            subject,
            to_status="deprecated",
            actor_id="human:x",
            reason="Stale.",
            created_at=NOW,
        )
        for key, value in subject.items():
            self.assertEqual(updated[key], value)
        self.assertEqual(updated["confidence"], {"level": "C2", "status": "supported"})
        self.assertEqual(updated["source_level"], "S3")

    def test_history_appends_without_deleting_prior_transition(self):
        deprecated, first = memory.transition_lifecycle(
            self.subject(),
            to_status="deprecated",
            actor_id="agent:a",
            reason="Needs checking.",
            created_at="2026-07-12T03:00:00+00:00",
        )
        active, second = memory.transition_lifecycle(
            deprecated,
            to_status="active",
            actor_id="human:b",
            reason="Reverified against the current primary source.",
            created_at="2026-07-12T04:00:00+00:00",
        )
        self.assertEqual(active["lifecycle_history"], [first, second])
        self.assertEqual(active["lifecycle_status"], "active")

    def test_same_transition_apply_is_idempotent(self):
        subject = self.subject()
        transition = memory.make_lifecycle_transition(
            target_ref="CLM-OLD",
            from_status="active",
            to_status="deprecated",
            actor_id="human:x",
            reason="Stale.",
            created_at=NOW,
        )
        once = memory.apply_lifecycle_transition(subject, transition)
        twice = memory.apply_lifecycle_transition(once, transition)
        self.assertEqual(once, twice)
        self.assertEqual(len(twice["lifecycle_history"]), 1)

    def test_unknown_or_delete_status_fails(self):
        for status in ("deleted", "promoted", "unknown"):
            with self.subTest(status=status), self.assertRaises(memory.MemoryFeedbackError):
                memory.make_lifecycle_transition(
                    target_ref="CLM-A",
                    from_status="active",
                    to_status=status,
                    actor_id="human:x",
                    reason="Invalid request.",
                    created_at=NOW,
                )

    def test_reason_is_required(self):
        with self.assertRaises(memory.MemoryFeedbackError):
            memory.make_lifecycle_transition(
                target_ref="CLM-A",
                from_status="active",
                to_status="archived",
                actor_id="human:x",
                reason=" ",
                created_at=NOW,
            )

    def test_unknown_transition_field_and_id_tamper_fail(self):
        transition = memory.make_lifecycle_transition(
            target_ref="CLM-A",
            from_status="active",
            to_status="archived",
            actor_id="human:x",
            reason="Out of scope.",
            created_at=NOW,
        )
        with_extra = copy.deepcopy(transition)
        with_extra["delete"] = True
        with self.assertRaises(memory.MemoryFeedbackError):
            memory.validate_lifecycle_transition(with_extra)
        tampered = copy.deepcopy(transition)
        tampered["id"] = "LCT-000000000000"
        with self.assertRaises(memory.MemoryFeedbackError):
            memory.validate_lifecycle_transition(tampered)

    def test_subject_id_and_prior_state_must_match(self):
        transition = memory.make_lifecycle_transition(
            target_ref="CLM-A",
            from_status="active",
            to_status="deprecated",
            actor_id="human:x",
            reason="Stale.",
            created_at=NOW,
        )
        with self.assertRaises(memory.MemoryFeedbackError):
            memory.apply_lifecycle_transition({"id": "CLM-B"}, transition)
        with self.assertRaises(memory.MemoryFeedbackError):
            memory.apply_lifecycle_transition({"id": "CLM-A", "lifecycle_status": "invalidated"}, transition)

    def test_archived_is_terminal(self):
        with self.assertRaises(memory.MemoryFeedbackError):
            memory.make_lifecycle_transition(
                target_ref="CLM-A",
                from_status="archived",
                to_status="active",
                actor_id="human:x",
                reason="Cannot reopen an archived identity; create a new record.",
                created_at=NOW,
            )


if __name__ == "__main__":
    unittest.main()
