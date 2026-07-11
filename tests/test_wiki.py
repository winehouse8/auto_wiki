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


class EventChainTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.old = (wiki.ROOT, wiki.STATE, wiki.RAW, wiki.WIKI, wiki.REPORTS, wiki.EVALUATIONS, wiki.OKF_BUNDLE)
        root = Path(self.temp.name)
        wiki.ROOT = root
        wiki.STATE = root / "state"
        wiki.RAW = root / "raw" / "sources"
        wiki.WIKI = root / "wiki"
        wiki.REPORTS = root / "reports"
        wiki.EVALUATIONS = root / "evaluations"
        wiki.OKF_BUNDLE = wiki.WIKI
        wiki.ensure_layout()

    def tearDown(self):
        wiki.ROOT, wiki.STATE, wiki.RAW, wiki.WIKI, wiki.REPORTS, wiki.EVALUATIONS, wiki.OKF_BUNDLE = self.old
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


if __name__ == "__main__":
    unittest.main()
