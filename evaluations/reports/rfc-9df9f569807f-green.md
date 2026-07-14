# RFC-9DF9F569807F Green 증거

- 명세: `SPEC-KO-DOCS-001`
- 제안 상태: `implemented`
- 릴리스 구성요소 지문: `66bb07834d81ed2655ba6a604152e0b49c72bddec03c44a571a2676bb9f4d3a4`
- 보관된 릴리스 보고서: `evaluations/reports/v4-release-66bb07834d81ed26.json`
- 운영 인증 주장: `false`

## 구현 결과

- 사람이 읽는 Wiki·하네스·Skill·프롬프트·생성 문서의 기본 언어를 한국어로 통일했다.
- 코드, 명령, 식별자, URL, 해시, 스키마 열거값, 외부 자료의 원제목과 출처가 표시된 정확한 원문 인용만 보존 예외로 남겼다.
- `render`와 `evaluate`가 한국어 파생 문서를 다시 생성하도록 템플릿과 기본 서술을 수정했다.
- 결정론적 `language-validate`를 독립 CLI와 전체 릴리스 게이트에 연결했다.
- 생성 문서 표시, 링크, 표, 주석, 여러 줄 frontmatter, Setext 제목, 줄바꿈 산문, 사람이 읽는 다이어그램, 짧은 목록, 불완전한 인용 표식과 닫히지 않은 코드 울타리로 검사를 우회하지 못하도록 회귀 테스트를 고정했다.
- 최종 감사에서 찾은 펜스와 문맥 우회는 `RFC-7D5F70EF4EEA`, `RFC-4550532AD310`으로 보완하고 같은 최신 릴리스 근거로 다시 봉인했다.

## 검증 결과

- `python3 -m unittest discover -s tests -v`: 286개 통과
- `python3 tools/wiki.py language-validate`: 통과, 발견 0건
- `python3 tools/wiki.py validate`: 통과, 기존 경고 45건
- `python3 tools/wiki.py okf-validate`: 통과, 경고 0건
- `python3 tools/wiki.py release-check --actor agent:codex`: 필수 게이트 8개 모두 통과
- Skill `quick_validate.py`: 통과
- 연속 무로그 렌더의 집계 해시: 동일

필수 게이트는 `structural_and_ledger`, `okf_bundle`, `calibration`, `security`, `runtime`, `regression_tests`, `memory_feedback_lifecycle_hygiene`, `korean_documentation_contract`이며, 중복이나 누락이 있으면 구현 완료 전이를 거부한다.

## 남은 제한

- 고정 fixture 기반 회귀 통과는 운영 환경 인증이 아니다.
- 기존 메타데이터 전용 출처 43건과 이의가 제기된 주장 1건은 이번 언어 정책과 별개인 공개된 품질 부채로 유지한다.
