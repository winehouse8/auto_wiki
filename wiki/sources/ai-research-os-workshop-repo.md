---
type: Reference
title: ai-research-os-workshop repository
description: Critical implementation review of the repository shared in the AI Engineer talk.
resource: https://github.com/iusztinpaul/ai-research-os-workshop
tags: [ai-research-os, source-code, implementation]
timestamp: '2026-07-11T23:40:00+09:00'
source_id: SRC-1BE9C681A9BA
source_level: S3
---

# ai-research-os-workshop repository

Source ID: `SRC-1BE9C681A9BA`  
Source level: S3 for implementation facts, not for efficacy  
[GitHub](https://github.com/iusztinpaul/ai-research-os-workshop)

## 확인한 구현

- `raw/`, `index.yaml`, `index.md`, `log.md`, `wiki/`의 file-first layout
- sources, concepts, entities, comparisons, questions, contradictions, open questions
- query/append/deep/init routing과 depth preset
- YouTube captions, GitHub, web, PDF, Obsidian, Readwise, NotebookLM connector
- deterministic index builder와 cheap lint scripts
- current conventions 자체 표기는 v4

## 강점

실제 파일과 code path를 검사할 수 있는 공개 MIT 구현이다. progressive disclosure, immutable raw, deterministic index, idempotency, graceful connector degradation 같은 운영 원칙이 구체적이다.

## 한계

- seed의 `relevance_score: 1.0`은 trust가 아니다.
- citation rule은 raw/source page 링크를 요구하지만 모든 문장에 atomic claim ID와 exact span을 강제하지 않는다.
- 사람은 wiki를 deliberate override로만 편집하는 구조여서 동일 contribution protocol이 아니다.
- lint는 stale/contradiction을 주로 LLM judge에 맡기며 independent model/benchmark 보장이 없다.
- source provenance, publication/retraction status, independence cluster, conflicts of interest가 신뢰 계산에 연결되지 않는다.
- self-scheduled research와 benchmark-gated harness evolution이 없다.

## 독립성 주의

이 저장소와 연결 영상은 같은 제작자 집단의 artifact이므로 두 개의 독립 corroboration으로 세지 않는다. (`ai-research-os-authors` independence group)

# Citations

[1] [ai-research-os-workshop](https://github.com/iusztinpaul/ai-research-os-workshop)
