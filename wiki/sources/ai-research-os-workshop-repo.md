---
type: Reference
title: ai-research-os-workshop 저장소 분석
description: AI Engineer 발표에서 공유된 저장소 구현에 대한 비판적 검토.
resource: https://github.com/iusztinpaul/ai-research-os-workshop
tags: [ai-research-os, source-code, implementation]
timestamp: '2026-07-11T23:40:00+09:00'
source_id: SRC-1BE9C681A9BA
source_level: S3
---

# ai-research-os-workshop 저장소 분석

출처 ID: `SRC-1BE9C681A9BA`

출처 수준: 구현 사실에는 S3, 효능에는 적용하지 않음

[GitHub](https://github.com/iusztinpaul/ai-research-os-workshop)

## 확인한 구현

- `raw/`, `index.yaml`, `index.md`, `log.md`, `wiki/`의 파일 우선 배치
- 출처, 개념, 개체, 비교, 질문, 모순, 미해결 질문
- `query`·`append`·`deep`·`init` 라우팅과 깊이 사전설정
- YouTube 자막, GitHub, 웹, PDF, Obsidian, Readwise, NotebookLM 커넥터
- 결정론적 색인 생성기와 저비용 린트 스크립트
- 현재 규약의 자체 표기는 v4

## 강점

실제 파일과 코드 경로를 검사할 수 있는 공개 MIT 구현이다. 점진적 공개, 불변 원문, 결정론적 색인, 멱등성, 커넥터 성능 저하 대응 같은 운영 원칙이 구체적이다.

## 한계

- 씨앗값의 `relevance_score: 1.0`은 신뢰가 아니다.
- 인용 규칙은 원문·출처 페이지 링크를 요구하지만 모든 문장에 원자적 주장 ID와 정확한 범위를 강제하지 않는다.
- 사람은 Wiki를 의도적 재정의로만 편집하는 구조여서 동일한 기여 절차가 아니다.
- 린트는 노후·모순 판정을 주로 LLM 판정자에 맡기며 독립 모델·벤치마크 보장이 없다.
- 출처 추적, 출판·철회 상태, 독립성 묶음, 이해관계 충돌이 신뢰 계산에 연결되지 않는다.
- 자체 예약 연구와 벤치마크 게이트를 거치는 하네스 발전이 없다.

## 독립성 주의

이 저장소와 연결 영상은 같은 제작자 집단의 산출물이므로 두 개의 독립 교차확인으로 세지 않는다. 독립성 그룹은 `ai-research-os-authors`다.

# 인용

[1] [ai-research-os-workshop](https://github.com/iusztinpaul/ai-research-os-workshop)
