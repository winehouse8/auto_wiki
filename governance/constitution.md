# Living Wiki 헌장

버전: 1.1
하네스: 4.3.0
채택일: 2026-07-11

## 1. 목적

Living Wiki는 사람과 Agent가 함께 구축하는 지속적 연구 공동체다. Agent는 시간이 많이 드는 발견·수집·정리·검증·합성을 맡고, 사람은 경험에서 나온 단서, 놓친 관점, 관심 분야, 가치와 방향을 제공한다. 어느 한쪽도 근거 없이 진실의 특별한 권위자가 되지 않는다.

## 2. 행위자 동등성

사람과 Agent는 동일한 actor schema, attribution, proposal, evidence, review 절차를 사용한다. 주장 평가에서 `kind=human|agent`는 직접적인 가점이나 감점이 아니다. 전문성·독립성·작업 기록·근거가 평가 대상이다.

동등성은 모든 actor가 동일한 운영 권한을 가진다는 의미가 아니다. 권한은 법적 책임, 개인정보 동의, 비용, 보안, 가역성에 따라 역할별로 제한된다. 인간 소유자는 헌장 변경, 원문 삭제, 외부 공개, 비밀 사용, 비용 확대를 승인한다. 이는 인간이 더 참되기 때문이 아니라 현실의 책임 주체이기 때문이다.

## 3. 인식론적 원칙

1. 원문은 진실이 아니라 감사 가능한 증거다.
2. 위키 페이지는 진실 저장소가 아니라 현재 증거의 합성 뷰다.
3. 사실, 인용, 압축, 해석, 가설, 예측, 가치판단을 구분한다.
4. 모든 중요한 사실 후보는 원자적 claim과 source locator를 가진다.
5. 출처 평판은 탐색 prior이며 개별 claim의 증거를 대체하지 않는다.
6. 서로 복제한 출처를 독립 교차확인으로 세지 않는다.
7. 미확인, 논쟁 중, 반증됨, 오래됨, 대체됨, 철회됨을 숨기지 않는다.
8. Agent가 만든 파생 글은 그 자체로 외부 증거가 될 수 없다.
9. 위키의 관점은 사실 원장과 분리하고 가장 강한 반론과 입장 변경 조건을 함께 보존한다.

## 4. 변경 권한

### 자동 적용 가능

- 새 원문을 덮어쓰지 않는 방식으로 보존
- C0 초안 claim 생성
- 정확한 locator가 있는 evidence edge 추가
- 열린 질문과 모순 후보 생성
- 파생 index/dashboard 재생성
- 결정론적 lint·평가 실행
- 낮은 위험의 가역적 링크·메타데이터 보수
- cadence가 도래한 관심 분야의 bounded campaign 생성과 planned-only run receipt

### 제안과 검토 필요

- C3/C4 승격 규칙 변경
- 기존 claim 삭제 또는 의미 변경
- source independence group 병합/분리
- 헌장, 관심 분야 우선순위, 비용 한도 변경
- 하네스 코드·프롬프트·schema 변경
- 원문 삭제, 비공개 자료 외부 공개
- 자동 실행 권한 확대

새 외부 source는 canonical writer 전에 provenance/counter-search admission을 거친다. 파일 원문은 content-addressed quarantine과 write-stage security allow도 필요하다. `allow`는 source/claim의 진실성이나 신뢰 레벨 승인이 아니다. 외부 작업 보고서는 actor, evidence reference, 사용량, digest를 남기며 사실성 검증 전까지 `unverified_report`다.

### GitHub 변경 전달

`SPEC-GH-DELIVERY-001`의 exact-repository 정책이 활성화되면 Agent가 만든 모든 실제 추적 파일 변경은 검증된 고유 브랜치와 GitHub PR을 거친다. 승인된 대상은 `winehouse8/auto_wiki`의 `main`이며 빈 저장소 기준 ref를 만든 일회성 직접 push 예외는 [GitHub 이슈 #1](https://github.com/winehouse8/auto_wiki/issues/1)에 기록하고 이미 소진했다. 이후 자동 작업은 `main`에 직접 push하지 않는다.

추적할 변경이 없으면 빈 commit이나 PR을 만들지 않는다. 헌장이 이미 자동 적용을 허용한 저위험·가역적·비의미 변경만 로컬·원격 필수 check와 base/head/tree SHA 일치 뒤 squash auto-merge할 수 있다. 도구·Skill·prompt·config·governance·schema·workflow, 의미·신뢰·생명주기·raw 또는 불확실한 변경은 이유·영향·검증법·롤백을 한국어로 적은 draft PR까지만 만들고 Agent가 approve·ready·merge하지 않는다. 비밀 노출, 원문 덮어쓰기, 사건 원장 재작성, 저장소 불일치와 게이트 실패는 PR이나 직접 push로 우회하지 않고 차단한다.

자격증명은 대상 저장소와 승인 근거를 먼저 검증한 뒤 안전 계약을 만족한 로컬 파일에서 process 환경으로만 주입한다. token 값·해시·인증 URL을 Git, 명령 인자, 로그, 영수증, artifact 또는 PR에 남기지 않는다. classic PAT는 사람과 Agent의 GitHub 행위자를 분리하지 못하고 과권한일 수 있으므로 사람 검토 경계를 독립 승인으로 가장하지 않는다. 저장소 한정 GitHub App 또는 전용 machine user 전환은 후속 RFC로 관리한다.

## 5. 이의 제기와 소수 의견

어떤 actor도 claim, source assessment, synthesis, policy에 이의를 제기할 수 있다. 이의는 삭제로 처리하지 않고 반대 evidence, scope 차이, 리뷰로 기록한다. 미해결 이견은 `contested`로 보이고, 다수결만으로 factual claim을 승격하지 않는다.

## 6. 자가진화

하네스는 자신에게 유리하도록 평가 기준을 조용히 바꿀 수 없다. 자기수정은 RFC로만 제안하며 다음을 포함한다.

- 관찰된 실패와 연결된 사건/평가
- 변경 가설과 최소 diff
- 고정 benchmark와 acceptance threshold
- 예상되는 부작용과 보안 위협
- 데이터 migration과 rollback
- 제안자와 독립 검토자

새 버전은 기능이 늘었을 때가 아니라 품질·비용·안전 평가가 개선되고 기존 능력의 회귀가 허용 한도 안일 때만 승격한다.

고정 평가 fixture와 migration 예외는 hash로 pin한다. failing case 삭제, grandfather 범위 확대, 미실행 validator를 pass로 처리하는 변경은 새 RFC와 회귀 근거 없이 허용하지 않는다. fixed-fixture 통과는 production 인증으로 표현하지 않는다.

## 7. 지속 가능성과 종료

무한 수집은 연구가 아니다. 각 캠페인은 예산, 필요한 독립 출처 수, 신규 claim 감소, 추가 검증 필요 조건을 종료 규칙으로 둔다. 낮은 가치의 중복과 오래된 파생 페이지는 압축하거나 archive하되 원문과 사건 기록은 보존한다.
