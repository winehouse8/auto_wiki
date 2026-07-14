# Living Wiki 협업 실행 환경

`tools/runtime.py`는 RFC `RFC-69828EB38078`의 인간 협업과 bounded runtime을 구현하는 Python 표준 라이브러리 전용 control plane이다. 이 모듈의 경계는 의도적으로 좁다.

```text
동일 협업 봉투
  → 어휘 검색
  → 의존성·의미 영향 미리보기
  → 범위 제한 예약 계획
  → 권한 판정
  → 모의 실행·내부 처리기·외부 영수증
  → 해시 연결 실행 영수증
```

런타임 자체는 네트워크 검색, 셸 실행, canonical ledger 수정, 원문 삭제, 외부 공개를 수행하지 않는다. 특히 scheduler가 내놓는 연구 작업은 `external.research.plan`이며 `execution=planned_only`다. 실제 외부 조사 결과는 별도의 executor 또는 사람이 수행한 뒤 `make_external_work_receipt()`로 보고할 수 있지만, 이 receipt도 결과의 사실성을 자동 보증하지 않는다.

## 1. 인간과 Agent의 동일 협업 객체

`human:*`와 `agent:*`는 모두 아래의 동일한 envelope를 사용한다. actor prefix는 provenance를 나타낼 뿐 schema, 사실성, permission 결정을 바꾸지 않는다.

```json
{
  "schema_version": 1,
  "id": "COL-...",
  "record_kind": "commitment | contribution | review",
  "intent": "direction | correction | lead | objection",
  "actor_id": "human:owner",
  "content": "반증 검색을 우선한다.",
  "targets": ["CMP-...", "CLM-..."],
  "stance": "request",
  "status": "proposed",
  "created_at": "...",
  "updated_at": "...",
  "supersedes": [],
  "metadata": {}
}
```

알 수 없는 top-level 필드는 거절한다. producer 확장은 `metadata`에 넣어 envelope의 동형성을 보존한다. 최소 lifecycle은 다음과 같다.

```text
draft(초안) → proposed(제안됨) → acknowledged(확인됨) → active(활성) → resolved(해결됨)
                                        ↘ rejected(거절됨) / withdrawn(철회됨) / superseded(대체됨)
```

terminal 상태는 다시 열지 않는다. 기존 객체를 수정해 되살리는 대신 새 객체가 이전 ID를 `supersedes`하도록 만든다. 모든 transition은 `metadata.transitions`에 수행 actor, 이유, 시각을 남긴다.

공개 API:

```python
make_collaboration_record(...)
validate_collaboration_record(record)
transition_collaboration_record(record, new_status, actor_id=..., reason=..., at=...)
```

canonical 저장은 이 모듈이 하지 않는다. 통합자는 검증이 끝난 record를 append-only 협업 원장에 기록하고 기존 Wiki event-chain에도 별도 event를 남겨야 한다.

## 2. 검색과 영향 미리보기

`build_search_documents()`는 다음 read-only corpus를 만든다.

- `state/claims.json`: `statement`, `scope`, `kind`, `tags`, `notes`, `confidence` 주장 필드
- `state/sources.json`: `title`, `authors`, `publisher`, `type`, `status`, `assessment` 출처 필드
- `state/campaigns.json`: `question`, `why-now`, `stop condition`, `claim/source membership` 캠페인 필드
- `wiki/**/*.md`: 최대 256 KB인 Markdown

`raw/`는 검색 corpus에서 제외한다. Wiki 문서 내용은 근거 데이터이지 지시가 아니며, 검색 결과도 최대 280자의 snippet만 돌려준다.

`BM25Index`는 고정 `k1=1.2`, `b=0.75`인 간단한 Okapi BM25 계열 구현이다. Unicode 영문·숫자·한글 어휘를 lowercase token으로 나누고, 동일 점수는 `doc_id` 오름차순으로 정렬한다. 임베딩이나 모델 호출이 없어 동일 corpus/query에서 결정론적이다.

```python
documents = build_search_documents(root)
results = lexical_search("반증 검색 독립 검토", documents=documents, limit=10)

preview = impact_preview(
    ["SRC-...", "CLM-...", "CMP-..."],
    "이 주장은 자동 승격을 허용하지 않는다",
    root=root,
)
```

`impact_preview()`는 canonical ID 관계를 따라 다음을 보여준다.

- source → evidence를 사용하는 claim → 해당 campaign
- claim → evidence source와 supersedes 관계 → 해당 campaign
- campaign → `claim_ids` / `source_ids`와 claim evidence source
- 알 수 없는 target ID
- 제안문과 가까운 lexical result
- negation, 명시적 correction/objection cue, 작은 antonym 목록에 걸린 semantic conflict **후보**

