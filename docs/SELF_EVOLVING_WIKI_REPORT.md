# 자가진화·인간협력 Living Wiki 설계 및 초기 구현 보고서

작성일: 2026-07-11  
연구 기준 시점: 2026-07-11 (Asia/Seoul)  
초기 구현: `/Users/jaewoo/Desktop/SSHWorkspace/projects/wiki_v1`  
요청 보고서 사본: `/Users/jaewoo/Desktop/SSHWorkspace/projects/wiki/docs/SELF_EVOLVING_WIKI_REPORT.md`

## 0. 결론부터

원하는 시스템은 “Agent가 대신 써주는 Obsidian”이나 “RAG에 신뢰 점수를 붙인 검색기”가 아니다. 가장 정확한 정의는 다음과 같다.

> 사람과 Agent가 같은 contribution protocol을 사용하는 연구 공동체이며, 외부 세계의 evidence를 claim 단위로 축적하고, Agent가 지속적으로 발견·검증·합성·보수하되, 인간이 새로운 단서와 가치·방향·이의를 언제든 주입할 수 있고, 공동체의 현재 관점과 하네스 자체도 평가를 거쳐 진화하는 로컬 우선 지식 시스템.

Karpathy의 [LLM Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)와 AI Engineer 발표 [Turn 10,994 Notes Into Memory](https://www.youtube.com/watch?v=ZRM_TfEZcIo), 그리고 발표에서 공유한 [ai-research-os-workshop](https://github.com/iusztinpaul/ai-research-os-workshop)은 좋은 뼈대를 준다.

```text
immutable raw → index → LLM-maintained Markdown wiki
```

하지만 그대로는 부족하다. 세 자료의 중심은 개인 연구 기억과 파일형 Wiki이고, 다음이 빠져 있거나 미완성이다.

- claim-level evidence와 exact locator
- relevance와 credibility의 분리
- source independence·이해상충·철회·최신성
- 사람/Agent의 동일 actor·contribution·review protocol
- 주기적 자율 discovery와 stop condition
- Wiki의 관점과 사실 원장의 분리
- 반복 편집 회귀평가
- memory poisoning과 prompt injection 방어
- benchmark-gated harness self-evolution

따라서 초기 시스템은 다섯 층으로 확장했다.

```text
1. Source evidence       불변 snapshot, hash, URL, license, publication status
2. Epistemic ledger      atomic claim, exact locator, support/contradiction, time
3. Living wiki           concept, comparison, synthesis, perspective, questions
4. Collaboration         actor, contribution, review, decision, campaign
5. Control & evolution   policy, eval, security gate, RFC, rollback, audit event
```

현재 `wiki_v1`에는 2026년 공식 [Open Knowledge Format v0.1](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md)을 따르는 portable `wiki/` bundle, 선별 출처와 evidence-linked claim, v1→v3.1 진화 기록, 표준 라이브러리 중심의 실행 CLI, unit test, 신뢰도 dashboard, 연구 campaign queue가 들어 있다. 모든 claim은 C2 이하로 유지했다. 독립 reviewer가 없는 상태에서 제가 만든 것을 제가 검사해 C3/C4라고 부르는 것은 시스템 철학에 어긋나기 때문이다.

## 1. 사용자가 원하는 철학의 기술적 해석

### 1.1 사람과 Agent는 같은 종류의 객체다

이 철학은 “모든 사람이 모든 권한을 갖고 모든 Agent가 임의 파일을 덮어쓴다”로 구현하면 위험하다. 더 강하고 일관된 구현은 사람과 Agent가 동일한 프로토콜을 사용하는 것이다.

```text
Actor → Proposal/Contribution → Evidence → Review → Commit/Event
```

모든 actor는 다음을 할 수 있다.

- source와 질문 제출
- claim과 관점 제안
- 기존 claim의 지지·반박 evidence 제출
- 다른 기여 검토
- 관심 분야와 연구 방향 제안
- 하네스 문제와 개선 RFC 제안

진위 판단에서 `kind=human|agent`는 직접 가점이나 감점이 아니다. 인간도 틀리고 Agent도 틀린다. 해당 분야 전문성, 독립성, 증거, 검증 이력, 이해상충이 중요하다.

다만 운영 권한은 별도다. 원문 삭제, 외부 공개, 개인정보·비밀, 비용 확대, 헌장 변경은 인간 승인이 필요하다. 이것은 인간이 epistemic 상위 존재라서가 아니라 현실에서 법적 책임·동의·비용·보안 경계를 가진 주체이기 때문이다. 반대로 일상적인 조사·정리·링크 보수·stale 검사·저위험 합성은 Agent가 기본 수행한다.

### 1.2 인간은 감독 버튼 이상의 존재다

인간의 역할을 마지막 승인으로만 축소하면 사용자의 철학을 잃는다. 사람은 다음을 제공한다.

- Agent가 알 수 없는 가치와 연구 목적
- 현장 경험과 암묵지
- Agent가 놓친 unknown unknown
- 좋은 source lead와 “이 사람/기관을 먼저 보라”는 탐색 prior
- 연구 중간의 방향 수정과 반론
- 결과가 실제 삶과 조직에 미치는 의미

2026년 [InterDeepResearch](https://arxiv.org/abs/2603.12608)는 기존 query-to-report deep research가 사람을 수동적 소비자로 만든다고 비판하며 관찰 가능성, 실시간 조향, 맥락 탐색을 강조한다. [Collaborative Gym](https://openreview.net/forum?id=GDYueXtKXT)은 결과뿐 아니라 비동기 협업 과정과 communication/situational-awareness failure를 평가한다. 선행 연구 [Co-STORM](https://aclanthology.org/2024.emnlp-main.554/)은 사람이 다중 Agent의 담화를 관찰하고 개입하며 동적 mind map을 함께 만드는 접근을 보여준다.

따라서 인간의 방향은 일회성 prompt가 아니라 지속되는 `interest`, `campaign`, `commitment`, `decision` 객체로 저장해야 한다.

### 1.3 Wiki의 독자적 관점

독자적 관점은 가능하고 유용하지만 사실과 섞으면 편향 증폭기가 된다. 다음을 분리한다.

- `claim ledger`: 무엇이 어떤 evidence에 의해 어느 범위에서 지지되는가
- `perspective/thesis`: 이 공동체가 현재 어떤 가정과 가치 아래 무엇을 중요하게 보는가

각 perspective에는 반드시 현재 입장, 전제, 지지 claim, 가장 강한 반론, 설명하지 못하는 관찰, 입장을 바꿀 조건, revision history가 있어야 한다. 과거 관점과 반대 evidence를 삭제하지 않는다. 초기 구현의 `wiki/perspectives/self-evolving-wiki-position.md`가 이 규칙을 실제로 사용한다.

## 2. 지정 자료 1 — Karpathy LLM Wiki 비판적 분석

### 2.1 핵심 제안

Karpathy의 글은 일반적인 파일 업로드/RAG가 질문마다 관련 chunk를 찾아 다시 종합하므로 지식이 누적되지 않는다고 지적한다. 대신 불변 raw sources와 사용자 사이에 LLM이 유지하는 Markdown Wiki를 둔다.

- 새 source를 읽고 source summary만 추가하지 않는다.
- entity, concept, comparison, overview, synthesis를 갱신한다.
- 기존 claim과의 모순을 표시한다.
- 질문 중 얻은 비교·분석·연결도 Wiki로 되돌린다.
- `index.md`는 내용 중심 router, `log.md`는 append-only timeline이 된다.
- ingest, query, lint를 분리한다.
- Obsidian은 인간의 IDE, LLM은 maintainer, Wiki는 codebase라는 비유를 쓴다.

이 설계는 RAG의 반대라기보다 raw knowledge 위의 지속적 materialized view에 가깝다. 규모가 커지면 Wiki도 retrieval이 필요하므로 최종 구조는 `raw retrieval + persistent synthesis`의 혼합이다.

### 2.2 그대로 가져올 것

1. **불변 원문과 가변 합성의 물리적 분리**
2. **대화를 지속 artifact로 컴파일**
3. **AGENTS.md/schema를 운영 헌법으로 사용**
4. **ingest/query/lint의 명시적 workflow**
5. **Markdown/Git 우선, 병목이 생긴 뒤 검색 인프라 추가**
6. **질문과 lint가 다음 연구 gap을 생성하는 compounding loop**

### 2.3 그대로 가져오면 안 되는 것

- raw source를 “source of truth”라고 부른다. 불변성은 감사 가능성을 뜻하지 정확성을 뜻하지 않는다.
- source와 page는 있으나 atomic claim과 exact evidence span이 없다.
- 사람은 source를 고르고 LLM이 Wiki를 소유하는 역할 분리라 actor parity와 다르다.
- 자율 discovery, cadence, budget, stop condition이 없다.
- 동일 모델이 writer와 linter일 때 correlated error를 다루지 않는다.
- LLM maintenance cost를 사실상 0처럼 표현하지만 API 비용, semantic drift, 검토, 복구, context 비용이 존재한다.
- query 결과를 다시 지식으로 저장할 때 self-generated 문장이 독립 evidence로 재순환할 위험이 있다.
- prompt injection, memory poisoning, privacy, copyright, concurrent editing, release evaluation이 없다.

이 Gist는 저자의 설계 의도를 확인하는 1차 자료이고 높은 탐색 가치가 있지만, 2026-04-04의 practitioner idea file이며 peer review, benchmark, reference implementation이 없다. 저자의 명성과 별 개수는 읽을 이유이지 효과의 증명이 아니다.

## 3. 지정 자료 2 — 영상과 공유 GitHub 비판적 분석

### 3.1 자료 관계

- 영상: [Turn 10,994 Notes Into Memory](https://www.youtube.com/watch?v=ZRM_TfEZcIo)
- 채널: [AI Engineer](https://www.youtube.com/@aiDotEngineer)
- 게시: 2026-06-26, 39분 32초
- 발표자: Paul Iusztin, Louis-François Bouchard
- 공개 구현: [ai-research-os-workshop](https://github.com/iusztinpaul/ai-research-os-workshop), MIT

공개 영어 자동자막 전체를 타임스탬프와 함께 추출하고, 저장소를 shallow clone해 `README`, `CONVENTIONS.md`, research/lint skills, index builder, YouTube transcript script까지 검사했다.

### 3.2 영상의 v1→v3

| 구간 | 내용 | 설계 의미 |
|---|---|---|
| 00:00–09:16 | 10,994개 수준의 흩어진 노트를 다음 연구에서 재사용하지 못함 | 문제는 context 양보다 지속 기억과 routing |
| 09:16–12:48 | 로컬 Markdown, Obsidian, 여러 connector | inspectable/local-first artifact |
| 12:48–15:29 | V1: golden links + deep research → 정적 `research.md` | 좋은 seed와 여러 검색 round |
| 15:29–18:28 | V2: 개인 Second Brain까지 검색, 여전히 정적 결과 | 개인화되나 새 질문마다 전체 재실행 |
| 18:28–25:01 | V3: raw + index.yaml + mutable Wiki | 점진적 context loading과 persistent synthesis |
| 25:01–27:04 | 전체 vault의 read-only snapshot과 프로젝트 Wiki 분리 | global memory와 working memory 분리 |
| 27:04–36:50 | web/GitHub/custom link demo | 실제 agent-native workflow |
| 36:50–38:45 | provenance, source strength/ranking, lint, compaction 미완성 인정 | 사용자의 trust 요구가 정확히 남은 문제 |
| 38:45–39:32 | 유료 강의 홍보 | 상업적 이해상충 표시 필요 |

### 3.3 현재 GitHub 구현

현재 저장소는 영상의 고정 V3 snapshot이 아니다. conventions는 스스로 v4라고 하며 다음을 추가했다.

- `contradictions.md`, open questions, question pages
- query/append/deep/init routing
- fast/light/deep research depth
- YouTube, GitHub, web, PDF, Obsidian, Readwise, NotebookLM connector
- deterministic index generation
- orphan, missing hub/comparison, broken link lint

하지만 핵심 trust 한계는 남는다.

- 사용자 seed는 `relevance_score: 1.0`이다. 이는 반드시 포함하라는 뜻이지 신뢰도 1.0이 아니다.
- Wiki claim은 raw/source page를 링크하지만 atomic claim ID와 exact span을 구조적으로 강제하지 않는다.
- `wiki/`는 LLM 소유이고 사람의 편집은 deliberate override라 동일 contribution protocol이 아니다.
- source authority, independence cluster, conflict, retraction, claim confidence가 admission에 연결되지 않는다.
- 사람 요청 없이 주기적으로 관심 분야를 감시하는 loop가 없다.
- 하네스 변경을 benchmark/RFC/rollback으로 관리하지 않는다.

영상과 저장소는 같은 제작자 집단의 artifact이므로 형식이 달라도 독립 corroboration 두 건으로 세지 않았다. 구현 사실에는 저장소가 강한 1차 evidence지만, 효과·확장성에는 독립 평가가 아니다.

## 4. OKF를 외부 지식 계약으로 채택

사용자 추가 지시에 따라 `wiki/`를 [Google Cloud가 2026년 6월 발표한 Open Knowledge Format](https://cloud.google.com/blog/products/data-analytics/how-the-open-knowledge-format-can-improve-data-sharing) bundle로 만들었다. 공식 [SPEC.md](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md)는 2026-07-11 현재 **Version 0.1 — Draft**이고, 공식 `okf/` 디렉터리는 Apache 2.0으로 배포된다.

OKF는 의도적으로 최소 규격이다.

1. bundle은 계층적 Markdown directory다.
2. `index.md`와 `log.md`를 제외한 모든 `.md`는 parseable YAML frontmatter와 비어 있지 않은 `type`을 가진다.
3. 내부 관계는 표준 Markdown link로 표현한다.
4. `index.md`는 progressive disclosure, `log.md`는 ISO 날짜별 update history다.
5. 외부 근거는 관례적으로 문서 아래 `# Citations`에 둔다.
6. producer-defined frontmatter key가 허용되고 consumer는 모르는 key를 보존해야 한다.

OKF가 정의하지 않는 것도 중요하다. 고정 taxonomy, 저장·검색 인프라, claim confidence, source credibility, actor identity, review, governance, security는 non-goal 또는 producer 영역이다. 따라서 OKF를 trust 표준이라고 과장하지 않고 **portable knowledge view**로 사용한다.

```text
repository control plane
├── state/ actors, sources, claims, reviews, campaigns, events
├── raw/ immutable evidence
├── governance/ evaluation/ tools/
└── wiki/                    ← exact OKF bundle boundary
    ├── index.md             ← reserved, no frontmatter
    ├── log.md               ← reserved, no frontmatter
    ├── okf-profile.md       ← typed concept declaring v0.1 profile
    ├── sources/*.md         ← type: Reference
    ├── concepts/*.md        ← type: Concept
    └── perspectives/*.md    ← type: Position
```

Living Wiki의 `claim_ids`, `source_id`, `source_level`, `lifecycle_status`, `generated`는 OKF가 허용하는 producer extension이다. 정식 OKF 필드인 것처럼 표현하지 않는다. OKF-only consumer는 `wiki/`만 읽을 수 있고, Living-Wiki-aware consumer는 ID를 따라 바깥 JSON ledger와 raw evidence로 내려가 더 강한 audit를 수행한다.

공식 v0.1에는 bundle manifest가 필수가 아니다. 별도 manifest 규격을 임의로 발명하지 않았다. 또한 §6은 index frontmatter가 없다고 하고 §11은 root index에 `okf_version`을 둘 수 있는 예외를 허용한다. 현재 profile은 보수적인 consumer 호환성을 위해 `index.md`를 frontmatter-free로 유지하고, version/status를 typed `okf-profile.md`에 기록한다.

CLI의 `okf-validate`는 bundle boundary, reserved file, non-empty `type`, YAML frontmatter, portable link를 검사하며 전체 `validate`에도 포함된다. 공식 spec이 Draft이므로 향후 변경은 silent rewrite가 아니라 migration RFC와 회귀평가를 거친다. 이 호환성 변화는 factual benchmark가 개선된 major release가 아니므로 v4가 아니라 **v3.1**로 기록했다.

## 5. 설계의 핵심 — 문서가 아니라 Claim/Evidence graph

### 5.1 최소 claim 구조

```yaml
id: CLM-...
statement: 독립적으로 검토 가능한 원자적 문장
kind: fact | interpretation | hypothesis | prediction | value
scope: 적용 도메인, 버전, 모집단, 조건
valid_at: 2026-07
created_by: actor-id
created_by_group: independence-group
evidence:
  - source_id: SRC-...
    relation: supports | contradicts | contextualizes
    locator: page 7, section 3.2 / 00:18:21-00:19:04
    strength: 1..4
status: open | supported | contested | refuted | superseded | stale
```

위키의 중요한 사실 문장은 claim ID로 연결돼 최종적으로 외부 원자료의 정확한 위치에 닿아야 한다. 모델이 만든 synthesis는 `derived artifact`이고 독립 evidence가 아니다.

2026년 [GenProve](https://aclanthology.org/2026.acl-long.228/)는 fine-grained provenance를 Quotation, Compression, Inference로 구분하며 inference provenance가 특히 어렵다고 보고한다. [FactSearch](https://aclanthology.org/2026.acl-demo.36/)는 모델 출력을 atomic claim으로 나누고 targeted query와 재현 가능한 로컬 검색으로 검증한다. [DeepFact](https://aclanthology.org/2026.acl-long.1586/)는 benchmark 정답도 감사와 이의 제기를 거쳐 고쳐져야 함을 보여준다.

### 5.2 왜 page confidence 하나로 부족한가

한 페이지에는 확실한 공식 사실, 단일 연구의 결과, Agent 해석, 예측, 가치판단이 섞인다. 페이지에 83%라고 붙이면 어떤 문장이 왜 83%인지 설명되지 않고 반증의 영향 범위도 알 수 없다. 따라서 page confidence는 내부 claim 분포, 최저/중앙 level, contested badge를 요약한 파생 view여야 한다.

### 5.3 시간과 범위

단순 모순 상당수는 실제로 버전·시점·모집단·조건 차이다. 2026년 [RAG or Learning?/Chronos](https://aclanthology.org/2026.findings-acl.546/)는 지속적 knowledge drift에서 RAG와 학습 기반 갱신 모두 temporal inconsistency를 겪는다고 보고한다. claim에는 `valid_from`, `valid_to`, `as_of`, `supersedes`가 필요하다.

## 6. 신뢰도 레벨링

### 6.1 단일 점수를 거부한다

최소한 다음을 분리한다.

- source provenance와 identity
- primary/secondary 여부와 claim 직접성
- 저자/기관의 해당 분야 전문성
- 방법·데이터·코드의 투명성
- peer review/official status와 correction/retraction
- 이해상충과 상업적 유인
- 독립 source group 수
- evidence entailment/faithfulness
- world factuality
- contradiction과 reviewer independence
- freshness와 extraction/OCR/transcript 품질

[FRANQ](https://aclanthology.org/2026.findings-acl.338/)는 retrieved context에 충실한지와 현실적으로 사실인지 분리한다. [Assessing Web Search Credibility and Response Groundedness](https://aclanthology.org/2026.eacl-long.115/)는 source credibility와 cited-source groundedness를 따로 평가한다. 그러므로 “메시지도 중요하지만 메신저도 중요하다”는 사용자의 원칙은 맞지만, 메신저 권위가 메시지의 evidence를 덮지 않게 해야 한다.

### 6.2 Source level S0–S4

| Level | 뜻 | 사용 |
|---|---|---|
| S0 | provenance/status 미평가 | search lead, canonical synthesis 금지 |
| S1 | 출처·방법이 약하거나 이해상충/검증 한계가 큼 | 질문 생성과 원출처 추적 |
| S2 | provenance는 있으나 실무자 self-report, 단일 사례, preprint 등 추가 검증 필요 | attributed evidence |
| S3 | 직접 자료·투명 방법·공식 기록·엄격한 검토 중 다수를 충족 | 강한 scoped evidence |
| S4 | 해당 claim 범위에서 표준/원데이터/재현/동료심사가 강함 | 권위 있는 scoped evidence, 면책 아님 |

S4도 범위를 벗어나면 약하다. S1도 중요한 최초 제보일 수 있다. level은 publisher 전체의 영구 평판이 아니라 **해당 문서가 해당 claim을 지지하는 범위**에서 평가한다.

### 6.3 Claim level C0–C4

| Level | gate |
|---|---|
| C0 미평가 | 연결 evidence 없음 |
| C1 보고됨 | exact locator가 있는 지지 source 하나 이상 |
| C2 지지됨 | 강한 직접 source 하나 또는 독립 source group 둘 |
| C3 교차확인 | 독립 group 둘 이상, S3+ evidence, 독립 review, 중대한 미해결 강한 반증 없음 |
| C4 견고함 | 고품질 독립 evidence 둘 이상, 독립 reviewer group 둘, adversarial review, peer-review/official/reproduced marker, 강한 미해결 반증 없음 |

`contested`, `refuted`, `stale`, `superseded`, `retracted`는 level과 별도 badge다. 출처가 많아도 같은 보도자료나 논문을 복제했다면 독립 group 하나다. 같은 모델 계열 Agent 여러 개의 동의도 독립 reviewer 여러 명으로 세지 않는다.

현재 초기 원장의 모든 claim이 C2인 이유가 이것이다. 한 Agent session이 source를 찾고 claim을 만들고 다시 검사했으므로 independent review gate를 통과하지 않았다.

### 6.4 메신저를 평가하되 권위 편향을 막는다

메신저 평가 항목:

- 해당 domain에서의 전문성
- identity/provenance 확인 가능성
- 원자료·방법 공개
- 정정·철회·예측 track record
- 이해상충과 incentive
- 다른 source와의 독립성

이 평가는 discovery priority와 review depth를 조절한다. claim truth를 직접 결정하지 않는다. 2026년 preprint [A Mechanistic View of Authority Hierarchy in LLM Sycophancy](https://arxiv.org/abs/2607.00415)는 모델이 증거보다 권위 persona에 끌릴 수 있음을 경고한다. 높은 권위에 더 낮은 검증 기준을 주는 대신, 영향이 큰 claim일수록 authority와 무관하게 더 깊게 검증해야 한다.

## 7. 정보 입수 시스템 — Garbage-in을 막는 법

### 7.1 Source ladder

기본 탐색 우선순위는 다음과 같다.

1. 공식 표준, 원 논문, 원 데이터, 원 코드, 법령/공식 기록
2. 저자·연구기관의 직접 발표
3. 학회·전문기관의 검증 가능한 합성
4. 평판 좋은 secondary synthesis
5. 블로그·뉴스레터·YouTube·SNS는 lead로 사용하고 원출처로 이동

YouTube는 가치가 낮은 source가 아니다. 구현자의 tacit knowledge, demo, 실패담을 얻기 좋다. 하지만 talk의 성능 주장은 논문과 독립 benchmark로 다시 확인해야 한다. transcript에는 자막 종류, 언어, 자동 생성 여부, timestamp, 발표자, 이해상충, 연결된 논문·코드가 필요하다. 화면에만 나오는 표/코드/도표는 별도 frame 검사가 필요하다.

### 7.2 Admission pipeline

```text
untrusted inbox
→ URL/identity/license/status 확인
→ immutable snapshot + SHA-256
→ sandboxed parsing/transcript extraction
→ embedded instruction 무시
→ message/messenger assessment
→ atomic claim + exact span
→ duplicate/origin independence clustering
→ primary-source and counter-evidence search
→ independent verifier
→ quarantine | candidate | accepted
→ dependency impact analysis
→ scoped patch
→ lint + factual regression test
```

검색 결과 자체는 evidence가 아니다. 검색 snippet을 인용하지 않고 원페이지·원논문으로 이동한다. 최신 논문은 arXiv만 보고 “논문”이라고 부르지 않고 official venue/OpenReview/ACL Anthology에서 peer-reviewed, accepted, under review, preprint, withdrawn를 구분한다. 과학 자료는 Crossref, PubMed, Retraction Watch 등 status registry 재검사가 필요하다.

### 7.3 Source diversity와 counter-search

확인 검색만 수행하면 관심 분야와 기존 관점이 확증편향을 만든다. 모든 중요 campaign은 다음을 요구한다.

- 주장을 지지하는 검색과 반증하는 검색을 별도로 기록
- 서로 다른 방법·기관·이해관계의 source 확보
- 동일 원출처의 파생 보도를 한 group으로 묶기
- 가장 강한 반론을 synthesis에 보존
- 반대 evidence를 찾지 못했다면 검색 범위와 query를 기록

## 8. Agent의 지속 연구 루프

### 8.1 Loop

```text
interests / current thesis / human leads
→ gap, contradiction, staleness detection
→ bounded research campaign
→ source discovery and admission
→ claim/evidence integration
→ counter-search and review
→ scoped Wiki synthesis
→ evaluation and regression checks
→ next question or stop
```

각 campaign은 질문, `why_now`, priority, 최대 source 수, 최대 시간, 필요한 독립 group 수, counter-search, stop condition을 가진다.

### 8.2 우선순위

- 사용자 관심도와 명시적 방향
- 현재 thesis를 바꿀 가능성
- uncertainty와 contradiction
- 정보의 빠른 노후 위험
- 예상 정보 이득
- 반대 evidence 부족
- 비용과 위험

### 8.3 Stop condition

무한 검색은 품질이 아니다.

- 두 round 연속 신규 claim 없음
- 필요한 독립 evidence group 확보
- 동일 내용 반복률 임계치 초과
- 시간/source/token 예산 소진
- 추가 검증에 유료 접근·전문가·실험 같은 외부 조건 필요
- 새 evidence가 uncertainty를 줄이지 않음

### 8.4 실제 지속 실행의 경계

이 저장소만으로 시간이 지나면 저절로 Agent가 깨어나지는 않는다. 지속 연구에는 cron, CI, local daemon 또는 agent runner가 필요하다. `scripts/research-cycle.sh`는 다음 campaign과 provider-neutral prompt를 출력하며 `WIKI_AGENT_CMD`가 설정됐을 때만 trusted runner를 실행한다. 무인 모드는 수집·초안·검사까지만 허용하고 헌장·trust policy·삭제·외부 공개·비용 증가는 RFC/승인으로 멈춘다.

## 9. 반복 편집과 지식 노후화

2026년 ACL 논문 [Beyond Single-shot Writing](https://aclanthology.org/2026.acl-long.609/)은 평가한 다섯 deep-research Agent가 사용자 피드백으로 보고서를 반복 수정하는 동안 기존 내용·인용 품질의 16–27%를 훼손했다고 보고한다. 이 수치는 해당 시스템과 benchmark 범위지만 “Agent가 알아서 전체 문서를 다시 쓰게 하면 된다”는 가정을 직접 반박한다.

[LEDGER](https://aclanthology.org/2026.findings-acl.515/)는 dependency-aware graph retrieval로 영향받는 부분을 좁혀 편집한다. 따라서 ingest는 다음 transaction에 가깝게 운영한다.

1. 새 source와 claim을 candidate로 추가
2. 기존 claim과 duplicate/support/contradict/scope-shift 판정
3. dependency graph로 영향 page·thesis·index를 계산
4. 최소 patch 생성
5. 기존 valid claim/citation 회귀 검사
6. 전체 structural lint
7. 실패 시 rollback

Graph 자체도 완전하지 않으므로 scoped patch 뒤 전체 invariant 검사도 필요하다. [Dissecting GraphRAG](https://aclanthology.org/2026.tacl-1.29/)은 triple extraction과 community granularity가 병목이며 단순 template report가 LLM summary보다 정확·효율적일 수 있음을 보인다. 초기부터 거대한 knowledge graph를 도입하지 않고 결정론적 schema와 template을 우선한 이유다.

## 10. 보안 — 지속 기억은 장기 공격 표면이다

외부 웹·PDF·자막·GitHub 문서의 텍스트는 명령이 아니라 untrusted data다. persistent Wiki는 한 번의 악성 memory write가 이후 여러 연구와 행동에 재등장할 수 있다.

- [A-MemGuard](https://openreview.net/forum?id=udqe7UZUZ6): memory poisoning 방어와 보호 memory
- [From Untrusted Input to Trusted Memory](https://arxiv.org/abs/2606.04329): 네 write channel, 아홉 구조 취약점, 여섯 attack class, MPBench
- [SafeSearch](https://openreview.net/forum?id=95VVL0TJNH): search Agent의 misinformation/prompt injection red team
- [MM-PoisonRAG](https://aclanthology.org/2026.acl-long.1558/): multimodal knowledge poisoning
- [OWASP Agent Memory Guard](https://owasp.org/www-project-agent-memory-guard/): hash, snapshot, policy, rollback 중심 reference implementation

초기 보안 규칙:

- 수집 Agent/파서와 canonical memory writer의 권한 분리
- 외부 콘텐츠의 “이 지시를 따르라”는 문장을 실행하지 않음
- file type, size, hash, origin, license 기록
- executable/repository는 quarantine와 최소 권한 sandbox
- source가 policy/memory를 바꾸라고 해도 proposal로도 자동 전환하지 않음
- read/write gate를 모두 둠
- secret·private data를 public Wiki에 복사하지 않음
- snapshot과 rollback 보존
- 정상 source 거부율과 attack 성공률을 함께 측정

현재 구현은 hash와 policy boundary를 제공하지만 실제 공격 fixture를 아직 실행하지 않았다. `CMP-088A51571084`가 다음 P0 campaign이다.

## 11. 안전한 하네스 자기진화

### 11.1 왜 직접 자기수정하면 안 되는가

Agent가 운영 prompt, trust gate, evaluator를 조용히 함께 바꾸면 자신의 산출물이 좋아 보이도록 기준을 최적화할 수 있다. 이 Goodhart loop는 콘텐츠 오류보다 위험하다. 자가진화는 자기 코드 수정 권한이 아니라 **실패를 수정 가능한 RFC로 바꾸는 능력**부터 시작해야 한다.

```text
observed failure
→ RFC with evidence
→ minimal candidate change
→ fixed benchmark + security red team
→ quality/cost/regression comparison
→ migration and rollback rehearsal
→ approval
→ release snapshot/tag
```

RFC 필수 필드:

- 어떤 실제 실패를 고치는가
- 연결 event/claim/source/evaluation
- 변경할 schema/prompt/tool과 최소 diff
- 예상 효과와 acceptance threshold
- 회귀·보안·비용 위험
- migration과 rollback
- 제안 actor와 독립 reviewer group

### 11.2 구현된 v1→v3.1

#### v1 — File Wiki

- raw → index → Markdown Wiki
- Karpathy/AI Research OS의 persistent synthesis와 progressive disclosure
- 실패: relevance/trust 혼동, page citation, 수동 실행, actor 부재

#### v2 — Epistemic Ledger

- actor/source/claim/evidence/review/event
- source independence, contradiction, C0–C4 gate
- raw hash와 event hash chain
- 실패: 지속 discovery 부재, 반복 편집 회귀, poisoning, self-review 편향

#### v3 — Governed Research Loop

- interests와 bounded campaign
- counter-search, evaluation, security policy
- dependency-aware minimal patch 원칙
- harness RFC와 rollback
- deterministic CLI/test/dashboard
- 남은 실패: 실제 장기 calibration, red team, 동시 편집, 대규모 검색

#### v3.1 — OKF Interoperability

- `wiki/`를 OKF v0.1 Draft bundle boundary로 지정
- typed YAML frontmatter와 표준 Markdown links
- reserved root/subdirectory index와 update log
- Living Wiki extension mapping과 OKF validator
- trust/governance 원장은 바깥 control plane에 유지

v4는 아직 만들지 않았다. 운영 evidence 없이 기능 이름만 늘리는 것은 진화가 아니기 때문이다.

## 12. 초기 구현 상세

### 12.1 디렉터리

```text
wiki_v1/
├── AGENTS.md                     Agent 운영 헌장
├── README.md
├── config/
│   ├── wiki.json                자율성·예산·freshness
│   ├── interests.json           관심 분야·watch source
│   └── trust-policy.json        S0-S4, C0-C4 gate
├── state/
│   ├── actors.json
│   ├── sources.json
│   ├── claims.json
│   ├── reviews.json
│   ├── campaigns.json
│   ├── proposals.json
│   └── events.jsonl             hash-chain append-only log
├── raw/sources/                 immutable artifact store
├── wiki/                        OKF v0.1 portable derived knowledge bundle
├── research/                    campaigns와 research notes
├── governance/                  헌장, ADR, RFC
├── evolution/                   v1→v2→v3.1 failure trail
├── evaluations/                 release gate와 snapshot
├── reports/                     lint와 보고서
├── prompts/research-cycle.md
├── scripts/research-cycle.sh
├── tools/wiki.py                stdlib-only CLI
└── tests/test_wiki.py
```

### 12.2 CLI

```bash
python3 tools/wiki.py status
python3 tools/wiki.py next-task
python3 tools/wiki.py source-add --help
python3 tools/wiki.py claim-add --help
python3 tools/wiki.py evidence-add --help
python3 tools/wiki.py review-add --help
python3 tools/wiki.py evaluate
python3 tools/wiki.py render
python3 tools/wiki.py lint
python3 tools/wiki.py okf-validate
python3 tools/wiki.py validate
python3 -m unittest discover -s tests -v
```

CLI가 담당하는 것은 판단이 아니라 invariant다.

- deterministic content ID
- actor attribution
- raw artifact SHA-256와 불변 copy
- exact evidence locator 강제
- source independence group
- gate-based claim level 계산
- reviewer group 중복 방지
- dangling reference와 raw hash 검사
- tamper-evident event chain 검사
- deterministic dashboard/index
- content-addressed evaluation snapshot

### 12.3 초기 연구 상태

- source 31개
- evidence-linked claim 18개
- C2 18개, C3/C4 0개
- OKF concept document 75개, OKF core/profile validation warning/error 0개
- unit test 12개
- pure OKF export 2회가 86개 Markdown 전체에서 byte-identical
- contested claim 1개: raw가 source of truth인가 evidence인가
- lint finding 1개: 영상과 GitHub가 같은 제작자 group으로 접힘
- 완료 campaign 2개
- queued P0 campaign 3개: confidence calibration, source admission, poisoning red team

### 12.4 현재 경고

대부분의 외부 source는 저작권·접근성·저장 비용 때문에 metadata/URL만 등록했고 immutable local snapshot이 없다. validator가 이를 오류로 숨기지 않고 warning으로 보인다. 이후 공개 라이선스·공식 문서는 snapshot을 추가하고, 유료/제한 자료는 hash 가능한 개인 사본 또는 접근 가능한 locator 정책을 정해야 한다.

## 13. 평가 지표

하네스가 “진화했다”고 말하려면 다음을 측정해야 한다.

### Structural

- claim-to-source provenance closure
- locator 누락, dangling reference, raw hash mismatch
- orphan/duplicate/broken link
- event chain integrity

### Epistemic

- citation entailment와 completeness
- claim factual accuracy
- known contradiction recall
- source independence clustering precision
- stale/retracted claim detection latency
- C-level별 empirical accuracy, Brier/ECE calibration
- counter-evidence coverage와 source diversity

### Collaboration

- 인간 방향 수정 반영률
- human correction rate와 correction survival
- unresolved commitment 체류 시간
- actor attribution coverage
- 사람이 발견한 unknown unknown의 후속 연구 반영률

### Regression and efficiency

- 수정 전 valid claim/citation 보존율
- fixed query answer quality
- query/ingest당 시간·token·tool call·비용
- raw retrieval/RAG-only baseline 대비 개선
- rollback 성공률

### Security

- poison write/retrieve/activate 단계별 공격 성공률
- prompt injection defense 성공률과 정상 자료 과잉 거부율
- secret exfiltration, malicious file/repo, multimodal poison
- policy bypass와 excessive agency

2026년 [LiveResearchBench](https://openreview.net/forum?id=ghwbZ3uhEd)는 동적·사용자 중심 deep research와 citation-grounded report 평가를 제공한다. [DeepFact](https://aclanthology.org/2026.acl-long.1586/)는 benchmark 자체도 이의 제기와 감사가 필요함을 보여준다. 따라서 evaluator도 provenance와 version을 가진 객체여야 한다.

## 14. 2026 핵심 연구 지도

상태를 구분해 읽었다. `peer-reviewed/accepted`는 강한 prior지만 자동 진실이 아니며, `preprint`는 최신 lead로 쓰되 추가 검증한다.

### Deep research와 평가

- [OpenScholar — Nature](https://www.nature.com/articles/s41586-025-10072-4), 2026-02, peer-reviewed: 4,500만 공개 논문 datastore, retriever/reranker, citation-aware generation, self-feedback. 강한 baseline이나 retrieval miss, unsupported output, 평가 규모 한계가 남는다.
- [LiveResearchBench](https://openreview.net/forum?id=ghwbZ3uhEd), ICLR 2026 Poster: dynamic/live research, citation, user alignment benchmark. live web 재현성 문제가 있다.
- [DeepFact](https://aclanthology.org/2026.acl-long.1586/), ACL 2026: benchmark와 Agent의 co-evolution, Audit-then-Score. 동일 verifier 편향을 경계해야 한다.
- [Beyond Single-shot Writing](https://aclanthology.org/2026.acl-long.609/), ACL 2026: 반복 수정 중 16–27% 회귀. dependency-aware editing의 직접 근거.
- [SAGE retrieval benchmark](https://arxiv.org/abs/2602.05975), 2026 preprint: 일부 agent/query에서 BM25가 LLM retriever보다 강함. retriever와 query policy를 함께 평가해야 한다.
- [Data-Centric Perspectives on Agentic RAG](https://aclanthology.org/2026.findings-acl.78/), Findings ACL 2026: data lifecycle survey. architecture 우월성 증명은 아니다.

### Memory, graph, continual evolution

- [UMEM](https://openreview.net/forum?id=BoiXvrwtdi), ICML 2026: memory extraction과 management를 이웃 task utility로 함께 최적화. utility가 factuality는 아니다.
- [Hindsight](https://aclanthology.org/2026.acl-demo.27/), ACL 2026 Demo: world/experience/observation/opinion network 분리. perspective layer의 직접 참고.
- [MAGMA](https://aclanthology.org/2026.acl-long.1709/), ACL 2026: semantic/temporal/causal/entity multi-graph. graph extraction 오류는 별도 문제.
- [Chronos](https://aclanthology.org/2026.findings-acl.546/), Findings ACL 2026: continuous knowledge drift와 event evolution graph.
- [LEDGER](https://aclanthology.org/2026.findings-acl.515/), Findings ACL 2026: dependency-aware scoped document editing.
- [Dissecting GraphRAG](https://aclanthology.org/2026.tacl-1.29/), TACL 2026: triple/community bottleneck과 deterministic template의 가치.
- [SkillWiki](https://arxiv.org/abs/2606.16523), 2026 preprint: living agent-skill knowledge lifecycle. factual Wiki가 아닌 skill infrastructure라는 범위 한계.
- [Vector RAG vs LLM-Compiled Wiki](https://arxiv.org/abs/2605.18490), 2026 preregistered preprint: persistent Wiki의 일부 장점과 query cost. 매우 작은 단일 저자 실험.

### Provenance, credibility, uncertainty

- [GenProve](https://aclanthology.org/2026.acl-long.228/), ACL 2026: Quotation/Compression/Inference provenance.
- [FRANQ](https://aclanthology.org/2026.findings-acl.338/), Findings ACL 2026: faithfulness와 factuality 분리.
- [Assessing Web Search Credibility and Response Groundedness](https://aclanthology.org/2026.eacl-long.115/), EACL 2026: messenger와 message grounding 동시 평가.
- [Uncertainty Quantification in LLM Agents](https://aclanthology.org/2026.acl-long.738/), ACL 2026: trajectory/entity별 uncertainty 필요.
- [CiteGuard](https://aclanthology.org/2026.acl-long.282/), ACL 2026: retrieval-augmented citation validation. 자동 canonicalization에는 여전히 불충분한 정확도.
- [Web Search Is Not Enough: Retraction Status](https://openreview.net/forum?id=yvivK8FdVI), 2026 under review: 검색 결과에 철회 정보가 있어도 Agent가 놓칠 수 있음. 공식 registry gate 필요.

### Human–Agent collaboration와 governance

- [Collaborative Gym](https://openreview.net/forum?id=GDYueXtKXT), ICLR 2026: 결과와 협업 과정 평가.
- [Adaptive Collaboration with Humans](https://openreview.net/forum?id=IKVUB9Exuc), ICLR 2026: cost/risk-aware defer policy.
- [InterDeepResearch](https://arxiv.org/abs/2603.12608), 2026 preprint: observability, steerability, context navigation.
- [Evolving Agentic Workflow Driven by Human-Agent Collaboration](https://aclanthology.org/2026.findings-acl.1250/), Findings ACL 2026: human preference-guided workflow evolution. factual governance는 별도다.
- [AgentBound](https://arxiv.org/abs/2606.30970), 2026 preprint: verifiable behavioral governance와 action receipt.
- [Regulating the Machine Contributor](https://arxiv.org/abs/2606.14594), 2026 preprint: disclosure, responsibility, oversight, licensing, enforcement.

### Security와 poisoning

- [A-MemGuard](https://openreview.net/forum?id=udqe7UZUZ6), ICML 2026: memory poisoning defense.
- [From Untrusted Input to Trusted Memory](https://arxiv.org/abs/2606.04329), 2026 preprint: memory write channels, vulnerability taxonomy, MPBench.
- [PRA-RAG](https://aclanthology.org/2026.findings-acl.1794/), Findings ACL 2026: retrieval corruption에 대한 robust aggregation. 이론 가정 범위에 한정.
- [MM-PoisonRAG](https://aclanthology.org/2026.acl-long.1558/), ACL 2026: multimodal knowledge poisoning.
- [SafeSearch](https://openreview.net/forum?id=95VVL0TJNH), ICML 2026: search agent red team.
- [BadScientist](https://aclanthology.org/2026.acl-long.1134/), ACL 2026: LLM reviewer가 문제를 지적하고도 accept하는 concern-acceptance conflict. Agent jury를 peer review 대체물로 보면 안 된다.

### 오래됐지만 필요한 기반

- [W3C PROV-O](https://www.w3.org/TR/prov-o/): Entity/Activity/Agent와 derivation/attribution. provenance이지 truth certificate가 아니다.
- [Nanopublications](https://nanopub.net/): assertion/provenance/publication-info 분리.
- [Wikidata data model](https://www.wikidata.org/wiki/Help:Data_model): statement qualifier/reference/rank. rank는 confidence가 아니다.
- [NIST AI RMF](https://www.nist.gov/itl/ai-risk-management-framework): Govern–Map–Measure–Manage release checklist.
- [STORM](https://aclanthology.org/2024.naacl-long.347/): perspective-guided Wikipedia형 synthesis.
- [Co-STORM](https://aclanthology.org/2024.emnlp-main.554/): 인간 개입형 multi-agent information seeking.
- [FActScore](https://aclanthology.org/2023.emnlp-main.741/): long-form을 atomic facts로 평가.
- [SAFE](https://deepmind.google/research/publications/85420/): search-augmented long-form factuality evaluation.

## 15. AI Engineer 채널 후속 관찰 목록

영상은 구현 패턴과 실패 사례를 얻는 practitioner source로 좋지만, 논문과 같은 신뢰 등급을 자동 부여하지 않는다.

- [Build Your Own Deep Research Agents](https://www.youtube.com/watch?v=mYSRn6PC1mc), 2026-04-20: web/YouTube/GitHub search, trust filtering, cited artifact, eval workshop.
- [How we taught agents to use good retrieval](https://www.youtube.com/watch?v=1IdzkRVmWAA), 2026-07-07: retriever가 좋아도 query policy가 옛 keyword 도구용이면 실패. vendor 이해상충 표시 필요.
- [Continual Learning for AI Agents](https://www.youtube.com/watch?v=2IxD9OB3XuQ), 2026-07-05: failure replay와 regression-aware loop.
- [Why your agents need decision traces](https://www.youtube.com/watch?v=B9h9ovW5H9U), 2026-05-29: 문서뿐 아니라 판단 이력/context graph. Neo4j 관점이 강함.
- [Production Evals for Agentic AI Systems](https://www.youtube.com/watch?v=vljxQZfJ9wY), 2026-06-25: continuous production eval과 telemetry.
- [Capturing Decisions for Humans and AI Alike](https://www.youtube.com/watch?v=504PvfXou5Y), 2026-06-03: ADR/BDD/Git/CI로 policy를 executable하게 만들기.
- [Harness Engineering](https://www.youtube.com/watch?v=am_oeAoUhew), 2026-04-17: humans steer, agents execute. software 경험을 epistemic trust로 바로 일반화하면 안 됨.
- [Design Patterns for AI Trust](https://www.youtube.com/watch?v=YZQsWVeN3rE), 2026-07-11: librarian/jury/model tier. 같은 모델 family의 합의는 독립 검증이 아님.

## 16. 권장 운영 순서

### 지금

1. `config/interests.json`에 실제 관심 분야와 cadence를 추가한다.
2. `human:owner`의 이름/역할을 원하는 정체성으로 바꾼다.
3. queued campaign 중 confidence calibration을 먼저 수행한다.
4. 공개 라이선스 핵심 source의 raw snapshot을 추가한다.
5. 사람이 3–5개 핵심 claim을 직접 읽고 review하되, 단순 approve가 아니라 반증 query와 rationale를 남긴다.

### 다음 단계

1. gold claim/evidence fixture 100개를 만든다.
2. C0–C4 calibration과 source independence clustering을 평가한다.
3. BM25 기반 로컬 검색 baseline을 추가하고 vector/graph는 실제 benchmark 후 선택한다.
4. memory poisoning fixture와 quarantine parser를 구현한다.
5. claim dependency와 page impact map을 추가한다.
6. scheduler/runner를 최소 권한으로 연결한다.

### 아직 하지 말 것

- 근거 없이 모든 source를 자동 score하는 LLM judge
- 여러 Agent 투표를 독립 사실 검증으로 간주
- 처음부터 거대한 GraphRAG/vector infrastructure 도입
- Agent에게 헌장과 trust policy 직접 수정 권한 부여
- 무제한 background crawling
- local raw 없이 요약만 계속 요약하는 재귀 memory

## 17. 최종 판단

사용자가 원하는 Wiki는 충분히 만들 수 있다. 핵심은 “Agent에게 시간이 많으니 자료를 많이 모으게 한다”가 아니라, Agent의 시간을 다음 네 가지에 쓰는 것이다.

1. 좋은 messenger와 원자료를 찾는 탐색
2. claim 단위 evidence와 반증의 bookkeeping
3. 사람이 읽기 좋은 관점과 synthesis의 지속 보수
4. 자기 작업의 오류·비용·보안을 평가하고 다음 개선을 RFC로 제안

철학적 핵심도 보존할 수 있다. 사람과 Agent는 동일 contributor protocol을 사용하며, 누구의 말도 actor 종류 때문에 참이 되지 않는다. 인간은 Agent가 놓친 세계와 목적을 제공하고, Agent는 인간이 지속하기 어려운 연구와 maintenance를 담당한다. Wiki의 독자성은 숨은 모델 편향이 아니라 공개된 관심사, evidence, 이견, 결정, 수정 조건에서 나온다.

가장 중요한 금지 규칙은 하나다.

> Agent가 만든 합성물이 외부 evidence인 것처럼 다시 들어와 자기 신뢰도를 올리게 하지 않는다.

이 규칙을 지키고 claim provenance, actor parity, counter-search, evaluation, RFC를 함께 운영하면, Wiki는 단순한 지식 저장소가 아니라 시간이 지나며 더 잘 틀리고, 더 빨리 고치고, 왜 그렇게 믿는지를 설명할 수 있는 공동 연구 객체로 진화할 수 있다.
