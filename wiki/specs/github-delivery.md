---
type: Specification
title: Living Wiki GitHub PR 전달과 위험 기반 자동 병합
description: 자동 Wiki 변경을 GitHub 브랜치·PR·검증·조건부 병합으로 전달하는 사용자 경험과 보안 계약.
tags: [github, pull-request, automation, audit, security, delivery]
timestamp: '2026-07-15T01:36:01+09:00'
---

# Living Wiki GitHub PR 전달과 위험 기반 자동 병합

- 명세 ID: `SPEC-GH-DELIVERY-001`
- 버전: `1.2.0`
- 상태: 사용자 지시에 따라 승인된 설계 계약
- 승인 방향: `COL-27B9ADD786ED`
- 연결 RFC: `RFC-03F4FE85BB44`
- 상위 계약: [Living Wiki 하네스 사용자 경험과 전달 계약](harness-ux.md)
- 연결 제품: [Living Wiki 관리인 Skill 제품 요구사항](living-wiki-steward-skill.md)

## 제품 목표

Living Wiki 관리인이 실제 추적 파일을 바꾸면 모든 변경을 GitHub의 고유 브랜치와 Pull Request로 전달한다. 사용자는 일반적인 위생·연구 요청만 하면 되며 저장소 이름, 브랜치, 라벨, 위험 분류나 CLI를 외울 필요가 없다.

저위험 자동 변경은 필수 검증이 성공한 뒤 GitHub의 squash auto-merge로 병합한다. GitHub auto-merge는 설정된 필수 리뷰와 상태 check가 충족된 뒤 병합하도록 설계된 기능이다.[1] 사람 판단이 필요한 변경은 검토 이유, 영향, 검증법과 롤백을 한국어로 적은 draft PR을 만들고 Agent는 auto-merge, 즉시 merge, 승인 또는 draft 해제를 수행하지 않는다.

GitHub는 변경 전달·검증·검토·병합의 감사 제어면이다. Agent를 깨우는 시계와 의미 연구 실행기는 계속 Codex 예약 작업과 관리인 Skill이 담당한다. GitHub Actions는 PR의 비밀 없는 읽기 전용 품질 검증을 담당하며, 별도 Agent 자격증명 없이 의미 연구를 수행한다고 가장하지 않는다.

## 정확한 운영 범위

- 대상 저장소: `winehouse8/auto_wiki`
- 기준 브랜치: `main`
- 자동 브랜치 접두사: `wiki-auto/`
- 병합 방식: `squash`
- 승인 근거: `COL-27B9ADD786ED`와 이 명세에 연결된 승인 RFC
- 기본 호출: Codex 예약·수동 관리 작업의 마지막 `검증 → GitHub 전달` 단계

저장소·기준 브랜치·승인 근거가 정확히 일치하지 않으면 토큰을 읽기 전에 중단한다. 일반 다중 저장소 관리자, fork 자동 생성기와 임의 셸 실행기는 범위 밖이다.

버전 `1.2.0`은 첫 통합 PR 병합 뒤 발견한 prospective gate의 자기 변경과 사람·비동기 자동 병합 영수증 재조정 결함을 좁게 보강한다. 현재 후속 실행은 begin 영수증과 운영 코드·설정의 `SPEC-GH-DELIVERY-001/v1.1.0` 식별자를 그대로 고정하고, 사람 검토 병합 뒤 별도 정책 버전 전환으로 v1.2를 활성화한다. 기존 승인 저장소·브랜치·행위자·병합 방식과 RFC 승인 범위를 넓히지 않으며, production 인증도 추가하지 않는다.

## 사용자에게 보이는 상태

