---
type: Concept
title: Persistent synthesis
description: Reusable materialized knowledge views layered over immutable source retrieval.
tags: [persistent-synthesis, retrieval, memory]
timestamp: '2026-07-11T23:40:00+09:00'
claim_ids: [CLM-F6367BFF8F35]
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

## 설계 결론

RAG 대 Wiki의 이분법을 거부한다. 작은 Wiki에는 index/BM25, 큰 Wiki에는 hybrid retrieval과 graph routing을 붙이되, retrieval 결과가 claim admission을 우회하지 못하게 한다.

# Citations

[1] [Karpathy, LLM Wiki](../sources/karpathy-llm-wiki.md)
[2] [Vector RAG vs LLM-Compiled Wiki](https://arxiv.org/abs/2605.18490)
