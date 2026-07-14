# RFC-9DF9F569807F Red 증거

- 실행 시각: 2026-07-12, Asia/Seoul
- 명세: `SPEC-KO-DOCS-001`
- 명령: `python3 -m unittest tests.test_korean_documentation_policy -v`
- 결과: 실패 7건, 오류 1건, 종료 코드 1

## 고정한 실패

- `tools.korean_docs` 결정론적 검사기가 아직 존재하지 않는다.
- README와 저장소 `AGENTS.md`가 한국어 문서 정책을 연결하지 않는다.
- 중앙 하네스 명세와 Skill 명세가 영문 중심이다.
- Skill 본문, 예약 작업 프롬프트와 Skill UI가 영문이다.
- 생성된 `wiki/index.md`와 인식론 대시보드의 제목·탐색 라벨·상태 라벨이 영문이다.

이 실패는 구현 전에 재현했으며 Green 단계에서 테스트를 삭제하거나 판정을 약화하지 않는다. 코드·명령·ID·URL·해시·스키마 값·외부 원제와 정확한 원문 인용은 명세의 보존 예외로 유지한다.
