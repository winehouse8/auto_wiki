---
type: Concept
title: Claim-level trust
description: Claim, evidence, source, independence, review, and lifecycle dimensions behind trust levels.
tags: [claims, evidence, provenance, trust]
timestamp: '2026-07-11T23:40:00+09:00'
claim_ids: [CLM-CB6E34C87DA3, CLM-6ED77E226EF7, CLM-860EB3D6AAEB]
---

# Claim-level trust

## 왜 page level로 부족한가

한 페이지에는 강한 사실, 약한 해석, 예측, 가치판단이 섞인다. 페이지 전체에 별점 하나를 붙이면 어떤 문장이 어느 evidence에 기대는지, 반증이 어디까지 영향을 미치는지 알 수 없다.

관련 claim: `CLM-CB6E34C87DA3`, `CLM-6ED77E226EF7`, `CLM-860EB3D6AAEB`

## 모델

- source: provenance, type, review status, method, independence, conflict, freshness
- evidence edge: relation, exact locator, directness/strength, extraction quality
- claim: kind, scope, temporal validity, evidence set, contradiction state
- review: actor, independence group, verdict, adversarial 여부
- display level: 위 벡터에서 gate로 계산한 C0–C4

## 분리해야 할 것

- source credibility
- evidence entailment/faithfulness
- world factuality
- model uncertainty
- freshness/retraction
- lifecycle status

단일 confidence 숫자는 이 차원을 숨기므로 navigation용 level만 파생하고 원래 벡터를 보존한다.

# Citations

[1] [GenProve](https://aclanthology.org/2026.acl-long.228/)
[2] [FRANQ](https://aclanthology.org/2026.findings-acl.338/)
[3] [Assessing Web Search Credibility and Response Groundedness](https://aclanthology.org/2026.eacl-long.115/)
[4] [FactSearch](https://aclanthology.org/2026.acl-demo.36/)
