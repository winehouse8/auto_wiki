---
type: Research Queue
title: Open questions
description: 정보 이득과 위험을 기준으로 정렬한 Living Wiki의 미해결 연구 질문.
tags: [research-queue, open-questions]
timestamp: '2026-07-11T23:40:00+09:00'
---

# Open questions

우선순위는 정보 이득, 사용자 관심도, 위험, 최신성, 비용으로 정한다.

## P0 — Confidence calibration

- C0–C4가 실제 claim 정확도와 얼마나 대응하는가?
- 과학 논문, 소프트웨어 버전, 법·정책, 실무자 경험에 같은 gate를 써도 되는가?
- empirical gold set을 누가 만들고 benchmark 자체의 오류를 어떻게 이의 제기하는가?

연결 캠페인: `CMP-76BD99582F70`

## P0 — Source admission quality

- Crossref, Retraction Watch, PubMed, 공식 changelog 같은 status registry를 어떻게 연결할 것인가?
- 동일 보도자료·논문을 재인용한 파생 출처를 어떻게 independence cluster로 자동 묶는가?
- 검색 시스템이 반대 증거와 소수 관점을 충분히 찾았는지 어떻게 측정하는가?

연결 캠페인: `CMP-7A543D820D83`

## P0 — Memory poisoning

- 악성 웹페이지·PDF·YouTube frame·GitHub README가 canonical memory에 지시를 심는 것을 어떻게 재현·차단하는가?
- write, retrieve, activate 단계별 방어 성능과 정상 자료 거부율을 어떻게 함께 측정하는가?

연결 캠페인: `CMP-088A51571084`

## P1 — Collaboration

- 사람이 연구 중간에 “그 방향이 아니다”라고 수정할 때 commitment와 영향받는 claim을 어떻게 갱신하는가?
- 사람과 Agent가 동시에 같은 synthesis를 수정할 때 textual merge가 아닌 semantic conflict를 어떻게 보여주는가?
- 인간의 correction도 틀릴 수 있는데 검토 비용과 자율성의 균형을 어떻게 잡는가?

## P1 — Scale and retrieval

- 어떤 규모와 query 패턴에서 JSON/Markdown index가 병목이 되는가?
- BM25, dense retrieval, citation graph, temporal graph를 어떤 router로 조합하는가?
- compiled Wiki가 raw retrieval보다 실제로 비용과 정확도에서 우수한 query 유형은 무엇인가?

## P1 — Perspective health

- Wiki가 독자적 관점을 가지면서도 echo chamber가 되지 않았음을 어떻게 측정하는가?
- 관점의 일관성과 새로운 증거에 대한 수정 가능성을 동시에 평가할 수 있는가?
