---
type: Concept
title: 기억 위생과 통제된 학습
description: 자동 신뢰 승격 없이 실패 기반 선별·결과 피드백·시간적 생명주기·사용자 제어 의존도를 다루는 방식.
tags: [memory-hygiene, continual-learning, staleness, feedback, human-control]
timestamp: '2026-07-12T17:30:00+09:00'
claim_ids: [CLM-95A38CACF2CD, CLM-F79558D817DF, CLM-EC52C0576A28, CLM-207429D54323]
---

# 기억 위생과 통제된 학습

## 결론

살아 있는 Wiki가 오래 기억하는 것만으로는 충분하지 않다. 무엇을 다시 조사할지, 과거 지식이 아직 유효한지, 검색된 기억이 실제로 도움이 됐는지, 사용자가 이번 작업에서 과거 관점에 얼마나 의존하고 싶은지를 각각 분리해 다뤄야 한다.

관련 주장:

- [CLM-95A38CACF2CD](../claims/clm-95a38cacf2cd.md): 실패는 지식 공백 탐색의 우선순위 신호이지 사실성 증명이 아니다.
- [CLM-F79558D817DF](../claims/clm-f79558d817df.md): retrieval 결과와 시간 상태는 감사하되 trust 승격·삭제를 자동화하지 않는다.
- [CLM-EC52C0576A28](../claims/clm-ec52c0576a28.md): 사용자가 기억 의존도를 조절한다.
- [CLM-207429D54323](../claims/clm-207429d54323.md): append-only log와 외부 세계 상태를 구분한다.

## 조사에서 채택한 패턴

### 1. 실패 → 조사 수요 → 검증 → 승격

Demand-Driven Context는 실제 실패를 이용해 어떤 도메인 지식이 부족한지 좁힌다. 그러나 논문의 20–30회 수렴은 아직 가설이며, 저자 자신의 예제와 구현이므로 독립 효능 검증이 아니다. Living Wiki는 실패를 캠페인 우선순위에만 쓰고, 출처 수용·반증 검색·재실행·인간 또는 독립 검토를 통과하기 전에는 새 지식을 정규 주장으로 승격하지 않는다.[1][2]

### 2. 실패 로그 → 재실행 가능한 평가 → 최소 계층 수정

지속 학습 발표는 로그와 피드백만으로는 부족하고, 실패 당시 조건과 성공 판정을 재실행할 수 있어야 하며, 모델·하네스·기억 중 가장 작은 지속 가능한 계층을 고쳐야 한다고 주장한다. 이는 기존의 벤치마크 게이트 기반 자기진화를 강화하지만, RELAI의 성능 수치는 독립 벤치마크가 없으므로 채택하지 않는다.[3]

### 3. 오래됨과 후속 결과는 위생 신호

Lovable 사례는 모델·기능 변경 뒤 문맥이 빠르게 낡는다고 보고한다. ACL 2026 실험은 잘못되거나 정렬되지 않은 과거 경험이 미래 실행에 오류를 전파할 수 있고, 이후 작업 평가가 기억 품질 신호가 될 수 있음을 보였다. 따라서 Living Wiki는 오래됐거나 해롭거나 무관한 후보를 보고하되, 그 신호만으로 C-level/S-level을 바꾸거나 원문을 삭제하지 않는다.[4][5]

### 4. 기억 의존도는 사용자 제어

SteeM은 장기 개인화 대화에서 모든 기억을 따르는 방식과 전혀 쓰지 않는 방식 사이를 사용자 제어 축으로 실험했다. Living Wiki는 이를 그대로 일반화하지 않고 다음 UX 원칙만 채택한다.[6]

- `wiki-first`: 기존 Wiki claim에서 시작한다.
- `fresh-check`: index는 읽되 기존 synthesis 결론을 잠시 괄호 친 뒤 원자료로 독립 재조사하고 마지막에 비교한다.
- `strict-evidence`: exact locator가 있는 C2 이상 factual claim만 답변의 핵심 근거로 쓴다.

`fresh-check`는 기억 삭제나 부트스트랩 우회가 아니다.

### 5. 로그는 기록이지 세계 전체가 아니다

`The Log Is The Agent`는 추가 전용 로그에서 문맥·UI·압축을 재투영하는 장점을 설명하면서도, 파일 변경·이메일·외부 서비스 상태는 로그 밖에 있고 분기가 부수 효과를 되돌리지 못한다고 인정한다. 따라서 Living Wiki의 사건 체인은 감사 기록으로 유지하되 스냅샷 해시, 출처 산출물, 버전, 외부 작업 영수증과 롤백 근거를 별도로 보존한다.[7]

## 채택하지 않은 것

- 공급자 자체 `utility score`를 검색 순위나 신뢰에 자동 반영
- 오래됐거나 조회가 적다는 이유만으로 출처·원문 자동 삭제
- 모델 설명이나 사고 과정 전체를 결정 출처 이력으로 저장
- 현재 규모에서 벤치마크 없이 GraphRAG·벡터 DB를 기본 계층으로 도입
- 추가 전용 텍스트 로그 하나만으로 작업 공간과 외부 부수 효과가 복구된다고 가정
- 실패한 Agent의 자기진단을 독립 검토로 계산

## 하네스 적용

승인된 `RFC-5D91E03B5BC5`는 다음을 additive하게 도입한다.

1. 설정된 최신성을 실제 날짜에 대조하는 결정론적 기억 위생 보고서
2. 원문 질의를 저장하지 않는 행위자 귀속 검색 피드백 원장
3. 삭제 대신 `deprecated/superseded/invalidated/archived`를 기록하는 lifecycle transition
4. `wiki-first/fresh-check/strict-evidence` 사용자 모드
5. 실패 참조, 재실행, 최소 변경 계층을 요구하는 자기진화 절차

# 인용

[1] [Demand-Driven Context video](../sources/src-f55fed177366.md)
[2] [Demand-Driven Context preprint](../sources/src-54d07435eb56.md)
[3] [Continual Learning for AI Agents](../sources/src-ad0b1d50c531.md)
[4] [How Lovable self-improves every hour](../sources/src-03641bcfc467.md)
[5] [How Memory Management Impacts LLM Agents](../sources/src-af06bcdc1ed2.md)
[6] [Controllable Memory Usage](../sources/src-f9ba839fa59d.md)
[7] [The Log Is The Agent](../sources/src-2e2ea9c214c1.md)
