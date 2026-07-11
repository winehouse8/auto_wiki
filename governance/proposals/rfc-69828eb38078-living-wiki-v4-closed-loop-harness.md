# RFC-69828EB38078: Living Wiki v4 closed-loop harness

Status: implemented
Proposed by: `agent:codex`
Created: 2026-07-11T15:41:50+00:00

## Problem

v3.1은 근거 원장과 OKF projection은 갖췄지만 calibration, source admission 자동 평가, poisoning 회귀검사, 인간 commitment/review queue, bounded runner와 release orchestration이 연결되지 않아 자가진화 루프가 실제로 닫히지 않는다.

## Proposed change

고정 calibration/security/admission fixture, 결정론적 평가기, 안전한 quarantine ingest, provenance-aware retrieval, commitment와 impact preview, run receipt를 갖는 bounded scheduler, 통합 gate와 migration을 추가한다. 외부 검색과 고위험 변경은 자동 실행하지 않고 계획·초안·제안까지만 허용한다.

## Evidence

- `CLM-1EB8BD726482`
- `CLM-61B3C391010C`
- `CLM-860EB3D6AAEB`
- `CLM-DA7C92E9A901`
- `CLM-F464CCF0AA1A`

## Benchmark and acceptance gate

기존 12개 테스트 유지, 새 calibration/admission/security/collaboration/runtime 테스트 전체 통과, deterministic fixture report, event chain과 OKF strict validation 통과, dry-run에서 권한 밖 action 0건, rollback rehearsal 문서화.

## Risks

- 규칙 복잡도 증가
- 기존 JSON schema 호환성
- 보안 scanner 오탐
- 자동화 권한 확대 오해
- 평가셋 과적합

## Rollback

v3.1 state는 append-only로 보존하고 새 v4 state 파일은 additive schema로 도입한다. 새 command와 runner를 비활성화하면 기존 tools/wiki.py와 OKF projection만으로 동작하며, release snapshot hash로 이전 파생 뷰를 재생성한다.

## Review decisions

- `2026-07-11T15:47:47+00:00` — **approve** by `human:owner`: 사용자가 2026-07-12 대화에서 해야 할 작업을 순서대로 수행해 프로젝트와 하네스를 완결성 있게 완수하라고 명시적으로 지시했다. 고위험 외부 공개·비밀·유료 작업은 승인 범위에 포함하지 않는다.

## Implementation evidence

- Release report: `evaluations/reports/v4-release-23fca36283d05651.json`
- Component fingerprint: `23fca36283d05651f124d9a893e6fd1b82b6cdeb62e111787e94c896deec4f00`
- Production certified: `False`
