---
type: "Claim"
title: "CLM-FF4A31447E3E"
description: "주장 CLM-FF4A31447E3E의 범위·생명주기·증거 성숙도 기록."
tags: ["claim", "fact", "C2", "supported", "active"]
timestamp: "2026-07-12T03:10:01+00:00"
claim_id: "CLM-FF4A31447E3E"
created_at: "2026-07-11T15:24:08+00:00"
freshness: "fast"
generated: true
last_verified_at: "2026-07-12T03:10:01+00:00"
lifecycle_status: "active"
---
<!-- state/claims.json에서 자동 생성함. -->
# CLM-FF4A31447E3E

> 기록된 주장: 프로젝트 지침 탐색에서 Codex는 프로젝트 루트부터 현재 작업 디렉터리까지 내려가며, 각 디렉터리에서 AGENTS.override.md, AGENTS.md, 설정된 fallback 이름 순으로 최대 한 파일을 선택한다.

## 범위와 생명주기

| 항목 | 값 |
|---|---|
| 종류 | `fact` |
| 범위 | OpenAI Codex 공식 문서 및 Codex CLI 0.144.1, 2026-07-12 현재 |
| 유효 시점 | 2026-07-12 |
| 최신성 분류 | `fast` |
| 생명주기 | **active** |
| 생명주기 사유 | - |
| 대체 주장 | - |
| 생성자 | [agent:codex](../actors/actor-agent-codex.md) |
| 생성 시각 | `2026-07-11T15:24:08+00:00` |
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
| `supports` | [출처 SRC-228828E53C40](../sources/src-228828e53c40.md) | `How Codex discovers guidance: Project scope` | 4 | `agent:codex` |

# 인용

[1] [OpenAI Codex: Custom instructions with AGENTS.md](https://developers.openai.com/codex/guides/agents-md)
