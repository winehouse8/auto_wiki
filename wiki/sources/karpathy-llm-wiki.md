---
type: Reference
title: Karpathy의 LLM Wiki 분석
description: LLM이 지속 관리하는 Markdown Wiki 패턴과 그 인식론적 한계.
resource: https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f
tags: [llm-wiki, practitioner-source, persistent-synthesis]
timestamp: '2026-07-11T23:40:00+09:00'
source_id: SRC-CFB88DDE3FF1
source_level: S2
---

# Karpathy의 LLM Wiki 분석

출처 ID: `SRC-CFB88DDE3FF1`

출처 수준: S2 — 실무자 아이디어 문서

[원문](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)

## 무엇을 제안하는가

RAG가 질문마다 raw chunk를 다시 조립하는 한계를 지적하고, 불변 raw sources와 사용자 사이에 LLM이 지속적으로 관리하는 Markdown Wiki를 둔다. 새 source가 들어오면 source summary만 추가하는 것이 아니라 entity, concept, overview, synthesis, contradiction, index, log를 함께 갱신한다. 질문에서 나온 가치 있는 비교와 분석도 Wiki에 되돌려 연구가 복리로 축적되게 한다.

세 계층은 `raw sources`, LLM이 소유하는 `wiki`, 운영 규약인 `schema/AGENTS.md`다. 연산은 ingest, query, lint다. 작은 규모에서는 index/log와 Markdown/Git/Obsidian으로 시작하고 필요할 때 hybrid search를 붙인다.

## 가져온 것

- 원문 불변성과 합성물 가변성 분리
- chat 답변을 지속 가능한 artifact로 컴파일
- schema를 단순 prompt가 아니라 운영 헌법으로 취급
- ingest/query/lint의 명시적 구분
- Markdown/Git 우선, 검색 인프라는 실제 병목이 생길 때 추가

## 비판

- raw를 source of truth라 부르지만 provenance와 truth는 다르다.
- 출처 신뢰성, 원자적 주장, 정확한 위치 지정자, 불확실성 모델이 없다.
- 사람이 source와 방향을 고르고 LLM이 관리하는 역할 분리라 actor parity와 다르다.
- 자율 source discovery, 주기, 예산, stop condition이 없다.
- 같은 모델이 쓰고 lint할 때의 correlated error를 다루지 않는다.
- “유지 비용이 거의 0”이라는 표현은 API 비용·semantic drift·검토·복구를 과소평가한다.
- query 산출물을 다시 evidence처럼 쓰면 self-citation loop가 생긴다.
- prompt injection, memory poisoning, 저작권·비밀·동시성·평가가 빠져 있다.

## 판정

설계 뼈대로는 매우 유용하지만 경험적 증명은 아니다. author reputation과 별 개수는 읽을 우선순위를 높일 뿐 claim confidence를 올리지 않는다.

# 인용

[1] [Karpathy, LLM Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)
