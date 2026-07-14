---
type: Evaluation
title: RFC-CB109FAC0820 일일 연구 포트폴리오 Red 근거
description: 지역 날짜별 단일 실행, 두 연구 트랙 공정 선택과 관심사 brief 전달을 구현 전에 고정한 실패 기록.
tags: [evaluation, red, scheduler, research, fairness, tdd]
timestamp: '2026-07-15T01:20:00+09:00'
---

# RFC-CB109FAC0820 일일 연구 포트폴리오 Red 근거

## 고정한 실패

기존 `interest-seed`는 UTC로 정규화한 시각의 rolling 24시간과 정적 `priority → ID` 순서를 사용한다. 따라서 같은 KST 날짜의 두 호출이 서로 다른 관심사를 각각 만들 수 있고, 매일 도래한 동률 관심사 중 ID가 뒤인 트랙은 영구히 선택되지 않는다. 차단된 캠페인도 성공 cadence와 질문 완료 횟수를 소진하며 선택된 캠페인에는 관심사의 `research_brief`가 전달되지 않는다.

## Red 실행

```bash
python3 -m unittest -v \
  tests.test_wiki.IntegratedGateTests.test_interest_seed_enforces_one_global_slot_per_local_day \
  tests.test_wiki.IntegratedGateTests.test_two_daily_interests_rotate_and_failed_question_is_retried \
  tests.test_wiki.IntegratedGateTests.test_interest_seed_copies_research_brief_into_campaign
```

결과: **3개 중 실패 2개, 오류 1개**.

- 같은 `Asia/Seoul` 날짜에 캠페인이 2개 생성됐다.
- 차단된 `INT-A` 뒤에도 `INT-B`와 교대하지 못했고 실패 질문을 완료된 질문처럼 회전했다.
- 생성 캠페인에 `research_brief`가 없어 `KeyError`가 발생했다.

테스트는 네트워크, 실제 예약 작업, 자격증명과 비용을 사용하지 않았다. 이 실패를 약화하지 않고 지역 날짜 전역 상한, 성공·배정 시계 분리, 결정론적 공정 선택과 brief 불변 복사로 Green을 만든다.
