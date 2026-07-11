import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SPEC = importlib.util.spec_from_file_location("living_wiki", Path(__file__).parents[1] / "tools" / "wiki.py")
wiki = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(wiki)


def source(source_id, group, level, markers=None):
    return {
        "id": source_id,
        "status": "active",
        "independence_group": group,
        "source_level": level,
        "assessment": {"quality_markers": markers or []},
    }


def edge(source_id, relation="supports", strength=3):
    return {
        "source_id": source_id,
        "relation": relation,
        "locator": "p.1",
        "strength": strength,
    }


class ConfidenceTests(unittest.TestCase):
    def base_claim(self):
        return {
            "id": "CLM-1",
            "created_by": "agent:writer",
            "created_by_group": "model-family-a",
            "evidence": [],
        }

    def test_no_evidence_is_c0(self):
        result = wiki.calculate_confidence(self.base_claim(), {}, [])
        self.assertEqual(result["level"], "C0")
        self.assertEqual(result["status"], "open")

    def test_single_attributed_source_is_c1(self):
        claim = self.base_claim()
        claim["evidence"] = [edge("SRC-A", strength=2)]
        result = wiki.calculate_confidence(claim, {"SRC-A": source("SRC-A", "G1", "S2")}, [])
        self.assertEqual(result["level"], "C1")

    def test_two_independent_sources_reach_c2(self):
        claim = self.base_claim()
        claim["evidence"] = [edge("SRC-A", strength=2), edge("SRC-B", strength=2)]
        sources = {
            "SRC-A": source("SRC-A", "G1", "S2"),
            "SRC-B": source("SRC-B", "G2", "S2"),
        }
        result = wiki.calculate_confidence(claim, sources, [])
        self.assertEqual(result["level"], "C2")
        self.assertEqual(result["supporting_groups"], 2)

    def test_c3_requires_independent_review(self):
        claim = self.base_claim()
        claim["evidence"] = [edge("SRC-A"), edge("SRC-B")]
        sources = {
            "SRC-A": source("SRC-A", "G1", "S3"),
            "SRC-B": source("SRC-B", "G2", "S2"),
        }
        self.assertEqual(wiki.calculate_confidence(claim, sources, [])["level"], "C2")
        reviews = [
            {
                "claim_id": "CLM-1",
                "actor_id": "human:reviewer",
                "reviewer_group": "human:reviewer",
                "verdict": "supports",
                "adversarial": False,
                "status": "active",
            }
        ]
        self.assertEqual(wiki.calculate_confidence(claim, sources, reviews)["level"], "C3")

    def test_c4_requires_two_reviewers_and_robust_marker(self):
        claim = self.base_claim()
        claim["evidence"] = [edge("SRC-A"), edge("SRC-B")]
        sources = {
            "SRC-A": source("SRC-A", "G1", "S4", ["peer-reviewed"]),
            "SRC-B": source("SRC-B", "G2", "S3", ["reproduced"]),
        }
        reviews = [
            {
                "claim_id": "CLM-1",
                "actor_id": "human:reviewer",
                "reviewer_group": "human:reviewer",
                "verdict": "supports",
                "adversarial": True,
                "status": "active",
            },
            {
                "claim_id": "CLM-1",
                "actor_id": "agent:independent",
                "reviewer_group": "model-family-b",
                "verdict": "supports",
                "adversarial": False,
                "status": "active",
            },
        ]
        self.assertEqual(wiki.calculate_confidence(claim, sources, reviews)["level"], "C4")

    def test_strong_contradiction_caps_promotion_and_marks_contested(self):
        claim = self.base_claim()
        claim["evidence"] = [edge("SRC-A"), edge("SRC-B"), edge("SRC-C", "contradicts")]
        sources = {
            "SRC-A": source("SRC-A", "G1", "S4", ["peer-reviewed"]),
            "SRC-B": source("SRC-B", "G2", "S3"),
            "SRC-C": source("SRC-C", "G3", "S3"),
        }
        reviews = [
            {
                "claim_id": "CLM-1",
                "actor_id": "human:reviewer",
                "reviewer_group": "human:reviewer",
                "verdict": "supports",
                "adversarial": True,
                "status": "active",
            }
        ]
        result = wiki.calculate_confidence(claim, sources, reviews)
        self.assertEqual(result["level"], "C2")
        self.assertEqual(result["status"], "contested")
        self.assertTrue(result["strong_contradiction"])

    def test_inactive_source_does_not_contribute_to_confidence(self):
        claim = self.base_claim()
        claim["evidence"] = [edge("SRC-A")]
        inactive = source("SRC-A", "G1", "S4", ["peer-reviewed"])
        inactive["lifecycle_status"] = "invalidated"
        result = wiki.calculate_confidence(claim, {"SRC-A": inactive}, [])
        self.assertEqual(result["level"], "C0")
        self.assertEqual(result["supporting_groups"], 0)


class EventChainTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.old = (
            wiki.ROOT,
            wiki.STATE,
            wiki.RAW,
            wiki.QUARANTINE,
            wiki.WIKI,
            wiki.REPORTS,
            wiki.EVALUATIONS,
            wiki.EVALUATION_REPORTS,
            wiki.OKF_BUNDLE,
        )
        root = Path(self.temp.name)
        wiki.ROOT = root
        wiki.STATE = root / "state"
        wiki.RAW = root / "raw" / "sources"
        wiki.QUARANTINE = root / "raw" / "quarantine"
        wiki.WIKI = root / "wiki"
        wiki.REPORTS = root / "reports"
        wiki.EVALUATIONS = root / "evaluations"
        wiki.EVALUATION_REPORTS = wiki.EVALUATIONS / "reports"
        wiki.OKF_BUNDLE = wiki.WIKI
        wiki.ensure_layout()

    def tearDown(self):
        (
            wiki.ROOT,
            wiki.STATE,
            wiki.RAW,
            wiki.QUARANTINE,
            wiki.WIKI,
            wiki.REPORTS,
            wiki.EVALUATIONS,
            wiki.EVALUATION_REPORTS,
            wiki.OKF_BUNDLE,
        ) = self.old
        self.temp.cleanup()

    def test_valid_chain(self):
        wiki.append_event("agent:test", "one", "A")
        wiki.append_event("agent:test", "two", "B")
        errors = []
        self.assertEqual(wiki.verify_event_chain(errors), 2)
        self.assertEqual(errors, [])

    def test_tamper_is_detected(self):
        wiki.append_event("agent:test", "one", "A")
        path = wiki.STATE / "events.jsonl"
        event = json.loads(path.read_text(encoding="utf-8"))
        event["subject"] = "tampered"
        path.write_text(json.dumps(event) + "\n", encoding="utf-8")
        errors = []
        wiki.verify_event_chain(errors)
        self.assertTrue(any("invalid event_hash" in error for error in errors))


class MemoryControlPlaneTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.old = (
            wiki.ROOT,
            wiki.STATE,
            wiki.RAW,
            wiki.QUARANTINE,
            wiki.WIKI,
            wiki.REPORTS,
            wiki.EVALUATIONS,
            wiki.EVALUATION_REPORTS,
            wiki.OKF_BUNDLE,
        )
        root = Path(self.temp.name)
        wiki.ROOT = root
        wiki.STATE = root / "state"
        wiki.RAW = root / "raw" / "sources"
        wiki.QUARANTINE = root / "raw" / "quarantine"
        wiki.WIKI = root / "wiki"
        wiki.REPORTS = root / "reports"
        wiki.EVALUATIONS = root / "evaluations"
        wiki.EVALUATION_REPORTS = wiki.EVALUATIONS / "reports"
        wiki.OKF_BUNDLE = wiki.WIKI
        wiki.ensure_layout()
        wiki.atomic_write_json(
            wiki.STATE / "actors.json",
            {
                "version": 1,
                "actors": [
                    {
                        "id": "agent:test",
                        "kind": "agent",
                        "display_name": "Test agent",
                        "roles": ["maintainer"],
                        "status": "active",
                        "metadata": {"independence_group": "test"},
                    },
                    {
                        "id": "agent:contributor",
                        "kind": "agent",
                        "display_name": "Contributor",
                        "roles": ["contributor"],
                        "status": "active",
                        "metadata": {"independence_group": "test-contributor"},
                    },
                ],
            },
        )
        wiki.save_collection(
            "claims",
            [
                {"id": "CLM-OLD", "lifecycle_status": "active"},
                {"id": "CLM-NEW", "lifecycle_status": "active"},
            ],
        )

    def tearDown(self):
        (
            wiki.ROOT,
            wiki.STATE,
            wiki.RAW,
            wiki.QUARANTINE,
            wiki.WIKI,
            wiki.REPORTS,
            wiki.EVALUATIONS,
            wiki.EVALUATION_REPORTS,
            wiki.OKF_BUNDLE,
        ) = self.old
        self.temp.cleanup()

    def test_feedback_add_and_resolve_are_attributed_and_audit_only(self):
        add_args = type(
            "Args",
            (),
            {
                "actor": "agent:test",
                "task_ref": "TASK-123",
                "targets": "CLM-OLD",
                "outcome": "harmful",
                "rationale": "The retrieved claim did not apply to this scoped task.",
                "evidence_refs": "CLM-NEW",
                "at": "2026-07-12T00:00:00+00:00",
            },
        )()
        wiki.memory_feedback_add(add_args)
        payload = wiki.load_json(wiki.STATE / "memory_feedback.json")
        self.assertEqual(set(payload), {"version", "feedback"})
        record = payload["feedback"][0]
        self.assertEqual(record["trust_effect"], "none")
        self.assertFalse(record["automatic_action"])
        resolve_args = type(
            "Args",
            (),
            {
                "actor": "agent:test",
                "feedback": record["id"],
                "rationale": "Reviewed against the replacement claim.",
                "at": "2026-07-12T01:00:00+00:00",
            },
        )()
        wiki.memory_feedback_resolve(resolve_args)
        resolved = wiki.collection("memory_feedback")[0]
        self.assertEqual(resolved["status"], "resolved")
        self.assertEqual(resolved["resolution"]["actor_id"], "agent:test")
        self.assertTrue(
            any(
                event["subject"] == record["id"]
                and event["details"].get("state_digest")
                for event in wiki.event_lines()
            )
        )

    def test_lifecycle_supersession_is_non_destructive_and_anchored(self):
        args = type(
            "Args",
            (),
            {
                "actor": "agent:test",
                "kind": "claim",
                "id": "CLM-OLD",
                "status": "superseded",
                "reason": "A narrower replacement preserves the corrected scope.",
                "replacement": "CLM-NEW",
                "at": "2026-07-12T00:00:00+00:00",
            },
        )()
        wiki.knowledge_lifecycle(args)
        claims = {item["id"]: item for item in wiki.collection("claims")}
        self.assertEqual(set(claims), {"CLM-OLD", "CLM-NEW"})
        self.assertEqual(claims["CLM-OLD"]["lifecycle_status"], "superseded")
        self.assertEqual(claims["CLM-OLD"]["replaced_by"], "CLM-NEW")
        transition = claims["CLM-OLD"]["lifecycle_history"][0]
        self.assertFalse(transition["automatic_action"])
        self.assertFalse(transition["destructive_action"])
        self.assertTrue(any(event["subject"] == transition["id"] for event in wiki.event_lines()))

    def test_lifecycle_transition_is_role_gated_not_species_gated(self):
        args = type(
            "Args",
            (),
            {
                "actor": "agent:contributor",
                "kind": "claim",
                "id": "CLM-OLD",
                "status": "archived",
                "reason": "Attempt without lifecycle authority.",
                "replacement": None,
                "at": "2026-07-12T00:00:00+00:00",
            },
        )()
        with self.assertRaises(wiki.WikiError):
            wiki.knowledge_lifecycle(args)


class ProposalGovernanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.old = (
            wiki.ROOT,
            wiki.STATE,
            wiki.RAW,
            wiki.QUARANTINE,
            wiki.WIKI,
            wiki.REPORTS,
            wiki.EVALUATIONS,
            wiki.EVALUATION_REPORTS,
            wiki.OKF_BUNDLE,
        )
        root = Path(self.temp.name)
        wiki.ROOT = root
        wiki.STATE = root / "state"
        wiki.RAW = root / "raw" / "sources"
        wiki.QUARANTINE = root / "raw" / "quarantine"
        wiki.WIKI = root / "wiki"
        wiki.REPORTS = root / "reports"
        wiki.EVALUATIONS = root / "evaluations"
        wiki.EVALUATION_REPORTS = wiki.EVALUATIONS / "reports"
        wiki.OKF_BUNDLE = wiki.WIKI
        wiki.ensure_layout()
        wiki.atomic_write_json(
            wiki.STATE / "actors.json",
            {
                "version": 1,
                "actors": [
                    {
                        "id": "human:owner",
                        "kind": "human",
                        "display_name": "Owner",
                        "roles": ["policy-approver"],
                        "status": "active",
                        "metadata": {"independence_group": "human:owner"},
                    },
                    {
                        "id": "agent:writer",
                        "kind": "agent",
                        "display_name": "Writer",
                        "roles": ["contributor"],
                        "status": "active",
                        "metadata": {"independence_group": "model-a"},
                    },
                ],
            },
        )
        (root / "config").mkdir(exist_ok=True)
        wiki.atomic_write_json(root / "config" / "wiki.json", {"harness_version": "4.1.0"})
        self.proposal = {
            "id": "RFC-1",
            "title": "Test change",
            "problem": "A reproducible problem",
            "proposed_change": "A minimal change",
            "evidence": [],
            "benchmark": "Tests pass",
            "risks": ["regression"],
            "rollback": "Disable it",
            "created_by": "agent:writer",
            "created_at": "2026-01-01T00:00:00+00:00",
            "status": "proposed",
            "approvals": [],
        }
        wiki.save_collection("proposals", [self.proposal])

    def tearDown(self):
        (
            wiki.ROOT,
            wiki.STATE,
            wiki.RAW,
            wiki.QUARANTINE,
            wiki.WIKI,
            wiki.REPORTS,
            wiki.EVALUATIONS,
            wiki.EVALUATION_REPORTS,
            wiki.OKF_BUNDLE,
        ) = self.old
        self.temp.cleanup()

    @staticmethod
    def args(actor="human:owner", decision="approve"):
        return type(
            "Args",
            (),
            {"actor": actor, "proposal": "RFC-1", "decision": decision, "rationale": "Explicit review"},
        )()

    def test_policy_approver_can_approve(self):
        wiki.proposal_review(self.args())
        proposal = wiki.collection("proposals")[0]
        self.assertEqual(proposal["status"], "approved")
        self.assertEqual(proposal["approvals"][0]["actor_id"], "human:owner")

    def test_non_approver_cannot_approve(self):
        with self.assertRaises(wiki.WikiError):
            wiki.proposal_review(self.args(actor="agent:writer"))

    def test_same_review_is_idempotent(self):
        wiki.proposal_review(self.args())
        wiki.proposal_review(self.args())
        self.assertEqual(len(wiki.collection("proposals")[0]["approvals"]), 1)

    def test_implemented_requires_passing_non_certifying_release_report(self):
        wiki.proposal_review(self.args())
        report_path = wiki.EVALUATION_REPORTS / "v4-release-report.json"
        gates = [{"name": "memory_feedback_lifecycle_hygiene", "passed": True}]
        harness_manifest = wiki.harness_component_manifest()
        report = {
            "release_id": "living-wiki-v4",
            "passed": True,
            "production_certified": False,
            "harness_version": "4.1.0",
            "component_fingerprint": wiki.digest_text(wiki.canonical_json(gates)),
            "gates": gates,
            "harness_manifest_sha256": wiki.digest_text(wiki.canonical_json(harness_manifest)),
            "harness_file_count": len(harness_manifest),
        }
        report["report_digest"] = wiki.digest_text(wiki.canonical_json(report))
        wiki.atomic_write_json(report_path, report)
        wiki.append_event(
            "human:owner",
            "release.evaluate",
            "living-wiki-v4",
            {
                "component_fingerprint": report["component_fingerprint"],
                "report_digest": report["report_digest"],
            },
        )
        args = type(
            "Args",
            (),
            {"actor": "human:owner", "proposal": "RFC-1", "release_report": str(report_path)},
        )()
        wiki.proposal_implement(args)
        proposal = wiki.collection("proposals")[0]
        self.assertEqual(proposal["status"], "implemented")
        self.assertFalse(proposal["implementation_evidence"]["production_certified"])

        newer_gates = [
            {"name": "memory_feedback_lifecycle_hygiene", "passed": True},
            {"name": "regression_tests", "passed": True},
        ]
        newer = {
            **{key: value for key, value in report.items() if key != "report_digest"},
            "component_fingerprint": wiki.digest_text(wiki.canonical_json(newer_gates)),
            "gates": newer_gates,
        }
        newer["report_digest"] = wiki.digest_text(wiki.canonical_json(newer))
        wiki.atomic_write_json(report_path, newer)
        wiki.append_event(
            "human:owner",
            "release.evaluate",
            "living-wiki-v4",
            {
                "component_fingerprint": newer["component_fingerprint"],
                "report_digest": newer["report_digest"],
            },
        )
        wiki.proposal_implement(args)
        resealed = wiki.collection("proposals")[0]
        self.assertEqual(
            resealed["implementation_evidence"]["component_fingerprint"],
            newer["component_fingerprint"],
        )
        self.assertIn("revalidated_at", resealed)

    def test_implementation_rejects_unanchored_or_external_report(self):
        wiki.proposal_review(self.args())
        outside = Path(self.temp.name) / "forged.json"
        outside.write_text("{}", encoding="utf-8")
        args = type(
            "Args",
            (),
            {"actor": "human:owner", "proposal": "RFC-1", "release_report": str(outside)},
        )()
        with self.assertRaises(wiki.WikiError):
            wiki.proposal_implement(args)


class IntegratedGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.old = (
            wiki.ROOT,
            wiki.STATE,
            wiki.RAW,
            wiki.QUARANTINE,
            wiki.WIKI,
            wiki.REPORTS,
            wiki.EVALUATIONS,
            wiki.EVALUATION_REPORTS,
            wiki.OKF_BUNDLE,
        )
        root = Path(self.temp.name)
        wiki.ROOT = root
        wiki.STATE = root / "state"
        wiki.RAW = root / "raw" / "sources"
        wiki.QUARANTINE = root / "raw" / "quarantine"
        wiki.WIKI = root / "wiki"
        wiki.REPORTS = root / "reports"
        wiki.EVALUATIONS = root / "evaluations"
        wiki.EVALUATION_REPORTS = wiki.EVALUATIONS / "reports"
        wiki.OKF_BUNDLE = wiki.WIKI
        wiki.ensure_layout()
        wiki.save_collection(
            "actors",
            [
                {
                    "id": "agent:test",
                    "kind": "agent",
                    "display_name": "Test Agent",
                    "roles": ["researcher"],
                    "capabilities": ["submit"],
                    "status": "active",
                    "metadata": {"independence_group": "test-group"},
                }
            ],
        )

    def tearDown(self):
        (
            wiki.ROOT,
            wiki.STATE,
            wiki.RAW,
            wiki.QUARANTINE,
            wiki.WIKI,
            wiki.REPORTS,
            wiki.EVALUATIONS,
            wiki.EVALUATION_REPORTS,
            wiki.OKF_BUNDLE,
        ) = self.old
        self.temp.cleanup()

    def test_security_screen_quarantines_without_source_promotion(self):
        candidate = wiki.ROOT / "candidate.txt"
        candidate.write_text("A plain research note with no executable instruction.", encoding="utf-8")
        args = type(
            "Args",
            (),
            {
                "actor": "agent:test",
                "input": str(candidate),
                "source_ref": "fixture:plain-note",
                "media_type": "text/plain",
                "extracted_text": None,
            },
        )()
        wiki.security_screen(args)
        admissions = wiki.collection("admissions")
        self.assertEqual(len(admissions), 1)
        self.assertEqual(admissions[0]["status"], "allow")
        self.assertEqual(wiki.collection("sources"), [])
        artifact = wiki.ROOT / admissions[0]["candidate"]["quarantine_artifact"]["path"]
        self.assertTrue(artifact.is_file())
        self.assertEqual(wiki.digest_file(artifact), admissions[0]["candidate"]["quarantine_artifact"]["sha256"])

    def test_completed_external_report_accounts_usage_once(self):
        wiki.save_collection(
            "campaigns",
            [
                {
                    "id": "CMP-1",
                    "status": "active",
                    "max_minutes": 20,
                    "max_sources": 2,
                    "runtime": {},
                }
            ],
        )
        action = {
            "id": "ACT-1",
            "campaign_id": "CMP-1",
            "external_work": True,
            "execution": "planned_only",
            "budget": {"minutes": 10, "sources": 1},
        }
        wiki.save_collection(
            "runs",
            [
                {
                    "id": "RUN-1",
                    "actor_id": "agent:test",
                    "status": "planned",
                    "plan": {"actions": [action]},
                    "receipt": {"side_effect_count": 0},
                    "external_receipts": [],
                }
            ],
        )
        args = type(
            "Args",
            (),
            {
                "actor": "agent:test",
                "run": "RUN-1",
                "action": "ACT-1",
                "status": "completed",
                "evidence": "SRC-1",
                "notes": "Externally completed and reported.",
                "used_minutes": 7,
                "used_sources": 1,
            },
        )()
        wiki.run_action_report(args)
        wiki.run_action_report(args)
        runtime = wiki.collection("campaigns")[0]["runtime"]
        self.assertEqual(runtime["used_minutes"], 7)
        self.assertEqual(runtime["used_sources"], 1)
        self.assertEqual(len(wiki.collection("runs")[0]["external_receipts"]), 1)

    def test_source_writer_requires_matching_allow_admission(self):
        base = {
            "actor": "agent:test",
            "title": "Admitted official page",
            "url": "https://example.org/reference",
            "file": None,
            "security_admission": None,
            "source_type": "official-doc",
            "authors": None,
            "publisher": "Example",
            "published": "2026-01-01",
            "publication_status": "active",
            "independence_group": None,
            "level": "S1",
            "rationale": "Identity and scope were checked.",
            "quality_markers": "official",
            "conflicts": None,
            "license": None,
            "notes": None,
        }
        with self.assertRaises(wiki.WikiError):
            wiki.source_add(type("Args", (), {**base, "admission": None})())
        decision = {"decision": "allow"}
        admission_id = wiki.stable_id("ADM", "CAND-1", wiki.canonical_json(decision))
        admission = {
            "id": admission_id,
            "candidate": {"id": "CAND-1", "title": base["title"], "url": base["url"]},
            "decision": decision,
            "status": "allow",
            "created_by": "agent:test",
            "created_at": "2026-01-01T00:00:00+00:00",
            "policy_effect": "advisory_only",
        }
        admission["record_digest"] = wiki.admission_record_digest(admission)
        wiki.save_collection(
            "admissions",
            [admission],
        )
        wiki.append_event(
            "agent:test",
            "source.admission.evaluate",
            admission_id,
            {"decision": "allow", "record_digest": admission["record_digest"]},
        )
        wiki.source_add(type("Args", (), {**base, "admission": admission_id})())
        source = wiki.collection("sources")[0]
        self.assertEqual(source["admission_ids"], [admission_id])

    def test_interest_seed_is_due_bounded_and_idempotent(self):
        config = wiki.ROOT / "config"
        config.mkdir(parents=True)
        wiki.atomic_write_json(
            config / "interests.json",
            {
                "interests": [
                    {
                        "id": "INT-1",
                        "priority": 1.0,
                        "cadence_days": 7,
                        "questions": ["What new counterevidence exists?"],
                    }
                ]
            },
        )
        wiki.atomic_write_json(
            config / "wiki.json",
            {
                "research_limits": {
                    "default_max_sources_per_cycle": 4,
                    "default_max_minutes_per_cycle": 20,
                    "min_independent_source_groups": 2,
                    "stop_after_no_novel_claim_rounds": 2,
                }
            },
        )
        args = type(
            "Args",
            (),
            {"actor": "agent:test", "now": "2026-07-12T00:00:00+00:00", "max_campaigns": 1},
        )()
        wiki.interest_seed(args)
        wiki.interest_seed(args)
        campaigns = wiki.collection("campaigns")
        self.assertEqual(len(campaigns), 1)
        self.assertEqual(campaigns[0]["status"], "queued")
        self.assertEqual(campaigns[0]["max_sources"], 4)