| 상태 | 조건 | GitHub 동작 | 사용자 결과 |
|---|---|---|---|
| `중요한 변경 없음` | 추적할 파일 차이가 없음 | commit과 PR을 만들지 않음 | 실행 요약만 반환 |
| `자동 병합 후보` | 모든 작업이 사전 승인된 저위험 범위이고 로컬·원격 게이트가 성공 | ready PR, `자동화`·`자동-병합-후보` 라벨, squash auto-merge 요청 | PR과 병합 요청 영수증 |
| `자동 병합 대기` | auto-merge 요청은 접수됐지만 재조회 시 아직 merge SHA가 없음 | 새 요청 없이 원격 PR 상태를 재조정 | 대기 PR과 다음 재조정 기준 |
| `사람 검토 필요` | 제어면·의미·권한 변경 또는 판정 불확실성 | draft PR, `자동화`·`사람-검토-필요` 라벨, 상세 검토 메시지 | GitHub에서 사람이 검토·병합 |
| `차단` | 비밀 노출, 금지 작업, 저장소 불일치, 게이트 실패 또는 안전한 PR 생성 불가 | 가능한 경우 기존 PR에 차단 설명, 아니면 비밀 없는 로컬 영수증 | 원인과 복구 방법 |

실제 변경이 있는데 브랜치·PR 영수증이 없으면 완료가 아니다. 반대로 무변경 실행을 감사하기 위해 빈 commit이나 빈 PR을 만들지 않는다.

## 위험 판정

전체 로컬 게이트가 생성·재생성한 파일까지 반영한 뒤, `begin`에서 고정한 base SHA 대비 실제 Git 상태와 diff로 최종 manifest를 다시 산출한다. 이 실측 manifest가 호출자가 제공한 `safe`, `generated_only`, `semantic_change` 같은 boolean이나 사전 manifest보다 권위 있다. 호출자 값은 설명용 힌트일 뿐 위험을 낮추거나 실제 diff를 누락시킬 수 없다. 둘이 어긋나거나 실측할 수 없는 항목이 있으면 최소 `사람 검토 필요`, 금지 경로나 비밀 가능성이 있으면 `차단`으로 올린다.

실측 manifest에는 추가·수정·삭제·이동과 새 추적 후보가 모두 포함돼야 한다. 금지 경로, 기존 raw 덮어쓰기, 사건 원장 재작성, symlink·submodule·실행 바이너리·과대 파일과 해석할 수 없는 상태는 어떤 파일도 stage하거나 commit하기 전에 차단한다. 허용 manifest를 stage한 뒤에는 staged tree를 같은 base SHA 및 manifest와 다시 비교하고, 불일치가 있으면 commit 전에 차단한다.

### 자동 병합 가능

다음 조건을 모두 만족해야 한다.

1. 실행 시작 시 최신 `origin/main`과 일치하는 깨끗한 전용 작업 사본이며 실행 ID와 기준 SHA를 고정했다.
2. 변경 manifest의 모든 파일과 작업이 헌장의 자동 적용 범위다.
3. 파생 Wiki 뷰·색인·보고서 재생성, 추가 전용 실행 영수증, 정확한 링크·frontmatter 보수처럼 의미·신뢰·권한을 바꾸지 않는 저위험 변경뿐이다.
4. 기존 raw를 수정·이동·삭제하지 않고 새 raw가 있으면 입수·보안 게이트가 연결된다.
5. 기존 claim/source의 statement, scope, evidence 의미, C/S-level, independence group 또는 lifecycle을 바꾸지 않는다.
6. 비밀, 심볼릭 링크, 실행 바이너리, 과대 파일, 알 수 없는 경로와 Git 사건 원장 재작성이 없다.
7. 로컬 전체 품질 게이트와 정확한 원격 필수 check `전체 저장소 품질 게이트`가 모두 성공하고 PR head SHA·기준 SHA·tree SHA가 영수증과 일치한다. 이름이 다른 성공 check는 이를 대신하지 않는다.
8. 미해결 리뷰, 충돌, 기준 브랜치 drift, 다른 실행 소유 브랜치와 fork가 없다.

하나라도 증명하지 못하면 자동 병합 후보가 아니다.

### 사람 검토 필요

다음 항목 중 하나라도 바뀌면 PR까지만 만들고 병합 호출을 하지 않는다.

