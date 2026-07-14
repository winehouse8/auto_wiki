# GitHub PR 전달 운영 안내

Living Wiki v4.3의 변경 전달 목표는 “자동 작업도 사람이 추적 가능한 PR 이력으로 남긴다”이다. Agent를 정해진 시각에 깨우는 역할은 Codex 예약 작업이, 위생·연구·검증은 `living-wiki-steward` Skill이 맡는다. GitHub는 실행 시계가 아니라 브랜치·PR·check·검토·병합을 기록하고 통제하는 감사 제어면이다.

권위 문서 계약은 [Living Wiki GitHub PR 전달과 위험 기반 자동 병합](../wiki/specs/github-delivery.md)의 `SPEC-GH-DELIVERY-001` 버전 `1.2.0`이다. 연결 구현 RFC는 `RFC-03F4FE85BB44`다. 현재 후속 PR의 begin 영수증과 실행 코드·설정은 변경 전 운영 식별자 `SPEC-GH-DELIVERY-001/v1.1.0`에 고정돼 있으므로 이 PR 안에서 조용히 바꾸지 않는다. 사람 검토 병합 뒤 별도 정책 버전 전환을 감사 가능한 변경으로 완료해야 하며, 이번 계약 보강은 기존 exact-repository 승인 범위를 넓히지 않는다.

## 정확한 대상과 현재 배포 상태