semantic 결과는 판정이 아니라 triage 후보다. `polarity_mismatch`는 특히 오탐이 많으므로 사람이 원문과 claim scope를 검토해야 한다. 이 구현은 embedding, 자연어 함의, 시간·관할·수치 조건의 의미를 이해하지 않는다.

## 3. 범위 제한 스케줄러

```python
plan = build_bounded_schedule(
    root=root,
    receipts=previous_receipts,
    now="2026-07-12T00:00:00+00:00",
    limits={
        "max_campaigns": 3,
        "max_actions": 3,
        "max_minutes": 45,
        "max_sources": 3,
        "action_minutes": 15,
        "sources_per_action": 1,
    },
)
```

선택 규칙은 다음 순서로 고정된다.

1. `queued` 또는 `active`가 아닌 campaign을 제외한다.
2. `runtime.stopped`, 소진된 `max_minutes`/`max_sources`, 충족된 stop condition을 제외한다.
3. interest 또는 campaign의 `cadence_days`와 마지막 **completed** action/external receipt 또는 `runtime.last_run_at`을 확인한다. `planned`, `dry_run`, `review_required`, `failed` receipt는 cadence를 소비하지 않는다. 한 번도 실행되지 않은 queued campaign은 즉시 due다.
4. `priority` 내림차순, 같은 priority는 campaign ID 오름차순으로 정렬한다.
5. 전역 limit와 campaign 잔여 budget의 작은 값만 할당한다.
6. 외부 실행 대신 `external.research.plan`만 생성한다.

문자열 stop condition은 자연어를 자의적으로 판정하지 않는다. 정확한 문자열이 `campaign.runtime.met_stop_conditions`에 들어왔을 때만 충족된 것으로 본다. 기계 판정이 필요하면 다음 구조형 조건을 사용할 수 있다.

```json
{"type": "deadline", "at": "2026-08-01T00:00:00+00:00"}
{"type": "sources_gte", "value": 10}
{"type": "minutes_gte", "value": 60}
{"type": "flag", "name": "counter-search-complete"}
```

schedule output에는 `allocated`, 선택된 `actions`, 제외된 campaign과 `reason`, `side_effects_executed=false`가 포함된다. plan은 현재 state를 갱신하지 않으므로, 실제 완료 receipt가 admission gate를 통과한 뒤에만 통합자가 campaign 사용량과 마지막 실행 시각을 원자적으로 갱신해야 한다.

## 4. 권한 경계

`decide_permission(action, actor=..., policy=...)`는 세 결과만 반환한다.

| 결과 | 의미 |
|---|---|
| `auto` | allowlist의 낮은 위험·가역적 control-plane action |
| `review` | 사람/정책 gate 뒤에서 별도 executor가 판단할 action |
| `deny` | append-only·원문 불변성·비밀·감사 경계를 침해하는 action |

대표 분류:

- 자동 허용(`auto`): `content.draft`, `evaluation.run`, `validation.run`, `render.preview`, `retrieval.search`, `impact.preview`, `external.research.plan`
- 검토(`review`): `raw.delete`, `governance.modify`, `trust-policy.modify`, `external.publish`, `credential.use`, `paid.operation`, `files.move.bulk`, `harness.self_modify`
- 거부(`deny`): `raw.overwrite`, `event.rewrite`, `credential.exfiltrate`, `execute.untrusted`, `gate.bypass`, `audit.delete`

`risk=high` 또는 `irreversible=true`는 custom policy가 allowlist에 추가해도 절대로 auto가 되지 않는다. actor가 human이라는 이유로 high-risk가 자동 허용되지 않는다. 실제 승인 token, 역할 capability, 만료, 2인 승인 정책은 상위 orchestrator가 확인해야 한다.

## 5. 영수증, 멱등성, 모의 실행, 복구

```python
store = ReceiptStore(root / "evaluations" / "receipts")

receipt = run_plan(
    plan,
    dry_run=True,
    store=store,
    idempotency_key="caller-request-123",
)

errors = store.verify()
```

`ReceiptStore`는 `receipts.jsonl`에 canonical JSON을 append하고 `prev_receipt_hash`/`receipt_hash`로 연결한다. idempotency key는 호출자 key, plan hash, `dry|live` mode에서 파생되므로 dry-run은 같은 key의 live 실행을 가로막지 않는다. terminal receipt가 있으면 새 handler를 호출하지 않고 기존 receipt의 사본에 `replayed=true`를 붙여 반환한다.

`run_plan()`의 방어선:

- 저장된 receipt chain에 기존 오류가 있으면 새 run을 시작하지 않음
- 실행 전 action/minute/source limit 재검사
- `deny`와 `review` action은 handler 미호출
- `external_work` 또는 `planned_only` action은 live mode에서도 handler 미호출
- dry-run은 모든 내부 handler 미호출
- 등록되지 않은 handler는 `review_required`
- handler 예외를 `failed` receipt로 기록하고 뒤 action은 `not_started`

