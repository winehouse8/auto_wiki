---
type: "Claim"
title: "CLM-409FCD3D2B82"
description: "주장 CLM-409FCD3D2B82의 범위·생명주기·증거 성숙도 기록."
tags: ["claim", "fact", "C2", "supported", "active"]
timestamp: "2026-07-12T03:10:01+00:00"
claim_id: "CLM-409FCD3D2B82"
created_at: "2026-07-12T01:59:41+00:00"
freshness: "fast"
generated: true
last_verified_at: "2026-07-12T03:10:01+00:00"
lifecycle_status: "active"
---
<!-- state/claims.json에서 자동 생성함. -->
# CLM-409FCD3D2B82

> 기록된 주장: Codex는 매 실행 시작 시 프로젝트 경로 탐색과 별도로 CODEX_HOME(기본 ~/.codex)의 전역 지침을 읽으며, non-empty AGENTS.override.md가 있으면 그것을 사용하고 그렇지 않으면 AGENTS.md를 사용한다.

## 범위와 생명주기

| 항목 | 값 |
|---|---|
| 종류 | `fact` |
| 범위 | 2026-07-12 현재 OpenAI Codex 공식 AGENTS.md 탐색 동작 |
| 유효 시점 | 2026-07-12 |
| 최신성 분류 | `fast` |
| 생명주기 | **active** |
| 생명주기 사유 | - |
| 대체 주장 | - |
| 생성자 | [agent:codex](../actors/actor-agent-codex.md) |
| 생성 시각 | `2026-07-12T01:59:41+00:00` |
| 마지막 검증 | `2026-07-12T03:10:01+00:00` |

## 관련 연구 프로젝트

- 공통·제어면 지식

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
| `supports` | [출처 SRC-228828E53C40](../sources/src-228828e53c40.md) | `How Codex discovers guidance: Global scope` | 4 | `agent:codex` |

# 인용

[1] [OpenAI Codex: Custom instructions with AGENTS.md](https://developers.openai.com/codex/guides/agents-md)
