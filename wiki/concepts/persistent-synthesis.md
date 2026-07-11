---
type: Concept
title: Persistent synthesis
description: Reusable materialized knowledge views layered over immutable source retrieval.
tags: [persistent-synthesis, retrieval, memory]
timestamp: '2026-07-12T18:30:00+09:00'
claim_ids: [CLM-F6367BFF8F35, CLM-F79558D817DF, CLM-EC52C0576A28]
---

# Persistent synthesis

## 정의

원문을 질의 때마다 처음부터 조합하지 않고, 재사용 가능한 concept·comparison·thesis를 지속 artifact로 유지하는 방식이다. raw retrieval을 없애는 것이 아니라 이미 수행한 고비용 synthesis를 materialized view처럼 보존한다.

관련 claim: `CLM-F6367BFF8F35` (C2)

## 언제 가치가 있는가

- 여러 source를 가로지르는 연결이 반복 질문에서 재사용될 때
- overview와 contradiction이 다음 연구 질문을 바꿀 때
- 원문보다 작은 active knowledge surface로 압축될 때
- 언제든 claim→evidence→raw로 내려갈 수 있을 때

## 실패 조건

- source마다 mirror page만 늘어 compression이 없을 때
- synthesis가 독립 evidence로 재인용될 때
- stale dependency를 갱신하지 않을 때
- 모든 간단한 질문까지 비싼 ingest/rewrite를 수행할 때
- model·도구·정책이 바뀐 뒤 stale synthesis를 계속 우선할 때
- 과거 Wiki 관점이 fresh investigation을 구조적으로 막을 때
- retrieval 결과의 이후 유용성을 기록하지 않거나 그 신호로 trust를 자동 조작할 때

## 설계 결론

RAG 대 Wiki의 이분법을 거부한다. 작은 Wiki에는 index/BM25, 큰 Wiki에는 hybrid retrieval과 graph routing을 붙이되, retrieval 결과가 claim admission을 우회하지 못하게 한다.

기본 응답은 `wiki-first`지만 사용자가 원하면 `fresh-check`로 원자료 기반 독립 재조사를 먼저 수행하고 기존 Wiki와 차이를 비교한다. 이 모드는 index bootstrap과 provenance 검사를 유지하며 과거 기록을 삭제하지 않는다.

# Citations

[1] [Karpathy, LLM Wiki](../sources/karpathy-llm-wiki.md)
[2] [Vector RAG vs LLM-Compiled Wiki](https://arxiv.org/abs/2605.18490)
[3] [How Memory Management Impacts LLM Agents](../sources/src-af06bcdc1ed2.md)
[4] [Controllable Memory Usage](../sources/src-f9ba839fa59d.md)