- `.github/**`, `AGENTS.md`, `governance/**`, `config/**`, `tools/**`, `scripts/**`, `prompts/**`, `skills/**`, `tests/**`, `wiki/specs/**`
- 헌장·신뢰 정책·schema·스케줄·권한·자격증명·외부 공개 경로
- 기존 claim/source의 의미·근거·신뢰·독립성·생명주기
- raw 삭제·덮어쓰기·이동, 광범위한 파일 이동, 의미 충돌의 정규 반영
- 게이트 불완전, unknown diff, rebase 또는 충돌 해결 필요

승인된 RFC 구현도 실제 diff를 사람이 볼 필요가 있는 제어면 변경이면 이 경로를 사용한다. 사용자 지시는 구현 권한일 수 있지만 아직 보지 않은 최종 diff의 독립 GitHub 리뷰를 자동으로 대체하지 않는다.

### 즉시 차단

`auth/**` 또는 token·private key가 diff에 포함됨, 기존 raw 덮어쓰기, `state/events.jsonl` 재작성, 대상 저장소 불일치, 금지 action, 토큰 파일 안전 계약 실패, merge conflict, 인증·권한 실패는 fail closed한다. 차단 상태를 자동 병합이나 성공으로 낮춰 기록하지 않는다.

## 토큰과 외부 권한 경계

초기 운영 자격증명은 사용자가 제공한 `auth/github_token.yaml`의 classic PAT다. 파일은 regular file이고 소유자 전용 `0600`이며 Git에서 ignore되고 미추적이어야 한다. YAML은 top-level `key` 하나의 non-empty string만 허용하고, 다른 형태, symlink, group/world-readable 파일은 거부한다.

토큰은 대상 저장소와 승인 근거를 먼저 검증한 뒤 child process의 `GH_TOKEN` 환경에만 넣는다. URL, argv, remote, Git config, receipt, cache, artifact, 로그, PR 본문과 오류에 값을 쓰지 않는다. `gh auth login`, persistent credential store와 Actions secret 복사는 이 구현의 기본 동작이 아니다. 오류 문자열과 subprocess 출력은 token pattern을 마스킹한다.

commit 전에 안전하게 읽은 실제 토큰 값과 바이트 단위로 정확히 일치하는 문자열이 base 대비 후보 파일, staged patch와 staged blob에 있는지 검사한다. 한 번이라도 발견하면 값을 출력·해시·부분 인용하지 않고 commit 전에 차단한다. 일반 secret pattern 검사는 이 exact token scan을 대체하지 않는다.

Git과 `gh`를 호출하는 자식 프로세스는 process-only 설정으로 먼저 상속된 credential helper 목록을 빈 `credential.helper` 값으로 초기화한 뒤, 대상 GitHub URL에만 `!gh auth git-credential` helper를 추가한다. 같은 자식 환경에 `GIT_TERMINAL_PROMPT=0`, `GH_PROMPT_DISABLED=1`을 적용해 대화형 자격증명 입력을 금지하고, 호출이 끝나면 `GH_TOKEN`과 임시 Git 설정을 폐기한다. 전역·로컬 Git config와 credential store는 수정하지 않는다.

classic PAT는 사람과 Agent를 GitHub에서 같은 `winehouse8` 계정으로 보이게 하며 권한도 넓다. 따라서 사람 검토 PR은 같은 계정에 형식적 self-review를 요청하지 못할 수 있다. 첫 버전은 draft·라벨·명시적 본문과 adapter의 merge 금지로 보수적으로 차단한다. 짧은 수명의 저장소 한정 GitHub App 또는 전용 machine user로 행위자를 분리하는 것은 후속 RFC다.

## 실행·영수증·멱등성

