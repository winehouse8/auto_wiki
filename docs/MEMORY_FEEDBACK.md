# 메모리 피드백과 비파괴 수명주기

`tools/memory_feedback.py`는 RFC `RFC-5D91E03B5BC5`의 retrieval feedback과 lifecycle 불변조건을 구현하는 Python 3.10+ 표준 라이브러리 모듈이다. 모든 함수는 pure/deterministic하며 파일, 원장, network, clock을 직접 읽거나 쓰지 않는다.

핵심 경계는 다음과 같다.

> Retrieval feedback은 검색 품질에 대한 귀속된 진단 관측치다. Claim/source trust, C-level/S-level, 검색 ranking, 삭제 또는 실행 가능한 action이 아니다.

## 정식 원장

Canonical 경로의 계약은 `state/memory_feedback.json`이다. 파일 부재는 통합자가 다음 빈 상태로 해석한다.

```json
{
  "version": 1,
  "feedback": []
}
```

모듈은 I/O를 하지 않는다. `make_feedback_collection()`과 `validate_feedback_collection()`이 payload만 만들고 검사하며, append/event 기록은 `tools/wiki.py` 같은 governed writer가 담당한다.

Feedback record의 exact schema:

```json
{
  "id": "MFB-...",
  "actor_id": "human:owner",
  "created_at": "2026-07-12T01:00:00+00:00",
  "task_ref": "task:opaque-9f7c",
  "targets": ["CLM-...", "SRC-..."],
  "outcome": "helpful",
  "rationale": "The retrieved source directly supported the bounded task.",
  "evidence_refs": ["RUN-..."],
  "trust_effect": "none",
  "automatic_action": false,
  "status": "open"
}
```

해결된 diagnostic item만 다음 필드를 추가한다.

```json
{
  "status": "resolved",
  "resolution": {
    "actor_id": "human:reviewer",
    "at": "2026-07-12T02:00:00+00:00",
    "rationale": "Reviewed against the task receipt."
  }
}
```

`status != resolved`는 unresolved다. `open` record에 resolution을 넣거나 `resolved` record에서 resolution을 생략하면 validation이 실패한다. Resolution은 원래 outcome, actor, target, rationale를 수정하지 않고 별도의 attribution만 추가한다.

## 개인정보 보호와 무결성

`task_ref`는 raw query가 아닌 opaque token이다. 공백, `?`, control character를 허용하지 않는다. Schema에는 `query`, `raw_query`, `content` 필드가 없으며 unknown top-level 또는 resolution field는 모두 거절된다.

```python
record = make_retrieval_feedback(
    actor_id="agent:researcher",
    targets=["CLM-A", "SRC-B"],
    outcome="helpful",
    task_ref="task:run-17",
    rationale="The retrieved evidence answered the scoped task.",
    evidence_refs=["RUN-17"],
    created_at="2026-07-12T01:00:00+00:00",
)
```

Rationale에는 유용성 판정 이유만 적고 사용자 원문 query, 비밀, 개인정보를 복사하지 않는다. 자유문 안에 raw query가 들어갔는지를 결정론적 validator가 완전하게 판별할 수는 없으므로 caller/UI에서 별도 redaction gate가 필요하다.

Timestamp는 caller가 명시해야 하며 UTC seconds로 정규화된다. Clock default가 없으므로 같은 의미의 입력은 byte-identical record를 만든다. Targets와 evidence refs는 검증 후 정렬·중복 제거된다.

ID는 immutable creation payload의 SHA-256 앞 12자리로 만든다. Resolution은 같은 관측의 lifecycle이므로 ID를 바꾸지 않는다.

```python
feedback_digest(record)       # immutable creation identity digest
feedback_state_digest(record) # resolution을 포함한 current-state digest
```

ID 또는 immutable creation field 변조는 validation에서 탐지된다.

## 결과 의미 체계

| 결과 | 의미 |
|---|---|
| `helpful` | 해당 retrieval이 bounded task 수행에 도움 됨 |
| `harmful` | stale, misleading, scope mismatch 등으로 작업을 해침 |
| `irrelevant` | 자료 자체의 진실성과 별개로 현재 task와 무관함 |
| `unknown` | 도움 여부를 판단할 관찰이 부족함 |