- 저장소: [`winehouse8/auto_wiki`](https://github.com/winehouse8/auto_wiki)
- 기준 브랜치: `main`
- 자동 브랜치 접두사: `wiki-auto/`
- 병합 방식: `squash`
- 허용 근거: `COL-27B9ADD786ED`, `RFC-03F4FE85BB44`

빈 저장소에 기준 ref를 만드는 일회성 예외는 깨끗한 로컬 기준 커밋 `5f1d7f0`만 `main`에 직접 게시하면서 이미 소진했다. 이 작업과 branch protection 적용은 [GitHub 이슈 #1](https://github.com/winehouse8/auto_wiki/issues/1)에 공개 영수증으로 남겼다. 이후 자동 실행은 이 예외를 재사용하거나 `main`에 직접 push할 수 없다.

현재 구현 범위는 exact-repository 정책, 비밀 안전 loader, 결정론적 위험 분류, PR 본문과 영수증, 멱등성·SHA drift·check 판정 코어, fake transport 회귀검사와 비밀 없는 PR 품질 workflow다. 첫 사람 검토 통합 [PR #2](https://github.com/winehouse8/auto_wiki/pull/2)는 병합됐다. 현재는 그 뒤 발견한 prospective gate 자기 변경과 병합 영수증 재조정 결함의 후속 사람 검토 PR, 운영 정책 버전 전환, 실제 live adapter와 원격 자동 병합 경로의 전진 검증이 남아 있다. 이 두 제어면 변경을 병합한 뒤 별도의 무해한 canary PR에서 정확한 필수 check `전체 저장소 품질 게이트`와 squash auto-merge를 검증한다. 이 순서가 끝나도 `production_certified=false`다.

## 한 번의 예약 실행 흐름

```text
Codex 예약 작업이 Agent를 깨움
  → 현재 wiki/index.md 부트스트랩
  → 정확한 저장소·깨끗한 기준 SHA 확인과 실행 시작 영수증
  → 위생 → 도래한 관심사 → 캠페인 최대 하나
  → 로컬 전체 품질 게이트
  → 고정 base 대비 실제 변경 manifest 재산출과 위험 분류
  → 금지 diff·exact token 사전 commit 차단
  → GitHub 고유 브랜치·PR
  → 원격 check·SHA 재확인
  → 조건부 자동 병합, 자동 병합 대기 또는 사람 검토에서 정지
  → Codex 예약 작업 받은 편지함에 PR·merge·차단 영수증
```

GitHub Actions가 Agent를 깨우거나 의미 연구를 대신하지 않는다. PR workflow는 비밀 없는 `pull_request` 검증만 수행하며, privileged `pull_request_target`에서 신뢰하지 않은 PR head를 checkout하거나 실행하지 않는다.

## 사용자에게 보이는 다섯 상태

### 중요한 변경 없음

추적 파일 차이가 없으면 token을 읽지 않고 branch, commit, PR을 만들지 않는다. 무변경 실행을 증명하려고 빈 이력을 만들지 않고 예약 실행 요약에 `중요한 변경 없음`만 남긴다.

### 자동 병합 후보

파생 Wiki 뷰·색인·보고서 재생성이나 정확한 비의미 메타데이터 보수처럼 헌장이 이미 허용한 저위험 변경만 이 경로를 사용할 수 있다. ready PR에 `자동화`, `자동-병합-후보` 라벨을 붙이고 다음 조건을 모두 다시 확인한 뒤에만 squash auto-merge를 요청한다.

- 전체 로컬 게이트 성공
- 정확한 원격 필수 check `전체 저장소 품질 게이트` 성공과 같은 head SHA
- 고정한 base/head/tree SHA 일치
- 충돌·미해결 대화·기준 브랜치 drift 없음
- diff 전체가 사전 승인된 저위험 범위

하나라도 알 수 없으면 자동 병합하지 않는다.

### 자동 병합 대기

GitHub의 auto-merge 활성화 응답은 실제 병합 완료가 아니다. 요청 직후 PR을 다시 조회했을 때 `merged=true`와 merge SHA를 확인하지 못하면 `자동 병합 대기`로 기록한다. 후속 실행은 같은 멱등성 키의 PR을 재조회해 완료·차단·계속 대기 중 하나로 재조정하며, 이미 활성화된 auto-merge를 중복 요청하지 않는다.

### 사람 검토 필요

다음 변경은 상세 한국어 본문이 있는 draft PR까지만 만든다.

- `.github/**`, `AGENTS.md`, `governance/**`, `config/**`, `tools/**`, `scripts/**`, `prompts/**`, `skills/**`, `tests/**`, `wiki/specs/**`
- 헌장·schema·스케줄·권한·자격증명·외부 공개 경로
- 기존 주장·출처의 의미, evidence, C/S-level, 독립성 그룹이나 생명주기
- 새 raw, 의미 충돌의 정규 반영, 판정이 불확실한 diff

PR 본문에는 실행·기준 SHA·변경 manifest·RFC와 승인 근거·검증·위험 이유·인식론적 영향·미해결 항목·검토 방법·롤백을 적는다. Agent는 이 PR을 approve하거나 ready로 바꾸거나 병합하지 않는다. 사람은 GitHub에서 실제 diff와 check를 확인한 뒤 병합 여부를 정한다.

### 차단

다음 문제는 PR이나 직접 push로 우회하지 않는다.

- 대상 저장소·기준 브랜치·승인 근거 불일치
- `auth/**` 또는 token·private key가 diff에 포함됨
- 기존 raw 덮어쓰기·이동·삭제
- `state/events.jsonl` 재작성 또는 append-only 미검증
- 토큰 파일 안전 계약 위반
- merge conflict, SHA drift, 필수 check 실패·누락
- 인증·권한 실패 또는 안전하게 PR을 만들 수 없음

가능하면 이미 열린 PR에 비밀 없는 차단 설명을 남기고, 그렇지 않으면 로컬 차단 영수증과 복구 방법을 보존한다. Wiki 내용 검증 성공과 GitHub 게시 성공을 별도 상태로 보고한다.

CLI가 `차단` 영수증을 반환하면 종료 코드는 반드시 nonzero여야 한다. 구조화된 영수증을 출력했다는 이유로 호출자에게 성공 종료를 반환하지 않는다. `자동 병합 대기`는 별도의 비동기 전달 상태이며 병합 완료로 보고하지 않는다.

## 자격증명 경계

초기 자격증명은 `auth/github_token.yaml`의 classic PAT다. 파일은 symbolic link가 아닌 regular file, 현재 사용자 소유, 정확한 `0600`, Git ignore 대상이면서 미추적이어야 한다. 문서는 top-level `key` 하나의 비어 있지 않은 단순 문자열만 허용한다.

정확한 저장소·기준 브랜치·승인 근거를 **토큰 본문을 읽기 전에** 검증한다. 토큰은 필요한 자식 프로세스의 `GH_TOKEN` 환경에만 전달하고 다음 위치에 쓰지 않는다.

- Git 원격 URL과 저장소 설정
- 명령 인자와 셸 기록
- 표준 출력·표준 오류와 오류 원문
- commit, PR 본문, comment와 라벨
- 영수증, 보고서, 산출물과 cache
- 값의 해시·길이처럼 식별에 쓸 수 있는 파생 정보

commit 전에는 안전하게 읽은 실제 토큰 문자열과 정확히 일치하는 바이트가 base 대비 후보 파일, staged patch와 staged blob에 없는지 검사한다. 일반적인 secret pattern 검사만으로 이를 대신하지 않는다. 일치가 있으면 값을 출력하거나 해시하지 않고 commit 전에 차단한다.

Git·`gh` 자식 프로세스에서는 상속된 credential helper를 빈 `credential.helper`로 process 범위에서 먼저 초기화하고, 대상 GitHub URL에만 `!gh auth git-credential` helper를 추가한다. `GIT_TERMINAL_PROMPT=0`, `GH_PROMPT_DISABLED=1`로 대화형 인증을 막고, 자식 프로세스가 끝나면 `GH_TOKEN`과 임시 설정을 폐기한다. 전역·로컬 Git config와 credential store는 바꾸지 않는다.

classic PAT는 인간 소유자와 Agent를 같은 `winehouse8` 계정으로 나타내며 권한 범위도 넓다. 그러므로 draft PR과 adapter의 merge 금지가 사람 검토 경계의 핵심이고, 같은 계정의 형식적 self-review를 독립 승인으로 간주하지 않는다. 짧은 수명의 저장소 한정 GitHub App이나 전용 machine user로 행위자를 분리하는 작업은 후속 RFC에서 다룬다.

## 공개 clean clone과 로컬 격리 보관

`raw/quarantine/`은 신뢰하지 않은 원문 payload의 로컬 보안 격리 영역이다. public 저장소에는 이 bytes를 올리지 않으며 delivery adapter는 추가를 포함한 이 경로의 모든 추적 변경을 사람 검토 PR보다 앞에서 차단한다. `.gitignore`만으로 강제 추적이나 ignore 변경을 막을 수 없으므로 실제 Git manifest·staged diff·commit diff의 차단이 권위 경계다.

일반적인 로컬 수집·보관 작업 사본은 기본 `strict-local-custody` 검증 프로필을 사용한다. 여기서는 admission이 가리키는 격리 파일이 하나라도 없으면 오류다. exact `winehouse8/auto_wiki` delivery linked worktree와 비밀 없는 PR workflow만 다음처럼 `public-clean-clone`을 명시한다.

```bash
python3 tools/wiki.py lint --quarantine-profile public-clean-clone
python3 tools/wiki.py validate --quarantine-profile public-clean-clone
python3 tools/wiki.py release-check --quarantine-profile public-clean-clone
```

이 프로필은 누락을 포괄 허용하지 않는다. content-addressed 경로·SHA-256·크기·미디어 유형, 보안 manifest와 출처 참조, 전체 무부작용 불변조건, canonical admission ID·record digest, 상세 `security.candidate.screen` 사건 anchor가 모두 맞을 때만 경고로 낮춘다. 결과의 `quarantine_payload_verified=false`는 원문 bytes를 재검증하지 못했다는 명시적 한계다. source·C/S-level·evidence·lifecycle을 승격하는 효과는 없다.

## 실행 소유권·멱등성과 복구

각 실행은 최신 `origin/main`과 일치하는 깨끗한 전용 작업 사본에서 run ID와 base SHA를 고정하고 `wiki-auto/<run-id>` 소유 브랜치를 사용한다. 첫 통합 PR을 포함한 모든 실행은 `origin/main` 기준의 별도 clean 작업 사본에서 `begin` 영수증을 먼저 만든 뒤 승인된 patch만 적용한다. 기존 dirty 기본 작업 사본을 직접 stage하거나 시작 영수증 이전 파일을 manifest로 추측하지 않는다.

전체 게이트가 끝나면 고정 base SHA 대비 실제 Git 상태와 diff로 추가·수정·삭제·이동·새 추적 후보를 포함한 manifest를 다시 만든다. 이 결과가 caller의 `safe`, `generated_only`, `semantic_change` boolean이나 사전 manifest보다 권위 있다. 금지 diff는 stage 전에 차단하고, 허용 파일을 stage한 뒤 같은 manifest 및 base와 다시 비교해 commit 전 불일치도 차단한다. `git add -A`로 사용자 변경이나 다른 실행의 파일을 추측해 포함하지 않는다.

publish 내부 재검증은 `render`, `lint`, `release-check`를 `--no-log`로 실행한다. begin 이후의 실제 관리 사건을 지우는 것이 아니라 같은 publish의 검증 때문에 사건 수와 릴리스 fingerprint가 계속 바뀌는 순환을 막는 경계다. 게이트가 최초로 만든 새 `evaluations/reports/v4-release-<fingerprint>.json`은 경로·component fingerprint·전체 gate 성공·`production_certified=false`·canonical report digest가 모두 맞을 때만 최종 실측 manifest에 추가한다. 다른 새 경로나 잘못된 archive는 token·stage 전에 차단한다.

멱등성 키는 `policy version + run ID + base SHA + tree SHA`다. timeout 뒤에는 생성·병합을 곧바로 반복하지 않고 원격 브랜치, PR marker와 merge 상태를 조회한다. 같은 키는 branch·PR·auto-merge 요청을 각각 최대 한 번만 만든다. force push, admin bypass, force merge와 다른 실행의 브랜치 재사용은 금지한다.

전달을 중단하려면 Codex 예약 작업을 먼저 일시 정지하고 열린 자동 PR을 삭제하지 않은 채 close한다. PAT는 revoke·rotate한다. adapter·workflow·설정 제거 역시 사람 검토 PR로 수행하고, 이미 남은 issue·PR·merge·comment 영수증은 감사 이력으로 보존한다. 병합된 내용은 이력을 지우지 않고 새 revert PR로 되돌린다.

## 검증 경계

GitHub 전달은 기존 여덟 개 통합 릴리스 게이트를 대체하거나 아홉 번째 게이트인 것처럼 가장하지 않는다. 로컬 릴리스 검사와 전체 단위 테스트가 먼저 성공한 뒤 별도의 delivery preflight가 exact repo, token 안전, 실측 manifest, 위험 경로와 SHA를 검증한다. 원격 PR check는 같은 품질 명령을 비밀 없이 다시 실행하며, 자동 병합 판정과 branch protection은 정확한 이름 `전체 저장소 품질 게이트`만 필수 check로 인정한다.

로컬 fake transport 성공, 일회성 seed, 첫 통합 PR과 canary 성공은 장기 장애, 권한 오용, 의미 공격, 토큰 탈취나 행위자 분리를 인증하지 않는다. 모든 결과에서 `production_certified=false`를 유지한다.
