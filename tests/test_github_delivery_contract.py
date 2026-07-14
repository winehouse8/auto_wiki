import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
DELIVERY_SPEC = ROOT / "wiki" / "specs" / "github-delivery.md"
HARNESS_SPEC = ROOT / "wiki" / "specs" / "harness-ux.md"
LWS_PRD = ROOT / "wiki" / "specs" / "living-wiki-steward-skill.md"
DELIVERY_CONFIG = ROOT / "config" / "github-delivery.json"
WORKFLOW = ROOT / ".github" / "workflows" / "wiki-pr-quality.yml"
CODEOWNERS = ROOT / ".github" / "CODEOWNERS"
SKILL = ROOT / "skills" / "living-wiki-steward" / "SKILL.md"
SCHEDULED_PROMPT = (
    ROOT
    / "skills"
    / "living-wiki-steward"
    / "references"
    / "scheduled-task-prompt.md"
)

EXPECTED_APPROVAL_REFS = {
    "COL-27B9ADD786ED",
    "RFC-03F4FE85BB44",
}

PROTECTED_CONTROL_SURFACES = {
    ".github/**",
    "AGENTS.md",
    "governance/**",
    "config/**",
    "tools/**",
    "scripts/**",
    "prompts/**",
    "skills/**",
    "tests/**",
    "wiki/specs/**",
}


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def top_level_yaml_block(text: str, key: str) -> list[str]:
    """Return non-comment lines in a simple top-level YAML mapping block.

    The project intentionally has no mandatory YAML dependency, so this contract
    inspects only the small workflow subset it owns.
    """

    lines = text.splitlines()
    start = next(
        (index for index, line in enumerate(lines) if line.rstrip() == f"{key}:"),
        None,
    )
    if start is None:
        return []
    block: list[str] = []
    for line in lines[start + 1 :]:
        if line and not line[0].isspace():
            break
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            block.append(stripped)
    return block


class GitHubDeliverySpecificationContractTests(unittest.TestCase):
    def test_narrow_spec_is_linked_and_owns_all_acceptance_ids(self):
        github_spec = read(DELIVERY_SPEC)
        harness = read(HARNESS_SPEC)
        prd = read(LWS_PRD)

        self.assertIn("SPEC-GH-DELIVERY-001", github_spec)
        self.assertIn("버전: `1.2.0`", github_spec)
        self.assertIn("RFC-7A0959853525", github_spec)
        self.assertIn("github-delivery.md", harness)
        self.assertIn("github-delivery.md", prd)
        self.assertIn("SPEC-GH-DELIVERY-001", prd)

        acceptance_ids = re.findall(r"`(AC-GH-\d{3})`:", github_spec)
        self.assertEqual(
            acceptance_ids,
            [f"AC-GH-{number:03d}" for number in range(1, 36)],
        )

    def test_lws_prd_connects_delivery_acceptance_criteria_23_through_28(self):
        prd = read(LWS_PRD)
        ids = set(re.findall(r"`(AC-LWS-\d{3})`:", prd))
        self.assertTrue(
            {f"AC-LWS-{number:03d}" for number in range(23, 29)} <= ids
        )
        for phrase in (
            "PR 번호·head SHA",
            "auto-merge",
            "draft 사람 검토 PR",
            "token read 전에 검증",
            "PR URL 또는 전달 차단",
            "production_certified=false",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase.casefold(), prd.casefold())


class GitHubDeliveryConfigurationContractTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(
            DELIVERY_CONFIG.is_file(),
            "SPEC-GH-DELIVERY-001의 버전 관리 설정이 필요하다",
        )
        self.config = json.loads(read(DELIVERY_CONFIG))

    def test_exact_repository_branch_merge_and_approval_scope(self):
        required = {
            "repository",
            "base_branch",
            "branch_prefix",
            "merge_method",
            "approval_refs",
            "safe_path_patterns",
            "protected_path_patterns",
            "bootstrap",
        }
        self.assertTrue(required <= set(self.config))
        self.assertEqual(self.config["repository"], "winehouse8/auto_wiki")
        self.assertEqual(self.config["base_branch"], "main")
        self.assertEqual(self.config["branch_prefix"], "wiki-auto/")
        self.assertEqual(self.config["merge_method"], "squash")
        self.assertEqual(set(self.config["approval_refs"]), EXPECTED_APPROVAL_REFS)

    def test_path_classification_and_bootstrap_consumption_are_explicit(self):
        safe = self.config["safe_path_patterns"]
        protected = self.config["protected_path_patterns"]
        self.assertIsInstance(safe, list)
        self.assertIsInstance(protected, list)
        self.assertTrue(safe)
        self.assertTrue(all(isinstance(item, str) and item for item in safe))
        self.assertTrue(all(isinstance(item, str) and item for item in protected))
        self.assertTrue(any(pattern.startswith("wiki/") for pattern in safe))
        self.assertTrue(PROTECTED_CONTROL_SURFACES <= set(protected))
        self.assertFalse(set(safe) & set(protected))

        bootstrap = self.config["bootstrap"]
        self.assertIsInstance(bootstrap, dict)
        self.assertIn("consumed", bootstrap)
        self.assertIs(type(bootstrap["consumed"]), bool)

        wiki_config = json.loads(read(ROOT / "config" / "wiki.json"))
        quarantine = wiki_config.get("quarantine_distribution", {})
        self.assertEqual(quarantine.get("mode"), "local-only-metadata-in-git")
        self.assertEqual(quarantine.get("path"), "raw/quarantine")
        self.assertEqual(
            quarantine.get("public_repository"),
            "winehouse8/auto_wiki",
        )
        self.assertEqual(
            quarantine.get("missing_artifact_policy"),
            "anchored-content-addressed-admission-only",
        )
        self.assertEqual(
            quarantine.get("default_validation_profile"),
            "strict-local-custody",
        )
        self.assertEqual(
            quarantine.get("portable_validation_profile"),
            "public-clean-clone",
        )

    def test_exact_one_hop_policy_transition_state_matches_active_policy(self):
        transition = self.config.get("policy_transition")
        self.assertIsInstance(transition, dict)
        self.assertEqual(
            transition.get("from_policy_version"),
            "SPEC-GH-DELIVERY-001/v1.1.0",
        )
        self.assertEqual(
            transition.get("to_policy_version"),
            "SPEC-GH-DELIVERY-001/v1.2.0",
        )
        active_policy = self.config.get("policy_version")
        expected_states = {
            "SPEC-GH-DELIVERY-001/v1.1.0": "armed",
            "SPEC-GH-DELIVERY-001/v1.2.0": "consumed",
        }
        self.assertIn(active_policy, expected_states)
        self.assertEqual(transition.get("state"), expected_states[active_policy])
        self.assertEqual(transition.get("mode"), "human-review-only")
        self.assertIn("COL-B80046FC1C56", transition.get("approval_refs", []))
        self.assertIn("RFC-7A0959853525", transition.get("rfc_ids", []))


class GitHubPullRequestQualityWorkflowContractTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(
            WORKFLOW.is_file(),
            "비밀 없는 pull_request 품질 workflow가 필요하다",
        )
        self.text = read(WORKFLOW)
        self.folded = self.text.casefold()

    def test_trigger_and_permissions_are_unprivileged(self):
        self.assertRegex(self.text, r"(?m)^on:\s*$")
        self.assertRegex(self.text, r"(?m)^\s{2}pull_request:\s*$")
        self.assertNotIn("pull_request_target", self.folded)

        permissions = top_level_yaml_block(self.text, "permissions")
        self.assertEqual(permissions, ["contents: read"])
        self.assertNotRegex(self.folded, r"(?m)^\s*[^#\n]+:\s*write\s*$")
        self.assertNotIn("${{ secrets.", self.folded)
        self.assertNotIn("gh pr merge", self.folded)

    def test_all_external_actions_are_pinned_to_full_commit_sha(self):
        action_refs = re.findall(
            r"(?m)^\s*(?:-\s*)?uses:\s*([^\s#]+)", self.text
        )
        self.assertTrue(action_refs, "최소 checkout action을 명시해야 한다")
        self.assertTrue(any(ref.startswith("actions/checkout@") for ref in action_refs))
        for ref in action_refs:
            if ref.startswith("./"):
                continue
            with self.subTest(action=ref):
                self.assertRegex(ref, r"^[^/@\s]+/[^@\s]+@[0-9a-f]{40}$")

    def test_workflow_calls_the_complete_repository_quality_gate(self):
        required_commands = (
            "python3 tools/wiki.py evaluate",
            "python3 tools/wiki.py render",
            "python3 tools/wiki.py memory-hygiene --now",
            "python3 tools/wiki.py hygiene-plan --now",
            "python3 tools/wiki.py lint",
            "python3 tools/wiki.py language-validate",
            "python3 tools/wiki.py validate",
            "python3 tools/wiki.py okf-validate",
            "python3 -m unittest discover -s tests -v",
            "python3 tools/wiki.py release-check",
        )
        for command in required_commands:
            with self.subTest(command=command):
                self.assertIn(command, self.text)
        self.assertIn("python3 tools/wiki.py render --no-log", self.text)
        self.assertIn(
            "python3 tools/wiki.py lint --quarantine-profile public-clean-clone",
            self.text,
        )
        self.assertIn(
            "python3 tools/wiki.py validate --quarantine-profile public-clean-clone",
            self.text,
        )
        self.assertIn(
            "python3 tools/wiki.py release-check --quarantine-profile public-clean-clone",
            self.text,
        )
        self.assertRegex(
            self.text,
            r"python3 tools/wiki\.py lint --quarantine-profile public-clean-clone --check-only",
        )
        self.assertRegex(
            self.text,
            r"python3 tools/wiki\.py release-check --quarantine-profile public-clean-clone --check-only",
        )
        release_position = self.text.index("release-check --quarantine-profile public-clean-clone --check-only")
        self.assertIn("git diff --exit-code", self.text[release_position:])
        self.assertIn(
            "git status --porcelain=v1 --untracked-files=all",
            self.text[release_position:],
        )
        self.assertNotRegex(
            self.text,
            r"(?m)^\s*python3 tools/wiki\.py render\s*$",
        )


