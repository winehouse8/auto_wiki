---
type: Reference
title: AI Engineer 발표 분석 — Turn 10,994 Notes Into Memory
description: AI Research OS 콘퍼런스 발표의 타임스탬프 기반 비판적 분석.
resource: https://www.youtube.com/watch?v=ZRM_TfEZcIo
tags: [ai-research-os, youtube, practitioner-source]
timestamp: '2026-07-11T23:40:00+09:00'
source_id: SRC-1C96ABEBBA41
source_level: S2
---

# AI Engineer 발표 분석 — Turn 10,994 Notes Into Memory

출처 ID: `SRC-1C96ABEBBA41`

출처 수준: S2 — 당사자 실무자 발표

[영상](https://www.youtube.com/watch?v=ZRM_TfEZcIo) · [구현](https://github.com/iusztinpaul/ai-research-os-workshop)

## 타임스탬프 지도

- `00:00–09:16`: 흩어진 세컨드 브레인을 다음 세션에 재사용하지 못하는 문제
- `09:16–12:48`: 로컬 Markdown/Obsidian과 커넥터
- `12:48–18:28`: V1 정적 research.md → V2 개인 source 연결의 한계
- `18:28–25:01`: V3 `raw`·`index`·`wiki`와 점진적 문맥 적재
- `25:01–27:04`: 전체 개인 보관소의 읽기 전용 스냅샷과 프로젝트 Wiki 분리
- `27:04–36:50`: 심층 조사, GitHub, 웹 링크 수집 시연
- `36:50–38:45`: 출처 추적, 출처 강도·순위, 린트, 압축, 사용자 경험의 미완성 인정
- `38:45–39:32`: 유료 강의 홍보

## 가져온 것

- `query`·`append`·`deep` 모드 분리
- 색인 요약 → 출처 문서 → 파생물 → 원문의 점진적 공개
- 전체 기억과 프로젝트별 연구 작업 분리
- 질문도 미해결 질문·비교·메모로 지속 저장
- 공개 코드와 일반 파일로 공급자 종속 최소화

## 비판

- 관련성 순위를 출처 신뢰로 오해하면 안 된다.
- “10,994 notes”는 입력 규모이지 주장 정확도나 장기 검색 재현율의 벤치마크가 아니다.
- 발표와 시연은 동일 제작자의 자기 보고이며 독립 성능 평가가 없다.
- 출처 구간 단위의 출처 추적, 행위자 식별, 검토·이의 제기, 자율 실행 주기가 없다.
- 개인 자료 우선은 확증편향을 강화할 수 있지만 반증 검색이 기본 규칙이 아니다.
- 임의 웹·저장소·영상 입력의 프롬프트 주입과 메모리 오염을 다루지 않는다.

## 저장소와의 관계

영상의 V3와 현재 GitHub의 v4 규약은 다르다. 현재 저장소에는 모순 기록과 린트가 추가됐지만, 사용자 씨앗값은 `relevance_score: 1.0`이고 주장 단위 신뢰 모델은 여전히 없다. 영상과 저장소를 하나의 고정 명세로 취급하지 않는다.

# 인용

[1] [Turn 10,994 Notes Into Memory](https://www.youtube.com/watch?v=ZRM_TfEZcIo)
[2] [ai-research-os-workshop](https://github.com/iusztinpaul/ai-research-os-workshop)
