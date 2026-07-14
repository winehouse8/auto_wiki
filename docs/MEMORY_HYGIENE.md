# Living Wiki 메모리 위생 보고서

`tools/memory_hygiene.py`는 `RFC-5D91E03B5BC5`의 **결정론적·읽기 전용 관찰기**다. 다음 네 입력을 읽어 검토 큐와 통계를 만들지만 canonical state, Wiki, trust level, lifecycle, 검색 순위 또는 파일을 변경하지 않는다.

- `config/wiki.json`
- `state/claims.json`
- `state/sources.json`
- `state/memory_feedback.json` — 선택 입력이며 없으면 빈 ledger로 평가

관련 기존 근거는 시간 범위와 계보가 필요하다는 `CLM-D2A1B46809DA`(C2), 지속 Wiki 수정은 scoped regression을 가져야 한다는 `CLM-1EB8BD726482`(C2), persistent memory의 write/retrieve gate가 필요하다는 `CLM-61B3C391010C`(C2)다. C2는 증거 성숙도이지 진실 확률이 아니다.

## v4.2 범위 제한 후보 계획

`memory-hygiene`는 claim/source 원장의 시간·생명주기 관찰기다. `hygiene-plan`은 그 결과와 전체 OKF 문서 그래프를 합쳐 관리인 Agent가 실제로 읽을 제한된 후보를 만든다.

```bash
python3 tools/wiki.py hygiene-plan \
  --now 2026-07-12T22:30:00+09:00
```

후보 계획은 다음 순서를 사용한다.

1. 정규 상태와 비예약 OKF 문서의 frontmatter·Markdown 링크·명시적 관계를 모델 호출 없이 전수 검사한다.
2. 구조 위험 전체, 최근 `timestamp` 문서 N개, 검토 기한이 지난 주장 N개와 의존성 지연을 중복 없이 시드로 만든다.
3. 문서 링크, `claim_ids`, evidence source, `supersedes`, 캠페인 소속만 최대 2-hop·전체 노드 상한으로 확장한다.
4. 같은 주제를 공유하면서 극성·수치·명시적 반박이 다른 쌍을 제한된 `검토 필요 후보`로 만든다.
5. 설정된 `semantic_review_limit`만 관리인 Agent가 claim→evidence→source locator 순서로 읽는다.

공유 태그는 약한 후보 단서일 뿐 자동 링크가 아니다. 모든 선택 항목에는 이유와 시작 시드까지의 경로가 있고, 동일 입력과 동일 시각의 JSON은 바이트가 같다. 후보 계획은 파일을 수정하거나 evidence, C/S-level, lifecycle, ranking을 변경하지 않는다.

기본 예산은 `config/wiki.json`의 `hygiene_selection`에 있다. 사용자는 이 내부 값을 외울 필요가 없고, 관리인 Skill이 실제 사용한 hop·노드·쌍·의미 검토 예산만 차이 보고에 표시한다.

## OKF 시간 필드

OKF `timestamp`는 마지막 의미 있는 내용 변경 시각이다. 생성 뷰를 다시 썼다는 이유만으로 바뀌지 않는다. Living Wiki는 알려진 경우 다음 생산자 확장을 함께 투영한다.

- `created_at`: 최초 생성 시각
- `last_verified_at`: 원근거와 적용 범위를 실제 재확인한 시각
- `freshness`: 검토 주기 분류
- `lifecycle_updated_at`: 내용 변경과 분리된 생명주기 전이 시각
- `retrieved_at`, `assessed_at`: 출처 검색·평가 시각

정규 레코드에 `content_updated_at`이 있으면 OKF `timestamp`의 권위 값으로 사용한다. 이전 레코드는 생성, evidence 추가, confidence 결과 변화, 생명주기 전이처럼 이미 기록된 의미 변경 시각에서 보수적으로 계산한다. `last_verified_at`은 별도 검증 시각이며 단순 confidence 재계산으로 갱신하지 않는다.

## 가장 중요한 의미 경계

**stale은 거짓, 철회, 폐기 또는 낮은 confidence를 뜻하지 않는다.** 설정된 기간 이후 다시 확인할 시점이 됐다는 warning일 뿐이다. 보고서는 stale claim을 자동 deprecate하지 않고 C-level을 내리지 않으며 evidence를 제거하지 않는다.

