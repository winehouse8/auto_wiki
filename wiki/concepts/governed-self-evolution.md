---
type: Concept
title: 거버넌스 기반 자기진화
description: 행위자가 귀속된 RFC와 벤치마크 게이트를 통한 가역적 하네스 진화.
tags: [self-evolution, evaluation, rollback, governance]
timestamp: '2026-07-12T12:00:00+09:00'
claim_ids: [CLM-F464CCF0AA1A, CLM-1EB8BD726482, CLM-FC9028899EE0, CLM-95A38CACF2CD]
---

# 거버넌스 기반 자기진화

## 자기진화의 의미

새 파일을 계속 추가하는 것은 진화가 아니다. 반복 작업의 실패를 관찰하고, 변경 가설을 만들고, 고정 평가에서 비교하며, 회귀 없이 유용성이 유지될 때 하네스를 승격하는 과정이다.

관련 주장: [CLM-F464CCF0AA1A](../claims/clm-f464ccf0aa1a.md), [CLM-1EB8BD726482](../claims/clm-1eb8bd726482.md), [CLM-FC9028899EE0](../claims/clm-fc9028899ee0.md), [CLM-95A38CACF2CD](../claims/clm-95a38cacf2cd.md)

## 안전한 루프

```text
관찰된 실패/사건
→ 재실행 가능한 환경과 성공 기준
→ 모델 / 하네스 / 메모리 / 콘텐츠 중 최소 변경 계층 선택
→ 최소 RFC
→ 후보 브랜치/스냅샷
→ 고정 벤치마크 + 보안 적대적 검증
→ 품질·비용·보안 비교
→ 마이그레이션과 롤백 예행연습
→ 승인
→ 릴리스 태그
```

실패는 다음 조사나 평가의 수요를 정하지만, Agent의 실패 원인 설명 자체가 새 사실의 근거는 아니다. 새 문맥이나 기억이 문제를 해결했다는 사실과 과거 능력을 회귀시키지 않았다는 사실을 같은 재실행 집합에서 분리해 확인한다.

## 금지

- 평가 기준과 후보 하네스를 같은 실행이 조용히 함께 수정
- 최신 벤치마크에만 맞춘 프롬프트를 개선으로 선언
- writer Agent 여러 개의 다수결을 독립 검증으로 간주
- 과거 실패와 반대 결과 삭제
- 롤백 없는 스키마 마이그레이션

현재 v4는 사람 `policy-approver`가 승인한 RFC만 릴리스 게이트와 롤백 근거 뒤에서 구현 완료로 닫는다. 미래 RFC를 자동 승인·적용하지 않으며 고정 fixture 통과도 운영 환경 인증으로 승격하지 않는다.

# 인용

[1] [DeepFact](https://aclanthology.org/2026.acl-long.1586/)
[2] [Beyond Single-shot Writing](https://aclanthology.org/2026.acl-long.609/)
[3] [LEDGER](https://aclanthology.org/2026.findings-acl.515/)
[4] [NIST AI Risk Management Framework](https://www.nist.gov/itl/ai-risk-management-framework)
[5] [Continual Learning for AI Agents](../sources/src-ad0b1d50c531.md)
[6] [Demand-Driven Context](../sources/src-54d07435eb56.md)
