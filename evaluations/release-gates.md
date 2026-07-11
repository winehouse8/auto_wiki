# Harness release gates

하네스 버전은 아래 기준을 모두 측정한 뒤에만 승격한다. 아직 수치가 없는 지표는 `unknown`이지 `pass`가 아니다.

## Structural

- `validate` 오류 0
- raw artifact hash mismatch 0
- broken event-chain link 0
- claim evidence의 locator 누락 0
- dangling actor/source/claim reference 0

## Epistemic

- provenance closure: factual sentence가 claim→evidence→raw/URL로 닫히는 비율
- citation entailment와 citation completeness
- known contradiction recall
- source independence clustering precision
- retraction/stale detection latency
- confidence level별 empirical accuracy와 calibration
- 반대 증거 검색 포함률

## Collaboration

- 인간 방향 전환이 캠페인과 synthesis에 반영된 비율
- human correction rate와 correction survival
- unresolved commitment/질문의 평균 체류 시간
- 사람/Agent 기여의 attribution coverage

## Regression

- 수정 후 기존 valid claim 보존율
- 기존 citation 보존율
- fixed query set의 answer quality·latency·token cost
- rollback 성공 여부

## Security

- indirect prompt injection corpus
- memory poisoning write/retrieve/activate 단계별 성공률
- duplicate/syndicated source attack
- malicious PDF/YouTube frame/repository fixture
- secret exfiltration and excessive-agency test

## 현재 v4 fixed-fixture baseline (2026-07-12)

- 구조/event/admission/report-digest 검증: 오류 0, 공개된 경고 36
- OKF v0.1 core + Living Wiki profile: 92 concept documents, 오류/경고 0
- unit test: 162개, failure/error/skip 0; Python 3.9.6 호환 확인, 지원 범위 Python 3.10+, Python 3.13.12 release 실행
- calibration: 15건 중 resolved 14, scorable 13, observed `p_correct=0.769231`; pilot regression only
- security: 공격 18/정상 13, stage 전체 attack allow 0, benign reject 0, benign review 0.384615
- runtime: actor parity/permission/schedule/receipt fixture 통과, unauthorized side effect 0
- rollback: committed v3.1 `d18213a78376c0543a0aa590a3db7fcf7022c187`의 격리 render/validate/OKF 3개 command 통과, live workspace hash 불변
- source migration: admission 이전 35개 ID만 hash-pinned grandfather, 새 무-admission source는 hard error
- canonical independent claim review 0, C3/C4 0

기계 판정과 component fingerprint의 source of truth는 `evaluations/reports/v4-release-report.json`이다. 이 baseline은 고정 fixture의 regression pass이며 실제 장기 dataset, unseen semantic attack, live external executor를 인증하지 않는다. 결론은 항상 `production_certified=false`다.
