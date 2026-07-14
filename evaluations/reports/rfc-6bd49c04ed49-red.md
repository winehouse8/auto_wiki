# RFC-6BD49C04ED49 Red 증거

- 명세: `SPEC-LWS-001` v1.2.0, `AC-LWS-015`~`AC-LWS-022`
- 고정 시각: 테스트 fixture의 `2026-07-12T00:00:00+00:00`
- 명령: `python3 -m unittest tests.test_wiki_hygiene tests.test_living_wiki_steward_skill tests.test_harness_spec_contract tests.test_wiki -v`
- 결과: 테스트 60개 중 새 계약 관련 실패 26건, 기존 회귀는 통과
- 후보 라우팅 Red 6건: `tools.wiki_hygiene`가 없어 결정성·읽기 전용, 최근·노후·위험 시드, 2-hop 경로·노드 상한, 약한 태그 비연결, 충돌 후보·쌍 상한 계약을 충족하지 못함
- Skill Red 8건: `hygiene-plan`, 상위 후보 점진 검토, hop·노드·쌍 예산과 자동 신뢰 효과 없음 절차가 없음
- 상위 명세 Red 1건: 최대 `2-hop` 기본값이 명시되지 않음
- 시간 계약 Red 11건: `content_updated_at` 우선 투영, 생성·검증·생명주기 시각 분리, 시간대 ISO-8601·순서 검증과 confidence 재계산의 검증 시각 불변이 없음
- 무결성 기록: 실패 단언과 기존 회귀를 약화하거나 삭제하지 않고 승인된 RFC의 최소 읽기 전용 후보 계획·시간 투영으로 Green을 만든다.
