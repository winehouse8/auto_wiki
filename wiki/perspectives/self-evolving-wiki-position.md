---
type: Position
title: 살아 있는 Wiki는 공동체의 검증 가능한 관점이어야 한다
description: Living Wiki의 잠정적 관점, 반론, 전제, 입장 변경 조건.
tags: [position, perspective, living-wiki]
timestamp: '2026-07-12T18:30:00+09:00'
lifecycle_status: provisional
claim_ids: [CLM-DCFACC957266, CLM-DA7C92E9A901, CLM-CB6E34C87DA3, CLM-F464CCF0AA1A, CLM-EC52C0576A28]
---

# 입장 — 살아 있는 Wiki는 공동체의 검증 가능한 관점이어야 한다

상태: `active`, `provisional`

기준일: 2026-07-12

## 현재 입장

Wiki는 중립을 가장한 문서 더미보다, 증거와 이견을 공개한 채 수정 가능한 관점을 가져야 더 유용하다. 그 관점은 특정 모델의 성격이나 한 사람의 취향이 아니라, 관심 분야·가치·선별 기준·축적된 claim·반대 증거·결정 이력에서 나온다.

다만 Wiki의 관점은 사용자를 과거 결론에 묶는 기본값이어서는 안 된다. 기본 `wiki-first` 외에 사용자가 `fresh-check`를 요청하면 현재 index는 읽되 기존 synthesis의 결론을 독립 원자료 조사 뒤에 비교하며, `strict-evidence`에서는 exact locator와 C2 이상 근거를 우선한다.

## 전제

- 지식의 유용성에는 사실성 외에도 목적과 관점이 관여한다.
- 인간은 Agent가 접근하기 어려운 가치·현장·unknown unknown을 제공한다.
- Agent는 인간이 지속하기 어려운 검증과 maintenance를 수행할 수 있다.
- 어떤 actor도 오류에 면역이 아니다.

## 지지 주장

- [CLM-DCFACC957266](../claims/clm-dcfacc957266.md): 관점과 사실 원장 분리
- [CLM-DA7C92E9A901](../claims/clm-da7c92e9a901.md): 관찰·조향 가능한 인간-Agent 협업
- [CLM-CB6E34C87DA3](../claims/clm-cb6e34c87da3.md): 원자적 주장의 출처 추적성
- [CLM-F464CCF0AA1A](../claims/clm-f464ccf0aa1a.md): 벤치마크 게이트를 거치는 자기진화
- [CLM-EC52C0576A28](../claims/clm-ec52c0576a28.md): 사용자 제어형 Wiki 기억 의존도

## 가장 강한 반론

1. Agent가 관리하는 관점은 모델 provider와 학습 데이터의 편향을 “Wiki의 독자성”으로 포장할 수 있다.
2. 사용자 관심사를 우선하면 불편한 반대 자료가 구조적으로 덜 들어올 수 있다.
3. 지속 합성은 초기 오류를 더 잘 기억하게 만들 뿐일 수 있다.
4. 복잡한 trust/governance schema가 maintenance 비용을 다시 인간에게 돌릴 수 있다.
5. 인간의 최종 승인권은 actor parity라는 철학과 실제로 충돌할 수 있다.

## 입장을 바꿀 조건

- 장기 평가에서 persistent synthesis가 raw retrieval baseline보다 사실성·비용·정보 이득을 개선하지 못할 때
- counter-search와 source diversity가 있어도 관점 고착이 줄지 않을 때
- claim-level bookkeeping 비용이 얻는 감사 가능성보다 지속적으로 클 때
- 인간이 개입 가능한 협업형보다 더 자율적인 Agent가 반복해서 정확하고 안전하며 사용자의 실제 목적을 잘 달성할 때

## 개정 규칙

새 evidence가 들어오면 반론을 삭제하지 않고, 어떤 claim이 어떻게 바뀌었는지 decision/event와 함께 새 revision을 만든다.

# 인용

[1] [Hindsight](https://aclanthology.org/2026.acl-demo.27/)
[2] [STORM](https://aclanthology.org/2024.naacl-long.347/)
[3] [Co-STORM](https://aclanthology.org/2024.emnlp-main.554/)