어떤 outcome도 epistemic truth label이 아니다. 특히 `helpful`은 C-level/S-level 승격 근거가 아니고 `harmful`은 삭제나 trust 하락 권한이 아니다. `trust_effect="none"`, `automatic_action=false` 외의 값은 schema 위반이다. `rank_delta`, `promotion`, `delete`, `claim_level`, `source_level` 같은 확장 필드도 거절한다.

## 해결과 중복 제거

```python
resolved = resolve_retrieval_feedback(
    record,
    actor_id="human:reviewer",
    rationale="Task receipt inspected.",
    at="2026-07-12T02:00:00+00:00",
)
```

함수는 원본을 수정하지 않고 copy를 반환한다. 같은 resolution의 재적용은 idempotent하며, 이미 resolved인 record를 다른 attribution/rationale로 덮어쓰려 하면 실패한다.

`deduplicate_feedback()`은 stable creation digest로 중복을 제거한다.

- exact duplicate는 하나로 합친다.
- 같은 관측의 open/resolved 사본은 monotonic하게 resolved를 보존한다.
- 서로 다른 resolution 두 개가 같은 ID를 주장하면 자동 선택하지 않고 실패한다.
- 다른 created_at의 반복 feedback은 서로 다른 관측으로 유지한다.

## 집계 보고서

```python
report = aggregate_feedback_report(
    records,
    generated_at="2026-07-12T03:00:00+00:00",
)
report_bytes = render_feedback_report(report)
```

Report는 다음 diagnostic count만 제공한다.

- input/unique/duplicate record 수
- outcome 및 open/resolved 수
- evidence attached/missing 수
- actor별 attribution count
- target별 outcome/unresolved count
- 안정적인 보고서 ID와 전체 SHA-256

정렬 순서와 생성 시각이 고정되면 입력 순서와 관계없이 byte-identical하다. Report에도 `trust_effect="none"`, `automatic_action=false`가 있으며 selection bias 경고가 포함된다. Count는 조사 우선순위를 사람이 판단하는 단서일 뿐 자동 ranking이나 lifecycle transition 입력이 아니다.

## 비파괴 수명주기

Lifecycle 대상은 claim/source 등 `id`가 있는 canonical subject다. 기존 subject에 `lifecycle_status`가 없으면 `active`로 해석한다.

지원 상태:

- `active`
- `deprecated`
- `superseded`
- `invalidated`
- `archived`

의도적인 transition matrix:

```text
active(활성)      → deprecated(사용 중단) | superseded(대체됨) | invalidated(무효화됨) | archived(보관됨)
deprecated(사용 중단)  → active(활성) | superseded(대체됨) | invalidated(무효화됨) | archived(보관됨)
invalidated(무효화됨) → active(활성) | superseded(대체됨) | archived(보관됨)
superseded(대체됨)  → archived(보관됨)
archived(보관됨)    → terminal(종료)
```

Archived identity를 되살리는 대신 새 record와 명시적 관계를 만든다. Superseded transition은 자신과 다른 `replacement_ref`가 필수이며 다른 status에는 replacement를 허용하지 않는다.

전이 봉투 구조:

```json
{
  "id": "LCT-...",
  "target_ref": "CLM-OLD",
  "from_status": "active",
  "to_status": "superseded",
  "actor_id": "human:owner",
  "reason": "A newer claim narrows the validity period.",
  "replacement_ref": "CLM-NEW",
  "created_at": "2026-07-12T02:00:00+00:00",
  "automatic_action": false,
  "destructive_action": false
}
```

모든 transition은 reason, actor, created_at, prior state가 필수다. `deleted` status, 자동 transition, destructive action, unknown field는 실패한다.

```python
updated, transition = transition_lifecycle(
    subject,
    to_status="superseded",
    actor_id="human:owner",
    reason="Replaced by a current scoped claim.",
    replacement_ref="CLM-NEW",
    created_at="2026-07-12T02:00:00+00:00",
)
```

반환된 subject copy에는 canonical top-level projection을 추가한다.

