import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
MODULE_PATH = ROOT / "tools" / "calibration.py"
FIXTURE_PATH = ROOT / "evaluations" / "fixtures" / "calibration-gold.json"
SPEC = importlib.util.spec_from_file_location("living_wiki_calibration", MODULE_PATH)
calibration = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(calibration)


def vote(group, label):
    return {"reviewer_group": group, "label": label}


def gold(record_id="G-1", level="C2", predicted="supported", adjudications=None):
    return {
        "id": record_id,
        "domain": "Science",
        "level": level,
        "predicted_label": predicted,
        "adjudications": adjudications
        or [vote("human:a", "supported"), vote("agent:independent", "supported")],
    }


def full_counter_search():
    return {"checks": ["origin", "status", "contradiction"]}


def candidate(candidate_id="C-1", **overrides):
    value = {
        "id": candidate_id,
        "title": "Primary source",
        "url": f"https://example.org/{candidate_id.casefold()}",
        "provenance_verified": True,
        "counter_search": full_counter_search(),
    }
    value.update(overrides)
    return value


class WilsonAndCalibrationTests(unittest.TestCase):
    def test_wilson_zero_trials_is_none(self):
        self.assertIsNone(calibration.wilson_interval(0, 0))

    def test_wilson_interval_is_bounded_and_not_wald(self):
        low, high = calibration.wilson_interval(1, 1)
        self.assertGreater(low, 0.0)
        self.assertEqual(high, 1.0)

    def test_wilson_rejects_invalid_counts(self):
        with self.assertRaises(calibration.CalibrationError):
            calibration.wilson_interval(2, 1)

    def test_duplicate_same_group_vote_is_ignored(self):
        record = gold(
            adjudications=[
                vote("human:a", "supported"),
                vote("human:a", "supported"),
                vote("agent:b", "supported"),
            ]
        )
        result = calibration.resolve_gold_record(record)
        self.assertEqual(result["status"], "resolved")
        self.assertEqual(result["duplicate_votes_ignored"], 1)
        self.assertEqual(result["adjudicator_groups"], 2)

    def test_strict_majority_resolves_three_adjudicators(self):
        record = gold(
            adjudications=[
                vote("human:a", "mixed"),
                vote("human:b", "mixed"),
                vote("agent:c", "supported"),
            ]
        )
        result = calibration.resolve_gold_record(record)
        self.assertEqual(result["label"], "mixed")
        self.assertEqual(result["agreement"], 0.666667)

    def test_tied_adjudication_is_disputed(self):
        record = gold(
            adjudications=[vote("human:a", "supported"), vote("human:b", "contradicted")]
        )
        result = calibration.resolve_gold_record(record)
        self.assertEqual(result["status"], "disputed")
        self.assertEqual(result["reason"], "no_strict_majority")

    def test_conflicting_duplicate_group_is_disputed(self):
        record = gold(
            adjudications=[
                vote("human:a", "supported"),
                vote("human:a", "contradicted"),
                vote("agent:b", "supported"),
            ]
        )
        result = calibration.resolve_gold_record(record)
        self.assertEqual(result["status"], "disputed")
        self.assertIn("human:a", result["conflicting_groups"])

    def test_declared_disputed_item_stays_disputed(self):
        record = gold()
        record["benchmark_status"] = "disputed"
        result = calibration.resolve_gold_record(record)
        self.assertEqual(result["status"], "disputed")
        self.assertEqual(result["reason"], "benchmark_marked_disputed")

    def test_invalid_gold_label_is_rejected(self):
        record = gold(adjudications=[vote("human:a", "true"), vote("human:b", "true")])
        with self.assertRaises(calibration.CalibrationError):
            calibration.resolve_gold_record(record)

    def test_calibration_excludes_dispute_and_tracks_abstention(self):
        disputed = gold("G-2")
        disputed["benchmark_status"] = "disputed"
        abstained = gold("G-3", predicted=None)
        report = calibration.calibration_report([gold(), disputed, abstained])
        self.assertEqual(report["coverage"]["total_records"], 3)
        self.assertEqual(report["coverage"]["disputed_records"], 1)
        self.assertEqual(report["coverage"]["abstained_resolved_records"], 1)
        self.assertEqual(report["overall"]["n"], 1)

    def test_calibration_report_declares_ordinal_not_probability(self):
        report = calibration.calibration_report([gold()])
        self.assertFalse(report["interpretation"]["c_levels_are_probabilities"])
        self.assertIn("ordinal", report["interpretation"]["scale"])

    def test_level_domain_matrix_includes_empty_cells(self):
        report = calibration.calibration_report([gold()])
        matrix = report["p_correct_given_level_domain"]
        self.assertEqual(len(matrix), 5)
        c0 = next(row for row in matrix if row["level"] == "C0")
        self.assertEqual(c0["n"], 0)
        self.assertIsNone(c0["p_correct"])

    def test_small_n_is_explicit_even_with_wilson_interval(self):
        report = calibration.calibration_report([gold()], small_n_threshold=3)
        self.assertTrue(report["overall"]["small_n"])
        self.assertIsNotNone(report["overall"]["wilson_95"])

    def test_duplicate_gold_ids_are_rejected(self):
        with self.assertRaises(calibration.CalibrationError):
            calibration.calibration_report([gold(), gold()])


