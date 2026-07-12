---
type: Concept
title: 출처 발견과 수용
description: 출처 사다리, 전달자·메시지 평가, 반증 검색, 오염 방어형 수용 절차.
tags: [source-quality, admission, security, search]
timestamp: '2026-07-11T23:40:00+09:00'
claim_ids: [CLM-860EB3D6AAEB, CLM-4A3051A018DC, CLM-61B3C391010C]
---

# 출처 발견과 수용

## 쓰레기 입력 문제

검색 결과 상위에 있다는 사실, 여러 사이트가 반복했다는 사실, 유명인이 말했다는 사실은 주장 근거가 아니다. 검색 시스템의 품질은 재현율뿐 아니라 전달자 품질, 메시지 품질, 독립성, 반대 근거, 상태를 포함한다.

관련 주장: [CLM-860EB3D6AAEB](../claims/clm-860eb3d6aaeb.md), [CLM-4A3051A018DC](../claims/clm-4a3051a018dc.md), [CLM-61B3C391010C](../claims/clm-61b3c391010c.md)

## 기본 출처 사다리

1. 공식 표준·원 논문·원 데이터·원 코드·법령/공식 기록
2. 저자/기관의 직접 설명
3. 학회·전문기관의 검증된 합성
4. 평판 좋은 2차 분석
5. 블로그·뉴스·YouTube·SNS는 단서로 사용하고 원출처 추적

## 메신저 평가

- 해당 분야 전문성
- 원자료 접근성·방법 투명성
- 동료 검토와 정정·철회 이력
- 이해상충과 상업적 유인
- 저자·기관 신원과 사칭 위험

## 메시지 평가

- 주장에 직접 답하는가
- 데이터와 방법이 공개됐는가
- 범위와 시점이 일치하는가
- 독립 재현·교차확인이 있는가
- 반대 근거를 다루는가

## 수용 게이트

비신뢰 수신함 → 스냅샷·해시 → 격리된 파싱 → 상태·라이선스 확인 → 주장 추출 → 기원 그룹 → 반증 검색 → 검증자 → `quarantine`/`candidate`/`accepted`.

출처 평판은 수용 우선순위를 바꾸지만, 정확한 근거와 모순을 무시할 권한을 주지 않는다.

# 인용

[1] [Assessing Web Search Credibility and Response Groundedness](https://aclanthology.org/2026.eacl-long.115/)
[2] [A-MemGuard](https://openreview.net/forum?id=udqe7UZUZ6)
[3] [From Untrusted Input to Trusted Memory](https://arxiv.org/abs/2606.04329)
[4] [SafeSearch](https://openreview.net/forum?id=95VVL0TJNH)
