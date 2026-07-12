# 초기 캠페인 기록 — 2026-07-11

캠페인: `CMP-C31903B13965`

## 입력

- Karpathy LLM Wiki Gist 자료
- AI Engineer 영상 `ZRM_TfEZcIo`
- 발표에서 공유한 `ai-research-os-workshop` GitHub repository
- 사용자의 철학: 사람과 Agent의 actor parity, Agent 중심 maintenance, 인간의 방향/lead 제공, Wiki의 독자적 관점

## 방법

- Gist 본문·revision·관련 구현 논의를 비판적으로 검토
- YouTube 공개 영어 자동자막 전체 추출 및 타임스탬프 분석
- 공개 저장소를 얕게 복제해 규약, 연구·검사 Skill, 스크립트를 검사
- 2026-07-11 기준 ACL/EACL/TACL/Nature/ICLR/ICML 공식 페이지 우선 검색
- arXiv/OpenReview 자료는 status를 preprint/under review/accepted로 구분
- 메모리, deep research, provenance, source credibility, 인간-Agent 협업, 문서 편집 회귀, 보안, GraphRAG 조사
- source independence group을 적용해 영상과 저장소 같은 동일 제작자 자료의 중복 집계 방지
- 모든 핵심 결론을 atomic claim과 exact locator로 등록

## 결과

- 출처 29개
- 주장 15개, 모두 C2 이하
- 명시적으로 논쟁 중인 주장 1개
- 동일 기원으로 독립적이지 않다는 명시적 린트 발견 1건
- v1→v2→v3 하네스와 대기 중인 후속 캠페인 3개

## 명시적 한계

- 대부분 외부 자료는 URL과 메타데이터만 있으며 로컬 불변 스냅샷은 없다.
- 독립 인간이나 다른 모델 검토자가 없어 C3/C4는 없다.
- 논문 초록과 공식 메타데이터를 넘어선 모든 정량 결과는 보고서에서 범위를 제한했다.
- 지속 운영에는 스케줄러나 Agent 실행기가 필요하며, 이 대화가 끝난 뒤 스스로 실행되는 데몬은 아니다.
