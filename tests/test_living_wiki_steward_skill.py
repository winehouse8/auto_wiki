import os
import re
import unittest
from pathlib import Path

from tools import wiki as wiki_tool


ROOT = Path(__file__).parents[1]
SKILL = ROOT / "skills" / "living-wiki-steward"
SKILL_MD = SKILL / "SKILL.md"
OPENAI_YAML = SKILL / "agents" / "openai.yaml"
SCHEDULED_PROMPT = SKILL / "references" / "scheduled-task-prompt.md"
PRD = ROOT / "wiki" / "specs" / "living-wiki-steward-skill.md"


def frontmatter(text):
    match = re.match(r"\A---\n(.*?)\n---\n", text, re.DOTALL)
    if not match:
        return {}
    result = {}
    for line in match.group(1).splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            result[key.strip()] = value.strip().strip('"')
    return result


class LivingWikiStewardSkillContractTests(unittest.TestCase):
    def test_required_skill_package_exists_without_auxiliary_docs(self):
        self.assertTrue(SKILL_MD.is_file())
        self.assertTrue(OPENAI_YAML.is_file())
        self.assertTrue(SCHEDULED_PROMPT.is_file())
        forbidden = {"README.md", "INSTALLATION_GUIDE.md", "QUICK_REFERENCE.md", "CHANGELOG.md"}
        self.assertFalse(forbidden & {path.name for path in SKILL.rglob("*") if path.is_file()})

    def test_trigger_metadata_is_specific_and_frontmatter_is_minimal(self):
        metadata = frontmatter(SKILL_MD.read_text(encoding="utf-8"))
        self.assertEqual(set(metadata), {"name", "description"})
        self.assertEqual(metadata["name"], "living-wiki-steward")
        description = metadata["description"].casefold()
        for term in ("예약", "위생", "반복 연구", "자가 발전", "living wiki"):
            with self.subTest(term=term):
                self.assertIn(term, description)

    def test_body_routes_to_prd_and_covers_required_workflow(self):
        text = SKILL_MD.read_text(encoding="utf-8")
        self.assertLess(len(text.splitlines()), 500)
        required = (
            "wiki/specs/living-wiki-steward-skill.md",
            "wiki/index.md",
            "python3 tools/wiki.py status",
            "python3 tools/wiki.py memory-hygiene",
            "python3 tools/wiki.py interest-seed",
            "python3 tools/wiki.py next-task",
            "python3 tools/wiki.py lint",
            "python3 tools/wiki.py language-validate",
            "python3 tools/wiki.py validate",
            "python3 tools/wiki.py okf-validate",
            "python3 -m unittest discover -s tests -v",
            "python3 tools/wiki.py release-check",
            "최대 하나",
            "반증 검색",
            "정확한 locator",
            "중요한 변경 없음",
        )
        folded = text.casefold()
        for term in required:
            with self.subTest(term=term):
                self.assertIn(term.casefold(), folded)

    def test_skill_forbids_unsafe_scheduled_actions(self):
        text = SKILL_MD.read_text(encoding="utf-8").casefold()
        for phrase in (
            "raw 원문을 삭제하지",
            "신뢰를 자동 승격하지",
            "외부에 공개하지",
            "자격증명을 사용하지",
            "승인하지",
            "production_certified=false",
            "의미적 관련성",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_scheduled_prompt_invokes_skill_and_sets_bounded_delta_contract(self):
        text = SCHEDULED_PROMPT.read_text(encoding="utf-8")
        self.assertIn("$living-wiki-steward", text)
        self.assertIn("독립 실행", text.casefold())
        self.assertIn("도래한 캠페인 하나", text.casefold())
        self.assertIn("중요한 변경", text.casefold())
        self.assertIn("권한을 확장하지", text.casefold())
        for phrase in (
            "Asia/Seoul",
            "RRULE:FREQ=DAILY;BYHOUR=20;BYMINUTE=0",
            "Wiki 하네스 연구",
            "Agent/Training 논문 연구",
            "project_id",
            "research_brief",
            "Apple M4·16GB",
            "구독을 API credit으로 간주하지",
            "fast-forward-only",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase.casefold(), text.casefold())

    def test_prd_separates_invocation_work_and_reliance_axes(self):
        text = PRD.read_text(encoding="utf-8")
        for phrase in (
            "호출 방식",
            "예약 호출",
            "수동 호출",
            "작업 종류",
            "위생",
            "지속 연구",
            "독립 검증",
            "하네스 개선",
            "Wiki 의존도 정책",
            "사용자에게 선택 메뉴로 요구하지",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase.casefold(), text.casefold())

    def test_skill_is_one_front_door_with_two_user_routes(self):
        text = SKILL_MD.read_text(encoding="utf-8")
        folded = text.casefold()
        self.assertNotIn("## 실행 모드 하나 선택하기", text)
        for phrase in (
            "호출 방식부터 정하기",
            "예약 호출",
            "수동 호출",
            "사용자에게 내부 이름을 선택하도록 요구하지",
            "Wiki 의존도 정책",
            "위생 → 도래한 관심사 → 캠페인 최대 하나 → 검증 → 차이 보고",
            "수동 응답",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase.casefold(), folded)

    def test_scheduled_prompt_fixes_route_order_and_noninteractive_behavior(self):
        text = SCHEDULED_PROMPT.read_text(encoding="utf-8").casefold()
        for phrase in (
            "호출 방식은 예약",
            "wiki 의존도 정책은 `wiki-first`",
            "먼저 위생",
            "도래한 관심사",
            "최대 하나",
            "검증한 뒤",
            "대화형 확인을 기다리지",
            "예약 작업 받은 편지함",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase.casefold(), text)

    def test_ui_default_prompt_is_a_clear_manual_single_intent(self):
        text = OPENAI_YAML.read_text(encoding="utf-8")
        self.assertIn("$living-wiki-steward", text)
        self.assertIn("오늘 Living Wiki 상태를 점검", text)
        self.assertNotIn("위생·연구 주기", text)

    def test_readme_exposes_the_simple_user_journey(self):
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        for phrase in (
            "가장 단순한 관리 사용자 경험",
            "예약 프롬프트를 한 번 수동 시험",
            "Codex 예약 작업 화면",
            "내부 모드를 고르지",
            "이 주제를 매주 조사해줘",
            "기존 결론과 독립적으로 확인해줘",
            "canonical 원본을 가리키는 링크",
            "기존 개인 Skill을 덮어쓰지",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_openai_interface_matches_skill(self):
        text = OPENAI_YAML.read_text(encoding="utf-8")
        self.assertIn('display_name: "Living Wiki 관리인"', text)
        self.assertRegex(text, r'short_description: ".{25,64}"')
        self.assertIn("$living-wiki-steward", text)

    def test_prd_has_all_acceptance_ids_and_entrypoints_link_it(self):
        text = PRD.read_text(encoding="utf-8")
        acceptance_ids = re.findall(r"`(AC-LWS-\d{3})`:", text)
        self.assertEqual(acceptance_ids, [f"AC-LWS-{number:03d}" for number in range(1, 41)])
        for entrypoint in (ROOT / "README.md", ROOT / "AGENTS.md"):
            self.assertIn("wiki/specs/living-wiki-steward-skill.md", entrypoint.read_text(encoding="utf-8"))

    def test_prd_v1_5_contracts_hygiene_time_github_daily_research_and_projects(self):
        text = PRD.read_text(encoding="utf-8")
        required = (
            "버전: `1.5.0`",
            "전체 상태·비예약 문서",
            "최근 문서 N개",
            "최대 2-hop",
            "전체 노드 상한",
            "선택 이유",
            "경로",
            "논리 충돌",
            "자동 evidence·신뢰·생명주기 효과가 없다",
            "같은 입력과 고정 시각",
            "OKF `timestamp`",
            "created_at",
            "last_verified_at",
            "freshness",
            "lifecycle_updated_at",
            "단순 render와 confidence 재계산",
            "GitHub PR 전달",
            "draft 사람 검토 PR",
            "token read 전에 검증",
            "지역 날짜",
            "미배정 우선",
            "research_brief",
            "Apple M4·16GB",
            "매일 20:00",
            "Wiki 하네스 연구",
            "Agent/Training 논문 연구",
            "project_id",
            "전역 원장에 한 번만",
            "wiki/projects/",
        )
        for term in required:
            with self.subTest(term=term):
                self.assertIn(term.casefold(), text.casefold())

    def test_skill_runs_a_read_only_bounded_hygiene_plan_before_deep_review(self):
        text = SKILL_MD.read_text(encoding="utf-8")
        hygiene_section = text.split("## 위생 작업 실행하기", 1)[1].split("## 반복 연구 진행하기", 1)[0]
        folded = hygiene_section.casefold()
        required = (
            "python3 tools/wiki.py hygiene-plan --now <NOW>",
            "상위 후보",
            "점진적으로",
            "hop",
            "노드",
            "쌍",
            "예산",
            "자동 신뢰 효과가 없음",
        )
        for term in required:
            with self.subTest(term=term):
                self.assertIn(term.casefold(), folded)

    def test_personal_install_resolves_to_canonical_source_when_present(self):
        codex_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
        installed = codex_home / "skills" / "living-wiki-steward"
        if not installed.exists():
            self.skipTest("personal skill installation is environment-specific")
        if installed.resolve() == SKILL.resolve():
            return

        def package_bytes(root):
            return {
                path.relative_to(root).as_posix(): path.read_bytes()
                for path in sorted(root.rglob("*"))
                if path.is_file() and "__pycache__" not in path.parts
            }

        self.assertEqual(
            package_bytes(installed.resolve()),
            package_bytes(SKILL.resolve()),
            "linked worktree에서는 설치 링크 대상이 달라도 canonical Skill 바이트가 같아야 한다",
        )

    def test_release_manifest_binds_skill_and_prd_bytes(self):
        manifest = wiki_tool.harness_component_manifest()
        self.assertIn("skills/living-wiki-steward/SKILL.md", manifest)
        self.assertIn("wiki/specs/living-wiki-steward-skill.md", manifest)


if __name__ == "__main__":
    unittest.main()
