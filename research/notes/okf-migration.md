# OKF 마이그레이션 캠페인 — 2026-07-11

캠페인: `CMP-0619AC235CCA`

## 사용자 방향

Wiki 구축 시 Open Knowledge Format 패턴을 따를 것.

## 검토한 1차 출처

- Google Cloud 발표
- 공식 `GoogleCloudPlatform/knowledge-catalog/okf/SPEC.md`
- 공식 OKF README, 예시 번들, reference-agent 문서·색인 코드와 테스트
- 공식 `okf/` 디렉터리의 Apache-2.0 라이선스

## 재현성 고정값

- 저장소 HEAD: `d44368c15e38e7c92481c5992e4f9b5b421a801d`
- SPEC blob 식별자: `55d0a46cc988e99aa35cd027964d6278a4f93f35`
- 로컬 스냅샷 SHA-256: `b9655e607346dbbdc6de21190e9a953313eda6a7eba68d4d272a65975940ad6e`
- 명세 상태: `Version 0.1 — Draft`, 2026-07-11 기준 릴리스나 태그를 발견하지 못함

## 결정

`wiki/` 자체를 전용 OKF 번들 루트로 사용한다. 저장소 루트는 OKF 번들이 아니다. 정식 주장·출처·행위자 상태, 원문 자료, 거버넌스, 테스트, 실행 도구는 제어면으로서 외부에 둔다.

## 변경 사항

- 모든 비예약 번들 문서에 형식이 지정된 YAML 앞부분 메타데이터 추가
- Obsidian 위키 링크 대신 표준 Markdown 링크 사용
- 앞부분 메타데이터가 없는 예약 색인과 갱신 로그
- 생산자 확장을 설명하는 `okf-profile.md`
- `okf-validate`와 전역 검증 통합
- 앞부분 메타데이터 파싱 단위 테스트
- 하네스 부 버전 3.1.0

## 중요한 주의사항

- OKF에는 필수 manifest, JSON Schema, 형식 등록부가 없다.
- 핵심 v0.1은 비어 있지 않은 `type`만 요구하지만, 더 폭넓은 도구 호환성을 위해 권장 메타데이터도 출력한다.
- OKF는 신뢰성, 출처 이력 의미 체계, 행위자 거버넌스, 보안을 해결하지 않는다.
- 공식 reference-agent 구현은 개념 증명이며 일부는 최소 명세보다 엄격하다. 규범 형식은 아니다.
