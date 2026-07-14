---
type: Knowledge Overview
title: Living Wiki 연구 개요
description: 자가진화 인간-Agent 협력 Wiki의 현재 범위, 규모, 탐색 경로.
tags: [living-wiki, overview, human-agent]
timestamp: '2026-07-12T18:30:00+09:00'
---

# Living Wiki 연구 개요

## 연구 질문

사람과 Agent가 같은 기여 프로토콜을 사용하면서, Agent가 관심 분야를 지속적으로 연구·관리하고, 출처와 주장 신뢰도를 투명하게 레벨링하며, Wiki와 하네스 자체가 안전하게 진화하려면 무엇이 필요한가?

## 현재 답

Karpathy의 LLM Wiki와 AI Research OS가 제시한 `불변 raw → index → 가변 wiki`를 출발점으로 삼되, 그 사이에 **atomic claim ↔ exact evidence** 원장을 넣고 바깥에 **actor/governance/evaluation** control plane을 둔다.

```text
신뢰되지 않은 출처 받은 편지함
        ↓
콘텐츠 주소 기반 격리 + 쓰기·검색·활성화 게이트
        ↓
신원·출처 이력·상태·반증 검색 입수
        ↓
원자적 주장 ↔ 정확한 지지·반박 증거
        ↓
개념 / 비교 / 관점 / 현재 종합
        ↑
행위자 중립 협업 + 실행 주기 캠페인 + 범위 제한 실행 + 검토 + 릴리스 RFC
        ↕
감사 전용 피드백 + 노후화 보고서 + 비파괴 수명주기
```

## 현재 규모

- 47개 선별 출처: 2026 동료심사 논문, 표준, preprint, 지정 Gist·영상·공개 코드, content-addressed 채널 감사 bundle
- 증거가 연결된 핵심 주장 34개: C1 4개, C2 30개. 독립 검토자가 없으므로 C3/C4는 없음
- AI Engineer memory/Wiki 연구와 coverage 재감사를 포함한 캠페인 7개와 cadence 기반 다음 campaign seeding 경로
- 같은 스키마를 쓰는 협업 기록 7개, 출처·보안 입수 판정 67개, 범위 제한 실행 1개, 감사 전용 메모리 피드백 1개
- 15건 calibration pilot과 31건 lexical security fixture; 둘 다 production 인증 아님

## 탐색 순서

1. [색인](index.md)
2. [종합](synthesis.md)
3. [인식론적 대시보드](epistemic-dashboard.md)
4. 관련 `concepts/`와 `sources/`
5. `state/claims.json`의 exact locator
6. 외부 원문 또는 `raw/` snapshot

## 핵심 페이지

- [지속 합성](concepts/persistent-synthesis.md)
- [주장 단위 신뢰](concepts/claim-level-trust.md)
- [인간과 Agent의 동등성](concepts/human-agent-parity.md)
- [출처 발견과 입수 심사](concepts/source-discovery-and-admission.md)
- [통제된 자기진화](concepts/governed-self-evolution.md)
- [메모리 위생과 통제된 학습](concepts/memory-hygiene-and-controlled-learning.md)
- [하네스 사용자 경험과 전달 계약](specs/harness-ux.md)
- [Living Wiki 관리인 Skill 제품 요구사항](specs/living-wiki-steward-skill.md)
- [현재 관점](perspectives/self-evolving-wiki-position.md)
- [열린 질문](open-questions.md)
- [모순](contradictions.md)
