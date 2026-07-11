---
type: Concept
title: Governed self-evolution
description: Benchmark-gated, reversible harness evolution through attributed RFCs.
tags: [self-evolution, evaluation, rollback, governance]
timestamp: '2026-07-12T12:00:00+09:00'
claim_ids: [CLM-F464CCF0AA1A, CLM-1EB8BD726482, CLM-FC9028899EE0]
---

# Governed self-evolution

## 자기진화의 의미

새 파일을 계속 추가하는 것은 진화가 아니다. 반복 작업의 실패를 관찰하고, 변경 가설을 만들고, 고정 평가에서 비교하며, 회귀 없이 유용성이 유지될 때 하네스를 승격하는 과정이다.

관련 claim: `CLM-F464CCF0AA1A`, `CLM-1EB8BD726482`, `CLM-FC9028899EE0`

## 안전한 루프

```text
failure/event
→ minimal RFC
→ candidate branch/snapshot
→ fixed benchmark + red team
→ quality/cost/security comparison
→ migration and rollback rehearsal
→ approval
→ release tag
```

## 금지

- 평가 기준과 후보 하네스를 같은 실행이 조용히 함께 수정
- 최신 benchmark에만 맞춘 prompt를 개선으로 선언
- writer Agent 여러 개의 다수결을 독립 검증으로 간주
- 과거 실패와 반대 결과 삭제
- rollback 없는 schema migration

현재 v4는 사람 policy-approver가 승인한 RFC만 release gate와 rollback evidence 뒤에서 구현 완료로 닫는다. 미래 RFC를 자동 승인·적용하지 않으며 fixed-fixture 통과도 production 인증으로 승격하지 않는다.

# Citations

[1] [DeepFact](https://aclanthology.org/2026.acl-long.1586/)
[2] [Beyond Single-shot Writing](https://aclanthology.org/2026.acl-long.609/)
[3] [LEDGER](https://aclanthology.org/2026.findings-acl.515/)
[4] [NIST AI Risk Management Framework](https://www.nist.gov/itl/ai-risk-management-framework)
