---
type: Evaluation
title: RFC-6BD49C04ED49 실제 Wiki 전진 검증
description: 실제 Wiki에서 고정 시각 후보 계획의 예산·정밀도·검토 전용 의미 분류를 확인한 기록.
tags: [evaluation, forward-test, hygiene, conflict-review]
timestamp: '2026-07-12T23:20:00+09:00'
---

# RFC-6BD49C04ED49 실제 Wiki 전진 검증

## 실행 조건

- 시각: `2026-07-12T22:30:00+09:00`
- 최근 문서: 20
- 검토 기한 초과 주장: 20
- 최대 hop: 2
- 최대 노드: 120
- 최대 충돌 쌍: 40
- 의미 검토: 10

## 계획 결과

- 시드: 22
- 선택 노드: 120
- 충돌 후보: 1
- 반환된 약한 관계 후보: 40, 상한 밖 생략 154
- 의미 검토 큐: 10
- 읽기 전용·충돌 검토 전용·trust/evidence/lifecycle 자동 변경 없음 불변조건: 모두 참
- node 상한에 도달했지만 생략된 seed는 0이다.

## 점진적 의미 검토

1. `CLM-6DDD53332A40` ↔ `CLM-F6367BFF8F35`: **범위 차이**. 같은 `SRC-CFB88DDE3FF1`이 첫 주장에는 “raw source of truth” 표현의 반례이고 둘째 주장에는 지속 합성 Wiki 설계의 지지 근거다. 두 주장 자체는 각각 원문 snapshot의 진실성 한계와 합성 Wiki의 검색 보완 역할을 말하므로 직접 논리 모순은 아니다. 기존 기등록 반증은 보존하고 새 evidence·신뢰 변경은 만들지 않았다.
2. `CLM-6DDD53332A40` 기등록 반증 위험: **근거 필요 상태 유지**. 현재 C2 contested 투영과 정확한 locator가 이미 일치한다.
3. `wiki/sources/open-knowledge-format-v0.1.md` 의존성 지연: **거짓 양성에 가까운 노후 후보**. source assessment가 문서 의미 시각보다 약 3분 늦지만 문서는 이미 동일한 S3 판단과 version pin을 설명한다. ingest 순서 차이만으로 timestamp나 내용을 자동 수정하지 않았다.
4. 최근 문서 7개: **검토 표본**. 최근 의미 변경이라는 선택 이유 외 구조·논리 결함 신호는 없었다.

## 결론

전체 문서를 모델에 넣지 않고도 전수 구조 검사 뒤 상위 10개만 읽었다. heuristic 충돌 거짓 양성은 제거됐고, 남은 명시 후보도 사람·Agent가 범위 차이로 설명할 수 있었다. 이 전진 검증은 자동 trust 변경이나 실제 의미 정확성 인증이 아니다.
