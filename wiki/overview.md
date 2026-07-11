---
type: Knowledge Overview
title: Living Wiki 연구 개요
description: 자가진화 인간-Agent 협력 Wiki의 현재 범위, 규모, 탐색 경로.
tags: [living-wiki, overview, human-agent]
timestamp: '2026-07-12T12:00:00+09:00'
---

# Living Wiki 연구 개요

## 연구 질문

사람과 Agent가 같은 기여 프로토콜을 사용하면서, Agent가 관심 분야를 지속적으로 연구·관리하고, 출처와 주장 신뢰도를 투명하게 레벨링하며, Wiki와 하네스 자체가 안전하게 진화하려면 무엇이 필요한가?

## 현재 답

Karpathy의 LLM Wiki와 AI Research OS가 제시한 `불변 raw → index → 가변 wiki`를 출발점으로 삼되, 그 사이에 **atomic claim ↔ exact evidence** 원장을 넣고 바깥에 **actor/governance/evaluation** control plane을 둔다.

```text
untrusted source inbox
        ↓
content-addressed quarantine + write/retrieve/activate gate
        ↓
identity/provenance/status/counter-search admission
        ↓
atomic claim ↔ exact supporting/contradicting evidence
        ↓
concept / comparison / perspective / current synthesis
        ↑
actor-neutral collaboration + cadence campaign + bounded run + review + release RFC
```

## 현재 규모

- 35개 선별 출처: 2026 동료심사 논문, 표준, preprint, 지정 Gist·영상·공개 코드
- 26개 evidence-linked 핵심 claim
- 모든 claim은 현재 C2. 독립 reviewer가 없으므로 C3/C4는 없음
- 완료된 캠페인 5개와 cadence 기반 다음 campaign seeding 경로
- 동일 schema의 collaboration 1개, source admission audit 1개, bounded run/외부 보고 1개
- 15건 calibration pilot과 31건 lexical security fixture; 둘 다 production 인증 아님

## 탐색 순서

1. [index](index.md)
2. [synthesis](synthesis.md)
3. [epistemic dashboard](epistemic-dashboard.md)
4. 관련 `concepts/`와 `sources/`
5. `state/claims.json`의 exact locator
6. 외부 원문 또는 `raw/` snapshot

## 핵심 페이지

- [Persistent synthesis](concepts/persistent-synthesis.md)
- [Claim-level trust](concepts/claim-level-trust.md)
- [Human-Agent parity](concepts/human-agent-parity.md)
- [Source discovery and admission](concepts/source-discovery-and-admission.md)
- [Governed self-evolution](concepts/governed-self-evolution.md)
- [Current position](perspectives/self-evolving-wiki-position.md)
- [Open questions](open-questions.md)
- [Contradictions](contradictions.md)