1. `begin`은 clean worktree, 원격 identity, 최신 기준 SHA를 확인하고 `wiki-auto/<run-id>` 브랜치와 Git 내부 실행 영수증을 만든다.
2. 관리인은 해당 실행 브랜치에서만 작업하고 전체 로컬 게이트를 수행한다.
3. `publish`는 게이트 완료 후 base SHA 대비 실측 manifest를 만들고 시작 영수증 이후의 허용된 변경만 stage한다. 시작 시 다른 변경이 있었거나 manifest 밖 변경이 생기면 중단한다. `git add -A`로 범위를 추측하지 않는다.
4. commit trailer와 PR 본문에는 run ID, actor, 호출 방식·작업 종류·Wiki 의존도, base/head/tree SHA, 파일 manifest, RFC·승인 근거, 게이트 digest, 위험 판정과 이유, C/S/lifecycle 영향, 미해결 항목과 롤백을 기록한다.
5. PR 번호·URL·head SHA·라벨·draft 여부·auto-merge 요청·merge method·merge SHA·시각을 비밀 없는 delivery receipt로 보존한다.

publish 내부의 prospective 품질 검증은 대상 작업 사본을 바꾸지 않아야 한다. `lint`와 통합 `release-check`는 check-only 모드에서 보고서·archive·event·파생 Wiki를 원본 작업 사본에 쓰지 않고 동일한 판정을 수행한다. 각 검증 단계 뒤의 실측 manifest가 gate 시작 전 manifest와 다르면 새 파일을 자동 수용하지 않고 stage 전에 차단한다. 날짜가 바뀌거나 사건 수가 달라져도 검증기 보고서의 자기 갱신이 저위험 변경을 사람 검토로 강등하거나 임의 파일을 commit하게 해서는 안 된다.

사람 검토 PR이 외부에서 병합된 뒤 재조정할 때는 실제 merge SHA와 원격 상태를 기록하되 자동화가 auto-merge를 요청했다고 소급해 기록하지 않는다. 원격 `autoMergeRequest`나 기존 자동 요청 영수증이 없는 사람 검토 경로는 `merge_requested=false`를 보존한다. 반대로 같은 멱등성 키와 PR의 이전 safe 영수증이 auto-merge 요청을 증명하면 GitHub가 병합 뒤 활성 요청 필드를 비워도 `merge_requested=true`를 보존한다. classic PAT가 사람과 Agent 행위자를 구분하지 못하므로 병합 주체를 근거 없이 특정하지 않는다.

멱등성 키는 `policy version + run ID + base SHA + tree SHA`다. timeout 뒤 생성·병합을 맹목적으로 재호출하지 않고 remote branch, PR marker와 merge 상태를 조회해 기존 작업을 재사용한다. 같은 키는 브랜치·PR·auto-merge 요청을 각각 최대 한 번만 만든다.

GitHub의 auto-merge 요청 성공은 병합 완료가 아니다. 요청 직후 PR을 재조회해 `merged=true`와 merge SHA가 확인된 경우에만 완료로 기록한다. 아직 병합되지 않았으면 `자동 병합 대기` 영수증을 남기고, 후속 실행이 같은 멱등성 키와 원격 PR을 재조정한다. 이미 auto-merge가 활성화됐거나 요청 영수증이 있으면 요청을 다시 보내지 않으며, 재조정은 최종 merge SHA·차단 사유·계속 대기 중 하나로만 상태를 진전시킨다.

로컬 잠금과 GitHub의 head SHA 비교를 함께 사용한다. merge 직전에 기준과 head를 다시 확인하고 drift가 있으면 자동 병합을 멈춘다. 다른 실행의 브랜치를 force push하지 않으며 admin bypass, force merge와 기준 브랜치 직접 push를 사용하지 않는다.

## GitHub-native 보호

- PR CI는 `pull_request`에서 비밀 없이 `contents: read`만 사용해 전체 품질 게이트와 delivery 정책 검사를 수행한다. GitHub의 새 개인 저장소는 기본 `GITHUB_TOKEN`이 read 중심이고 workflow의 PR 생성·승인도 기본 비활성일 수 있으므로 workflow와 저장소 권한을 별도로 좁게 고정한다.[2]
- privileged `pull_request_target`에서 PR head를 checkout하거나 실행하지 않는다.
- 외부 action은 불변 commit SHA에 고정한다. GitHub는 privileged trigger가 신뢰하지 않은 PR 코드를 checkout하면 저장소 탈취로 이어질 수 있고, action을 full commit SHA에 고정하는 것이 불변 릴리스 사용 방법이라고 안내한다.[3]
- `main`은 PR 필수, 정확한 필수 check `전체 저장소 품질 게이트` 성공, 대화 해결, force push·삭제 금지로 보호한다.
- 안전 PR만 auto-merge를 활성화한다. 사람 검토 PR은 draft를 유지하고 자동화가 approve·ready·merge하지 않는다.
- `.github/**`와 다른 제어면은 `CODEOWNERS`와 위험 분류가 사람 검토로 보낸다.

