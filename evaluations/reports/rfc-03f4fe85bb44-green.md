---
type: Evaluation
title: RFC-03F4FE85BB44 GitHub PR 전달 Green 근거
description: exact-repository PR 전달 코어·live CLI adapter·비밀 경계·위험 분류의 회귀 및 초기 원격 설정 결과.
tags: [evaluation, green, github, pull-request, security, tdd]
timestamp: '2026-07-13T00:57:56+09:00'
---

# RFC-03F4FE85BB44 GitHub PR 전달 Green 근거

## 구현

- `tools/github_delivery.py`: exact target 선검증, strict token loader, redaction, fail-closed 변경 분류, 한국어 PR 본문, SHA 기반 멱등성, fake/live transport, `begin`·`publish` CLI
- `config/github-delivery.json`: `winehouse8/auto_wiki`, `main`, `wiki-auto/`, `squash`, 승인 refs, 보호 경로, 값 없는 token metadata와 소진된 bootstrap 영수증
- `.github/workflows/wiki-pr-quality.yml`: secret-free `pull_request`, `contents: read`, full SHA checkout, 전체 품질 게이트
- `.github/CODEOWNERS`: 제어면 `@winehouse8` 소유
- 관리인 Skill·예약 프롬프트: `begin → 작업 → 검증 → publish`, no-op·safe·human-review·blocked 결과 계약

## 회귀 검증

```bash
python3 -m unittest tests.test_github_delivery tests.test_github_delivery_cli -v
python3 -m unittest tests.test_github_delivery_contract tests.test_living_wiki_steward_skill -v
python3 -m py_compile tools/github_delivery.py
git diff --check
```

결과:

- core·CLI: **27/27 통과**
- config·workflow·CODEOWNERS·UX 계약과 Skill: **26/26 통과**
- 실제 network와 실제 token을 사용한 unit test: 0
- token은 Git·argv·remote·본문·receipt에 없고 child `GH_TOKEN`과 비영속 Git config 환경에만 주입
- 사람 검토 경로의 merge·approve·ready 호출: 0
- 안전 경로는 local gate, 원격 check watch, base/head/tree SHA 재확인 뒤에만 squash auto-merge 요청

## 실제 초기 원격 설정

