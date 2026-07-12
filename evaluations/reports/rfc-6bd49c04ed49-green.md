---
type: Evaluation
title: RFC-6BD49C04ED49 범위 제한 위생 Green 근거
description: 결정론적 전수 구조 검사·시간 시드·2-hop 라우팅·검토 전용 충돌 후보의 구현 및 회귀 결과.
tags: [evaluation, green, hygiene, routing, tdd]
timestamp: '2026-07-12T23:20:00+09:00'
---

# RFC-6BD49C04ED49 범위 제한 위생 Green 근거

## 구현 결과

- `tools/wiki_hygiene.py`가 정규 상태와 비예약 Wiki 문서를 모델 없이 전수 검사한다.
- 구조 위험, 최근 문서, 검토 기한 초과 주장과 더 최신인 의존성을 시드로 만들고 강한 유형 관계만 최대 2-hop·전체 노드 상한에서 확장한다.
- 논리 충돌은 명시적 evidence 관계 또는 충분한 문장 주제 anchor가 있는 극성·수치·조건 차이만 제안한다.
- 충돌과 약한 관계는 모두 `review_only=true`이며 evidence·C/S-level·lifecycle 자동 변경이 없다.
- OKF 의미 시각과 `created_at`, `last_verified_at`, `freshness`, `lifecycle_updated_at`을 보수적으로 투영하고 단순 평가·렌더가 검증 시각을 진전시키지 않는다.

## 검증

```bash
python3 -m unittest tests.test_wiki_hygiene tests.test_wiki tests.test_living_wiki_steward_skill tests.test_harness_spec_contract -v
```

초기 Green: **60개 테스트 통과**.

정밀도 Refactor 뒤:

```bash
python3 -m unittest tests.test_wiki_hygiene -v
python3 -m py_compile tools/wiki.py tools/wiki_hygiene.py
git diff --check
```

결과: **위생 계약 8개 통과**, compile과 diff 검사 통과. 고정 입력·고정 시각 계획을 두 번 만든 canonical bytes도 같다.

## Refactor 효과

- heuristic conflict: 17개에서 1개로 감소했다.
- 약한 관계 전체 후보: 1,927개에서 194개로 감소했다.
- 의미 검토 큐는 `충돌 → 구조 위험 → 노후 → 의존성 지연 → 최근 문서 → 약한 관계` 순서를 사용한다.
- 실제 상위 10개는 충돌 1, 기등록 반증 위험 1, 의존성 지연 1, 최근 문서 7이다.

고정 Red fixture는 삭제하거나 완화하지 않았다.
