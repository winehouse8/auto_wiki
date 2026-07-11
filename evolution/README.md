# Harness evolution

이 디렉터리는 버전 이름만 붙인 복사본이 아니라, 각 단계에서 실제로 발견한 실패와 다음 설계의 인과관계를 기록한다. 현재 실행 코드는 v4이며 과거 버전은 설계 snapshot으로 남긴다.

| Version | 중심 구조 | 자체 연구에서 발견한 한계 | 다음 변화 |
|---|---|---|---|
| v1 | raw → index → Markdown wiki | 관련도와 신뢰도 혼동, page-level citation, 수동 실행 | claim/evidence/actor 원장 |
| v2 | provenance·trust·review·contradiction | 자율 연구 부재, 수정 회귀, poisoning, 자기평가 편향 | bounded campaign, eval, security gate, RFC |
| v3 | 지속 연구·품질 게이트·안전한 자기진화 | 아직 실제 장기 운영/보정 데이터 부족 | 운영 로그로 v4 RFC를 만들되 자동 승격 금지 |
| v3.1 | OKF v0.1 portable knowledge bundle | OKF는 trust/governance schema가 아니며 아직 Draft | control plane은 유지하고 spec migration을 RFC로 관리 |
| v4 | admission·security·collaboration·bounded runtime·통합 release gate | pilot fixture, 외부 executor와 multi-writer 인증 부재 | 장기 운영 데이터와 독립 adjudication으로만 다음 RFC 제안 |

버전 간 schema와 migration 없이 단순 복사본을 늘리지 않는다. 실제 릴리스 snapshot은 `evaluations/snapshots/`의 content hash와 Git tag로 보존한다.
