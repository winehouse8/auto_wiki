---
type: Reference
title: Open Knowledge Format v0.1 초안 분석
description: Living Wiki와 관련된 공식 OKF 구조·적합성 규칙·확장 모델·한계.
resource: https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md
tags: [okf, specification, interoperability]
timestamp: '2026-07-11T23:55:00+09:00'
source_id: SRC-477696BD1807
source_level: S3
claim_ids: [CLM-7FDAF2F91E73, CLM-952258184EF2, CLM-F526A53CB69F]
---

# Open Knowledge Format v0.1 초안 분석

## 출처 상태

- 공식 저장소: `GoogleCloudPlatform/knowledge-catalog`
- 명세 상태: Version 0.1 — Draft
- 릴리스·태그: 2026-07-11 기준 관찰되지 않음
- 공식 `okf/` 디렉터리 라이선스: Apache-2.0
- 검사한 저장소 커밋: `d44368c15e38e7c92481c5992e4f9b5b421a801d`
- `SPEC.md` blob 해시: `55d0a46cc988e99aa35cd027964d6278a4f93f35`
- 로컬 스냅샷 SHA-256: `b9655e607346dbbdc6de21190e9a953313eda6a7eba68d4d272a65975940ad6e`

## 이 Wiki가 사용하는 규범적 핵심

1. 번들은 Markdown 파일로 이뤄진 계층형 디렉터리다.
2. 예약 문서가 아닌 모든 Markdown 개념은 파싱 가능한 YAML frontmatter를 가진다.
3. `type`은 유일한 필수 핵심 필드이며 비어 있으면 안 된다.
4. `index.md`와 `log.md`는 예약 파일명이다.
5. 표준 Markdown 링크로 개념 사이의 관계를 표현한다.
6. 생산자 확장 필드를 허용하며, 알 수 없는 필드도 보존해야 한다.

## 의도적으로 제외한 목표

OKF는 고정된 유형 분류 체계, 저장·질의 실행 환경, 도메인 스키마의 대체물을 규정하지 않는다. 또한 Living Wiki의 주장 신뢰도, 출처 신뢰성, 행위자 신원, 근거 독립성, 검토, 오염 방어, 자기진화 거버넌스도 정의하지 않는다.

## 구현상 주의점

공식 참조 Agent는 형식 자체가 아니라 개념 증명이다. 일부 경로에서 내부 문서 모델이 최소 명세보다 엄격하므로, 이 Wiki는 필수 `type`뿐 아니라 권장 필드인 `title`, `description`, `timestamp`도 포함한다.

# 인용

[1] [Official Open Knowledge Format v0.1 specification](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/d44368c15e38e7c92481c5992e4f9b5b421a801d/okf/SPEC.md)
[2] [Google Cloud announcement](https://cloud.google.com/blog/products/data-analytics/how-the-open-knowledge-format-can-improve-data-sharing)
[3] [Official OKF README and reference implementation](https://github.com/GoogleCloudPlatform/knowledge-catalog/tree/d44368c15e38e7c92481c5992e4f9b5b421a801d/okf)
