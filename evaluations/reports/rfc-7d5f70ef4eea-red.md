# RFC-7D5F70EF4EEA Red 증거

- 명세: `SPEC-KO-DOCS-001` 버전 `1.1.0`, `AC-KO-011`
- 명령: `python3 -m unittest tests.test_korean_documentation_policy.KoreanDocumentationPolicyTests.test_human_readable_diagram_fences_are_checked_but_code_fences_are_not -v`
- 결과: 실패 1건, 종료 코드 1

검사기가 `text`와 `mermaid` 펜스 안의 사람이 읽는 영문 라벨을 한 건도 보고하지 않아 테스트가 실패했다. 실행 가능한 `bash` 코드 펜스는 계속 보존해야 한다.
