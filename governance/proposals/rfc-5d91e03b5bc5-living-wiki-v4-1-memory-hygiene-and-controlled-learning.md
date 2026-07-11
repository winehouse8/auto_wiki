# RFC-5D91E03B5BC5: Living Wiki v4.1 memory hygiene and controlled learning

Status: implemented
Proposed by: `agent:codex`
Created: 2026-07-11T17:21:34+00:00

## Problem

v4는 provenance와 release gate를 갖췄지만 configured staleness를 실제로 검사하지 않고, retrieval이 도움이 됐는지 안전하게 기록할 ledger와 obsolete 지식을 비파괴적으로 비활성화하는 lifecycle 명령이 없으며, 사용자가 Wiki 의존도를 fresh-check 방식으로 낮출 명시적 UX도 없다.

## Proposed change

additive memory-feedback ledger와 결정론적 memory-hygiene report를 추가하고, claim/source에 active/deprecated/superseded/invalidated/archived lifecycle transition을 이유·replacement와 함께 기록한다. AGENTS/README에는 wiki-first, fresh-check, strict-evidence 모드를 정의한다. feedback은 raw query를 저장하지 않고 ranking, C-level, source level, 삭제를 자동 변경하지 않는다. harness proposal은 관찰된 failure/replay와 최소 change layer를 명시하도록 prompt와 문서를 강화한다.

## Evidence

- `CLM-207429D54323`
- `CLM-95A38CACF2CD`
- `CLM-D2A1B46809DA`
- `CLM-EC52C0576A28`
- `CLM-F464CCF0AA1A`
- `CLM-F79558D817DF`

## Benchmark and acceptance gate

기존 release gate와 전체 테스트가 유지되고, 새 모듈은 고정 시각에서 deterministic byte-identical report를 만든다. stale/active/inactive, feedback schema·attribution·privacy, lifecycle transition·replacement validation, no-auto-promotion/deletion을 테스트한다. validate와 OKF가 통과하고 rollback rehearsal에서 새 state와 optional fields를 제거해도 v4 reader가 동작해야 한다.

## Risks

- feedback selection bias
- staleness를 거짓으로 오해
- 사용자 모드가 bootstrap을 우회
- 새 state schema 호환성
- 자동 lifecycle 오용
- 평가 fixture 과적합

## Rollback

새 memory-feedback.json과 선택적 lifecycle fields는 additive다. 새 CLI/AGENTS mode 블록을 제거하고 v4.0 tools/wiki.py 및 config version으로 되돌리면 기존 source/claim/event 원장은 유지된다. feedback은 trust 계산 입력이 아니므로 제거해도 C-level이 변하지 않으며 lifecycle transition은 append-only event와 이전 status로 수동 복원한다.

## Review decisions

- `2026-07-11T17:21:41+00:00` — **approve** by `human:owner`: 사용자가 2026-07-12 현재 요청에서 신뢰 검증을 통과한 ai.engineer memory/wiki/second-brain 연구 결과를 Wiki와 하네스에 적용하라고 명시적으로 승인했다. 범위는 로컬 additive schema, 비파괴 lifecycle, audit-only feedback, read-only hygiene와 문서화된 memory mode이며 삭제·외부 공개·credential·자동 trust 승격은 제외한다.

## Implementation evidence

- Release report: `evaluations/reports/v4-release-ae0b13f351e1d4d7.json`
- Component fingerprint: `ae0b13f351e1d4d7b8c841d06faa8b7b05c9ae805170a8a41e2b3531d7967cf7`
- Production certified: `False`
