---
type: "Admission Decision"
title: "ADM-630AF6D54A6B"
description: "자동 신뢰 변경이 없는 출처·보안 입수 판정 ADM-630AF6D54A6B 기록."
tags: ["admission", "reject", "audit"]
timestamp: "2026-07-11T17:14:08+00:00"
generated: true
lifecycle_status: "reject"
---
<!-- state/admissions.json에서 자동 생성함. 신뢰하지 않는 payload 본문은 의도적으로 제외함. -->
# ADM-630AF6D54A6B

| 항목 | 값 |
|---|---|
| 후보 | `CAND-36045B5CE5EC` |
| 출처 참조 | https://aclanthology.org/2026.acl-long.670.pdf |
| 판정 | **reject** |
| 정책 효과 | `quarantine_only_no_source_promotion` |
| 평가자 | [agent:codex](../actors/actor-agent-codex.md) |
| 평가 시각 | `2026-07-11T17:14:08+00:00` |

## 설명 가능한 사유

- `CONTENT_OVERSIZE`

## 격리 명세표

- bundle 밖 경로: `raw/quarantine/cd68d108d075b2ff4f56dc5f1b4ec0aa53452b658fad4d3cf7ad698100da106d/artifact.pdf`
- SHA-256: `cd68d108d075b2ff4f56dc5f1b4ec0aa53452b658fad4d3cf7ad698100da106d`
- 크기: `2615191` 바이트
- 미디어 유형: `application/pdf`

이 후보는 정규 출처로 자동 승격되지 않았고, 이 판정은 C0–C4를 변경하지 않았다.

# 인용

[1] [후보 출처](https://aclanthology.org/2026.acl-long.670.pdf)
