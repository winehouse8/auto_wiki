# Decision log

## [2026-07-11] ADR-001 | Claim ledger before graph database

- 결정: Markdown/JSON/Git 기반으로 시작하고, claim/evidence/actor 구조를 먼저 안정화한다.
- 이유: 2026년 GraphRAG 연구는 triple extraction과 community granularity 오류가 전체 추론으로 전파될 수 있음을 보여준다. 구조가 작을 때는 결정론적 파일과 검증기가 더 감사하기 쉽다.
- 재검토 조건: claim 10,000개 또는 현재 CLI 검색의 p95가 1초를 넘고, 실제 query benchmark에서 hybrid retrieval이 유의미하게 우수할 때.

## [2026-07-11] ADR-002 | Actor parity with role-scoped authority

- 결정: 사람과 Agent는 동일 actor/contribution schema를 사용한다. 고위험 권한은 actor kind가 아니라 책임·위험 역할로 제한한다.
- 이유: 철학적 동등성과 운영 안전을 동시에 보존한다.
- 반례/위험: 인간 소유자의 최종 승인권이 사실상 계층으로 굳을 수 있다. 승인 사유와 거부 이력을 공개해 견제한다.

## [2026-07-11] ADR-003 | Confidence vector first, display level second

- 결정: source level, independence, evidence relation, review, contradiction을 보존하고 C0–C4는 파생 표시로만 쓴다.
- 이유: 단일 숫자는 사실성·충실성·권위·최신성을 섞어 오판을 만든다.

## [2026-07-11] ADR-004 | Self-modification through RFC only

- 결정: 콘텐츠 자동 편집과 하네스 자기수정을 분리한다. 하네스 변경은 benchmark·rollback이 있는 RFC로만 제안한다.
- 이유: evaluator까지 자기 편의적으로 바꾸는 Goodhart loop와 안전 회귀를 막는다.

## [2026-07-11] ADR-005 | `wiki/` is an OKF v0.1 bundle

- 결정: `wiki/`를 portable Open Knowledge Format bundle로 정의하고 JSON 원장·raw·도구·평가는 바깥 control plane에 둔다.
- 이유: Markdown/Git/agent-first 철학을 유지하면서 다른 OKF consumer가 별도 adapter 없이 지식층을 읽게 한다.
- 중요한 경계: OKF v0.1은 `type`, reserved index/log, Markdown link 같은 최소 상호운용 형식이지 신뢰·provenance·governance 규격이 아니다.
- 버전: 공식 spec이 Draft이므로 0.1을 pin하고 silent migration을 금지한다.
