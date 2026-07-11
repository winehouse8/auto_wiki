# v2 — Epistemic ledger

## 추가한 구조

```text
Actor → Contribution/Event
Source(snapshot, assessment, independence group)
Claim(kind, scope, time)
Claim ↔ Evidence span (support/contradict/context)
Review(independent/adversarial)
Derived Wiki
```

## 핵심 변경

- 신뢰 최소 단위를 page에서 claim으로 이동
- source S0–S4와 claim C0–C4 분리
- 사람/Agent를 같은 actor schema에 등록
- hash로 raw 변경 탐지, hash-chain event log로 감사 단서 제공
- self-generated synthesis가 corroboration으로 재순환하지 못하도록 규정

## 자체 연구와 평가에서 발견한 한계

1. 신뢰도 schema가 있어도 좋은 자료를 지속적으로 찾아오지 못하면 쓰레기를 정교하게 정리할 뿐이다.
2. deep-research agent는 반복 수정에서 기존 내용·인용을 훼손할 수 있다.
3. 같은 모델이 writer와 reviewer를 맡으면 correlated error가 독립 검토처럼 보인다.
4. persistent memory는 prompt injection보다 오래가는 poisoning 표면이 된다.
5. source level을 수동 설정하면 calibration이 검증되지 않는다.
6. 하네스가 자기 benchmark를 바꾸며 “개선”을 선언할 수 있다.

## v3로 넘긴 요구사항

- 관심 분야별 bounded research campaign과 stop condition
- counter-search, retraction/status 확인, source diversity
- dependency-aware scoped patch와 회귀평가
- admission quarantine, 원문/명령 분리, 최소 권한
- harness RFC, fixed benchmark, rollback, 승인 gate