## 공개 clean clone과 격리 원문

`raw/quarantine/`의 원문 payload는 로컬 보안 격리 영역이며 public Git 저장소에 게시하지 않는다. delivery adapter는 이 경로의 추가·수정·이동·삭제를 사람 검토 PR로도 낮추지 않고 stage·commit·push 전에 차단한다. `.gitignore`는 편의 설정일 뿐 이 보안 경계를 대신하지 않는다.

기본 검증 프로필은 `strict-local-custody`다. 이 프로필에서는 격리 원문 누락이 항상 오류이므로 수집·보관 작업 사본에서 실수로 payload를 잃은 상태가 통과할 수 없다. exact-repository delivery linked worktree와 GitHub의 비밀 없는 PR workflow만 `public-clean-clone` 프로필을 명시할 수 있다. 이 프로필에서도 누락을 일반적으로 허용하지 않고 다음 조건을 모두 만족한 보안 admission에만 메타데이터 검증으로 대체한다.

1. `config/wiki.json`의 배포 정책이 exact repository `winehouse8/auto_wiki`, 로컬 전용 모드, `raw/quarantine` 경로와 `anchored-content-addressed-admission-only` 누락 정책에 정확히 일치한다.
2. artifact 경로가 `raw/quarantine/<sha256>/artifact[.<확장자>]` 형식이며 경로 digest와 기록된 SHA-256이 일치한다.
3. 크기와 미디어 유형이 기록되고 보안 manifest의 digest·크기·미디어 유형·출처 참조와 일치하며, `payload_executed=false`, `credentials_accessed=false`, `network_used=false`, `allow_means_data_use_only=true`, write-stage 판정 일치와 `quarantine_only_no_source_promotion` 효과가 보존된다.
4. admission ID와 record digest가 현재 정규 레코드에서 다시 계산한 값과 일치하고, 추가 전용 사건 원장의 `security.candidate.screen` 사건이 같은 actor·digest·artifact SHA·판정·no-execution 값으로 anchor한다.

원문이 로컬에 있으면 두 프로필 모두 실제 파일의 SHA-256을 다시 계산한다. 위 조건 중 하나라도 증명하지 못한 누락은 오류다. `public-clean-clone` 결과는 `quarantine_payload_verified=false`와 누락 수를 명시하며, 메타데이터 대체는 부재한 bytes를 검증했다는 뜻이 아니다. source admission, C/S-level, evidence, lifecycle을 만들거나 바꾸지 않으며 public 저장소에 원문을 복사할 권한도 부여하지 않는다.

## 빈 저장소 부트스트랩 예외

PR은 존재하는 기준 ref가 필요하다. 현재 빈 `winehouse8/auto_wiki`에는 ref가 없으므로 기존의 깨끗한 로컬 기준 커밋 `5f1d7f0`과 그 이전 이력만 `main`에 한 번 직접 게시할 수 있다. 현재 dirty 변경이나 새 자동 작업을 이 seed에 섞지 않는다.

