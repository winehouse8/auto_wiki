---
type: OKF Profile
title: Living Wiki의 OKF 프로필
description: 이 OKF v0.1 번들이 인식론·거버넌스 확장을 대응시키는 방식.
resource: https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md
tags: [okf, interoperability, profile]
timestamp: '2026-07-12T22:30:00+09:00'
okf_version: '0.1'
spec_status: Draft
bundle_boundary: wiki/
claim_ids: [CLM-7FDAF2F91E73, CLM-952258184EF2, CLM-F526A53CB69F]
---

# Living Wiki의 OKF 프로필

`wiki/` 디렉터리는 이식 가능한 Open Knowledge Format 번들이다. 그 주변 저장소는 제어 영역이며 의도적으로 번들 경계 밖에 둔다.

# 적합성

- 예약 문서가 아닌 모든 Markdown 문서는 비어 있지 않은 `type`을 포함한 YAML frontmatter를 가진다.
- `index.md`와 `log.md`는 예약 파일이며 frontmatter 없이 유지한다.
- 교차 링크는 표준 Markdown 링크를 사용한다.
- 디렉터리 색인은 점진적 공개를 제공한다.
- 외부 근거가 있는 경우 `# 인용` 절에 표시한다.
- 소비자는 알 수 없는 생산자 확장 키도 보존해야 한다.

# Living Wiki 확장

OKF v0.1은 분류 체계, 저장소, 질의 인프라, 신뢰, 거버넌스를 의도적으로 생산자에게 맡긴다. 이 번들은 허용된 다음 frontmatter 확장을 사용한다.

공식 `timestamp`는 확장 필드가 아니며 마지막 의미 있는 내용 변경 시각으로 사용한다. 단순 렌더링·색인 재생성·파일 시스템 mtime는 이 값을 진전시키지 않는다.

정규 claim/source에 `content_updated_at`이 있으면 이를 `timestamp`로 투영한다. 이 정규 필드는 별도 frontmatter 키를 중복 생성하지 않는다. 이전 레코드는 이미 기록된 생성·증거 추가·confidence 결과 변화·검색·평가·생명주기 시각에서 보수적으로 `timestamp`를 계산하며, 실제 검증 시각은 그 계산과 분리한다.

| 키 | 의미 |
|---|---|
| `claim_ids` | `../state/claims.json`의 정규 식별자 |
| `source_id` | `../state/sources.json`의 정규 출처 레코드 |
| `source_level` | 범위가 한정된 S0–S4 출처 근거 성숙도 |
| `lifecycle_status` | `draft`/`active`/`contested`/`superseded` 상태 |
| `generated` | 결정론적으로 생성한 파생 뷰 |
| `okf_version` | 이 프로필 문서에 고정한 형식 버전 |
| `created_at` | 정규 상태에서 알려진 최초 생성 시각 |
| `last_verified_at` | 원근거와 적용 범위를 실제 재확인한 시각 |
| `freshness` | 검토 기한을 계산하는 최신성 분류 |
| `lifecycle_updated_at` | 내용 변경과 구분한 생명주기 전이 시각 |
| `retrieved_at` | 출처를 검색·입수한 시각 |
| `assessed_at` | 출처의 범위 한정 평가를 수행한 시각 |

이 키들은 OKF를 확장하며, v0.1 명세가 신뢰나 출처 이력 의미론을 정의한다는 주장이 아니다.

# 객체 대응

| Living Wiki 객체 | OKF 표현 | 정규 제어 영역 레코드 |
|---|---|---|
| 개념·종합·입장 | 형식이 지정된 개념 Markdown | frontmatter·본문의 주장 링크 |
| 외부 출처 | `sources/src-*.md`, `type: Reference` | `state/sources.json` |
| 원자적 주장 | 근거 표가 있는 `claims/clm-*.md`, `type: Claim` | `state/claims.json` |
| 행위자 | `actors/actor-*.md`, `type: Actor` | `state/actors.json` |
| 검토 | `reviews/rev-*.md`, `type: Review` | `state/reviews.json` |
| 연구 캠페인 | `campaigns/cmp-*.md`, `type: Research Campaign` | `state/campaigns.json` |
| 협업 레코드 | `collaborations/col-*.md`, `type: Collaboration Record` | `state/collaborations.json` |
| 수용 결정 | `admissions/adm-*.md`, `type: Admission Decision` | `state/admissions.json` |
| 실행 영수증 | `runs/run-*.md`, `type: Runtime Receipt` | `state/runs.json`과 외부 영수증 원장 |
| 신뢰·거버넌스 | 형식이 지정된 생산자 정책 개념 | `config/`와 `governance/` |
| 사건 | 사람이 읽을 수 있는 예약 `log.md` 요약 | `state/events.jsonl` 해시 체인 |
| 탐색·이력 | 예약 `index.md`·`log.md` | 정규 상태에서 재생성 |

# 경계 설정 근거

OKF는 상호운용 가능한 지식 교환 계층이지 전체 실행 환경이 아니다. JSON 원장, 원문·격리 산출물, 평가기 스냅샷, 영수증, 비밀, 실행 도구는 번들 밖에 둔다. 행위자, 출처, 주장, 검토, 캠페인, 협업, 수용, 실행, 신뢰, 거버넌스 레코드는 단방향 투영이며 내보내기 도구가 상태를 만들어 내거나 승격하지 않는다. OKF만 이해하는 소비자도 지식을 읽을 수 있고, Living Wiki를 이해하는 소비자는 확장 식별자를 따라 더 강한 출처 이력·거버넌스 데이터로 이동할 수 있다. v4에서는 생성된 개념을 직접 편집해도 정규 상태로 역수입하지 않는다.

# 알려진 한계

공식 명세는 2026-07-11 기준 0.1 버전이며 `Draft`로 표시돼 있다. 이 저장소는 프로필을 고정하고 로컬에서 검사한다. 향후 호환성을 깨는 OKF 변경에는 조용한 재작성 대신 마이그레이션 RFC가 필요하다.

# 인용

[1] [Google Cloud announcement: How the Open Knowledge Format can improve data sharing](https://cloud.google.com/blog/products/data-analytics/how-the-open-knowledge-format-can-improve-data-sharing)
[2] [Official Open Knowledge Format v0.1 specification](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md)