- 깨끗한 기존 SHA `5f1d7f0b26a601f4e60a64713c30da8d7f10d1ff`만 빈 원격 `main`에 일회성 seed했다.
- 제공 token exact-match, `auth/` 경로와 실제 credential 형태가 seed에 없음을 먼저 확인했다.
- 저장소는 squash만 허용하고 auto-merge·병합 뒤 branch 삭제를 활성화했다.
- `main`은 PR 필수, linear history, 대화 해결, force push·삭제 금지다.
- `자동화|자동-병합-후보|사람-검토-필요|전달-차단` 라벨을 만들었다.
- 소진된 예외는 [GitHub Issue #1](https://github.com/winehouse8/auto_wiki/issues/1)에 기록했다.

## 남은 운영 경계

현재 구현 diff는 도구·Skill·config·governance·workflow를 포함하므로 `사람 검토 필요`다. 첫 통합 draft PR은 Agent가 병합하지 않는다. 사람이 병합한 뒤에만 품질 check를 branch protection의 필수 check로 추가하고 별도 무해한 canary에서 실제 auto-merge를 전진 검증한다.

classic PAT는 `winehouse8` 인간과 Agent를 같은 GitHub actor로 보이게 하고 과권한이다. GitHub App 또는 machine user 전환과 장기 장애 시험 전에는 `production_certified=false`다.

## v1.1 감사 보강 Green

- 전체 게이트 뒤 base SHA 대비 NUL 구분 Git diff와 미추적 파일을 직접 관찰하고, lstat·크기·binary·symlink·비밀 패턴·event prefix·generator ownership을 재계산한다.
- caller 선언은 위험을 높일 수만 있고 실측 상태를 낮추지 못한다. 금지 위험은 stage 전에, 실제 token exact match는 commit 전에 차단한다.
- stage와 commit diff의 경로·상태를 base 및 권위 manifest와 다시 비교한다.
- exact 정책 버전·승인 방향·전달 RFC를 token 전에 pin하고, 공통 Git 잠금·linked worktree receipt·소유 commit 재개를 지원한다.
- 정확한 필수 check 이름과 미해결 review thread를 확인하며, 401·403은 즉시 차단하고 조회 전용 5xx·rate limit만 제한 재시도한다.
- auto-merge가 활성화됐지만 merge SHA가 없으면 `자동 병합 대기`로 남기고 같은 요청을 중복하지 않는다. 최종 재조회 실패는 요청 여부를 거짓으로 `false`라 기록하지 않는다.
- blocked receipt는 CLI 종료 코드 2이며, 자식 Git은 상속 helper를 비우고 비대화형 process-only GitHub helper만 사용한다.

이 보강도 `production_certified=false`를 바꾸지 않는다. 첫 통합 PR은 clean linked worktree의 `begin` 영수증으로 만들고 사람 검토 상태로 유지한다.

최종 보강 검증 결과는 core·CLI **45/45**, config·workflow·CODEOWNERS·UX·Skill **27/27**, 전체 저장소 회귀 **366/366** 통과다. 통합 릴리스 보고서는 8개 게이트 모두 성공했고 하네스 버전 `4.3.0`, `production_certified=false`를 기록했다.

첫 linked worktree 전진 시험에서 드러난 한글 rename 회귀까지 고친 뒤, publish의 모든 범위 비교는 줄 단위 porcelain이 아니라 NUL 구분 Git diff를 사용한다. rename은 자동 의미 추측 없이 삭제+추가 두 경로로 낮추며 같은 범위가 실제 임시 Git 저장소 fixture에서 재현됐다.

## public clean clone 격리 원문 Green

- 기본 `strict-local-custody`는 로컬 격리 원문 누락을 계속 오류로 처리한다.
- exact delivery linked worktree와 PR workflow만 `public-clean-clone`을 명시한다.
- 공개 프로필은 canonical admission ID·record digest, content-addressed artifact, 보안 manifest의 digest·크기·미디어 유형·출처 참조, 네 가지 무부작용 불변조건과 상세 사건 anchor가 모두 맞아야 누락을 경고로 낮춘다.
- 원문이 있으면 두 프로필 모두 실제 bytes hash를 확인하고 symbolic link는 거부한다.
- 결과는 누락 수와 `quarantine_payload_verified=false`를 표시해 metadata 정합성과 부재 bytes 검증을 구분한다.
- `raw/quarantine/**`의 모든 추적 변경은 추가도 사람 검토로 낮추지 않고 token·stage·commit·push·PR 전에 차단한다.

새 helper·anchor·분류·실제 임시 Git publish·quality command·workflow 대상 회귀 6개는 Green에서 모두 통과했다. source 보관 작업 사본의 strict 검증은 격리 원문 54/54의 실제 SHA-256을 확인했고 오류 0건, 기존 경고 45건으로 통과했다. clean linked worktree의 public 검증은 실제 payload 0개·누락 54개를 `quarantine_payload_verified=false`와 metadata-only 경고로 드러내면서 오류 0건, 전체 경고 99건으로 통과했다. 같은 linked worktree에서 strict 프로필은 누락 오류 54건으로 실패했다. 게이트 archive 순환 회귀를 포함한 전체 저장소 회귀는 **371/371** 통과했다. 이 보수는 public payload 공개나 신뢰·source promotion 권한을 추가하지 않으며 `production_certified=false`를 유지한다.

게이트 자기변경 순환은 publish 내부 `render`·`lint`·`release-check`에 `--no-log`를 적용해 begin 실행의 기존 사건을 중복 추가하지 않도록 보수했다. 그래도 실제 작업 때문에 최초 생성될 수 있는 새 archive는 exact 경로, 정규 component fingerprint, 8개 이상 전부 통과 gate, `production_certified=false`와 canonical report digest가 모두 맞을 때만 게이트 후 최종 manifest에 추가한다. 선언 경로 누락, 다른 새 경로, malformed·실패·digest 불일치 archive는 token·stage 전에 계속 차단한다.
