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

## 현재 baseline (2026-07-11)

- 구조 검증과 unit test: 구현됨
- OKF v0.1 core + Living Wiki profile: 75 concepts, 0 warning/error
- Pure OKF projection idempotence: 86 Markdown files, byte-identical across two runs
- 위 지표의 실제 장기 dataset: 아직 없음
- 결론: v3.1은 연구 가능한 초기 하네스이지 production 신뢰 시스템으로 인증되지 않았다.
