import hashlib
import json
import tempfile
import unittest
from pathlib import Path


try:
    from tools import wiki_hygiene
except ImportError as exc:  # Red 단계에서는 아직 구현 모듈이 없다.
    wiki_hygiene = None
    WIKI_HYGIENE_IMPORT_ERROR = exc
else:
    WIKI_HYGIENE_IMPORT_ERROR = None


NOW = "2026-07-12T12:00:00+09:00"
DEFAULT_LIMITS = {
    "recent_documents": 1,
    "stale_claims": 1,
    "max_hops": 2,
    "max_nodes": 32,
    "max_pairs": 10,
    "semantic_review_limit": 2,
}


def _write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _tree_fingerprints(root):
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(item for item in root.rglob("*") if item.is_file())
    }


def _claim(
    claim_id,
    statement,
    *,
    tags,
    scope="동일한 위키 관리 정책, 2026년",
    last_verified_at="2026-07-11T00:00:00+00:00",
    content_updated_at="2026-07-11T00:00:00+00:00",
    freshness="normal",
    evidence=None,
    supersedes=None,
):
    return {
        "id": claim_id,
        "statement": statement,
        "kind": "factual",
        "scope": scope,
        "tags": tags,
        "freshness": freshness,
        "created_at": "2025-01-01T00:00:00+00:00",
        "content_updated_at": content_updated_at,
        "last_verified_at": last_verified_at,
        "lifecycle_status": "active",
        "supersedes": supersedes or [],
        "evidence": evidence or [],
        "confidence": {
            "level": "C2",
            "status": "supported",
            "computed_at": "2026-07-12T00:00:00+00:00",
        },
    }


def _evidence(source_id, relation):
    return {
        "source_id": source_id,
        "relation": relation,
        "locator": "section 1",
        "strength": 2,
        "added_at": "2025-01-01T00:00:00+00:00",
        "added_by": "agent:test",
    }


def _source(source_id, title):
    return {
        "id": source_id,
        "title": title,
        "url": f"https://example.test/{source_id.casefold()}",
        "source_type": "specification",
        "source_level": "S3",
        "status": "active",
        "retrieved_at": "2026-07-01T00:00:00+00:00",
        "independence_group": source_id,
    }


class WikiHygienePlanContractTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self._make_repository()
        self.assertIsNotNone(
            wiki_hygiene,
            f"Red: tools.wiki_hygiene가 아직 구현되지 않음: {WIKI_HYGIENE_IMPORT_ERROR}",
        )

    def tearDown(self):
        self.temporary_directory.cleanup()

    def _make_repository(self):
        (self.root / "config").mkdir(parents=True)
        _write_json(
            self.root / "config" / "wiki.json",
            {
                "timezone": "Asia/Seoul",
                "staleness_days": {
                    "fast": 30,
                    "normal": 180,
                    "slow": 730,
                    "timeless": None,
                },
            },
        )

        sources = [
            _source("SRC-111111111111", "그래프 근거"),
            _source("SRC-444444444444", "첫 번째 반박 근거"),
            _source("SRC-AAAAAAAAAAAA", "두 번째 반박 근거"),
        ]
        claims = [
            _claim(
                "CLM-111111111111",
                "최근 문서는 강한 관계를 통해 근거와 연결된다.",
                tags=["graph"],
                freshness="slow",
                evidence=[_evidence("SRC-111111111111", "supports")],
            ),
            _claim(
                "CLM-222222222222",
                "이웃 문서는 최근 문서와 직접 연결된다.",
                tags=["graph"],
                freshness="slow",
            ),
            _claim(
                "CLM-333333333333",
                "의존성 변경은 문서의 의미 변경보다 최신이다.",
                tags=["dependency"],
                content_updated_at="2026-07-10T00:00:00+00:00",
                freshness="slow",
            ),
            _claim(
                "CLM-444444444444",
                "첫 번째 정책은 반박 근거의 검토가 필요하다.",
                tags=["explicit-conflict"],
                last_verified_at="2020-01-01T00:00:00+00:00",
                freshness="fast",
                evidence=[_evidence("SRC-444444444444", "contradicts")],
            ),
            _claim(
                "CLM-555555555555",
                "첫 번째 정책은 반박 근거와 일치한다.",
                tags=["explicit-conflict"],
                evidence=[_evidence("SRC-444444444444", "supports")],
            ),
            _claim(
                "CLM-AAAAAAAAAAAA",
                "두 번째 정책은 별도 반박 근거의 검토가 필요하다.",
                tags=["explicit-conflict-2"],
                last_verified_at="2021-01-01T00:00:00+00:00",
                freshness="fast",
                evidence=[_evidence("SRC-AAAAAAAAAAAA", "contradicts")],
            ),
            _claim(
                "CLM-BBBBBBBBBBBB",
                "두 번째 정책은 별도 반박 근거와 일치한다.",
                tags=["explicit-conflict-2"],
                evidence=[_evidence("SRC-AAAAAAAAAAAA", "supports")],
            ),
            _claim(
                "CLM-666666666666",
                "관리인은 자동 신뢰 승격을 허용한다.",
                tags=["trust-policy"],
            ),
            _claim(
                "CLM-777777777777",
                "관리인은 자동 신뢰 승격을 허용하지 않는다.",
                tags=["trust-policy"],
            ),
            _claim(
                "CLM-888888888888",
                "빠른 지식의 재검토 주기는 7일이다.",
                tags=["review-period"],
            ),
            _claim(
                "CLM-999999999999",
                "빠른 지식의 재검토 주기는 30일이다.",
                tags=["review-period"],
            ),
        ]
        _write_json(self.root / "state" / "sources.json", {"version": 1, "sources": sources})
        _write_json(self.root / "state" / "claims.json", {"version": 1, "claims": claims})
        _write_json(
            self.root / "state" / "campaigns.json",
            {
                "version": 1,
                "campaigns": [
                    {
                        "id": "CMP-111111111111",
                        "status": "completed",
                        "claim_ids": [],
                        "source_ids": ["SRC-111111111111"],
                    }
                ],
            },
        )
        _write_json(self.root / "state" / "memory-feedback.json", {"version": 1, "feedback": []})
        (self.root / "state" / "events.jsonl").write_text("", encoding="utf-8")

        wiki = self.root / "wiki"
        concepts = wiki / "concepts"
        concepts.mkdir(parents=True)
        (wiki / "index.md").write_text(
            "# 색인\n\n"
            "- [최근](concepts/recent.md)\n"
            "- [이웃](concepts/neighbor.md)\n"
            "- [약한 태그](concepts/weak-only.md)\n"
            "- [의존성](concepts/dependency.md)\n"
            "- [구조 위험](concepts/broken.md)\n",
            encoding="utf-8",
        )
        (concepts / "recent.md").write_text(
            "---\n"
            "type: Concept\n"
            "title: 최근 문서\n"
            "description: 최근 의미 변경 문서다.\n"
            "tags: [graph, shared-only, allow]\n"
            "timestamp: '2026-07-11T12:00:00+09:00'\n"
            "claim_ids: [CLM-111111111111]\n"
            "---\n"
            "# 최근 문서\n\n[이웃 문서](neighbor.md)\n",
            encoding="utf-8",
        )
        (concepts / "neighbor.md").write_text(
            "---\n"
            "type: Concept\n"
            "title: 이웃 문서\n"
            "description: 최근 문서에서 한 hop 떨어진 문서다.\n"
            "tags: [graph]\n"
            "timestamp: '2026-05-01T00:00:00+09:00'\n"
            "claim_ids: [CLM-222222222222]\n"
            "---\n"
            "# 이웃 문서\n",
            encoding="utf-8",
        )
        (concepts / "weak-only.md").write_text(
            "---\n"
            "type: Concept\n"
            "title: 약한 태그 문서\n"
            "description: 최근 문서와 태그만 공유한다.\n"
            "tags: [shared-only, allow]\n"
            "timestamp: '2024-01-01T00:00:00+09:00'\n"
            "---\n"
            "# 약한 태그 문서\n",
            encoding="utf-8",
        )
        (concepts / "dependency.md").write_text(
            "---\n"
            "type: Concept\n"
            "title: 의존성 지연 문서\n"
            "description: 연결 주장이 문서보다 나중에 변경됐다.\n"
            "tags: [dependency]\n"
            "timestamp: '2025-01-01T00:00:00+09:00'\n"
            "claim_ids: [CLM-333333333333]\n"
            "---\n"
            "# 의존성 지연 문서\n",
            encoding="utf-8",
        )
        (concepts / "broken.md").write_text(
            "---\n"
            "type: Concept\n"
            "title: 구조 위험 문서\n"
            "description: 끊어진 표준 Markdown 링크가 있다.\n"
            "tags: [structure]\n"
            "timestamp: '2024-02-01T00:00:00+09:00'\n"
            "---\n"
            "# 구조 위험 문서\n\n[없는 문서](missing.md)\n",
            encoding="utf-8",
        )

    def _plan(self, **limit_overrides):
        limits = {**DEFAULT_LIMITS, **limit_overrides}
        return wiki_hygiene.build_hygiene_plan(self.root, now=NOW, limits=limits)

    @staticmethod
    def _by_id(items):
        return {item["id"]: item for item in items}

    def test_same_input_and_now_are_byte_deterministic_and_read_only(self):
        before = _tree_fingerprints(self.root)
        api_before = wiki_hygiene.repository_fingerprints(self.root)

        first = self._plan()
        middle = _tree_fingerprints(self.root)
        second = self._plan()
        after = _tree_fingerprints(self.root)

        self.assertEqual(before, middle)
        self.assertEqual(before, after)
        self.assertEqual(api_before, wiki_hygiene.repository_fingerprints(self.root))
        self.assertEqual(first, second)
        self.assertEqual(
            wiki_hygiene.canonical_plan_bytes(first),
            wiki_hygiene.canonical_plan_bytes(second),
        )
        self.assertEqual(
            wiki_hygiene.canonical_plan_bytes(first),
            (json.dumps(first, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode(
                "utf-8"
            ),
        )

    def test_seed_quotas_deduplicate_and_preserve_all_selection_reasons(self):
        plan = self._plan()
        seeds = plan["seeds"]
        by_id = self._by_id(seeds)

        self.assertEqual(len(seeds), len(by_id))
        self.assertEqual(
            [item["id"] for item in seeds if "recent_document" in item["reasons"]],
            ["document:wiki/concepts/recent.md"],
        )
        self.assertEqual(
            [item["id"] for item in seeds if "review_due_claim" in item["reasons"]],
            ["claim:CLM-444444444444"],
        )
        self.assertIn("registered_contradiction", by_id["claim:CLM-444444444444"]["reasons"])
        self.assertIn("review_due_claim", by_id["claim:CLM-444444444444"]["reasons"])
        self.assertIn("registered_contradiction", by_id["claim:CLM-AAAAAAAAAAAA"]["reasons"])
        self.assertIn("broken_markdown_link", by_id["document:wiki/concepts/broken.md"]["reasons"])
        self.assertIn(
            "dependency_newer_than_document",
            by_id["document:wiki/concepts/dependency.md"]["reasons"],
        )

        hard_risk = {
            item["id"]
            for item in seeds
            if {"registered_contradiction", "broken_markdown_link"} & set(item["reasons"])
        }
        self.assertEqual(
            hard_risk,
            {
                "claim:CLM-444444444444",
                "claim:CLM-AAAAAAAAAAAA",
                "document:wiki/concepts/broken.md",
            },
        )
        self.assertLessEqual(len(plan["semantic_review_queue"]), DEFAULT_LIMITS["semantic_review_limit"])

    def test_strong_typed_edges_use_bounded_bfs_paths_and_report_node_truncation(self):
        plan = self._plan()
        nodes = self._by_id(plan["selected_nodes"])
        source = nodes["source:SRC-111111111111"]

        self.assertEqual(source["hop"], 2)
        self.assertEqual(
            source["selection_path"],
            [
                {"node_id": "document:wiki/concepts/recent.md", "relation": "seed"},
                {"node_id": "claim:CLM-111111111111", "relation": "claim_ids"},
                {"node_id": "source:SRC-111111111111", "relation": "evidence_source"},
            ],
        )
        self.assertIn("document:wiki/concepts/neighbor.md", nodes)
        self.assertNotIn("campaign:CMP-111111111111", nodes)
        allowed_relations = {
            "seed",
            "markdown_link",
            "claim_ids",
            "evidence_source",
            "supersedes",
            "campaign_membership",
        }
        for node in nodes.values():
            with self.subTest(node=node["id"]):
                self.assertLessEqual(node["hop"], 2)
                self.assertLessEqual(len(node["selection_path"]) - 1, 2)
                self.assertTrue(
                    {step["relation"] for step in node["selection_path"]} <= allowed_relations
                )

        capped = self._plan(max_nodes=5)
        self.assertLessEqual(len(capped["selected_nodes"]), 5)
        self.assertIn("max_nodes_reached", {item["code"] for item in capped["truncations"]})

    def test_shared_tag_is_a_weak_review_candidate_not_an_automatic_graph_edge(self):
        plan = self._plan()
        node_ids = {item["id"] for item in plan["selected_nodes"]}
        weak_only = "document:wiki/concepts/weak-only.md"

        self.assertNotIn(weak_only, node_ids)
        relations = {
            step["relation"]
            for node in plan["selected_nodes"]
            for step in node["selection_path"]
        }
        self.assertNotIn("shared_tag", relations)
        matching = [
            item
            for item in plan["weak_candidates"]
            if set(item["node_ids"])
            == {"document:wiki/concepts/recent.md", "document:wiki/concepts/weak-only.md"}
            and "shared_tag" in item["signals"]
        ]
        self.assertEqual(len(matching), 1)
        self.assertIs(matching[0]["review_only"], True)
        self.assertEqual(matching[0]["shared_tags"], ["shared-only"])

    def test_conflict_candidates_are_bounded_and_review_only(self):
        plan = self._plan(max_pairs=10)
        candidates = {
            frozenset(item["claim_ids"]): item for item in plan["conflict_candidates"]
        }
        expected = {
            frozenset({"CLM-444444444444", "CLM-555555555555"}): "explicit_contradiction",
            frozenset({"CLM-666666666666", "CLM-777777777777"}): "polarity_difference",
            frozenset({"CLM-888888888888", "CLM-999999999999"}): "numeric_difference",
        }
        for pair, signal in expected.items():
            with self.subTest(pair=sorted(pair), signal=signal):
                self.assertIn(pair, candidates)
                self.assertIn(signal, candidates[pair]["signals"])

        for candidate in plan["conflict_candidates"]:
            self.assertIs(candidate["review_only"], True)
            self.assertEqual(candidate["automatic_actions"], [])

        bounded = self._plan(max_pairs=2, semantic_review_limit=1)
        self.assertEqual(len(bounded["conflict_candidates"]), 2)
        self.assertLessEqual(len(bounded["semantic_review_queue"]), 1)
        self.assertIn("max_pairs_reached", {item["code"] for item in bounded["truncations"]})

    def test_heuristic_conflicts_require_statement_topic_anchor_overlap(self):
        claims_path = self.root / "state" / "claims.json"
        sources_path = self.root / "state" / "sources.json"
        payload = json.loads(claims_path.read_text(encoding="utf-8"))
        source_payload = json.loads(sources_path.read_text(encoding="utf-8"))
        source_payload["sources"].append(
            _source("SRC-C40000000000", "주제 앵커와 독립된 명시적 충돌 근거")
        )
        _write_json(sources_path, source_payload)
        payload["claims"].extend(
            [
                _claim(
                    "CLM-C10000000001",
                    "Codex의 프로젝트 지침 결합 용량 기본값은 32 KiB이며, 한도에 도달하면 추가 지침 파일을 더하지 않는다.",
                    tags=["codex-broad-polarity"],
                    scope="OpenAI Codex 공식 문서, 2026-07-12 현재",
                ),
                _claim(
                    "CLM-C10000000002",
                    "Codex는 선택된 프로젝트 지침을 루트에서 현재 디렉터리 순으로 결합하므로 가까운 디렉터리의 지침이 앞선 지침을 재정의할 수 있다.",
                    tags=["codex-broad-polarity"],
                    scope="OpenAI Codex 공식 문서, 2026-07-12 현재",
                ),
                _claim(
                    "CLM-C20000000001",
                    "Codex 프로젝트 지침의 결합 용량은 32 KiB이다.",
                    tags=["codex-broad-numeric"],
                    scope="OpenAI Codex 공식 문서, 2026-07-12 현재",
                ),
                _claim(
                    "CLM-C20000000002",
                    "Codex는 작업 시작 시 설정 파일을 4단계로 탐색한다.",
                    tags=["codex-broad-numeric"],
                    scope="OpenAI Codex 공식 문서, 2026-07-12 현재",
                ),
                _claim(
                    "CLM-C30000000001",
                    "Codex는 지침 파일이 있는 경우 루트에서 읽는다.",
                    tags=["codex-broad-condition"],
                    scope="OpenAI Codex 공식 문서, 2026-07-12 현재",
                ),
                _claim(
                    "CLM-C30000000002",
                    "Codex는 네트워크 권한이 있을 때만 요청을 보낸다.",
                    tags=["codex-broad-condition"],
                    scope="OpenAI Codex 공식 문서, 2026-07-12 현재",
                ),
                _claim(
                    "CLM-C40000000001",
                    "원문 snapshot은 감사 가능한 증거다.",
                    tags=["explicit-unanchored-left"],
                    evidence=[_evidence("SRC-C40000000000", "supports")],
                ),
                _claim(
                    "CLM-C40000000002",
                    "지속적 합성은 반복 재합성을 줄인다.",
                    tags=["explicit-unanchored-right"],
                    evidence=[_evidence("SRC-C40000000000", "contradicts")],
                ),
            ]
        )
        _write_json(claims_path, payload)

        candidates = {
            frozenset(item["claim_ids"]): item
            for item in self._plan(max_pairs=30)["conflict_candidates"]
        }
        for pair in (
            {"CLM-C10000000001", "CLM-C10000000002"},
            {"CLM-C20000000001", "CLM-C20000000002"},
            {"CLM-C30000000001", "CLM-C30000000002"},
        ):
            with self.subTest(pair=sorted(pair)):
                self.assertNotIn(frozenset(pair), candidates)

        explicit_pair = frozenset({"CLM-C40000000001", "CLM-C40000000002"})
        self.assertIn(explicit_pair, candidates)
        self.assertEqual(candidates[explicit_pair]["signals"], ["explicit_contradiction"])

    def test_semantic_queue_prioritizes_actionable_seeds_before_weak_relations(self):
        queue = self._plan(max_pairs=1, semantic_review_limit=8)[
            "semantic_review_queue"
        ]

        self.assertEqual(queue[0]["kind"], "conflict_candidate")
        selected = [item for item in queue if item["kind"] == "selected_node"]
        self.assertEqual(
            [item["node_id"] for item in selected],
            [
                "claim:CLM-444444444444",
                "claim:CLM-AAAAAAAAAAAA",
                "document:wiki/concepts/broken.md",
                "document:wiki/concepts/dependency.md",
                "document:wiki/concepts/neighbor.md",
                "document:wiki/concepts/recent.md",
            ],
        )
        for item in selected:
            with self.subTest(node_id=item["node_id"]):
                self.assertTrue(item["reasons"])
                self.assertNotEqual(item["reasons"], ["graph_expansion"])

        selected_positions = [
            index for index, item in enumerate(queue) if item["kind"] == "selected_node"
        ]
        weak_positions = [
            index
            for index, item in enumerate(queue)
            if item["kind"] == "weak_relation_candidate"
        ]
        self.assertTrue(weak_positions)
        self.assertLess(max(selected_positions), min(weak_positions))

    def test_plan_records_input_fingerprints_limits_counts_and_safety_invariants(self):
        plan = self._plan()
        inputs = plan["inputs"]
        fingerprints = inputs["fingerprints"]

        self.assertEqual(plan["now"], NOW)
        self.assertEqual(plan["limits"], DEFAULT_LIMITS)
        self.assertEqual(inputs["scanned_documents"], 5)
        self.assertEqual(inputs["scanned_claims"], 11)
        self.assertEqual(fingerprints, wiki_hygiene.repository_fingerprints(self.root))
        self.assertEqual(list(fingerprints), sorted(fingerprints))
        self.assertTrue(
            {
                "config/wiki.json",
                "state/claims.json",
                "state/sources.json",
                "state/campaigns.json",
                "wiki/concepts/recent.md",
                "wiki/concepts/weak-only.md",
            }
            <= set(fingerprints)
        )
        for path, digest in fingerprints.items():
            with self.subTest(path=path):
                self.assertRegex(digest, r"\A[0-9a-f]{64}\Z")

        self.assertEqual(
            plan["invariants"],
            {
                "read_only": True,
                "conflicts_are_review_only": True,
                "automatic_evidence_mutation": False,
                "automatic_trust_mutation": False,
                "automatic_lifecycle_mutation": False,
            },
        )


if __name__ == "__main__":
    unittest.main()
