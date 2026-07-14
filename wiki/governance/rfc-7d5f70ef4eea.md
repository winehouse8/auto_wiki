---
type: "Harness Proposal"
title: "RFC-7D5F70EF4EEA: 하네스 제안"
description: "하네스 제안 RFC-7D5F70EF4EEA의 문제·변경·검토·구현 근거."
tags: ["governance", "harness-proposal", "implemented"]
timestamp: "2026-07-12T04:00:23+00:00"
generated: true
lifecycle_status: "implemented"
proposal_id: "RFC-7D5F70EF4EEA"
---
<!-- state/proposals.json에서 자동 생성함. -->
# RFC-7D5F70EF4EEA: 하네스 제안 — 한국어 문서 게이트의 사람이 읽는 다이어그램 검사

- 상태: **implemented**
- 제안자: [agent:codex](../actors/actor-agent-codex.md)
- 생성 시각: `2026-07-12T03:44:48+00:00`

## 문제

기록된 문제: SPEC-KO-DOCS-001의 검사기가 text와 Mermaid 코드 펜스를 전부 코드로 간주해 사람이 읽는 영문 다이어그램 문구를 놓친다.

## 제안 변경

기록된 변경안: 사람이 읽는 다이어그램 펜스를 한국어 계약 범위에 포함하고 기존 다이어그램을 한국어화하며 Red 회귀검사와 전체 릴리스 게이트를 다시 통과한다.

## 근거 주장

- 없음

## 수용 게이트

기록된 수용 기준: AC-KO-011 실패 테스트를 먼저 고정하고 text·plaintext·Mermaid 다이어그램의 영문 전용 라벨을 거부하되 bash·python·json·yaml 등 실행 가능한 코드 펜스와 기계 토큰은 보존한다. 전체 283개 이상 테스트와 8개 릴리스 게이트를 다시 통과한다.

## 위험

- 기록된 위험: 다이어그램 번역으로 의미가 바뀔 수 있음
- 기록된 위험: 코드 예제를 오탐할 수 있음

## 롤백

기록된 롤백: 다이어그램 검사 확장을 되돌리되 한국어로 바꾼 설명 문구와 append-only 사건 원장은 보존한다. 코드·경로·식별자는 변경하지 않는다.

## 검토 결정

- **approve** / 검토자 `human:owner` / 시각 `2026-07-12T03:44:52+00:00` — 기록된 사유: 사용자가 모든 Wiki와 하네스 문서를 한국어로 작성하라고 명시했다. 사람이 읽는 다이어그램도 문서이므로 기존 지시의 범위 안에서 이 누락을 수정하도록 승인한다.

## 구현 근거

- 릴리스 보고서: `evaluations/reports/v4-release-66bb07834d81ed26.json`
- 구성요소 지문: `66bb07834d81ed2655ba6a604152e0b49c72bddec03c44a571a2676bb9f4d3a4`
- 운영 환경 인증: `False`