class CanonicalizationTests(unittest.TestCase):
    def test_doi_variants_have_one_identity(self):
        variants = [
            "10.1000/ABC",
            "doi:10.1000/abc",
            "https://doi.org/10.1000/AbC",
        ]
        self.assertEqual(
            {calibration.canonicalize_doi(value) for value in variants},
            {"10.1000/abc"},
        )

    def test_invalid_doi_is_rejected(self):
        with self.assertRaises(calibration.CalibrationError):
            calibration.canonicalize_doi("not-a-doi")

    def test_url_drops_fragment_tracking_and_default_port(self):
        value = "HTTPS://Example.COM:443/a/../b/?z=2&utm_source=x&a=1#section"
        self.assertEqual(
            calibration.canonicalize_url(value),
            "https://example.com/b?a=1&z=2",
        )

    def test_url_keeps_semantic_query(self):
        first = calibration.canonicalize_url("https://example.org/search?q=wiki&page=2")
        second = calibration.canonicalize_url("https://example.org/search?page=2&q=wiki")
        self.assertEqual(first, second)
        self.assertIn("page=2", first)

    def test_url_with_credentials_is_rejected(self):
        with self.assertRaises(calibration.CalibrationError):
            calibration.canonicalize_url("https://user:secret@example.org/path")

    def test_github_repository_variants_have_one_identity(self):
        variants = [
            "Owner/Repo",
            "git@github.com:OWNER/REPO.git",
            "https://github.com/owner/repo/tree/main",
        ]
        self.assertEqual(
            {calibration.canonicalize_repository(value) for value in variants},
            {"https://github.com/owner/repo"},
        )

    def test_gitlab_nested_group_is_preserved(self):
        self.assertEqual(
            calibration.canonicalize_repository(
                "https://gitlab.com/group/subgroup/repo/-/tree/main"
            ),
            "https://gitlab.com/group/subgroup/repo",
        )

    def test_unsupported_repository_host_is_rejected(self):
        with self.assertRaises(calibration.CalibrationError):
            calibration.canonicalize_repository("https://example.org/owner/repo")


