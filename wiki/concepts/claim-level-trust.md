---
type: Concept
title: 주장 단위 신뢰
description: 신뢰 수준을 구성하는 주장·근거·출처·독립성·검토·생명주기 차원.
tags: [claims, evidence, provenance, trust]
timestamp: '2026-07-11T23:40:00+09:00'
claim_ids: [CLM-CB6E34C87DA3, CLM-6ED77E226EF7, CLM-860EB3D6AAEB]
---

# 주장 단위 신뢰

## 왜 페이지 단위로는 부족한가

한 페이지에는 강한 사실, 약한 해석, 예측, 가치판단이 섞인다. 페이지 전체에 별점 하나를 붙이면 어떤 문장이 어느 근거에 기대는지, 반증이 어디까지 영향을 미치는지 알 수 없다.

관련 주장: [CLM-CB6E34C87DA3](../claims/clm-cb6e34c87da3.md), [CLM-6ED77E226EF7](../claims/clm-6ed77e226ef7.md), [CLM-860EB3D6AAEB](../claims/clm-860eb3d6aaeb.md)

## 모델

- 출처: 출처 이력, 유형, 검토 상태, 방법, 독립성, 이해상충, 최신성
- 근거 연결: 관계, 정확한 위치 지정자, 직접성·강도, 추출 품질
- 주장: 종류, 범위, 시간적 유효성, 근거 집합, 모순 상태
- 검토: 행위자, 독립성 그룹, 판정, 적대적 검토 여부
- 표시 수준: 위 벡터를 게이트로 계산한 C0–C4

## 분리해야 할 것

- 출처 신뢰성
- 근거의 함의·충실성
- 세계에 대한 사실성
- 모델 불확실성
- 최신성·철회 여부
- 생명주기 상태

단일 신뢰도 숫자는 이 차원을 숨기므로 탐색용 수준만 파생하고 원래 벡터를 보존한다.

# 인용

[1] [GenProve](https://aclanthology.org/2026.acl-long.228/)
[2] [FRANQ](https://aclanthology.org/2026.findings-acl.338/)
[3] [Assessing Web Search Credibility and Response Groundedness](https://aclanthology.org/2026.eacl-long.115/)
[4] [FactSearch](https://aclanthology.org/2026.acl-demo.36/)
