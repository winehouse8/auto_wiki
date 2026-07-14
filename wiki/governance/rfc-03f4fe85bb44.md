---
type: "Harness Proposal"
title: "RFC-03F4FE85BB44: 하네스 제안"
description: "하네스 제안 RFC-03F4FE85BB44의 문제·변경·검토·구현 근거."
tags: ["governance", "harness-proposal", "approved"]
timestamp: "2026-07-12T14:44:35+00:00"
generated: true
lifecycle_status: "approved"
proposal_id: "RFC-03F4FE85BB44"
---
<!-- state/proposals.json에서 자동 생성함. -->
# RFC-03F4FE85BB44: 하네스 제안 — Living Wiki GitHub 네이티브 PR 전달과 위험 기반 자동 병합

- 상태: **approved**
- 제안자: [agent:codex](../actors/actor-agent-codex.md)
- 생성 시각: `2026-07-12T14:00:23+00:00`

## 문제

기록된 문제: 현재 자동 관리 작업은 로컬 변경·commit에서 끝나 GitHub PR 단위의 명시적 감사, 원격 품질 check, 안전 변경의 조건부 병합과 사람 검토 보류가 없다. 대상 winehouse8/auto_wiki는 빈 public 저장소이며 classic PAT 사용·외부 공개·자동 병합은 기존 RFC-6BD49C04ED49의 읽기 전용 승인 범위를 넘는다.

## 제안 변경

기록된 변경안: SPEC-GH-DELIVERY-001에 따라 exact-repo allowlist, token 안전 loader, clean-run receipt, 결정론적 diff 위험 분류, 고유 branch/PR publisher, safe auto-merge와 human-review draft 경로, 비밀 없는 PR CI, CODEOWNERS·보호 설정 manifest를 추가한다. 빈 저장소에는 기존 clean HEAD 5f1d7f0만 일회성 seed하고 이후 main 직접 push를 금지한다. Codex 관리인 실행의 마지막을 검증→GitHub 전달로 연결한다.

## 근거 주장

- [CLM-207429D54323](../claims/clm-207429d54323.md)
- [CLM-A49ACF085321](../claims/clm-a49acf085321.md)
- [CLM-DA7C92E9A901](../claims/clm-da7c92e9a901.md)
- [CLM-F464CCF0AA1A](../claims/clm-f464ccf0aa1a.md)

## 수용 게이트

기록된 수용 기준: Red에서 safe/review/block/no-op, token 비노출, repo mismatch-before-token-read, clean manifest, 멱등성, base/head drift, 실패 check, Korean PR template와 secret-free pinned workflow fixture를 고정한다. Green에서 대상 테스트와 전체 release gate를 통과한다. 실제 배포는 clean HEAD seed receipt→첫 사람 검토 통합 PR까지 수행하고, 병합 뒤 별도 canary에서 remote check→auto-merge를 검증한다.

## 위험

- 기록된 위험: classic PAT가 과권한이며 GitHub에서 winehouse8 인간과 Agent 행위자를 구분하지 못함
- 기록된 위험: 첫 통합 PR은 아직 기준 브랜치에 없는 새 workflow를 필수 원격 check로 사용할 수 없음
- 기록된 위험: GitHub 장애·rate limit·기준 또는 head drift·동시 실행 때문에 전달 상태가 불명확해질 수 있음
- 기록된 위험: 자격증명이 로그·원격 URL·Git 설정·영수증 또는 PR 본문에 누출될 수 있음
- 기록된 위험: 잘못된 위험 분류가 제어면 변경을 자동 병합 후보로 오판할 수 있음
- 기록된 위험: admin 우회·main 직접 push·self-approval·신뢰하지 않은 privileged workflow를 사용하면 사람 검토 경계가 무력화될 수 있음

## 롤백

기록된 롤백: delivery를 비활성화하고 Codex 예약을 중지한다. 열린 자동 PR은 삭제하지 않고 close하며 PAT를 revoke·rotate한다. adapter·workflow·config 제거도 사람 검토 PR로 수행하고 이미 병합된 GitHub·Wiki 감사 이력은 보존한다. 내용 되돌림은 새 revert PR로 수행한다.

## 검토 결정

- **approve** / 검토자 `human:owner` / 시각 `2026-07-12T14:00:30+00:00` — 기록된 사유: 사용자가 2026-07-12 현재 요청에서 winehouse8/auto_wiki를 새 운영 저장소로 지정하고 제공한 classic GitHub token을 사용해 모든 자동 변경을 PR로 기록하며, 저위험 변경은 검증 후 자동 병합하고 사람 판단이 필요한 변경은 상세 PR만 남기도록 명시적으로 지시했다. 승인은 정확한 저장소, SPEC-GH-DELIVERY-001의 fail-closed 분류, 일회성 clean baseline seed와 비밀 비노출 경계에 한정한다. 임의 저장소·권한 확대, raw 파괴, trust 자동 변경, self-approval, admin bypass와 production 인증은 제외한다.

## 구현 근거

- 아직 구현되지 않음.