class UtilityTests(unittest.TestCase):
    def test_stable_id_is_deterministic(self):
        self.assertEqual(wiki.stable_id("CLM", "x", "y"), wiki.stable_id("CLM", "x", "y"))

    def test_slugify_preserves_korean_and_ascii(self):
        self.assertEqual(wiki.slugify("Human-Agent 공동 Wiki!"), "human-agent-공동-wiki")

    def test_okf_frontmatter_parser_requires_mapping(self):
        metadata, body, errors = wiki.split_okf_frontmatter(
            "---\ntype: Concept\ntitle: Test\ntags: [a, b]\n---\n# Body\n"
        )
        self.assertEqual(errors, [])
        self.assertEqual(metadata["type"], "Concept")
        self.assertIn("# Body", body)

    def test_okf_frontmatter_missing_is_detected(self):
        _, _, errors = wiki.split_okf_frontmatter("# No frontmatter\n")
        self.assertTrue(errors)

    def test_admission_integrity_detects_status_or_decision_tamper(self):
        decision = {"decision": "review", "reasons": [{"code": "duplicate"}]}
        item = {
            "id": wiki.stable_id("ADM", "CAND-1", wiki.canonical_json(decision)),
            "candidate": {"id": "CAND-1", "title": "Candidate"},
            "decision": decision,
            "status": "review",
            "created_by": "agent:test",
            "created_at": "2026-01-01T00:00:00+00:00",
            "policy_effect": "advisory_only",
        }
        item["record_digest"] = wiki.admission_record_digest(item)
        self.assertEqual(wiki.admission_integrity_findings(item), [])
        item["status"] = "allow"
        self.assertTrue(wiki.admission_integrity_findings(item))

    def test_external_report_digest_detects_payload_tamper(self):
        report = {
            "receipt_id": "EXT-1",
            "status": "completed",
            "notes": "original",
            "verification_status": "unverified_report",
        }
        report["report_digest"] = wiki.external_report_digest(report)
        self.assertEqual(report["report_digest"], wiki.external_report_digest(report))
        report["notes"] = "tampered"
        self.assertNotEqual(report["report_digest"], wiki.external_report_digest(report))


if __name__ == "__main__":
    unittest.main()
