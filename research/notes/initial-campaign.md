# Initial campaign note — 2026-07-11

Campaign: `CMP-C31903B13965`

## Inputs

- Karpathy LLM Wiki Gist
- AI Engineer video `ZRM_TfEZcIo`
- 발표에서 공유한 `ai-research-os-workshop` GitHub repository
- 사용자의 철학: 사람과 Agent의 actor parity, Agent 중심 maintenance, 인간의 방향/lead 제공, Wiki의 독자적 관점

## Methods

- Gist 본문·revision·관련 구현 논의를 비판적으로 검토
- YouTube 공개 영어 자동자막 전체 추출 및 타임스탬프 분석
- 공개 repository를 shallow clone해 conventions, research/lint skills, scripts 검사
- 2026-07-11 기준 ACL/EACL/TACL/Nature/ICLR/ICML 공식 페이지 우선 검색
- arXiv/OpenReview 자료는 status를 preprint/under review/accepted로 구분
- 메모리, deep research, provenance, source credibility, 인간-Agent 협업, 문서 편집 회귀, 보안, GraphRAG 조사
- source independence group을 적용해 영상과 저장소 같은 동일 제작자 자료의 중복 집계 방지
- 모든 핵심 결론을 atomic claim과 exact locator로 등록

## Outcome

- 29 sources
- 15 claims, all C2 or below
- one explicit contested claim
- one explicit same-origin non-independence lint finding
- v1→v2→v3 harness and three queued follow-up campaigns

## Honest limits

- 대부분 외부 자료는 URL/metadata-only이며 local immutable snapshot은 없다.
- 독립 인간/다른 모델 reviewer가 없어 C3/C4는 없음.
- 논문 abstract와 공식 metadata를 넘어선 모든 정량 결과는 보고서에서 범위를 제한했다.
- continuous operation은 scheduler/agent runner가 필요하며 이 대화가 끝난 뒤 스스로 실행되는 daemon은 아니다.

