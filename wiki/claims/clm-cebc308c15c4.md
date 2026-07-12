---
type: "Claim"
title: "CLM-CEBC308C15C4"
description: "주장 CLM-CEBC308C15C4의 범위·생명주기·증거 성숙도 기록."
tags: ["claim", "fact", "C2", "supported", "active"]
timestamp: "2026-07-12T03:10:01+00:00"
claim_id: "CLM-CEBC308C15C4"
created_at: "2026-07-11T14:31:10+00:00"
freshness: "normal"
generated: true
last_verified_at: "2026-07-12T03:10:01+00:00"
lifecycle_status: "active"
---
<!-- state/claims.json에서 자동 생성함. -->
# CLM-CEBC308C15C4

> 기록된 주장: GraphRAG의 그래프 구조는 잘못 추출된 triple과 부적절한 community 구성에서 생기는 오류를 자동으로 상쇄하지 못한다.

## 범위와 생명주기

| 항목 | 값 |
|---|---|
| 종류 | `fact` |
| 범위 | Dissecting GraphRAG에서 평가한 GraphRAG 시스템 |
| 유효 시점 | - |
| 최신성 분류 | `normal` |
| 생명주기 | **active** |
| 생명주기 사유 | - |
| 대체 주장 | - |
| 생성자 | [agent:codex](../actors/actor-agent-codex.md) |
| 생성 시각 | `2026-07-11T14:31:10+00:00` |
| 마지막 검증 | `2026-07-12T03:10:01+00:00` |

## 증거 성숙도

| 항목 | 값 |
|---|---|
| 표시 레벨 | **C2** |
| 상태 | **supported** |
| 지지 독립성 그룹 | 1 |
| 반박 독립성 그룹 | 0 |
| 독립 검토자 그룹 | 0 |
| 강한 미해결 반증 | False |

평가 근거: 추적 가능한 지지 출처가 하나 이상 있음; 강한 직접 출처가 있거나 독립 출처 그룹이 둘 이상임

## 증거 연결

| 관계 | 출처 | 정확한 원문 위치 | 강도 | 추가한 행위자 |
|---|---|---|---:|---|
| `supports` | [출처 SRC-4E9BB033389D](../sources/src-4e9bb033389d.md) | `Abstract and component ablations on triple extraction and community granularity` | 4 | `agent:codex` |

# 인용

[1] [Dissecting GraphRAG](https://aclanthology.org/2026.tacl-1.29/)
