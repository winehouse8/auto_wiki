<!-- state/proposals.json에서 자동 생성함. -->
# RFC-1B8A142F2DD6: 하네스 제안 — Living Wiki 관리인 Codex Skill v1

상태: `implemented`
제안자: `agent:codex`
생성 시각: 2026-07-12T02:42:48+00:00

## 문제

기록된 문제: Codex Scheduled Tasks는 예약 실행을 제공하지만 현재 Wiki에는 예약 작업이 재사용할 단일 Skill이 없다. 기존 AGENTS와 연구 프롬프트는 분산되어 있고 위생, 도래한 연구, 자기 발전, 무변경 차이와 권한 경계를 하나의 호출 가능한 작업 절차와 수용 계약으로 묶지 못한다.

## 제안 변경

기록된 변경안: SPEC-LWS-001을 표준 제품 요구사항으로 두고 저장소에서 관리하는 skills/living-wiki-steward 패키지를 생성한다. SKILL.md는 색인 우선 부트스트랩, 의도 분기, 결정론적 위생, 단일 캠페인 제한 연구, 자연어 관심사 제어, RFC로 통제되는 자기 발전과 간결한 차이를 규정한다. agents/openai.yaml과 예약 작업 프롬프트 참고 문서를 포함하고 CODEX_HOME 개인 Skill에는 표준 원본 링크로 설치한다. 새 스케줄러, 상태 스키마와 네트워크 권한은 만들지 않는다.

## 근거

- `CLM-1EB8BD726482`
- `CLM-CB6E34C87DA3`
- `CLM-DA7C92E9A901`
- `CLM-F464CCF0AA1A`
- `CLM-F79558D817DF`

## 벤치마크와 수용 게이트

기록된 수용 기준: AC-LWS-001~010을 계약 테스트로 고정한다. Red에서 Skill 패키지 부재와 메타데이터·작업 절차·안전장치·예약 프롬프트·설치 링크 계약 실패를 보존하고, Green에서 init_skill.py 생성물, quick_validate, 저장소 테스트, 독립 읽기 전용 전진 시험, render, lint, 고정 시각 memory-hygiene, validate, okf-validate, 전체 단위 테스트와 release-check가 통과해야 한다.

## 위험

- 기록된 위험: 홈 설치본과 저장소 원본의 차이 발생
- 기록된 위험: 무변경 실행이 불필요한 변경을 만듦
- 기록된 위험: 예약 프롬프트가 과도한 권한으로 해석됨
- 기록된 위험: 의미 관계 링크의 잘못된 수정
- 기록된 위험: Skill과 제품 요구사항의 차이 발생
- 기록된 위험: 장기 연구 비용 확대

## 롤백

기록된 롤백: Scheduled Task를 일시 정지하고 CODEX_HOME의 living-wiki-steward 링크와 저장소 관리 Skill 디렉터리를 제거한다. SPEC/RFC와 사건 이력은 감사용으로 남기거나 대체 상태로 전환한다. 새 표준 상태 스키마가 없으므로 기존 주장·출처·원문·캠페인은 마이그레이션 없이 유지된다.

## 검토 결정

- `2026-07-12T02:42:54+00:00` — **approve** / 검토자 `human:owner`: 사용자가 Codex 기본 Scheduled Tasks 조사 결과를 수용하고 필요한 Skill을 제품 요구사항과 명세 주도 테스트 개발 방식으로 즉시 만들라고 명시했다. 승인은 SPEC-LWS-001의 저장소 관리 Skill, 개인 검색 링크, 읽기 전용 전진 시험과 문서·테스트 변경에 한정하며 Scheduled Task 생성·실행, 새 네트워크·자격증명·비용 권한과 신뢰도 자동 승격은 포함하지 않는다.

## 구현 근거

- 릴리스 보고서: `evaluations/reports/v4-release-65af31652c9b7040.json`
- 구성요소 지문: `65af31652c9b7040b8c70d80db641370ef14c260ee7bff7c201b4213df2f8225`
- 운영 환경 인증: `False`
