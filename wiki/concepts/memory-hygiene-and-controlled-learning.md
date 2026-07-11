---
type: Concept
title: Memory hygiene and controlled learning
description: Failure-driven curation, outcome feedback, temporal lifecycle, and user-controlled reliance without automatic trust promotion.
tags: [memory-hygiene, continual-learning, staleness, feedback, human-control]
timestamp: '2026-07-12T17:30:00+09:00'
claim_ids: [CLM-95A38CACF2CD, CLM-F79558D817DF, CLM-EC52C0576A28, CLM-207429D54323]
---

# Memory hygiene and controlled learning

## 결론

살아 있는 Wiki가 오래 기억하는 것만으로는 충분하지 않다. 무엇을 다시 조사할지, 과거 지식이 아직 유효한지, 검색된 기억이 실제로 도움이 됐는지, 사용자가 이번 작업에서 과거 관점에 얼마나 의존하고 싶은지를 각각 분리해 다뤄야 한다.

관련 claim:

- `CLM-95A38CACF2CD`: 실패는 지식 공백 탐색의 우선순위 신호이지 사실성 증명이 아니다.
- `CLM-F79558D817DF`: retrieval 결과와 시간 상태는 감사하되 trust 승격·삭제를 자동화하지 않는다.
- `CLM-EC52C0576A28`: 사용자가 기억 의존도를 조절한다.
- `CLM-207429D54323`: append-only log와 외부 세계 상태를 구분한다.

## 조사에서 채택한 패턴

### 1. 실패 → 조사 수요 → 검증 → 승격

Demand-Driven Context는 실제 실패를 이용해 어떤 domain knowledge가 부족한지 좁힌다. 그러나 논문의 20–30회 수렴은 아직 가설이며, 저자 자신의 worked example과 구현이므로 독립 효능 검증이 아니다. Living Wiki는 실패를 campaign priority에만 쓰고, source admission·counter-search·replay·human/independent review를 통과하기 전에는 새 지식을 canonical claim으로 승격하지 않는다.[1][2]

### 2. 실패 로그 → replayable evaluation → 최소 계층 수정

Continual-learning 발표는 log와 feedback만으로는 부족하고, 실패 당시 조건과 성공 판정을 재실행할 수 있어야 하며, model·harness·memory 중 가장 작은 지속 가능한 계층을 고쳐야 한다고 주장한다. 이는 기존 benchmark-gated self-evolution을 강화하지만, RELAI의 성능 수치는 독립 benchmark가 없으므로 채택하지 않는다.[3]

### 3. staleness와 downstream outcome은 위생 신호

Lovable 사례는 model·feature 변경 뒤 context가 빠르게 낡는다고 보고한다. ACL 2026 실험은 잘못되거나 misaligned한 과거 경험이 미래 실행에 오류를 전파할 수 있고, 이후 task 평가가 memory quality 신호가 될 수 있음을 보였다. 따라서 Living Wiki는 stale·harmful·irrelevant 후보를 보고하되, 그 신호만으로 C-level/S-level을 바꾸거나 원문을 삭제하지 않는다.[4][5]

### 4. 기억 의존도는 사용자 제어

SteeM은 장기 개인화 대화에서 모든 기억을 따르는 방식과 전혀 쓰지 않는 방식 사이를 사용자 제어 축으로 실험했다. Living Wiki는 이를 그대로 일반화하지 않고 다음 UX 원칙만 채택한다.[6]

- `wiki-first`: 기존 Wiki claim에서 시작한다.
- `fresh-check`: index는 읽되 기존 synthesis 결론을 잠시 괄호 친 뒤 원자료로 독립 재조사하고 마지막에 비교한다.
- `strict-evidence`: exact locator가 있는 C2 이상 factual claim만 답변의 핵심 근거로 쓴다.

`fresh-check`는 기억 삭제나 bootstrap 우회가 아니다.

### 5. log는 기록이지 세계 전체가 아니다

`The Log Is The Agent`는 append-only log에서 context·UI·compaction을 재투영하는 장점을 설명하면서도, 파일 변경·이메일·외부 서비스 상태는 log 밖에 있고 fork가 side effect를 되돌리지 못한다고 인정한다. 따라서 Living Wiki의 event chain은 감사 기록으로 유지하되 snapshot hash, source artifact, version, external-work receipt와 rollback evidence를 별도로 보존한다.[7]

## 채택하지 않은 것

- vendor 자체 `utility score`를 retrieval ranking이나 trust에 자동 반영
- 오래됐거나 조회가 적다는 이유만으로 source/raw 자동 삭제
- model rationale나 chain-of-thought 전체를 decision provenance로 저장
- 현재 규모에서 benchmark 없이 GraphRAG/vector DB를 기본 계층으로 도입
- append-only text log 하나만으로 workspace와 외부 side effect가 복구된다고 가정
- 실패한 Agent의 자기진단을 독립 검토로 계산

## 하네스 적용

승인된 `RFC-5D91E03B5BC5`는 다음을 additive하게 도입한다.

1. configured freshness를 실제 날짜에 대조하는 deterministic memory-hygiene report
2. raw query를 저장하지 않는 attributed retrieval-feedback ledger
3. 삭제 대신 `deprecated/superseded/invalidated/archived`를 기록하는 lifecycle transition
4. `wiki-first/fresh-check/strict-evidence` 사용자 모드
5. failure reference, replay, 최소 change layer를 요구하는 self-evolution 절차

# Citations

[1] [Demand-Driven Context video](../sources/src-f55fed177366.md)
[2] [Demand-Driven Context preprint](../sources/src-54d07435eb56.md)
[3] [Continual Learning for AI Agents](../sources/src-ad0b1d50c531.md)
[4] [How Lovable self-improves every hour](../sources/src-03641bcfc467.md)
[5] [How Memory Management Impacts LLM Agents](../sources/src-af06bcdc1ed2.md)
[6] [Controllable Memory Usage](../sources/src-f9ba839fa59d.md)
[7] [The Log Is The Agent](../sources/src-2e2ea9c214c1.md)
