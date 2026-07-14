---
type: Contradiction Register
title: 모순과 긴장
description: 숨기지 않고 추적하는 claim 충돌, 철학적 긴장, 현재 해소 방식.
tags: [contradictions, epistemics, governance]
timestamp: '2026-07-12T18:30:00+09:00'
claim_ids: [CLM-6DDD53332A40, CLM-F79558D817DF, CLM-EC52C0576A28]
---

# 모순과 긴장

## 원문 출처는 진실의 원천인가, 근거인가

- Karpathy의 Gist는 불변 raw sources를 “source of truth”라고 부른다. (`SRC-CFB88DDE3FF1`, Architecture)
- 이 Wiki는 raw source를 “감사 가능한 evidence”로 부른다. 원문도 틀리거나 편향되거나 철회될 수 있기 때문이다. W3C PROV는 provenance를 표현할 뿐 truth를 인증하지 않고, 2026 웹 검색 신뢰도 연구는 검색된 출처 자체가 비신뢰일 수 있음을 보여준다.
- 판정: 실질적 모순이라기보다 용어와 안전 경계의 차이다. [CLM-6DDD53332A40](claims/clm-6ddd53332a40.md)은 이를 숨기지 않기 위해 `contested`로 유지한다.

## Human/Agent parity와 인간 승인권

- 철학: 사람과 Agent는 같은 수준의 contributor 객체다.
- 현실: 외부 공개·비밀·비용·삭제·헌장 변경은 인간 승인이 필요하다.
- 해소: 인간이 사실성의 상위 권위라서가 아니라 법적 책임, 동의, 보안 경계를 가진 현실 주체이기 때문이다. 모든 승인·거부는 근거와 함께 기록해 권한 남용을 견제한다.

## 개인화와 확증편향

- 개인 노트와 관심사는 Wiki를 유용하고 독자적으로 만든다.
- 같은 prior는 반대 자료를 덜 검색하게 해 관점을 고착시킬 수 있다.
- 해소: 사용자 시드는 relevance 우선권만 받고 source trust 가점은 받지 않는다. 모든 중요 캠페인은 counter-search와 가장 강한 반론을 요구한다.

## 지속 합성과 오류 고착

- 지속 합성은 반복 재조합 비용을 줄인다.
- 초기 요약 오류를 장기간 증폭할 수 있다.
- 해소: synthesis는 evidence가 아니며, claim locator와 dependency-aware 재검증을 통해 raw까지 다시 내려갈 수 있어야 한다.

## 기억 활용과 anchoring

- Wiki-first는 이전 연구를 재사용해 비용을 줄이지만 과거 synthesis에 질문을 맞추는 anchoring을 만들 수 있다.
- 완전한 fresh-start는 같은 조사 비용을 반복하고 이미 알려진 반증을 놓칠 수 있다.
- 해소: 모든 모드에서 index는 읽되, `fresh-check`는 기존 결론을 괄호에 둔 독립 조사 뒤 차이를 비교한다. feedback은 이 절차의 결과를 감사할 뿐 ranking·trust를 자동 변경하지 않는다.

# 인용

[1] [Karpathy LLM Wiki](sources/karpathy-llm-wiki.md)
[2] [W3C PROV-O](https://www.w3.org/TR/prov-o/)
[3] [Assessing Web Search Credibility and Response Groundedness](https://aclanthology.org/2026.eacl-long.115/)
