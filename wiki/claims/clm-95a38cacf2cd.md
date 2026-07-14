---
type: "Claim"
title: "CLM-95A38CACF2CD"
description: "주장 CLM-95A38CACF2CD의 범위·생명주기·증거 성숙도 기록."
tags: ["claim", "interpretation", "C2", "supported", "active"]
timestamp: "2026-07-12T03:10:01+00:00"
claim_id: "CLM-95A38CACF2CD"
created_at: "2026-07-11T17:18:47+00:00"
freshness: "normal"
generated: true
last_verified_at: "2026-07-12T03:10:01+00:00"
lifecycle_status: "active"
---
<!-- state/claims.json에서 자동 생성함. -->
# CLM-95A38CACF2CD

> 기록된 주장: Agent 실패는 어떤 지식 공백을 조사할지 우선순위화하는 신호가 될 수 있지만, 실패 원인이나 새 지식의 사실성을 스스로 증명하지 않으므로 독립 근거 검증과 재현 가능한 재시도 뒤에만 Wiki 지식으로 승격해야 한다.

## 범위와 생명주기

| 항목 | 값 |
|---|---|
| 종류 | `interpretation` |
| 범위 | Living Wiki의 실패 주도 지식 획득 |
| 유효 시점 | 2026-07-12 |
| 최신성 분류 | `normal` |
| 생명주기 | **active** |
| 생명주기 사유 | - |
| 대체 주장 | - |
| 생성자 | [agent:codex](../actors/actor-agent-codex.md) |
| 생성 시각 | `2026-07-11T17:18:47+00:00` |
| 마지막 검증 | `2026-07-12T03:10:01+00:00` |

## 증거 성숙도

| 항목 | 값 |
|---|---|
| 표시 레벨 | **C2** |
| 상태 | **supported** |
| 지지 독립성 그룹 | 2 |
| 반박 독립성 그룹 | 0 |
| 독립 검토자 그룹 | 0 |
| 강한 미해결 반증 | False |

평가 근거: 추적 가능한 지지 출처가 하나 이상 있음; 강한 직접 출처가 있거나 독립 출처 그룹이 둘 이상임

## 증거 연결

| 관계 | 출처 | 정확한 원문 위치 | 강도 | 추가한 행위자 |
|---|---|---|---:|---|
| `supports` | [출처 SRC-54D07435EB56](../sources/src-54d07435eb56.md) | `pp. 1-2: failure as primary curation signal; §3 pp. 5-7: human validation and graduation; §3.5 pp. 7-8: convergence explicitly remains an unvalidated hypothesis` | 3 | `agent:codex` |
| `supports` | [출처 SRC-AF06BCDC1ED2](../sources/src-af06bcdc1ed2.md) | `pp. 623-625: experience-following, error propagation, and evaluator feedback; pp. 627-630: misaligned replay and downstream outcome labels` | 4 | `agent:codex` |
| `contextualizes` | [출처 SRC-F55FED177366](../sources/src-f55fed177366.md) | `video description and linked preprint; published 2026-05-05` | 2 | `agent:codex` |

# 인용

[1] [Demand-Driven Context: A Methodology for Building Enterprise Knowledge Bases Through Agent Failure](https://arxiv.org/abs/2603.14057)
[2] [How Memory Management Impacts LLM Agents: An Empirical Study of Experience-Following Behavior](https://aclanthology.org/2026.acl-long.27/)
[3] [Demand-Driven Context: A Methodology for Coherent Knowledge Bases Through Agent Failure](https://www.youtube.com/watch?v=_QAVExf_1uw)
