# Governance

* [Living Wiki constitution](constitution.md) - Actor parity, epistemic rules, authority boundaries, and self-evolution policy.
* [Living Wiki decision log](decision-log.md) - Architectural decisions and their explicit rationale.
* [RFC-5D91E03B5BC5: Living Wiki v4.1 memory hygiene and controlled learning](rfc-5d91e03b5bc5.md) - v4는 provenance와 release gate를 갖췄지만 configured staleness를 실제로 검사하지 않고, retrieval이 도움이 됐는지 안전하게 기록할 ledger와 obsolete 지식을 비파괴적으로 비활성화하는 lifecycle 명령이 없으며, 사용자가 Wiki 의존도를 fresh-check 방식으로 낮출 명시적 UX도 없다.
* [RFC-69828EB38078: Living Wiki v4 closed-loop harness](rfc-69828eb38078.md) - v3.1은 근거 원장과 OKF projection은 갖췄지만 calibration, source admission 자동 평가, poisoning 회귀검사, 인간 commitment/review queue, bounded runner와 release orchestration이 연결되지 않아 자가진화 루프가 실제로 닫히지 않는다.