class IndependenceAndRegistryTests(unittest.TestCase):
    def test_shared_doi_clusters_sources(self):
        sources = [
            {"id": "A", "doi": "10.1000/x"},
            {"id": "B", "doi": "https://doi.org/10.1000/X"},
        ]
        result = calibration.cluster_independence(sources)
        self.assertEqual(result["cluster_count"], 1)
        self.assertEqual(result["membership"]["A"], result["membership"]["B"])

    def test_explicit_derivation_clusters_sources(self):
        sources = [
            {"id": "ORIGIN", "url": "https://example.org/release"},
            {
                "id": "NEWS",
                "url": "https://news.example.org/story",
                "derived_from": "ORIGIN",
            },
        ]
        result = calibration.cluster_independence(sources)
        self.assertEqual(result["membership"]["ORIGIN"], result["membership"]["NEWS"])
        links = result["clusters"][0]["links"]
        self.assertTrue(any(link["reason"] == "explicit_derived_from" for link in links))

    def test_publisher_overlap_alone_does_not_cluster(self):
        sources = [
            {"id": "A", "url": "https://example.org/a", "publisher": "Same"},
            {"id": "B", "url": "https://example.org/b", "publisher": "Same"},
        ]
        result = calibration.cluster_independence(sources)
        self.assertEqual(result["cluster_count"], 2)

    def test_invalid_identity_is_auditable_not_fatal_to_cluster_report(self):
        result = calibration.cluster_independence([{"id": "BAD", "url": "relative"}])
        self.assertEqual(result["cluster_count"], 1)
        self.assertEqual(result["identity_errors"][0]["source_id"], "BAD")

    def test_fixture_registry_matches_canonical_doi(self):
        registry = calibration.FixtureStatusRegistry(
            [{"identifier": "doi:10.1000/x", "status": "active"}]
        )
        result = registry.lookup({"doi": "https://doi.org/10.1000/X"})
        self.assertEqual(result["status"], "active")
        self.assertEqual(result["adapter"], "offline-fixture-registry")

    def test_registry_uses_safest_status_when_identifiers_disagree(self):
        registry = calibration.FixtureStatusRegistry(
            [
                {"identifier": "doi:10.1000/x", "status": "active"},
                {"identifier": "url:https://example.org/x", "status": "retracted"},
            ]
        )
        result = registry.lookup({"doi": "10.1000/x", "url": "https://example.org/x"})
        self.assertEqual(result["status"], "retracted")

    def test_conflicting_registry_entries_are_rejected(self):
        with self.assertRaises(calibration.CalibrationError):
            calibration.FixtureStatusRegistry(
                [
                    {"identifier": "doi:10.1000/x", "status": "active"},
                    {"identifier": "doi:10.1000/X", "status": "retracted"},
                ]
            )


