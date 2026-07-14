---
type: "Harness Proposal"
title: "RFC-6BD49C04ED49: 하네스 제안"
description: "하네스 제안 RFC-6BD49C04ED49의 문제·변경·검토·구현 근거."
tags: ["governance", "harness-proposal", "implemented"]
timestamp: "2026-07-12T15:25:35+00:00"
generated: true
lifecycle_status: "implemented"
proposal_id: "RFC-6BD49C04ED49"
---
<!-- state/proposals.json에서 자동 생성함. -->
# RFC-6BD49C04ED49: 하네스 제안 — Living Wiki v4.2 범위 제한 위생 후보 라우팅과 OKF 시간 계약

- 상태: **implemented**
- 제안자: [agent:codex](../actors/actor-agent-codex.md)
- 생성 시각: `2026-07-12T13:22:37+00:00`

## 문제

기록된 문제: 현재 위생은 상태·링크를 전수 구조 검사하지만 최신 문서와 검토 기한 초과 주장을 시드로 고르고 강한 관계를 N-hop 확장해 제한된 논리 충돌 후보만 깊게 읽는 절차가 없다. OKF timestamp도 마지막 의미 변경·생성·실제 검증 시각을 분리해 후보 필터에 쓰지 못한다.

## 제안 변경

기록된 변경안: Codex 예약 작업은 호출 계층으로 유지한다. 저장소에는 읽기 전용 hygiene-plan을 추가해 구조 위험, 최근 문서, review-due 주장과 의존성 지연을 시드로 만들고 최대 2-hop·노드·쌍 상한으로 그래프를 확장한다. 극성·수치·조건 차이는 검토 후보로만 반환하고 선택 경로·입력 지문·무신뢰효과 불변조건을 남긴다. OKF timestamp는 마지막 의미 변경으로 검증하고 생성 투영에 알려진 created_at, last_verified_at, freshness, lifecycle_updated_at을 추가한다. render와 confidence 재계산은 실제 의미 변경·검증 없이 시간값을 진전시키지 않는다.

## 근거 주장

- [CLM-1EB8BD726482](../claims/clm-1eb8bd726482.md)
- [CLM-207429D54323](../claims/clm-207429d54323.md)
- [CLM-952258184EF2](../claims/clm-952258184ef2.md)
- [CLM-F79558D817DF](../claims/clm-f79558d817df.md)

## 수용 게이트

기록된 수용 기준: SPEC-LWS-001 v1.2.0의 AC-LWS-015~022를 Red 테스트로 먼저 고정한다. 동일 입력·고정 시각 결정성, 읽기 전용성, 최근·노후 시드 할당량, 강한 관계 2-hop과 노드 상한, 선택 경로, 제한된 충돌 후보, 자동 신뢰 효과 없음, 시간대 ISO-8601 frontmatter, render·confidence 시간 불변을 검증한다. 대상 테스트와 evaluate, render, memory-hygiene, lint, language-validate, validate, okf-validate, 전체 단위 테스트, release-check가 통과해야 한다.

## 위험

- 기록된 위험: 시간 마이그레이션에서 과거 생성 시각을 추정할 위험
- 기록된 위험: 일괄 렌더가 최신성으로 오인됨
- 기록된 위험: 태그·어휘 기반 거짓 양성
- 기록된 위험: 후보 계획을 사실 판정으로 오해할 위험
- 기록된 위험: 후보 그래프 팽창

## 롤백

기록된 롤백: 새 hygiene_selection 설정, tools/wiki_hygiene.py, hygiene-plan CLI와 테스트를 제거하고 Skill을 기존 위생 명령으로 되돌린다. 생성 frontmatter의 선택적 시간 확장을 제거하되 정규 claim/source/event 원장은 유지한다. 후보 보고서는 비권위적 평가이므로 삭제하지 않아도 신뢰·생명주기에는 영향이 없다.

## 검토 결정

- **approve** / 검토자 `human:owner` / 시각 `2026-07-12T13:22:43+00:00` — 기록된 사유: 사용자가 2026-07-12 이번 요청에서 앞서 제안한 위생 알고리즘을 명세 주도 방식으로 구현하라고 명시적으로 승인했다. 승인은 Codex 예약 작업을 유지한 채 로컬 읽기 전용 후보 계획, 2-hop 상한, 검토 전용 충돌 후보와 보수적 OKF 시간 투영에 한정한다. 데몬, 네트워크 실행기, 자동 의미 수정, 자동 신뢰·생명주기 변경은 제외한다.

## 구현 근거

- 릴리스 보고서: `evaluations/reports/v4-release-4c4c3fd4dceba0c5.json`
- 구성요소 지문: `4c4c3fd4dceba0c58dcae3060ac95483f06c9eb31a742ebf704223bbbc87a4ad`
- 운영 환경 인증: `False`
