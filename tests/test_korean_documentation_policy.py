import re
import inspect
import os
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
SPEC = ROOT / "wiki" / "specs" / "korean-documentation-policy.md"
SKILL = ROOT / "skills" / "living-wiki-steward"


class KoreanDocumentationPolicyTests(unittest.TestCase):
    def test_policy_is_linked_from_human_and_agent_entrypoints(self):
        for path in (ROOT / "README.md", ROOT / "AGENTS.md"):
            text = path.read_text(encoding="utf-8")
            self.assertIn("wiki/specs/korean-documentation-policy.md", text)
            self.assertIn("한국어", text)

    def test_core_skill_surfaces_are_korean(self):
        paths = (
            ROOT / "wiki" / "specs" / "harness-ux.md",
            ROOT / "wiki" / "specs" / "living-wiki-steward-skill.md",
            SKILL / "SKILL.md",
            SKILL / "references" / "scheduled-task-prompt.md",
            SKILL / "agents" / "openai.yaml",
        )
        for path in paths:
            with self.subTest(path=path.relative_to(ROOT)):
                text = path.read_text(encoding="utf-8")
                self.assertRegex(text, r"[가-힣]")
                english_only_prose = [
                    line
                    for line in text.splitlines()
                    if re.search(r"(?:[A-Za-z]+[ -]+){5,}[A-Za-z]+", line)
                    and not re.search(r"[가-힣]", line)
                    and not line.lstrip().startswith(("```", "# 인용", "["))
                ]
                self.assertEqual([], english_only_prose[:5])

    def test_rendered_router_and_labels_are_korean(self):
        index = (ROOT / "wiki" / "index.md").read_text(encoding="utf-8")
        dashboard = (ROOT / "wiki" / "epistemic-dashboard.md").read_text(encoding="utf-8")
        for phrase in ("시작하기", "지식 상태 시각", "출처 문서", "개념 문서"):
            self.assertIn(phrase, index)
        for phrase in ("인식론 대시보드", "주장", "출처", "증거 상태"):
            self.assertIn(phrase, dashboard)

    def test_deterministic_document_language_gate_passes(self):
        from tools import korean_docs

        findings = korean_docs.validate_repository(ROOT)
        self.assertEqual([], findings, "\n".join(findings[:30]))

    def test_policy_keeps_machine_and_source_exceptions_explicit(self):
        text = SPEC.read_text(encoding="utf-8")
        for term in ("코드", "명령", "ID", "URL", "해시", "스키마", "외부 원제", "원문 인용"):
            self.assertIn(term, text)
        for number in range(1, 13):
            self.assertIn(f"AC-KO-{number:03d}", text)

    def test_gate_rejects_english_prose_but_preserves_explicit_exceptions(self):
        from tools import korean_docs

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ui = root / "skills" / "living-wiki-steward" / "agents"
            ui.mkdir(parents=True)
            (ui / "openai.yaml").write_text(
                'interface:\n  display_name: "리빙 위키 관리인"\n'
                '  short_description: "신뢰 가능한 위키를 관리하고 발전시킴"\n'
                '  default_prompt: "$living-wiki-steward로 위키 위생을 실행해줘."\n',
                encoding="utf-8",
            )
            (root / "README.md").write_text(
                "# 한국어 계약\n\n`python3 tools/wiki.py validate`와 `RFC-ABC123`, "
                "https://example.com은 원형을 유지한다.\n",
                encoding="utf-8",
            )
            self.assertEqual([], korean_docs.validate_repository(root))

            (root / "BAD.md").write_text(
                "# 한국어 제목\n\nThis ordinary documentation sentence is written only in English words.\n",
                encoding="utf-8",
            )
            findings = korean_docs.validate_repository(root)
            self.assertTrue(any("BAD.md:3" in item and "KO-DOC-004" in item for item in findings))
            self.assertTrue(all("한국어" in item or "일반 문장" in item for item in findings))

    def test_external_source_title_may_remain_original(self):
        from tools import korean_docs

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ui = root / "skills" / "living-wiki-steward" / "agents"
            ui.mkdir(parents=True)
            (ui / "openai.yaml").write_text(
                'interface:\n  display_name: "리빙 위키 관리인"\n'
                '  short_description: "신뢰 가능한 위키를 관리하고 발전시킴"\n'
                '  default_prompt: "$living-wiki-steward로 위키를 관리해줘."\n',
                encoding="utf-8",
            )
            source = root / "wiki" / "sources" / "source.md"
            source.parent.mkdir(parents=True)
            source.write_text(
                "---\ntype: Reference\ntitle: An Exact External Source Title\n"
                "description: 외부 출처의 정규 원제와 한국어 설명.\n---\n\n"
                "# An Exact External Source Title\n\n## 출처 설명\n\n원제는 추적성을 위해 유지한다.\n",
                encoding="utf-8",
            )
            self.assertEqual([], korean_docs.validate_repository(root))

    def test_gate_cannot_be_bypassed_by_links_tables_short_lines_or_comments(self):
        from tools import korean_docs

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ui = root / "skills" / "living-wiki-steward" / "agents"
            ui.mkdir(parents=True)
            (ui / "openai.yaml").write_text(
                'interface:\n  display_name: "English Display Name" # 한국어 주석\n'
                '  short_description: "한국어 짧은 설명"\n',
                encoding="utf-8",
            )
            (root / "BYPASS.md").write_text(
                "<!-- 자동 생성 문서라고 주장함 -->\n# 한국어 제목\n\ngenerated: true\n\n"
                "- [Only English Link Label](https://example.com)\n\n"
                "| 항목 | 값 |\n|---|---|\n| 첫째 | English table body sentence here |\n\n"
                "Short English sentence here.\n\n```text\nignored but fence is never closed\n",
                encoding="utf-8",
            )
            findings = korean_docs.validate_repository(root)
            joined = "\n".join(findings)
            for location in ("BYPASS.md:6", "BYPASS.md:10", "BYPASS.md:12"):
                self.assertTrue(
                    any(location in item and "KO-DOC-004" in item for item in findings),
                    location,
                )
            self.assertIn("BYPASS.md:15 [KO-DOC-007]", joined)
            self.assertIn("display_name 사용자 표시 값", joined)
            self.assertIn("필수 사용자 표시 필드 default_prompt", joined)

    def test_human_readable_diagram_fences_are_checked_but_code_fences_are_not(self):
        from tools import korean_docs

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "DIAGRAM.md").write_text(
                "# 한국어 다이어그램\n\n"
                "```text\nUntrusted source inbox\n-> bounded research campaign\n```\n\n"
                "```mermaid\ngraph TD\n  A[English review queue] --> B[한국어 승인]\n```\n\n"
                "```bash\npython3 tools/wiki.py language-validate\n```\n",
                encoding="utf-8",
            )
            findings = korean_docs.validate_repository(root)
            joined = "\n".join(findings)
            self.assertIn("DIAGRAM.md:4 [KO-DOC-010]", joined)
            self.assertIn("DIAGRAM.md:5 [KO-DOC-010]", joined)
            self.assertIn("DIAGRAM.md:10 [KO-DOC-010]", joined)
            self.assertNotIn("DIAGRAM.md:14", joined)

    def test_frontmatter_quotes_tables_and_short_lists_cannot_bypass_the_gate(self):
        from tools import korean_docs

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ui = root / "skills" / "mixed" / "agents"
            ui.mkdir(parents=True)
            (ui / "openai.yaml").write_text(
                'interface:\n  display_name: "가 English Display Name Here"\n'
                '  short_description: "한국어 짧은 설명"\n'
                '  default_prompt: "한국어 기본 프롬프트"\n',
                encoding="utf-8",
            )
            (root / "BYPASS_CONTEXT.md").write_text(
                "---\ntype: Note\ntitle: 한국어 제목\n"
                "description: 한국어 설명\nsummary: English summary only\n---\n\n"
                "# 한국어 본문\n\n- English bullet\n\n"
                "| 항목 | 값 |\n|---|---|\n"
                "| 링크 | [English external label](https://example.com) |\n\n"
                "원문 출처: `SRC-ABC123`\n\n"
                "> English quote without locator\n",
                encoding="utf-8",
            )
            (root / "UNPIPED.md").write_text(
                "# 한국어 표\n\n항목 | 값\n--- | ---\n"
                "ID | This is explanatory prose\n\n- Read more.\n",
                encoding="utf-8",
            )
            findings = korean_docs.validate_repository(root)
            joined = "\n".join(findings)
            self.assertIn("BYPASS_CONTEXT.md:5 [KO-DOC-002]", joined)
            self.assertIn("BYPASS_CONTEXT.md:10 [KO-DOC-004]", joined)
            self.assertIn("BYPASS_CONTEXT.md:14 [KO-DOC-004]", joined)
            self.assertIn("BYPASS_CONTEXT.md:18 [KO-DOC-004]", joined)
            self.assertIn("UNPIPED.md:5 [KO-DOC-004]", joined)
            self.assertIn("UNPIPED.md:7 [KO-DOC-004]", joined)
            self.assertIn("skills/mixed/agents/openai.yaml:2 [KO-DOC-006]", joined)

    def test_empty_locator_and_token_korean_cannot_bypass_the_gate(self):
        from tools import korean_docs

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "MIXED.md").write_text(
                "---\ntype: Note\ntitle: 한국어 제목\ndescription: 한국어 설명\n"
                "summary: 가 English dominated summary text here\n---\n\n"
                "# 한국어 본문\n\n## 가 English heading with too many words here\n\n"
                "- Continue.\n\n원문 출처: `SRC-ABC123`; locator:\n\n"
                "> English quoted words\n",
                encoding="utf-8",
            )
            findings = korean_docs.validate_repository(root)
            joined = "\n".join(findings)
            self.assertIn("MIXED.md:5 [KO-DOC-002]", joined)
            self.assertIn("MIXED.md:10 [KO-DOC-005]", joined)
            self.assertIn("MIXED.md:12 [KO-DOC-004]", joined)
            self.assertIn("MIXED.md:16 [KO-DOC-004]", joined)

    def test_exact_original_quote_requires_and_accepts_provenance_marker(self):
        from tools import korean_docs

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ui = root / "skills" / "living-wiki-steward" / "agents"
            ui.mkdir(parents=True)
            (ui / "openai.yaml").write_text(
                'interface:\n  display_name: "Living Wiki 관리인"\n'
                '  short_description: "신뢰 가능한 위키를 관리하고 발전시킴"\n'
                '  default_prompt: "$living-wiki-steward로 위키를 관리해줘."\n',
                encoding="utf-8",
            )
            (root / "QUOTE.md").write_text(
                "# 인용 보존\n\n원문 출처: `SRC-ABC123`, locator `p. 3`\n\n"
                "> This exact external quotation remains in its original language.\n",
                encoding="utf-8",
            )
            self.assertEqual([], korean_docs.validate_repository(root))

            (root / "UNMARKED.md").write_text(
                "# 인용 거부\n\n> This quotation has no source or exact locator marker.\n",
                encoding="utf-8",
            )
            findings = korean_docs.validate_repository(root)
            self.assertTrue(any("UNMARKED.md:3" in item and "KO-DOC-004" in item for item in findings))

            (root / "SCOPED.md").write_text(
                "# 인용 범위\n\n원문 출처: `SRC-ABC123`, locator `p. 3`\n\n"
                "## 다른 절\n\n> This unrelated quotation must not inherit the earlier marker.\n",
                encoding="utf-8",
            )
            findings = korean_docs.validate_repository(root)
            self.assertTrue(any("SCOPED.md:7" in item and "KO-DOC-004" in item for item in findings))

    def test_frontmatter_setext_wrapping_and_all_skill_ui_are_checked(self):
        from tools import korean_docs

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first_ui = root / "skills" / "one" / "agents"
            first_ui.mkdir(parents=True)
            (first_ui / "openai.yaml").write_text(
                'interface:\n  display_name: "한국어 관리인"\n'
                '  short_description: "한국어 짧은 설명"\n'
                '  default_prompt: "한국어 기본 프롬프트"\n',
                encoding="utf-8",
            )
            second_ui = root / "skills" / "two" / "agents"
            second_ui.mkdir(parents=True)
            (second_ui / "openai.yaml").write_text(
                'interface:\n  display_name: "English Name" # 한국어 주석\n'
                '  short_description: "English short description"\n'
                '  default_prompt: "English default prompt"\n',
                encoding="utf-8",
            )
            (root / "MULTI_OK.md").write_text(
                "---\ntype: Note\ntitle: 한국어 제목\ndescription: |\n  여러 줄 한국어 설명이다.\n---\n\n본문도 한국어다.\n",
                encoding="utf-8",
            )
            (root / "MULTI_BAD.md").write_text(
                "---\ntype: Note\ntitle: English title # 한국어 주석\ndescription: |\n"
                "  English wrapped description only.\n---\n\n본문은 한국어다.\n",
                encoding="utf-8",
            )
            (root / "SETEXT.md").write_text(
                "English Setext Heading\n======================\n\nTwo English\nwords only.\n",
                encoding="utf-8",
            )
            findings = korean_docs.validate_repository(root)
            joined = "\n".join(findings)
            self.assertNotIn("MULTI_OK.md", joined)
            self.assertIn("MULTI_BAD.md:3 [KO-DOC-002]", joined)
            self.assertIn("MULTI_BAD.md:4 [KO-DOC-002]", joined)
            self.assertIn("SETEXT.md:1 [KO-DOC-003]", joined)
            self.assertIn("SETEXT.md:4 [KO-DOC-004]", joined)
            self.assertIn("skills/two/agents/openai.yaml", joined)

    def test_active_global_loader_is_korean_when_installed(self):
        codex_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
        override = codex_home / "AGENTS.override.md"
        global_agents = override if override.is_file() and override.stat().st_size else codex_home / "AGENTS.md"
        if not global_agents.is_file():
            self.skipTest("전역 Codex 지침이 설치되지 않은 환경")
        text = global_agents.read_text(encoding="utf-8")
        match = re.search(
            r"<!-- LIVING_WIKI_BOOTSTRAP:BEGIN -->(.*?)<!-- LIVING_WIKI_BOOTSTRAP:END -->",
            text,
            re.DOTALL,
        )
        self.assertIsNotNone(match)
        self.assertRegex(match.group(1), r"[가-힣]")
        self.assertIn("wiki/specs/korean-documentation-policy.md", match.group(1))

    def test_each_proposal_id_has_one_human_readable_document(self):
        import json

        proposals = json.loads((ROOT / "state" / "proposals.json").read_text(encoding="utf-8"))["proposals"]
        for proposal in proposals:
            matches = list((ROOT / "governance" / "proposals").glob(f"{proposal['id'].lower()}-*.md"))
            self.assertEqual(1, len(matches), proposal["id"])

    def test_release_regenerates_views_and_validates_its_markdown(self):
        from tools import korean_docs
        from tools import wiki as wiki_tool

        source = inspect.getsource(wiki_tool.release_check)
        self.assertLess(source.index("render_all"), source.index("_run_regression_suite"))
        self.assertIn("validate_markdown_text", source)
        report = {
            "passed": True,
            "readiness": "ready",
            "production_certified": False,
            "calibration_status": "pilot",
            "security_status": "fixed",
            "memory_hygiene_status": "fixed",
            "harness_version": "4.1.0",
            "harness_manifest_sha256": "abc",
            "harness_file_count": 1,
            "component_fingerprint": "def",
            "report_digest": "ghi",
            "gates": [{"name": "korean_documentation_contract", "passed": True}],
        }
        markdown = wiki_tool._release_report_markdown(report)
        self.assertEqual(
            [],
            korean_docs.validate_markdown_text(
                ROOT,
                Path("evaluations/reports/v4-release-report.md"),
                markdown,
            ),
        )


if __name__ == "__main__":
    unittest.main()
