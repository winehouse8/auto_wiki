---
type: Evaluation
title: RFC-03F4FE85BB44 GitHub PR 전달 Red 근거
description: GitHub PR 감사·위험 분류·token 안전·workflow 계약을 구현 전에 고정한 실패 기록.
tags: [evaluation, red, github, pull-request, security, tdd]
timestamp: '2026-07-13T00:57:56+09:00'
---

# RFC-03F4FE85BB44 GitHub PR 전달 Red 근거

## 고정한 문제

현재 하네스에는 `tools.github_delivery`, exact-repo 설정, PR 품질 workflow, CODEOWNERS와 관리인 Skill의 GitHub 전달 절차가 없다. 따라서 자동 Wiki 변경을 PR로 감사하고 위험에 따라 자동 병합 또는 사람 검토로 보낸다는 `SPEC-GH-DELIVERY-001`을 재현할 수 없다.

## 실행

```bash
python3 -m unittest tests.test_github_delivery tests.test_github_delivery_contract -v
```

결과: **28개 테스트, 38개 의도된 실패**.

- 순수 코어 17개 테스트는 `tools.github_delivery` 부재로 실패했다.
- 저장소 계약 11개 테스트에서 좁은 명세 2개는 통과했고, config·workflow·CODEOWNERS·Skill·예약 프롬프트 부재가 subtest를 포함해 실패했다.
- fake transport와 임시 fake token만 사용했다. 실제 GitHub network call과 실제 token read는 0회다.

## Red가 고정한 경계

- 대상 repository·base·approval 불일치는 token loader 호출 전에 차단한다.
- token은 regular file·`0600`·ignored·untracked·단일 `key` string이어야 하고 모든 출력에서 마스킹한다.
- `no_op|auto_merge|human_review|required_block` 네 경로를 fail closed로 분류한다.
- `auth/**`, raw overwrite, event rewrite는 즉시 차단한다.
- protected·unknown path는 자동 병합으로 낮추지 않는다.
- 사람 검토, 실패·누락 check, base/head drift는 merge transport 호출을 0회로 만든다.
- 같은 멱등성 키는 branch·PR·merge를 중복 생성하지 않는다.
- 병합은 PR 재조회에서 merge SHA가 확인된 뒤에만 완료다.
- PR 본문은 한국어로 실행·SHA·manifest·검증·위험·C/S/lifecycle·롤백을 포함한다.
- PR workflow는 `pull_request`, 최소 read permission, full commit SHA action, 비밀·`pull_request_target`·write merge 부재와 전체 품질 게이트를 고정한다.

이 실패를 약화하거나 삭제하지 않고 승인된 RFC의 최소 구현으로 Green을 만든다.

## 실행 계층 추가 Red

순수 코어 Green 뒤 Skill에 명시한 실제 `begin`·`publish` 경로가 구현되지 않은 공백을 별도 fixture로 고정했다.

```bash
python3 -m unittest tests.test_github_delivery_cli -v
```

결과: **10개 테스트, 12개 의도된 fixture 실패**.

- 누락 API: `main`, `begin_run`, `publish_run`, `quality_gate_commands`, `GitHubCliTransport`
- `begin`: exact origin/main, clean worktree, 최신 base, token read 0, 실행 브랜치와 `.git` 내부 receipt
- `publish`: begin receipt·branch·manifest 일치, 고정 gate 순서, 명시 경로 stage, commit trailer, branch push와 core delivery 연결
- 무변경·게이트 실패 경로: token·stage·commit·push·PR 호출 0회
- live adapter: 실제 token 값은 argv·remote·출력에 없이 child `GH_TOKEN` 환경에만 존재

fake git/gh runner만 사용했으며 실제 network와 실제 token read는 0회다. 기존 순수 코어 17개 Green은 그대로 통과했다.

### 운영 보안 Refactor Red

CLI Green 뒤 실제 운영 흐름을 검토해 다음 두 실패를 추가로 고정했다.

- 안전 PR의 원격 check 완료를 기다리는 `--watch --fail-fast`가 없음
- clean clone의 `git push`가 persistent 설정 없이 `gh auth git-credential`을 쓰는 process-only 환경 계약이 없음
- 같은 계정 PAT 한계에서 사람 검토 PR의 `@winehouse8` 본문 요청과 assignee가 없음

추가 assertion을 넣은 첫 실행은 27개 중 2개 테스트가 실패했고, 최소 보수 뒤 27개 모두 다시 통과했다.

## v1.1 실측 전달 보안 Red

