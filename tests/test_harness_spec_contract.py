import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
SPEC = ROOT / "wiki" / "specs" / "harness-ux.md"


class HarnessSpecContractTests(unittest.TestCase):
    def test_central_spec_is_reachable_from_agent_and_human_entrypoints(self):
        self.assertTrue(SPEC.is_file())
        for entrypoint in (ROOT / "AGENTS.md", ROOT / "README.md"):
            self.assertIn("wiki/specs/harness-ux.md", entrypoint.read_text(encoding="utf-8"))

    def test_spec_covers_the_product_and_delivery_contract(self):
        text = SPEC.read_text(encoding="utf-8").casefold()
        required_terms = (
            "자연어",
            "s0–s4",
            "c0–c4",
            "매일",
            "변경 임계값",
            "반복 연구",
            "자가 발전",
            "red → green → refactor",
            "rfc",
            "롤백",
        )
        for term in required_terms:
            with self.subTest(term=term):
                self.assertIn(term.casefold(), text)

    def test_entrypoints_require_spec_driven_tdd_before_harness_changes(self):
        for entrypoint in (ROOT / "AGENTS.md", ROOT / "README.md"):
            text = entrypoint.read_text(encoding="utf-8").casefold()
            self.assertIn("spec-driven tdd", text)
            self.assertIn("red", text)
            self.assertIn("릴리스 게이트", text)

    def test_spec_contracts_bounded_semantic_hygiene_and_okf_time_meaning(self):
        text = SPEC.read_text(encoding="utf-8").casefold()
        required_terms = (
            "범위 제한 의미 위생",
            "okf 시간 의미",
            "timestamp",
            "2-hop",
            "선택 이유",
            "시작 시드까지의 경로",
            "결정론적 전수 검사",
            "같은 입력과 시각에서는 바이트가 같은 결과",
        )
        for term in required_terms:
            with self.subTest(term=term):
                self.assertIn(term.casefold(), text)


if __name__ == "__main__":
    unittest.main()