class GitHubCodeOwnersContractTests(unittest.TestCase):
    def test_control_surfaces_have_explicit_human_ownership(self):
        self.assertTrue(CODEOWNERS.is_file(), "GitHub 제어면 CODEOWNERS가 필요하다")
        entries: list[tuple[str, list[str]]] = []
        for raw_line in read(CODEOWNERS).splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            fields = line.split()
            self.assertGreaterEqual(len(fields), 2)
            entries.append((fields[0], fields[1:]))

        self.assertTrue(entries)
        for pattern, owners in entries:
            with self.subTest(pattern=pattern):
                self.assertIn("@winehouse8", owners)

        patterns = [pattern.casefold().lstrip("/") for pattern, _ in entries]
        for fragment in (
            ".github",
            "agents.md",
            "governance",
            "config",
            "tools",
            "scripts",
            "prompts",
            "skills",
            "tests",
            "wiki/specs",
        ):
            with self.subTest(fragment=fragment):
                self.assertTrue(
                    any(fragment in pattern for pattern in patterns),
                    f"{fragment} 제어면의 명시적 소유자가 없다",
                )


class LivingWikiStewardGitHubDeliveryUxContractTests(unittest.TestCase):
    def test_skill_orders_begin_work_validate_publish(self):
        text = read(SKILL)
        self.assertIn("SPEC-GH-DELIVERY-001", text)

        begin = text.casefold().find("begin")
        work = text.casefold().find("작업", begin + 1)
        validate = text.casefold().find("검증", work + 1)
        publish = text.casefold().find("publish", validate + 1)
        self.assertGreaterEqual(begin, 0)
        self.assertGreater(work, begin)
        self.assertGreater(validate, work)
        self.assertGreater(publish, validate)

    def test_skill_explains_no_op_and_human_review_without_unsafe_calls(self):
        text = read(SKILL)
        folded = text.casefold()
        for phrase in (
            "중요한 변경 없음",
            "commit이나 PR을 만들지",
            "사람 검토 필요",
            "draft PR",
            "검토 이유",
            "영향",
            "검증법",
            "롤백",
            "PR URL",
            "전달 차단",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase.casefold(), folded)
        self.assertRegex(
            folded,
            r"사람 검토[^\n]{0,300}(?:approve|ready|merge)[^\n]{0,100}(?:않|금지)",
        )

    def test_scheduled_prompt_delivers_after_validation_and_reports_receipt(self):
        prompt = read(SCHEDULED_PROMPT)
        folded = prompt.casefold()
        for phrase in (
            "GitHub 실행 시작",
            "검증 → GitHub 전달 → 차이 보고",
            "PR URL",
            "전달 차단",
            "commit이나 PR을 만들지",
            "사람 검토 필요",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase.casefold(), folded)


if __name__ == "__main__":
    unittest.main()