metadata-only도 같은 원칙을 따른다. immutable artifact가 없다는 preservation warning이지 source가 거짓이거나 낮은 S-level이라는 뜻이 아니다. feedback의 `harmful`·`irrelevant`도 검토 lead이며 target의 trust나 ranking을 자동 변경하지 않는다.

보고서는 항상 다음 invariant를 출력한다.

```json
{
  "read_only": true,
  "trust_mutated": false,
  "lifecycle_mutated": false,
  "status_mutated": false,
  "content_deleted": false,
  "staleness_changes_truth_value": false,
  "staleness_changes_confidence": false,
  "feedback_changes_ranking_or_trust": false,
  "host_paths_included": false,
  "wall_clock_used": false
}
```

## 실행

평가 시각을 명시적으로 넘겨야 한다. host wall clock을 암묵적으로 읽는 기본값은 없다.

```bash
python3 tools/memory_hygiene.py \
  --root . \
  --now 2026-08-11T00:00:00+00:00
```

byte 비교가 필요하면 compact JSON을 사용한다.

```bash
python3 tools/memory_hygiene.py \
  --root . \
  --now 2026-08-11T00:00:00Z \
  --compact
```

CLI는 stdout만 사용한다. 정상적인 stale/inactive/metadata-only/feedback finding이 있어도 exit code는 `0`이다. 입력 JSON, schema, timestamp, lifecycle 또는 feedback invariant가 잘못되면 stderr에 path-free JSON error를 쓰고 exit code `2`로 실패한다. `--now`가 없거나 timezone offset이 없으면 실행하지 않는다.

## 오래됨 판정 규칙

threshold는 `config/wiki.json`의 `staleness_days`를 그대로 사용하며 evaluator가 기본값을 만들지 않는다.

```json
{
  "staleness_days": {
    "fast": 30,
    "normal": 180,
    "slow": 730,
    "timeless": null
  }
}
```

claim별 기준 시각의 우선순위는 다음과 같다.

1. `last_verified_at`
2. `confidence.computed_at`
3. `created_at`

상위 필드가 malformed이면 하위 필드로 조용히 우회하지 않고 `unassessable_claims`에 남긴다. timestamp에는 명시적 UTC offset이 필요하다. 기준 시각이 `now`보다 미래이면 stale로 만들지 않고 `future_reference_claims`에 분리한다. threshold가 `null`인 `timeless` claim은 age-based stale 대상이 아니다.

판정은 다음과 같다.

```text
review_due_at = reference_at + threshold_days  # 검토 예정 시각
stale_warning = now >= review_due_at           # 노후 경고 판정
```

정확히 threshold에 도달한 시점부터 warning이다. report의 `stale_claims`에는 inactive claim도 감사 목적으로 남지만 `active_stale_count`는 lifecycle이 `active`인 항목만 센다.

## 수명주기 관찰

v4.1 canonical 필드는 다음과 같다.

```json
{
  "lifecycle_status": "active | deprecated | superseded | invalidated | archived",
  "lifecycle_reason": "...",
  "lifecycle_updated_at": "...",
  "lifecycle_updated_by": "actor:id",
  "replaced_by": "CLM-..."
}
```

필드가 없는 v4 레코드는 하위 호환 방식으로 `active`다. 파서는 정규 `lifecycle_status`를 가장 먼저 사용하고, 마이그레이션 견고성을 위해 이전 `lifecycle.status`, 마지막으로 기존 출처의 최상위 `status`를 읽는다. `confidence.status`의 `supported`, `contested`, `refuted`는 인식론적 상태이며 생명주기로 사용하지 않는다.

`deprecated`, `superseded`, `invalidated`, `archived`는 inactive다. `superseded`에 `replaced_by`가 없으면 report의 lifecycle `issues`에 남긴다. evaluator는 replacement를 만들거나 predecessor를 비활성화하지 않는다.

## 메타데이터 전용 출처

source의 `artifact`가 object가 아니거나, `artifact.path` 또는 `artifact.sha256`가 없으면 metadata-only로 집계한다. report는 ID와 lifecycle만 투영한다. URL, 원문, assessment rationale을 복사하지 않는다.

이 검사는 artifact file의 존재나 hash 일치를 대신하지 않는다. 그 불변조건은 계속 `python3 tools/wiki.py validate`가 담당한다.

## 정식 피드백 스키마

선택 ledger의 정확한 경로는 underscore를 사용하는 `state/memory_feedback.json`이며 top-level key는 `feedback`이다.

