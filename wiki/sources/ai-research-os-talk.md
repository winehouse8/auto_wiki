---
type: Reference
title: AI Engineer — Turn 10,994 Notes Into Memory
description: Timestamped critical analysis of the AI Research OS conference talk.
resource: https://www.youtube.com/watch?v=ZRM_TfEZcIo
tags: [ai-research-os, youtube, practitioner-source]
timestamp: '2026-07-11T23:40:00+09:00'
source_id: SRC-1C96ABEBBA41
source_level: S2
---

# AI Engineer — Turn 10,994 Notes Into Memory

Source ID: `SRC-1C96ABEBBA41`  
Source level: S2 — first-party practitioner talk  
[영상](https://www.youtube.com/watch?v=ZRM_TfEZcIo) · [구현](https://github.com/iusztinpaul/ai-research-os-workshop)

## 타임스탬프 지도

- `00:00–09:16`: 흩어진 Second Brain을 다음 세션에 재사용하지 못하는 문제
- `09:16–12:48`: 로컬 Markdown/Obsidian과 커넥터
- `12:48–18:28`: V1 정적 research.md → V2 개인 source 연결의 한계
- `18:28–25:01`: V3 raw/index/wiki와 점진적 context loading
- `25:01–27:04`: 전체 개인 vault의 읽기 전용 snapshot과 프로젝트 Wiki 분리
- `27:04–36:50`: deep research, GitHub, web-link ingest 데모
- `36:50–38:45`: provenance, source strength/ranking, lint, compaction, UX의 미완성 인정
- `38:45–39:32`: 유료 강의 홍보

## 가져온 것

- query/append/deep mode 분리
- index summary → source page → derivative → raw의 progressive disclosure
- 전체 memory와 프로젝트별 working research 분리
- 질문도 open question/comparison/note로 지속 저장
- 공개 코드와 일반 파일로 provider lock-in 최소화

## 비판

- relevance ranking을 source trust로 오해하면 안 된다.
- “10,994 notes”는 입력 규모이지 claim accuracy나 장기 검색 recall의 benchmark가 아니다.
- 발표와 데모는 동일 제작자의 self-report이며 독립 성능 평가가 없다.
- source span 단위 provenance, actor identity, review/appeal, autonomous cadence가 없다.
- 개인 자료 우선은 확증편향을 강화할 수 있지만 counter-search가 기본 규칙이 아니다.
- 임의 웹/저장소/영상 input의 prompt injection과 memory poisoning을 다루지 않는다.

## 저장소와의 관계

영상의 V3와 현재 GitHub의 v4 conventions는 다르다. 현재 저장소에는 contradictions와 lint가 추가됐지만, 사용자 seed는 `relevance_score: 1.0`이고 claim-level trust model은 여전히 없다. 영상과 저장소를 하나의 고정 명세로 취급하지 않는다.

# Citations

[1] [Turn 10,994 Notes Into Memory](https://www.youtube.com/watch?v=ZRM_TfEZcIo)
[2] [ai-research-os-workshop](https://github.com/iusztinpaul/ai-research-os-workshop)