```text
lifecycle_status        # 생명주기 상태
lifecycle_reason        # 생명주기 변경 이유
lifecycle_updated_at    # 생명주기 갱신 시각
lifecycle_updated_by    # 생명주기 갱신 행위자
replaced_by             # superseded에서만 새로 설정하는 대체 대상
lifecycle_history[]     # 전체 전이 봉투
```

`apply_lifecycle_transition()`은 다음을 보장한다.

- caller의 원본 object를 변경하지 않음
- 기존 key를 삭제하지 않음
- confidence, C-level, source level, evidence를 변경하지 않음
- target ID와 prior state가 정확히 일치해야 함
- transition history를 append함
- 같은 transition 재적용은 history를 중복하지 않음
- superseded subject를 archived로 바꿀 때 기존 `replaced_by`를 보존함

Lifecycle 자체는 truth 판정이나 S-level 변경이 아니다. 예를 들어 C3 claim도 validity period가 끝나 deprecated될 수 있고, C1 claim도 새 evidence 없이 active일 수 있다. 다만 source가 inactive가 된 뒤 사람이 명시적으로 `evaluate`를 실행하면 그 source를 active support로 세지 않으므로 의존 claim의 파생 C-level은 내려갈 수 있다. 이는 lifecycle transition이 trust를 직접 조작한 것이 아니라 현재 active evidence set을 다시 계산한 결과다.

## 통합 순서

권장 control-plane 순서:

1. actor와 target 존재 여부를 canonical registry에서 확인한다.
2. `make_retrieval_feedback()` 또는 `resolve_retrieval_feedback()`을 호출한다.
3. `validate_feedback_collection()`을 통과한 전체 payload를 atomic write한다.
4. append-only Wiki event에 actor, feedback ID, outcome/status만 남긴다. Raw query는 event에도 넣지 않는다.
5. Aggregate는 read-only evaluation artifact로 저장한다.
6. Harmful feedback을 조사할 때 원 evidence와 task receipt를 사람이 검토한다.
7. Lifecycle 변경이 필요하면 별도 승인 경계에서 `transition_lifecycle()`을 호출하고 transition envelope를 event에 기록한다.
8. Claim confidence와 source level 계산은 기존 evidence/review policy만 사용한다.

Missing `state/memory_feedback.json`은 빈 collection으로 처리해야 v4.0 reader와 호환된다. 모듈 제거 또는 ledger 제거가 기존 claim/source trust를 바꾸면 안 된다. 반면 inactive lifecycle record를 v3.1 reader로 되돌리면 active로 부활해 보일 수 있으므로 현재 release rehearsal은 그런 상태에서 fail-closed하고, 별도 migration 또는 v4.1-compatible rollback reader를 요구한다.

## 공개 API

```python
make_retrieval_feedback(...)
validate_retrieval_feedback(record)
resolve_retrieval_feedback(record, ...)
feedback_digest(record)
feedback_state_digest(record)
deduplicate_feedback(records)
make_feedback_collection(records)
validate_feedback_collection(payload)
aggregate_feedback_report(records, generated_at=...)
render_feedback_report(report)

make_lifecycle_transition(...)
validate_lifecycle_transition(transition)
lifecycle_transition_digest(transition)
apply_lifecycle_transition(subject, transition)
transition_lifecycle(subject, ...)
```

## 알려진 한계

- Feedback는 자발적으로 수집되므로 selection bias가 크다.
- Rationale의 개인정보·raw query 여부는 caller-side redaction이 필요하다.
- Opaque task ref가 실제로 어떤 task를 가리키는지는 이 모듈이 확인하지 않는다.
- Actor/target/evidence reference의 registry 존재성은 통합자가 확인한다.
- Aggregate count는 causal utility나 truth calibration을 제공하지 않는다.
- Lifecycle transition은 권한 승인 UI나 동시성 transaction을 구현하지 않는다.
- 모듈은 state/event/OKF 파일을 직접 쓰거나 render하지 않는다.

고정 fixture는 `evaluations/fixtures/memory-feedback-scenarios.json`, 불변조건 회귀검사는 `tests/test_memory_feedback.py`에 있다.