이 예외는 bootstrap receipt와 첫 PR 본문에 기록한다. 실제 seed `5f1d7f0b26a601f4e60a64713c30da8d7f10d1ff`와 소진된 예외는 [GitHub Issue #1](https://github.com/winehouse8/auto_wiki/issues/1)에 기록했다. 기준 ref가 생긴 뒤에는 예외가 소진되며 이후 `main` 직접 push는 정책 위반이다.

첫 GitHub 통합 [PR #2](https://github.com/winehouse8/auto_wiki/pull/2)는 `origin/main`의 고정 SHA와 clean 작업 사본에서 사람 검토로 병합했고, 보호 규칙에 정확한 필수 check `전체 저장소 품질 게이트`를 적용했다. 현재는 그 뒤 발견한 v1.2 제어면 결함의 후속 사람 검토 PR과 운영 정책 버전 전환을 같은 clean `begin` 계약으로 전달하는 단계다. 두 변경을 병합한 뒤 무해한 canary PR에서 check와 자동 병합 경로를 전진 검증한다. 시작 영수증 이전의 dirty 파일을 manifest로 추측해 가져오면 언제나 차단한다.

## 수용 기준

- `AC-GH-001`: 실제 자동 변경은 모두 고유 브랜치와 PR을 거치며 소진된 bootstrap 외 `main` 직접 push가 없다.
- `AC-GH-002`: 무변경 실행은 commit·PR을 만들지 않고 `중요한 변경 없음`을 반환한다.
- `AC-GH-003`: exact repository·base·approval allowlist 불일치는 token read 전에 차단된다.
- `AC-GH-004`: token 파일은 regular·`0600`·ignored·untracked여야 하며 secret은 모든 diff·argv·remote·로그·receipt·PR 본문에 0회다.
- `AC-GH-005`: clean 전용 worktree와 시작 receipt 이후의 명시적 manifest만 stage하며 관련 없는 변경은 보존하고 차단한다.
- `AC-GH-006`: 위험 판정이 하나라도 unknown이거나 사람 검토 경로·작업을 포함하면 전체 PR이 `사람 검토 필요`가 된다.
- `AC-GH-007`: safe fixture만 ready PR과 auto-merge 요청을 만들고 모든 로컬·원격 check 및 SHA 비교 전 merge하지 않는다.
- `AC-GH-008`: 사람 검토 fixture는 draft·라벨·한국어 검토 메시지를 만들고 merge·approve·ready 호출은 0회다.
- `AC-GH-009`: 비밀 staged, raw overwrite, event rewrite와 repo mismatch fixture는 PR 또는 merge 성공으로 가장하지 않는다.
- `AC-GH-010`: 같은 멱등성 키의 재시도와 동시 실행은 branch·PR·merge를 중복 생성하지 않는다.
- `AC-GH-011`: base drift, head drift, merge conflict, 실패·누락 check와 미해결 review는 merge 호출을 0회로 만든다.
- `AC-GH-012`: 401·403은 즉시 비밀 없는 차단으로 끝나고 조회·5xx·rate limit만 제한적으로 재시도한다.
- `AC-GH-013`: merge 성공은 PR 상태와 merge SHA를 재조회한 뒤에만 완료되며 후속 comment 실패는 재조정 가능한 상태로 남는다.
- `AC-GH-014`: unit·릴리스 fixture는 fake transport만 사용하고 live network·credential read를 성공 근거로 세지 않는다.
- `AC-GH-015`: PR 본문·라벨·comment template은 한국어 문서 정책을 따르고 실행·검증·위험·롤백 정보를 포함한다.
- `AC-GH-016`: Actions workflow는 최소 read permission, pinned action, secret-free PR 검증을 사용하고 `pull_request_target`과 자동 merge write를 포함하지 않는다.
- `AC-GH-017`: 최초 seed만 일회성 예외이고 첫 통합 PR은 사람 검토, 병합 후 canary가 원격 check→자동 병합을 검증한다.
- `AC-GH-018`: classic PAT의 행위자 혼합·과권한 한계와 GitHub App 전환 조건을 사용자에게 숨기지 않는다.
- `AC-GH-019`: 전체 게이트 뒤 base SHA 대비 실측 manifest가 caller boolean과 사전 manifest보다 권위 있으며, 불일치는 위험을 낮추지 않는다.
- `AC-GH-020`: 금지 diff는 stage·commit 전에 차단되고, 실제 token의 exact scan은 후보 파일과 staged 내용에서 commit 전에 0회를 증명한다.
- `AC-GH-021`: branch protection과 자동 병합 판정은 정확한 필수 check 이름 `전체 저장소 품질 게이트`만 인정한다.
- `AC-GH-022`: auto-merge 요청 뒤 merge SHA가 없으면 `자동 병합 대기`로 남고, 재조정은 같은 멱등성 키의 auto-merge 요청을 중복 호출하지 않으며 같은 PR의 기존 요청 영수증을 비동기 병합 완료 뒤에도 보존한다.
- `AC-GH-023`: `차단`으로 끝난 CLI는 비밀 없는 영수증을 남기고 nonzero 종료 코드로 실패를 호출자에게 전달한다.
- `AC-GH-024`: GitHub 자식 프로세스는 상속 helper를 process 범위에서 초기화하고 대상 helper만 사용하며 대화형 prompt와 영속 credential 변경이 0회다.
- `AC-GH-025`: 첫 통합 PR은 `origin/main` 기준의 clean linked worktree에서 `begin` 영수증을 만든 뒤에만 patch를 적용한다.
- `AC-GH-026`: 기본 `strict-local-custody`는 누락 격리 원문을 실패시키고, 명시적 `public-clean-clone`만 exact 정책·content-addressed artifact와 보안 manifest·전체 무부작용 불변조건·정규 ID/digest·상세 event anchor를 모두 만족한 누락을 경고로 검증하며 `quarantine_payload_verified=false`를 보고한다.
- `AC-GH-027`: delivery adapter는 `raw/quarantine/**`의 모든 추적 변경을 stage·commit·token read·push·PR 전에 차단하며 사람 검토 경로로 공개하지 않는다.
- `AC-GH-028`: publish와 PR Actions의 prospective `lint`·`release-check`는 check-only로 원본 작업 사본의 보고서·archive·event·파생 Wiki를 바꾸지 않고 같은 실패 판정을 반환한다.
- `AC-GH-029`: 날짜·event 수·release fingerprint가 달라진 safe fixture도 전체 gate 전후 manifest가 같고, gate 자기 산출물이 safe canary diff에 추가되지 않는다.
- `AC-GH-030`: 이미 병합된 사람 검토 PR을 재조정하면 실제 merge SHA를 기록하되 `merge_requested=false`를 유지하고 자동 병합 요청을 소급 주장하지 않는다.

## 실패와 롤백

전달 실패는 Wiki 내용 검증의 성공과 GitHub 게시 성공을 구분해 보고한다. 인증 실패나 GitHub 장애 때문에 PR을 만들지 못했으면 로컬 변경을 삭제하지 않고 비밀 없는 차단 영수증과 복구 명령을 남긴다.

CLI가 `차단`을 반환하면 구조화된 비밀 없는 차단 영수증을 출력하더라도 종료 코드는 반드시 nonzero다. `자동 병합 대기`는 비동기 전달이 접수된 상태이므로 차단이나 병합 완료로 가장하지 않고 별도 상태로 반환한다.

롤백은 GitHub 전달을 비활성화하고 Codex 예약 작업을 중지한 뒤, 열린 자동 PR은 삭제하지 않고 close하며 token을 revoke·rotate한다. adapter·workflow·config를 제거하는 변경도 새 사람 검토 PR로 수행한다. 이미 병합된 commit, PR, comment와 receipt는 감사 이력으로 보존하고 내용 되돌림은 새 revert PR로 수행한다.

`production_certified=false`는 유지한다. 로컬 fake transport, 첫 실제 저장소와 canary 성공은 장기 장애·권한 오용·의미 공격 또는 GitHub App 수준 행위자 분리를 인증하지 않는다.

# 인용

[1] [Automatically merging a pull request — GitHub Docs](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/incorporating-changes-from-a-pull-request/automatically-merging-a-pull-request)
[2] [Managing GitHub Actions settings for a repository — GitHub Docs](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/enabling-features-for-your-repository/managing-github-actions-settings-for-a-repository)
[3] [Secure use reference — GitHub Docs](https://docs.github.com/en/actions/reference/security/secure-use)
[4] [Triggering a workflow — GitHub Docs](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow)
[5] [About protected branches — GitHub Docs](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches)
