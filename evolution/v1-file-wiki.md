# v1 — Persistent file wiki

## 채택한 가설

매 질문마다 raw chunk를 다시 조합하는 대신, 불변 원문 위에 Agent가 유지하는 Markdown synthesis를 두면 연구가 세션 사이에 누적된다.

## 구조

```text
raw/ → index → wiki/{sources,concepts,entities,comparisons}
                  ↘ overview / synthesis / open questions
```

## 근거

- Karpathy의 LLM Wiki idea file
- AI Engineer의 AI Research OS 발표와 공개 저장소

## 실험적 산출물

- 지정 Gist와 영상을 source page로 요약
- `index.md`, `overview.md`, `synthesis.md`, `open-questions.md`
- raw/index/wiki의 점진적 읽기 순서

## 자체 lint 결과

1. 사용자 제공 자료의 relevance 1.0은 “반드시 읽어라”이지 신뢰도 1.0이 아니다.
2. page 끝 출처 목록만으로는 문장별 evidence span을 찾기 어렵다.
3. 개인화된 원자료가 확증편향을 강화할 수 있다.
4. 사람과 Agent의 contribution/identity schema가 없다.
5. “살아 있음”은 요청 시 갱신일 뿐 주기적 연구나 품질 보장을 뜻하지 않는다.

## v2로 넘긴 요구사항

- atomic claim과 exact locator
- source assessment와 independence cluster
- actor-neutral attribution/review
- contradiction, stale, retracted 상태
- 결정론적 validator와 tamper-evident event log

