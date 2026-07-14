# 결정 기록

## [2026-07-11] ADR-001 | 그래프 데이터베이스보다 주장 원장을 먼저 구축

- 결정: Markdown/JSON/Git 기반으로 시작하고, claim/evidence/actor 구조를 먼저 안정화한다.
- 이유: 2026년 GraphRAG 연구는 triple extraction과 community granularity 오류가 전체 추론으로 전파될 수 있음을 보여준다. 구조가 작을 때는 결정론적 파일과 검증기가 더 감사하기 쉽다.
- 재검토 조건: claim 10,000개 또는 현재 CLI 검색의 p95가 1초를 넘고, 실제 query benchmark에서 hybrid retrieval이 유의미하게 우수할 때.

## [2026-07-11] ADR-002 | 역할별 권한을 적용한 행위자 동등성

- 결정: 사람과 Agent는 동일 actor/contribution schema를 사용한다. 고위험 권한은 actor kind가 아니라 책임·위험 역할로 제한한다.
- 이유: 철학적 동등성과 운영 안전을 동시에 보존한다.
- 반례/위험: 인간 소유자의 최종 승인권이 사실상 계층으로 굳을 수 있다. 승인 사유와 거부 이력을 공개해 견제한다.

## [2026-07-11] ADR-003 | 신뢰 벡터를 우선하고 표시 레벨은 그다음으로 적용

- 결정: source level, independence, evidence relation, review, contradiction을 보존하고 C0–C4는 파생 표시로만 쓴다.
- 이유: 단일 숫자는 사실성·충실성·권위·최신성을 섞어 오판을 만든다.

## [2026-07-11] ADR-004 | 자기 수정은 RFC로만 수행

- 결정: 콘텐츠 자동 편집과 하네스 자기수정을 분리한다. 하네스 변경은 benchmark·rollback이 있는 RFC로만 제안한다.
- 이유: evaluator까지 자기 편의적으로 바꾸는 Goodhart loop와 안전 회귀를 막는다.

## [2026-07-11] ADR-005 | `wiki/`는 OKF v0.1 번들

- 결정: `wiki/`를 portable Open Knowledge Format bundle로 정의하고 JSON 원장·raw·도구·평가는 바깥 control plane에 둔다.
- 이유: Markdown/Git/agent-first 철학을 유지하면서 다른 OKF consumer가 별도 adapter 없이 지식층을 읽게 한다.
- 중요한 경계: OKF v0.1은 `type`, reserved index/log, Markdown link 같은 최소 상호운용 형식이지 신뢰·provenance·governance 규격이 아니다.
- 버전: 공식 spec이 Draft이므로 0.1을 pin하고 silent migration을 금지한다.

## [2026-07-12] ADR-006 | 외부 실행기 권한 없이 순환을 닫기

- 결정: 관심사 주기 → 범위 제한 캠페인 → 계획 전용 실행환경 → 격리·입수 판정 → 출처 추적 원장 → 통합 릴리스 게이트를 연결한다.
- 경계: runtime은 네트워크 조사나 shell-configured Agent를 실행하지 않는다. 외부 작업은 별도 actor의 `unverified_report`로 귀속하고 source/evidence gate를 다시 거친다.
- 이유: 지속 연구와 과도한 agency를 분리하고, 계획·예산·권한·결과 attribution을 감사 가능하게 만들기 위해서다.

## [2026-07-12] ADR-007 | 마이그레이션 예외와 평가 fixture 고정

- 결정: admission이 없던 v3.1 source는 정확한 35개 ID manifest로만 grandfather하고, calibration/security/runtime fixture의 canonical SHA-256을 release gate에 pin한다.
- 이유: 새 source를 legacy로 가장하거나 평가 실패를 fixture 삭제로 숨기는 우회를 막는다.
- 변경 조건: manifest나 fixture hash 변경은 benchmark 차이, 위험, rollback이 있는 새 RFC를 요구한다.

## [2026-07-12] ADR-008 | v4 통과는 운영 환경 인증이 아님

- 결정: 모든 fixed gate가 통과해도 release report는 `production_certified=false`를 유지한다.
- 이유: 15건 calibration pilot, lexical security corpus, unsigned single-writer receipt는 장기 정확도·unseen attack·actor identity를 입증하지 않는다.
- 승격 조건: 독립 adjudication, 시간 분할 holdout, live adapter 장애 시험, semantic/multimodal red team, executor/sandbox/credential 경계, multi-writer locking/signature가 별도 근거를 갖춰야 한다.
