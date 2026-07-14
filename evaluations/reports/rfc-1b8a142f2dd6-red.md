# RFC-1B8A142F2DD6 Red 증거

- 명세: `SPEC-LWS-001` v1.0.0
- 명령: `python3 -m unittest tests.test_living_wiki_steward_skill -v`
- 결과: Skill 초기화 전 예상대로 실패
- 요약: 테스트 8개, 실패 2건, 오류 5건, 환경 의존 건너뜀 1건
- 누락 동작: Skill 패키지, 트리거 메타데이터, 작업 절차 본문, 예약 프롬프트, 안전 경계, UI 메타데이터와 README·AGENTS의 직접 PRD 링크
- 두 번째 Red: 릴리스 지문에서 `skills/living-wiki-steward/SKILL.md`와 `wiki/specs/living-wiki-steward-skill.md`가 모두 빠져 `test_release_manifest_binds_skill_and_prd_bytes`가 실패함
- 무결성 기록: 이 증거를 남긴 뒤 실패 fixture나 단언을 약화하지 않음