failed live run만 `recover_run()`으로 재개할 수 있다. 이전 receipt에서 `completed`인 action ID는 재실행하지 않고 `recovered=true`로 남긴다. 동일 plan의 terminal 성공을 recovery하려 하면 거절한다.

이 hash chain은 우발적 변조 탐지용이지 서명이나 동시성 제어가 아니다. 현재 store는 **single writer** 계약이다. 여러 process가 쓴다면 상위에서 파일 lock/transactional DB가 필요하다. canonical event chain과 runtime receipt chain 사이의 anchoring도 통합자의 책임이다.

## 6. CLI 사용법

CLI는 검색·preview·plan·검증만 제공하며 외부 작업 실행 command가 없다.

```bash
python3 tools/runtime.py search "반증 검색" --limit 5
python3 tools/runtime.py impact CLM-... SRC-... --text "새 correction 내용"
python3 tools/runtime.py schedule --now 2026-07-12T00:00:00+00:00 \
  --max-campaigns 3 --max-actions 3 --max-minutes 45 --max-sources 3
python3 tools/runtime.py permission governance.modify
python3 tools/runtime.py validate-record path/to/record.json
python3 tools/runtime.py verify-receipts evaluations/receipts
```

통합 CLI는 canonical state/event 연결까지 담당한다.

```bash
python3 tools/wiki.py collaboration-add --help
python3 tools/wiki.py interest-seed
python3 tools/wiki.py search '반증 검색'
python3 tools/wiki.py impact --targets CLM-... --text '새 correction'
python3 tools/wiki.py run-plan --max-campaigns 1 --max-actions 1
python3 tools/wiki.py run-action-report --help
```

통합 receipt chain의 실제 경로는 `evaluations/receipts/receipts.jsonl`이다. 외부 completed report만 campaign cadence와 사용량을 소비한다. report는 digest가 event chain에 anchor되지만 `verification_status=unverified_report`를 유지하며, run lifecycle의 `reported-complete`는 사실 검증 완료를 뜻하지 않는다.

`--root`는 subcommand 앞에 둔다.

```bash
python3 tools/runtime.py --root /path/to/wiki search "claim trust"
```

## 7. `tools/wiki.py` 통합 계약

기존 control plane과 연결할 때 다음 순서를 유지한다.

1. collaboration 입력을 `make_*`/`validate_*`로 검증한다.
2. `impact_preview()`를 사용자에게 보여주고 semantic candidate를 사람이 판정한다.
3. canonical collaboration/event 원장에 append한다. runtime이 직접 `state/*.json`을 덮어쓰게 하지 않는다.
4. `build_bounded_schedule()`로 계획을 만들고 `run_plan(dry_run=True)` receipt를 먼저 남긴다.
5. 승인된 낮은 위험 내부 action만 명시적으로 등록된 handler에 연결한다.
6. 외부 연구는 별도 격리 executor가 수행하고 `make_external_work_receipt()`로 반환한다.
7. source admission, claim/evidence 연결, evaluation gate를 통과한 결과만 기존 `tools/wiki.py` 명령으로 승격한다.
8. runtime receipt hash를 Wiki event detail에 anchor하고 `validate`, `okf-validate`, 전체 test를 실행한다.

통합 시 import할 핵심 symbol은 다음과 같다.

```python
from runtime import (
    BM25Index,
    ReceiptStore,
    SearchDocument,
    build_bounded_schedule,
    build_search_documents,
    decide_permission,
    impact_preview,
    lexical_search,
    make_collaboration_record,
    make_external_work_receipt,
    recover_run,
    run_plan,
    transition_collaboration_record,
    validate_collaboration_record,
)
```

## 8. 명시적 한계

- BM25-like retrieval은 의미 검색이 아니며 한국어 형태소 분석을 하지 않는다.
- semantic conflict는 후보 생성기일 뿐 entailment/contradiction 판정기가 아니다.
- scheduler는 자연어 stop condition의 달성을 추측하지 않는다.
- receipt는 외부 executor가 정직하다는 증명이 아니며 결과 evidence를 별도 검증해야 한다.
- permission 결과는 승인 UI, credential broker, sandbox 자체를 구현하지 않는다.
- process 간 동시 write lock, 서명, remote attestation, secret management는 범위 밖이다.
- 이 모듈은 canonical Wiki state나 OKF projection을 직접 변경하지 않는다.
- 장기 calibration, 사용자별 권한 정책, semantic model의 품질 평가는 별도 release gate가 필요하다.

회귀 fixture는 `evaluations/fixtures/runtime-scenarios.json`, 테스트는 `tests/test_runtime.py`에 있다. 테스트는 인간/Agent schema parity, lifecycle, retrieval 결정성, dependency propagation, conflict candidate, permission, cadence/budget/stop condition, external non-execution, idempotency, receipt 변조, 실패 복구를 고정한다.
