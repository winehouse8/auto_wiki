---
type: "Admission Decision"
title: "ADM-CDEAF3837B3E"
description: "자동 신뢰 변경이 없는 출처·보안 입수 판정 ADM-CDEAF3837B3E 기록."
tags: ["admission", "reject", "audit"]
timestamp: "2026-07-11T17:14:08+00:00"
generated: true
lifecycle_status: "reject"
---
<!-- state/admissions.json에서 자동 생성함. 신뢰하지 않는 payload 본문은 의도적으로 제외함. -->
# ADM-CDEAF3837B3E

| 항목 | 값 |
|---|---|
| 후보 | `CAND-25ECE62A70EB` |
| 출처 참조 | https://aclanthology.org/2026.acl-long.981.pdf |
| 판정 | **reject** |
| 정책 효과 | `quarantine_only_no_source_promotion` |
| 평가자 | [agent:codex](../actors/actor-agent-codex.md) |
| 평가 시각 | `2026-07-11T17:14:08+00:00` |

## 설명 가능한 사유

- `CONTENT_OVERSIZE`
- `OBFUSCATED_BASE64_BLOB`
- `PERSIST_MEMORY_WRITE`

## 격리 명세표

- bundle 밖 경로: `raw/quarantine/ba41464f84dbd8e0d0aeb1e6e0d7fd83b4086b2922579b88f7947448a8e1958f/artifact.pdf`
- SHA-256: `ba41464f84dbd8e0d0aeb1e6e0d7fd83b4086b2922579b88f7947448a8e1958f`
- 크기: `1006813` 바이트
- 미디어 유형: `application/pdf`

이 후보는 정규 출처로 자동 승격되지 않았고, 이 판정은 C0–C4를 변경하지 않았다.

# 인용

[1] [후보 출처](https://aclanthology.org/2026.acl-long.981.pdf)
