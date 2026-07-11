---
type: Research Queue
title: Open questions
description: 정보 이득과 위험을 기준으로 정렬한 Living Wiki의 미해결 연구 질문.
tags: [research-queue, open-questions]
timestamp: '2026-07-12T18:30:00+09:00'
---

# Open questions

우선순위는 정보 이득, 사용자 관심도, 위험, 최신성, 비용으로 정한다.

## P0 — Pilot calibration을 empirical calibration으로 확장

- 설계된 100개 층화 gold claim을 작성자와 독립된 reviewer group이 어떻게 blind adjudication할 것인가?
- 과학 논문, 소프트웨어 버전, 법·정책, 실무자 경험에 같은 gate를 써도 되는가?
- 시간 분할 holdout, benchmark 이의 제기, obsolete label migration을 어떻게 운영할 것인가?

pilot 결과: `CMP-76BD99582F70` 완료. 15건 smoke fixture는 production calibration이 아니다.

## P0 — Live source status와 dependency 품질

- offline contract를 live Crossref/Retraction Watch/PubMed/GitHub adapter로 옮길 때 outage·rate limit·stale cache를 어떻게 fail-closed 처리할 것인가?
- DOI가 없는 웹·영상·법령과 공유 dataset/model family의 independence를 어떻게 benchmark할 것인가?
- 검색 시스템이 반대 증거와 소수 관점을 충분히 찾았는지 어떻게 측정하는가?

baseline 결과: `CMP-7A543D820D83` 완료. 현재 adapter는 fixture/계약이고 live service가 아니다.

## P0 — Unseen·semantic·multimodal poisoning

- lexical rule을 피하는 다국어·동의어·분할·multi-turn·image/audio 공격을 holdout으로 어떻게 수집할 것인가?
- PDF/Office/archive parser sandbox와 retrieval label propagation을 어떻게 검증할 것인가?
- false-positive review 비용을 낮추면서 attack allow 0 기준을 어떻게 유지할 것인가?

baseline 결과: `CMP-088A51571084` 완료. fixed corpus 통과는 production security 인증이 아니다.

## P1 — Collaboration

- 사람이 연구 중간에 “그 방향이 아니다”라고 수정할 때 commitment와 영향받는 claim을 어떻게 갱신하는가?
- 사람과 Agent가 동시에 같은 synthesis를 수정할 때 textual merge가 아닌 semantic conflict를 어떻게 보여주는가?
- 인간의 correction도 틀릴 수 있는데 검토 비용과 자율성의 균형을 어떻게 잡는가?
- active commitment의 체류 시간과 correction survival을 실제 장기 운영에서 어떻게 측정하는가?

## P1 — Scale and retrieval

- 어떤 규모와 query 패턴에서 JSON/Markdown index가 병목이 되는가?
- BM25, dense retrieval, citation graph, temporal graph를 어떤 router로 조합하는가?
- compiled Wiki가 raw retrieval보다 실제로 비용과 정확도에서 우수한 query 유형은 무엇인가?

## P1 — Memory hygiene와 사용자 의존도

- `fast|normal|slow` review warning이 실제 outdated claim을 찾는 precision/recall은 얼마인가?
- helpful/harmful feedback의 selection bias와 credit assignment를 어떤 no-op control로 측정할 것인가?
- `wiki-first|fresh-check|strict-evidence`가 anchoring, 사실 오류, 시간, 비용에 미치는 영향을 어떻게 비교할 것인가?
- inactive lifecycle을 보존하면서 v3.1 rollback reader의 silent reactivation을 막는 migration은 무엇인가?

## P1 — Executor와 multi-writer 운영 경계

- 별도 외부 executor의 sandbox, credential broker, 승인 token, 만료와 결과 attestation을 어떻게 결합할 것인가?
- event/receipt chain에 actor signature와 process 간 locking을 추가하면서 local-first 복구성을 어떻게 유지할 것인가?

## P1 — Perspective health

- Wiki가 독자적 관점을 가지면서도 echo chamber가 되지 않았음을 어떻게 측정하는가?
- 관점의 일관성과 새로운 증거에 대한 수정 가능성을 동시에 평가할 수 있는가?