class AdmissionTests(unittest.TestCase):
    def setUp(self):
        self.registry = calibration.FixtureStatusRegistry(
            [
                {"identifier": "doi:10.1000/active", "status": "active"},
                {"identifier": "doi:10.1000/retracted", "status": "retracted"},
                {"identifier": "doi:10.1000/corrected", "status": "corrected"},
            ]
        )

    def test_counter_search_coverage_reports_missing_dimensions(self):
        result = calibration.counter_search_coverage({"checks": ["origin", "unrelated"]})
        self.assertEqual(result["coverage"], 0.333333)
        self.assertEqual(result["missing"], ["contradiction", "status"])

    def test_clean_source_is_allowed(self):
        result = calibration.admission_decision(candidate(), registry=self.registry)
        self.assertEqual(result["decision"], "allow")

    def test_retracted_source_is_rejected(self):
        value = candidate("C-R", doi="10.1000/retracted")
        value.pop("url")
        result = calibration.admission_decision(value, registry=self.registry)
        self.assertEqual(result["decision"], "reject")
        self.assertIn("registry_terminal_status", [reason["code"] for reason in result["reasons"]])

    def test_malformed_identifier_is_rejected_without_registry_crash(self):
        value = candidate("C-BAD", url="relative/path")
        result = calibration.admission_decision(value, registry=self.registry)
        self.assertEqual(result["decision"], "reject")
        self.assertEqual(result["registry"]["status"], "not_checked_invalid")

    def test_incomplete_counter_search_requires_review(self):
        value = candidate("C-Q", counter_search={"checks": ["origin"]})
        result = calibration.admission_decision(value, registry=self.registry)
        self.assertEqual(result["decision"], "review")
        self.assertIn("counter_search_incomplete", [reason["code"] for reason in result["reasons"]])

    def test_unverified_provenance_requires_review(self):
        result = calibration.admission_decision(
            candidate("C-P", provenance_verified=False), registry=self.registry
        )
        self.assertEqual(result["decision"], "review")

    def test_corrected_status_requires_review(self):
        value = candidate("C-C", doi="10.1000/corrected", registry_required=True)
        value.pop("url")
        result = calibration.admission_decision(value, registry=self.registry)
        self.assertEqual(result["decision"], "review")
        self.assertIn("registry_requires_review", [reason["code"] for reason in result["reasons"]])

    def test_exact_duplicate_requires_review_not_reject(self):
        existing = [{"id": "S-OLD", "doi": "10.1000/active"}]
        value = candidate("C-DUP", doi="https://doi.org/10.1000/ACTIVE")
        value.pop("url")
        result = calibration.admission_decision(
            value, registry=self.registry, existing_sources=existing
        )
        self.assertEqual(result["decision"], "review")
        self.assertIn("duplicate_existing_source", [reason["code"] for reason in result["reasons"]])

    def test_derived_source_requires_independence_review(self):
        origin = {"id": "S-ORIGIN", "url": "https://example.org/origin"}
        value = candidate("C-DERIVED", derived_from=["S-ORIGIN"])
        clustered = calibration.cluster_independence([origin, value])
        result = calibration.admission_decision(
            value,
            registry=self.registry,
            existing_sources=[origin],
            independence=clustered,
        )
        self.assertEqual(result["decision"], "review")
        self.assertIn(
            "derived_independence_collision", [reason["code"] for reason in result["reasons"]]
        )


class FixtureAndCliTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    def test_fixture_exercises_all_admission_decisions(self):
        report = calibration.build_report(self.fixture)
        self.assertEqual(report["admission"]["counts"], {"allow": 2, "review": 4, "reject": 2})
        self.assertFalse(report["trust_policy_mutated"])

    def test_fixture_has_domains_levels_dispute_and_abstention(self):
        report = calibration.build_report(self.fixture)
        self.assertEqual(set(report["calibration"]["by_domain"]), {"policy", "science", "software"})
        self.assertEqual(set(report["calibration"]["by_level"]), set(calibration.CLAIM_LEVELS))
        self.assertEqual(report["calibration"]["coverage"]["disputed_records"], 1)
        self.assertEqual(report["calibration"]["coverage"]["abstained_resolved_records"], 1)

    def test_complete_report_is_deterministic(self):
        first = calibration.canonical_json(calibration.build_report(self.fixture))
        second = calibration.canonical_json(calibration.build_report(self.fixture))
        self.assertEqual(first, second)

    def test_cli_stdout_is_deterministic_json(self):
        command = [
            sys.executable,
            str(MODULE_PATH),
            "report",
            "--input",
            str(FIXTURE_PATH),
            "--compact",
        ]
        first = subprocess.run(command, check=True, capture_output=True, text=True)
        second = subprocess.run(command, check=True, capture_output=True, text=True)
        self.assertEqual(first.stdout, second.stdout)
        self.assertEqual(json.loads(first.stdout)["schema_version"], calibration.SCHEMA_VERSION)
        self.assertEqual(first.stderr, "")

    def test_cli_invalid_fixture_has_machine_readable_error_and_exit_two(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.json"
            path.write_text("[]", encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(MODULE_PATH), "report", "--input", str(path), "--compact"],
                check=False,
                capture_output=True,
                text=True,
            )
        self.assertEqual(result.returncode, 2)
        self.assertIn("error", json.loads(result.stderr))


if __name__ == "__main__":
    unittest.main()