첫 Green 뒤 별도 읽기 전용 사전 PR 감사에서 자기신고 manifest와 실제 Git diff의 경계가 충분히 고정되지 않았음을 확인했다. 특히 금지 변경도 `deliver` 분류 전에 로컬 commit이 될 수 있고, 성공한 임의 check가 필수 check를 대신하며, 비동기 auto-merge가 활성화된 열린 PR을 `blocked/merge_requested=false`로 잘못 기록하고, 차단 영수증이 CLI 종료 코드 0으로 보이는 실패가 있었다.

```bash
python3 -m unittest tests.test_github_delivery tests.test_github_delivery_cli -v
```

초기 보강 fixture 결과: **34개 테스트, 16개 의도된 실패, 오류 0개**.

- base 대비 실측 manifest가 caller의 `secret_detected`, `binary`, `symlink`, `oversized`, `append_only_verified`, `generated`, `semantic_change` 선언보다 권위 있어야 한다.
- 금지 diff와 실제 classic token exact match는 stage·commit·push·transport 호출 전에 멈춰야 한다.
- 정확한 `전체 저장소 품질 게이트` 이름이 없으면 auto-merge 호출은 0회여야 한다.
- 열린 armed auto-merge는 `자동 병합 대기`이며, 재시도에서 요청을 중복하지 않아야 한다.
- blocked CLI는 구조화된 영수증을 출력해도 nonzero로 끝나야 한다.
- 상속 credential helper 초기화, 비대화형 Git 인증, linked worktree begin 영수증과 process-only helper를 고정했다.

후속 Red는 정책 버전·승인 RFC pin, 실제 Git 저장소에서 prefix 없는 token의 commit 전 차단, 사건 원장 비-prefix 재작성, commit 뒤 소유권 기반 재개와 gate 지문, 미해결 review thread 전수 확인, 조회 전용 5xx 제한 재시도·403 무재시도, 제어문자 경로와 PR gate 지문 누락을 각각 재현했다. 이 fixture들은 실제 network와 실제 token을 사용하지 않았다.

첫 clean linked worktree publish 전진 시험에서는 한글 제안 문서 rename 두 건을 구형 줄 단위 porcelain 파서가 단일 경로로 축약해 `Git status 변경 경로가 잘못되었거나 중복됨`으로 차단하는 실전 Red가 추가로 관찰됐다. 이 시도는 gate·commit·token·remote 호출 전에 종료됐다. 초입·게이트 후·stage 후 범위 비교를 `--name-status -z --no-renames` 관찰기로 통일하고 실제 한글 rename을 delete+add로 보존하는 임시 Git 저장소 회귀 fixture를 추가했다.

## public clean clone 격리 원문 Red

한글 경로 보수 뒤 같은 clean linked worktree에서 publish를 다시 전진 시험했다. public Git에서 의도적으로 제외한 `raw/quarantine` payload는 0개였고 canonical security admission은 54개였다. 기존 `lint`의 실제 결과는 `quarantine artifact missing` 오류 54개였으며 품질 게이트에서 중단했다. 실제 token read·stage·commit·push·PR 호출은 0회였다.

처음 제안한 metadata-only Green을 다시 적대적으로 검토하자 두 실패가 더 드러났다.

- public 설정만으로 모든 작업 사본의 누락을 경고로 낮추면 로컬 보관 사본에서 payload를 실수로 잃어도 통과한다.
- 새 `raw/quarantine/**`를 일반 새 raw처럼 사람 검토로 보내면 draft PR 브랜치 push만으로 격리 payload가 public Git에 공개된다.

따라서 기본 strict와 명시적 public profile 분리, canonical admission·보안 manifest·전체 무부작용 불변조건·상세 사건 anchor, 그리고 quarantine 추적 변경 전면 차단을 추가 Red로 고정했다. 강화 전 대상 실행은 helper/anchor API 부재 2건, 새 quarantine 분류 1건, workflow profile 부재 1건으로 실패했고 기존 구현이 포괄 허용하던 잘못된 exact-policy·record-digest·write-gate 사례 3건도 별도 실패로 재현했다.

public profile Green 뒤 publish 재시도에서는 내부 `render`·`lint`·`release-check`가 새 사건을 추가해 structural event count와 위생·rollback evidence를 바꿨다. 그 결과 content-addressed 릴리스 archive 경로가 context 생성 뒤 하나씩 늘어나 `명시적 manifest 밖 변경`으로 매번 token 전에 차단되는 순환 Red가 드러났다. 선언 범위를 지키면서도 게이트가 생성한 산출물을 최종 manifest에 포함해야 한다는 `AC-GH-019`에 따라, digest가 유효한 단일 `v4-release-<fingerprint>.json` 추가만 인정하고 임의 경로·잘못된 digest는 거부하는 회귀와 publish 내부 `--no-log` 명령 계약을 고정했다.
