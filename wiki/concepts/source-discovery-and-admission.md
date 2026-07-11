---
type: Concept
title: Source discovery and admission
description: Source ladder, messenger/message assessment, counter-search, and poisoning-resistant admission.
tags: [source-quality, admission, security, search]
timestamp: '2026-07-11T23:40:00+09:00'
claim_ids: [CLM-860EB3D6AAEB, CLM-4A3051A018DC, CLM-61B3C391010C]
---

# Source discovery and admission

## Garbage-in 문제

검색 결과 상위에 있다는 사실, 여러 사이트가 반복했다는 사실, 유명인이 말했다는 사실은 claim support가 아니다. 검색 시스템의 품질은 recall만 아니라 messenger quality, message quality, independence, counter-evidence, status를 포함한다.

관련 claim: `CLM-860EB3D6AAEB`, `CLM-4A3051A018DC`, `CLM-61B3C391010C`

## 기본 source ladder

1. 공식 표준·원 논문·원 데이터·원 코드·법령/공식 기록
2. 저자/기관의 직접 설명
3. 학회·전문기관의 검증된 합성
4. 평판 좋은 2차 분석
5. 블로그·뉴스·YouTube·SNS는 lead로 사용하고 원출처 추적

## 메신저 평가

- 해당 domain 전문성
- 원자료 접근성·방법 투명성
- peer review와 정정/철회 이력
- 이해상충과 상업적 유인
- 저자/기관 identity와 impersonation 위험

## 메시지 평가

- claim에 직접 답하는가
- 데이터와 방법이 공개됐는가
- scope와 시점이 일치하는가
- 독립 재현·교차확인이 있는가
- 반대 evidence를 다루는가

## Admission gate

untrusted inbox → snapshot/hash → sandboxed parse → status/license 확인 → claim extraction → origin cluster → counter-search → verifier → quarantine/candidate/accepted.

출처 평판은 admission 우선순위를 바꾸지만, exact evidence와 contradiction을 무시할 권한을 주지 않는다.

# Citations

[1] [Assessing Web Search Credibility and Response Groundedness](https://aclanthology.org/2026.eacl-long.115/)
[2] [A-MemGuard](https://openreview.net/forum?id=udqe7UZUZ6)
[3] [From Untrusted Input to Trusted Memory](https://arxiv.org/abs/2606.04329)
[4] [SafeSearch](https://openreview.net/forum?id=95VVL0TJNH)
