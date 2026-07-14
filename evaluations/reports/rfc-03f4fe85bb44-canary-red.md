---
type: Evaluation
title: RFC-03F4FE85BB44 병합 후 canary Red 근거
description: prospective gate 자기 변경과 사람·자동 병합 영수증 오귀속을 실제 canary 전에 고정한 실패 기록.
tags: [evaluation, red, github, canary, delivery, tdd]
timestamp: '2026-07-15T01:20:00+09:00'
---

# RFC-03F4FE85BB44 병합 후 canary Red 근거

## 관찰한 실패

첫 사람 검토 PR 병합 뒤 `main`의 정확한 필수 check를 점검하는 과정에서 두 결함을 확인했다.

1. `lint --no-log`는 날짜가 든 `reports/latest-lint.md`를 계속 쓰고, `release-check --no-log`도 latest 보고서·content-addressed archive·파생 Wiki를 쓴다. publish의 prospective gate가 스스로 manifest를 바꾸므로 무해한 safe canary가 차단되거나 사람 검토로 강등될 수 있다.
2. 이미 사람이 병합한 review PR을 기존 상태기계가 재조정하면 원격 auto-merge 요청이 없었는데도 `merge_requested=true`로 기록한다.
3. 비동기 auto-merge가 완료된 뒤 GitHub가 활성 요청 필드를 비우면, 이전 로컬 영수증을 읽지 않는 재조정이 실제 요청 이력을 `merge_requested=false`로 덮는다.

## Red 실행

```bash
python3 -m unittest -v \
  tests.test_github_delivery.GitHubDeliveryContractTests.test_reconciled_human_review_merge_never_claims_auto_merge_request \
  tests.test_github_delivery_cli.GitHubDeliveryCliDispatchRedTests.test_quality_gates_have_exact_order_and_failure_blocks_before_token_or_stage \
  tests.test_github_delivery_contract.GitHubPullRequestQualityWorkflowContractTests.test_workflow_calls_the_complete_repository_quality_gate
```

사람 병합 fixture는 `merge_requested=true`로 실패했다. CLI와 workflow는 `lint`·`release-check`의 `--check-only`를 아직 호출하지 않아 계약과 달랐다. fake transport와 로컬 fixture만 사용했으며 실제 merge·PR 생성·token 출력은 없었다.

독립 최종 검토 뒤 대칭 회귀 `test_reconciled_safe_merge_preserves_prior_auto_merge_request_evidence`도 추가했다. 기존 API가 이전 영수증을 받을 수 없어 `unexpected keyword argument 'prior_receipt'`로 예상대로 실패했다.

Green은 prospective gate를 격리된 사본에서 실행해 원본 manifest를 바꾸지 않고, review 경로의 외부 병합에는 실제 merge SHA만 기록하면서 `merge_requested=false`를 보존해야 한다. safe 경로는 같은 멱등성 키·PR의 이전 영수증이 auto-merge 요청을 증명할 때 비동기 완료 뒤에도 `merge_requested=true`를 보존한다. 그 뒤에만 별도 harmless canary를 실행한다.
