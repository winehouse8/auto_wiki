---
type: Synthesis
title: 문서 저장소가 아니라 검증 가능한 연구 공동체
description: Living Wiki가 현재 채택한 전체 설계 종합과 신뢰 경계.
tags: [living-wiki, synthesis, provenance, governance]
timestamp: '2026-07-11T23:40:00+09:00'
claim_ids: [CLM-F6367BFF8F35, CLM-CB6E34C87DA3, CLM-F464CCF0AA1A]
---

# 현재 종합 — 문서 저장소가 아니라 검증 가능한 연구 공동체

## Thesis

살아 있는 Wiki의 핵심은 Agent가 글을 많이 쓰는 데 있지 않다. 외부 세계의 흔적을 불변 증거로 보존하고, 그 위에서 누가 어떤 주장을 왜 믿게 되었는지 추적하며, 새로운 증거가 들어올 때 관련 관점과 문서를 제한적으로 다시 컴파일하는 데 있다.

Karpathy와 AI Research OS의 가장 강한 통찰은 지식을 매 질의마다 raw chunk에서 재발견하지 말고 지속적인 Markdown 합성물로 축적하라는 것이다. 하지만 둘 다 신뢰성·행위자·자율 연구·보안·평가를 충분히 다루지 않는다. 특히 AI Research OS의 `relevance_score`는 신뢰 점수가 아니며 발표자도 source provenance, strength, ranking, compaction이 미완성이라고 인정했다. [Karpathy LLM Wiki](sources/karpathy-llm-wiki.md), [AI Research OS talk](sources/ai-research-os-talk.md), [AI Research OS repository](sources/ai-research-os-workshop-repo.md)

2026년 연구는 이 빈칸을 구체화한다. FRANQ와 웹 검색 신뢰도 평가는 factuality, evidence faithfulness, source credibility를 분리하라고 요구한다. GenProve와 FactSearch는 claim-level provenance가 필요함을 보여준다. multi-turn report revision 연구와 LEDGER는 Wiki 수정이 scoped patch와 regression test를 가져야 함을 보여준다. Collaborative Gym, InterDeepResearch, Co-STORM은 사람을 마지막 승인 버튼으로만 두지 말고 진행 중인 연구를 관찰·조향·수리할 수 있게 해야 함을 보여준다. A-MemGuard와 memory-poisoning 연구는 지속 기억이 장점인 동시에 장기 공격 표면임을 보여준다.

따라서 현재 Wiki의 설계 입장은 다음과 같다.

1. 원문은 진실이 아니라 감사 가능한 evidence다. (`CLM-6DDD53332A40`, contested)
2. 신뢰의 최소 단위는 page가 아니라 atomic claim과 locator다. (`CLM-CB6E34C87DA3`)
3. 신뢰는 한 숫자가 아니라 source·evidence·independence·contradiction·review 벡터다.
4. 사람과 Agent는 같은 actor/contribution protocol을 사용한다. 권한은 책임과 위험에 따라 역할별로 다르다.
5. Wiki의 관점은 사실 원장과 분리하고 강한 반론과 변화 조건을 보존한다.
6. 자율 연구는 관심 분야 → gap → counter-search → admission → synthesis → eval의 bounded loop다.
7. 하네스 자기수정은 콘텐츠 편집과 다르며 RFC, 고정 benchmark, rollback이 필요하다.

## 현재 신뢰 경계

이 종합은 production 인증이 아니다. 31개 source record 중 OKF 공식 spec 하나만 local immutable snapshot까지 보존했고, 나머지 대부분은 저작권·접근성 때문에 URL과 metadata만 있어 경고가 남는다. C0–C4 gate의 empirical calibration, 장기 반복 편집, 실제 memory-poisoning red team, 동시 편집은 아직 평가하지 않았다. 이 한계를 숨기지 않는 것이 v3 계열의 첫 번째 품질 기능이다.

# Citations

[1] [Karpathy LLM Wiki](sources/karpathy-llm-wiki.md)
[2] [AI Research OS talk](sources/ai-research-os-talk.md)
[3] [Open Knowledge Format v0.1 Draft](sources/open-knowledge-format-v0.1.md)
[4] [FRANQ](https://aclanthology.org/2026.findings-acl.338/)
[5] [Collaborative Gym](https://openreview.net/forum?id=GDYueXtKXT)
[6] [A-MemGuard](https://openreview.net/forum?id=udqe7UZUZ6)