```json
{
  "version": 1,
  "feedback": [
    {
      "id": "MFB-...",
      "actor_id": "human:owner",
      "created_at": "2026-08-01T00:00:00+00:00",
      "task_ref": "opaque-task-reference",
      "targets": ["CLM-...", "SRC-..."],
      "outcome": "helpful | harmful | irrelevant | unknown",
      "rationale": "...",
      "evidence_refs": ["CLM-..."],
      "trust_effect": "none",
      "automatic_action": false,
      "status": "open | resolved",
      "resolution": {
        "actor_id": "human:owner",
        "at": "2026-08-02T00:00:00+00:00",
        "rationale": "..."
      }
    }
  ]
}
```

`resolution`은 상태에 따라 조건부다. `open`에는 없어야 하고 `resolved`에는 정확한 `actor_id`, `at`, `rationale`가 반드시 있어야 한다. 이 조합이 어긋나면 observer도 fail-closed한다.

report는 다음만 투영한다.

- outcome별 count
- 해결된 항목 수
- 상태가 `open`인 `harmful` 또는 `irrelevant` 결과의 피드백 ID와 대상 ID
- 중복 제거된 unresolved target ID
- claim/source ledger에 없는 target ID
- concerning feedback인데 target이 없는 schema-hygiene issue

`task_ref`, `rationale`, `evidence_refs`, resolution rationale 같은 자유 텍스트는 report에 복사하지 않는다. raw query를 `task_ref`로 사용해서도 안 되며 opaque reference만 기록해야 한다. `trust_effect`는 정확히 `none`, `automatic_action`은 정확히 `false`여야 한다. `digest`, `raw_query`, ranking·promotion 같은 canonical schema 밖 필드는 출력에서 숨기는 대신 입력 단계에서 거절한다.

## 보고서 구조

```text
memory_hygiene_observation  메모리 위생 관찰
├── as_of                  호출자가 제공한 시각만 사용
├── input_fingerprints     정규 입력 SHA-256, 호스트 경로 없음
├── summary                개수만 제공
├── staleness              임계값·노후·영구·평가 불가·미래 상태
├── lifecycle              주장·출처 상태 개수와 비활성 레코드
├── preservation           메타데이터 전용 출처
├── feedback               결과와 미해결 우려 대상
└── invariants             변경·삭제·자동 신뢰 효과 없음
```

동일 입력과 동일 `--now`는 byte-identical JSON을 만든다. report에는 실행 host, absolute path, implicit generated timestamp, random ID가 없다. input fingerprint는 비교용 digest이며 actor signature가 아니다.

## Python API 사용법

```python
from tools import memory_hygiene

report = memory_hygiene.evaluate_repository(
    "/path/to/wiki",
    now="2026-08-11T00:00:00+00:00",
)
```

순수 evaluator를 직접 호출할 수도 있다.

```python
report = memory_hygiene.build_report(
    config=config_snapshot,
    claims=claim_records,
    sources=source_records,
    feedback=feedback_payload_or_none,
    now="2026-08-11T00:00:00+00:00",
)
```

공개 helper는 `canonical_json`, `digest`, `parse_time`, `freshness_thresholds`, `freshness_reference`, `lifecycle_status`, `evaluate_staleness`, `evaluate_lifecycle`, `evaluate_sources`, `evaluate_feedback`, `build_report`, `evaluate_repository`다.

## 테스트

```bash
python3 -m unittest tests.test_memory_hygiene -v
python3 -m unittest discover -s tests -v
```

전용 테스트는 임계값 경계, 시각 우선순위와 시간대, 시각 없음·미래·형식 오류 기록, 표준·레거시 생명주기, 대체 문제, 메타데이터 전용 판정, 피드백 결과·개인정보·불변식, 선택형 원장, 입력 불변성, 경로와 무관한 결정론적 CLI, 실제 시계·네트워크·프로세스 권한 부재를 고정한다.

## 한계

- stale warning은 원출처가 실제로 바뀌었는지 확인하지 않는다.
- source publication/retraction status 조회는 live registry adapter의 책임이다.
- feedback은 selection bias와 actor 오류를 포함할 수 있으며 independent review가 아니다.
- unknown target은 삭제됐다는 뜻이 아니라 현재 claim/source 두 ledger에 없다는 뜻이다.
- report는 사용자 개인정보 삭제 요청을 수행하지 않는다.
- report 실행만으로 review, lifecycle transition, Wiki render 또는 release가 발생하지 않는다.
