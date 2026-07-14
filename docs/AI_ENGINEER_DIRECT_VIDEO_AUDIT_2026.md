# AI Engineer 메모리·위키 채널 감사 — 2026-04-01..2026-07-12

## 집계

- 날짜 범위 탭 목록에서 ID 중복을 제거한 항목: **264**
- 완료되어 시청 가능한 조사 분모: **262** = 일반 영상 251 + 라이브 스트림 다시보기 11, Shorts 0
- 분모에서 제외한 공개 예정 영상: **2**
- 선별 결과: 직접 관련 34, 인접 관련 32, 제외 196
- 직접 관련 자막 시도: 34/34, 입수 34, 보안 허용 31, 거부 3
- 검토 처분: 승격 14, 보류 17, 자막 검토 후 제외 3

`promote`는 출처 입수·반증 검색의 가치가 있거나 이미 범위 제한 S2 단서로 사용했다는 뜻이다. 주장이 참이거나 독립적으로 검증됐다는 뜻은 아니다.

## 범위와 재현성

- 탭: `/videos`, `/streams`, `/shorts`, `/podcasts`. 팟캐스트 탭에는 해당 기간 영상 행이 아니라 재생목록 컨테이너 하나가 노출됐다.
- 11자 영상 ID는 모두 중복 제거했다. 제목, 날짜, 상태, 유형, 채널 신원은 각 영상 페이지에서 다시 읽었다.
- 각 manifest 행에 포함된 규칙 ID로 고정된 의미 판정을 수행했다.
- 탭 목록의 항목 2개는 공개 예정 영상(`is_upcoming`)이므로 스냅샷 시점에 시청할 수 있는 영상이 아니었다.
- 자막은 신뢰할 수 없는 데이터로 취급했다. 자격증명이나 쿠키를 쓰지 않았고 자막 속 지시를 실행하지 않았다.
- 재배포 권리가 확인되지 않아 자막 본문은 이 보고서나 정식 출처에 넣지 않았다. 보안 게이트는 콘텐츠 주소 기반 바이트를 추적 제외된 로컬 격리 구역에 보관할 수 있지만, 이를 추적하거나 승격하지 않는다. 크기 초과 또는 보안 거부된 행사 자막 3개는 자막 결론에 쓰지 않았고 공개 설명의 챕터 메타데이터만 사용했다.

## 직접 관련 후보 검토

| 날짜 | 영상 | 규칙 | 자막 게이트 | 위치 | 처분 | 주제 |
|---|---|---|---|---|---|---|
| 2026-07-11 | [Chat and citations won't save your vertical AI - Atul Ramachandran, Filed Inc](https://www.youtube.com/watch?v=RGiXcVxSD3s) | `D1_PERSISTENT_MEMORY_LEARNING` | 허용 `ADM-26C5AF515293` | 00:08:51 | **제외** (`exclude`) | Skill은 반복 가능한 수직 도메인 실무를 부호화하지만, 검토한 자막 구간에서 명시적 메모리 표현을 찾지 못함 |
| 2026-07-11 | [Develop at Idea Velocity - Jeffrey Lee-Chan, Snapchat](https://www.youtube.com/watch?v=9arM9b7JgOo) | `D1_PERSISTENT_MEMORY_LEARNING` | 허용 `ADM-6926D3A55A13` | 00:01:27 | **보류** (`defer`) | Agent가 이전 요청을 대화형 작업 맥락으로 사용함 |
| 2026-07-05 | [Continual Learning for AI Agents: From Failures to Durable Improvements - Soheil Feizi, RELAI](https://www.youtube.com/watch?v=2IxD9OB3XuQ) | `D1_PERSISTENT_MEMORY_LEARNING` | 허용 `ADM-67D31B298783` | 00:04:27 | **승격** (`promote`) | 실패에는 재실행 가능한 채점, 가장 작은 지속 변경, 회귀 통제가 필요함 |
| 2026-06-29 | [Your Agent Failed in Prod. Good Luck Reproducing It. - Tisha Chawla & Susheem Koul, Microsoft](https://www.youtube.com/watch?v=Lc8zRh9muoY) | `D4_LOG_REPLAY_SNAPSHOT` | 허용 `ADM-D75EF9A9C881` | 00:05:39 | **승격** (`promote`) | 기록·재생은 비트 단위 결정성을 요구하지 않고도 비결정적 Agent 실패의 디버깅을 지원함 |
| 2026-06-28 | [User Signal Dies at the Retrieval Boundary - Sonam Pankaj, StarlightSearch](https://www.youtube.com/watch?v=Jx4ZFEAq6bY) | `D1_PERSISTENT_MEMORY_LEARNING` | 허용 `ADM-4A136815DF3E` | 00:04:32 | **승격** (`promote`) | 하류 결과를 메모리 검색의 효용 신호로 제안하되, 드리프트와 잡음이 있는 라벨이라는 주의사항을 둠 |
| 2026-06-26 | [A Genius With Amnesia - Victor Savkin, Nx](https://www.youtube.com/watch?v=jVjt-2g8NMY) | `D1_PERSISTENT_MEMORY_LEARNING` | 허용 `ADM-E9B6861EF116` | 00:03:18 | **보류** (`defer`) | 저장소를 넘나드는 Agent는 매 세션을 빈 상태로 시작해 사람이 메모리 역할을 하게 됨 |
| 2026-06-26 | [Turn 10,994 Notes Into Memory - Paul Iusztin, Decoding AI & Louis-François Bouchard, Towards AI](https://www.youtube.com/watch?v=ZRM_TfEZcIo) | `D2_WIKI_SECOND_BRAIN_KB` | 허용 `ADM-A501A17F7383` | 00:18:36 | **승격** (`promote`) | 불변 원문 파일이 색인과 영속 Wiki 종합 계층의 입력이 됨 |
| 2026-06-25 | [The Log Is The Agent - Ishaan Sehgal, Omnara](https://www.youtube.com/watch?v=UPwGaM2MKHY) | `D4_LOG_REPLAY_SNAPSHOT` | 허용 `ADM-50C544F56457` | 00:05:38 | **승격** (`promote`) | 추가 전용 Agent 이력이 투영을 가능하게 하며, 압축은 손실이 있고 외부 상태는 로그 밖에 남음 |
| 2026-06-11 | [Your Attention Is the Bottleneck, Not Your Agents — Zack Proser, WorkOS](https://www.youtube.com/watch?v=so9l_MwS2yg) | `D1_PERSISTENT_MEMORY_LEARNING` | 허용 `ADM-7C5B47E01BC5` | 00:13:22 | **보류** (`defer`) | 대화 이력을 분석해 시스템을 개선하고 누락된 Skill을 생성함 |
| 2026-06-08 | [Why More Context Makes Your Agent Dumber and What to Do About It — Nupur Sharma, Qodo](https://www.youtube.com/watch?v=EcqMYoIV57A) | `D3_DECISION_CONTEXT_LIFECYCLE` | 허용 `ADM-34CA627510FB` | 00:24:51 | **보류** (`defer`) | 맥락 과부하, 반복 검색, PR 이력, 수락·거부 피드백이 이후 제안에 영향을 줌 |
| 2026-06-03 | [AI Engineer Melbourne 2026 Keynote Livestream \| Day 1](https://www.youtube.com/watch?v=wjXowoQ7E8c) | `D5_MIXED_EVENT_EXPLICIT_MEMORY_SEGMENT` | 허용 `ADM-406441F17CC7` | 01:01:26 | **보류** (`defer`) | 전용 행사 챕터가 코딩 Agent가 잊는 이유를 다루고 메모리 구조와 맥락 창을 대조함 |
| 2026-06-03 | [BDD, ADR, PRD, WTF: Capturing Decisions for Humans and AI Alike — Michal Cichra, Safe Intelligence](https://www.youtube.com/watch?v=504PvfXou5Y) | `D3_DECISION_CONTEXT_LIFECYCLE` | 허용 `ADM-B26ADBF1D827` | 00:07:47 | **승격** (`promote`) | ADR은 이유를 보존하고 Git 훅과 CI는 프롬프트 밖에서 지속 규칙을 강제함 |
| 2026-06-02 | [How Lovable self-improves every hour — Benjamin Verbeek, Lovable](https://www.youtube.com/watch?v=KA5kPbdkK2E) | `D1_PERSISTENT_MEMORY_LEARNING` | 허용 `ADM-106F0474E838` | 00:10:35 | **승격** (`promote`) | 모델과 기능 변경이 주입된 지식을 빠르게 낡게 만들며, 가지치기 전에 검토와 유보 집합을 사용함 |
| 2026-05-30 | [How I deleted 95% of my agent skills and got better results — Nick Nisi, WorkOS](https://www.youtube.com/watch?v=vy7o1g2iHY8) | `D1_PERSISTENT_MEMORY_LEARNING` | 허용 `ADM-2F43A5943C09` | 00:09:29 | **승격** (`promote`) | 대량의 생성 Skill 맥락이 측정 성능을 해쳤고, 평가가 과감한 가지치기를 정당화함 |
| 2026-05-29 | [Why your agents need decision traces, not just documents — Zach Blumenfeld, Neo4j](https://www.youtube.com/watch?v=B9h9ovW5H9U) | `D3_DECISION_CONTEXT_LIFECYCLE` | 허용 `ADM-4E2204EE1B5B` | 00:03:02 | **보류** (`defer`) | 맥락 그래프가 개체와 결정 흔적을 보존해 과거 추론을 선례로 검색할 수 있게 함 |
| 2026-05-28 | [Context Graphs for Explainable, Decision-Aware AI Agents — Andreas Kollegger & Zaid Zaim, Neo4j](https://www.youtube.com/watch?v=abvQEhvRI_c) | `D3_DECISION_CONTEXT_LIFECYCLE` | 허용 `ADM-0247698C16F8` | 00:15:25 | **보류** (`defer`) | 결정, 행동, 근거를 후속 Agent의 선례로 다시 기록함 |
| 2026-05-28 | [Most Enterprise Agentic Projects Are Doomed, Here's Why — Jess Grogan-Avignon & Jack Wang, Accenture](https://www.youtube.com/watch?v=AGkzpxMdPn8) | `D1_PERSISTENT_MEMORY_LEARNING` | 허용 `ADM-97ED3E1E1042` | 00:17:39 | **보류** (`defer`) | 공급자가 제품 수정과 사용자 행동을 누적되는 살아 있는 메모리로 설명함 |
| 2026-05-25 | [Bounded Autonomy: Between Free Will and Determinism — Angus J. McLean, Oliver](https://www.youtube.com/watch?v=t4359sKBu4w) | `D1_PERSISTENT_MEMORY_LEARNING` | 허용 `ADM-822099EBE7B5` | 00:10:38 | **제외** (`exclude`) | 더 넓은 자율성 발표에서 메모리와 압축은 실험적 하네스 제안으로만 등장함 |
| 2026-05-22 | [Fast Models Need Slow Developers — Sarah Chieng, Cerebras](https://www.youtube.com/watch?v=TeGsFFNqRLA) | `D1_PERSISTENT_MEMORY_LEARNING` | 허용 `ADM-26ED4B6C1FB6` | 00:15:50 | **승격** (`promote`) | 파일 4개로 구성한 외부 메모리를 통해 새 세션이 범위 제한 목표를 이어감 |
| 2026-05-16 | [Connecting the Dots with Context Graphs — Stephen Chin, Neo4j](https://www.youtube.com/watch?v=eW_vxrjvERk) | `D3_DECISION_CONTEXT_LIFECYCLE` | 허용 `ADM-39C0AB129AD1` | 00:13:21 | **보류** (`defer`) | 그래프가 검색 사실뿐 아니라 과거 결정의 정책과 추론을 전달함 |
| 2026-05-16 | [AIE Singapore Day 1 ft. Minister, NanoClaw, OpenAI, Google, Vercel, Cursor & more](https://www.youtube.com/watch?v=_xQnSNlBP_w) | `D2_WIKI_SECOND_BRAIN_KB` | 거부 `ADM-A9C0E203A5C3` | 설명 챕터 00:41:40 | **보류** (`defer`) | 메타데이터가 개인의 이해와 책임을 강조하는 세컨드 브레인 작업 흐름 챕터를 식별함 |
| 2026-05-13 | [Self-Training Agents: Hermes Agent, HF Traces, Skills, MCP & Finetuning  — Merve Noyan, Hugging Face](https://www.youtube.com/watch?v=OV56RddyFuU) | `D1_PERSISTENT_MEMORY_LEARNING` | 허용 `ADM-B8D27F426710` | 00:07:56 | **제외** (`exclude`) | 메모리 관리는 폭넓은 Hugging Face 생태계 발표 안의 짧은 Hermes Agent 구간임 |
| 2026-05-12 | [Give Your Agent a Computer — Nico Albanese, Vercel](https://www.youtube.com/watch?v=wflNENRSUb4) | `D1_PERSISTENT_MEMORY_LEARNING` | 허용 `ADM-EA135A102802` | 00:57:20 | **보류** (`defer`) | 영속 샌드박스 파일과 결정론적 검색을 핵심 메모리와 대화 이력에 쓰도록 제안함 |
| 2026-05-11 | [Viktor: AI Coworker That Lives in Slack — Fryderyk Wiatrowski](https://www.youtube.com/watch?v=ohKt066uFhg) | `D1_PERSISTENT_MEMORY_LEARNING` | 허용 `ADM-D8754BF4E2EB` | 00:07:12 | **보류** (`defer`) | 다중 사용자 Slack Agent 메모리가 격리와 확장 문제를 일으킴 |
| 2026-05-10 | [Two Roads to Durable Agents: Replay vs. Snapshot — Eric Allam, CEO, Trigger.dev](https://www.youtube.com/watch?v=svCnShDvgQg) | `D4_LOG_REPLAY_SNAPSHOT` | 허용 `ADM-A08A794959D5` | 00:09:35 | **승격** (`promote`) | 맥락 로그의 내구성과 실행 상태의 내구성에는 서로 다른 장치가 필요하며 스냅샷은 연산 상태를 복원함 |
| 2026-05-10 | [How we solved Context Management in Agents — Sally-Ann Delucia](https://www.youtube.com/watch?v=esY99nYXxR4) | `D6_WORKING_CONTEXT_MEMORY_STORE` | 허용 `ADM-844E8A203EC9` | 00:06:15 | **승격** (`promote`) | 단순 절단과 요약은 추론을 잃게 하므로 검색 가능한 외부 저장과 장기 세션 평가를 제안함 |
| 2026-05-05 | [Demand-Driven Context: A Methodology for Coherent Knowledge Bases Through Agent Failure](https://www.youtube.com/watch?v=_QAVExf_1uw) | `D2_WIKI_SECOND_BRAIN_KB` | 허용 `ADM-128EFD21AA6C` | 00:16:05 | **승격** (`promote`) | 실패한 작업이 지식 공백을 드러내고, 사람의 검증을 거쳐 지식베이스로 승격함 |
| 2026-05-03 | [Context Is the New Code — Patrick Debois, Tessl](https://www.youtube.com/watch?v=bSG9wUYaHWU) | `D3_DECISION_CONTEXT_LIFECYCLE` | 허용 `ADM-636C5C91C52C` | 00:03:04 | **승격** (`promote`) | 맥락을 버전이 있는 생성·평가·배포·관찰 수명주기로 취급함 |
| 2026-05-03 | [Mergeable by default: Building the context engine to save time and tokens — Peter Werry, Unblocked](https://www.youtube.com/watch?v=5ID22ACI7IM) | `D3_DECISION_CONTEXT_LIFECYCLE` | 허용 `ADM-1A2153BDCA9A` | 00:15:42 | **보류** (`defer`) | 조직 이력과 과거 결정이 Agent의 충돌 맥락 해결을 도움 |
| 2026-05-02 | [I Gave an AI Agent the Keys to My Life (Here's What Happened) — Radek Sienkiewicz (@velvetshark-com)](https://www.youtube.com/watch?v=sJ2jc7leKBk) | `D1_PERSISTENT_MEMORY_LEARNING` | 허용 `ADM-38279B46494C` | 00:01:02 | **보류** (`defer`) | 개인 Agent가 장기 활동 메모리를 기반으로 작동하며 권한과 자율성 위험을 보여줌 |
| 2026-04-28 | [Building your own software factory — Eric Zakariasson, Cursor](https://www.youtube.com/watch?v=rnDm57Py54A) | `D1_PERSISTENT_MEMORY_LEARNING` | 허용 `ADM-66CFC9AEBA45` | 00:30:15 | **보류** (`defer`) | 플러그인이 Agent 자막에서 재사용 가능한 규칙을 추출해 지속 학습에 사용함 |
| 2026-04-21 | [AIE Miami Day 2 ft. Cerebras, OpenCode, Cursor, Arize AI, and more!](https://www.youtube.com/watch?v=DeM_u2Ik0sk) | `D5_MIXED_EVENT_EXPLICIT_MEMORY_SEGMENT` | 거부 `ADM-D876BB4A014D` | 설명 챕터 02:27:02 / 05:17:08 / 05:35:07 | **보류** (`defer`) | 메타데이터가 혼합 행사 안에서 결정 흔적, Agent 메모리, 지속 학습 챕터를 따로 제시함 |
| 2026-04-09 | [AIE Europe Keynotes & OpenClaw ft Deepmind, OpenAI, Vercel, @pragmaticengineer , @mattpocockuk](https://www.youtube.com/watch?v=O_IMsEg91g8) | `D5_MIXED_EVENT_EXPLICIT_MEMORY_SEGMENT` | 거부 `ADM-9AD3913E71DD` | 설명 일정 12:20pm | **보류** (`defer`) | 메타데이터가 혼합 행사에서 메모리 구조·형식 검증 세션을 예고함 |
| 2026-04-08 | [Cognitive Exhaust Fumes, or: Read-Only AI Is Underrated — Šimon Podhajský, Head of AI, Waypoint](https://www.youtube.com/watch?v=u0TOSBbAw7c) | `D2_WIKI_SECOND_BRAIN_KB` | 허용 `ADM-36EFCA0F7453` | 00:01:12 | **승격** (`promote`) | 읽기 전용 개인 지능 계층이 쓰기 권한 없이 출처 간 패턴을 찾음 |

## 규칙 정의

- `A1_RETRIEVAL_RAG_INDEX`: 검색·RAG·색인이 중심이지만 증거로 통제되는 지속 Wiki 메모리는 중심이 아니다.
- `A2_EVAL_OBSERVABILITY_REPRODUCTION`: 평가, 관찰 가능성, 피드백, 재현성이 중심이며 하네스에 간접적으로 도움을 준다.
- `A3_SKILL_CONTEXT_PACKAGING`: Skill 또는 맥락 패키징이 중심이며 영속 사실 메모리는 부차적이다.
- `A4_SOURCE_DISCOVERY_RESEARCH`: 조사·출처 접근이 중심이며 영속 메모리 자체보다 입수 과정에 도움을 준다.
- `D1_PERSISTENT_MEMORY_LEARNING`: 영속 Agent 메모리, 메모리 위생, 이전 실행에서 얻는 지속 학습이 중심 주제다.
- `D2_WIKI_SECOND_BRAIN_KB`: Wiki, 지식베이스, 세컨드 브레인, 개인 지능 계층이 중심 주제 또는 명시적 행사 챕터다.
- `D3_DECISION_CONTEXT_LIFECYCLE`: 지속되는 결정·맥락 자료, 그 수명주기, 출처 이력, 이후 재사용이 중심 주제다.
- `D4_LOG_REPLAY_SNAPSHOT`: 추가 전용 이력, 재생, 스냅샷, Agent 상태 복원이 중심 주제다.
- `D5_MIXED_EVENT_EXPLICIT_MEMORY_SEGMENT`: 혼합 라이브 스트림에 제목으로 명시된 메모리·세컨드 브레인·결정 흔적 챕터가 있다.
- `D6_WORKING_CONTEXT_MEMORY_STORE`: 검색 가능한 메모리 저장소를 이용한 작업 맥락 보존이 중심 주제다.
- `X0_UPCOMING_NOT_VIEWABLE`: 공개 예정 영상이 탭에 있었지만 감사 스냅샷 시점에는 볼 수 없었다.
- `X1_HARDWARE_OR_MODEL_MEMORY`: 메모리 관련 표현이 지속 Agent 지식이 아니라 하드웨어·모델 용량을 뜻한다.
- `X2_NON_WIKI_PERSONA_MEMORY`: 메모리 표현이 연구·Wiki 지식이 아니라 오락·인격 연속성을 뜻한다.
- `X3_MIXED_EVENT_NO_QUALIFYING_CHAPTER`: 혼합 라이브 스트림 메타데이터에 조건을 만족하는 메모리·Wiki·세컨드 브레인 챕터가 없다.
- `X4_OUT_OF_SCOPE`: 제목과 설명에서 지속 메모리·Wiki·세컨드 브레인 또는 인접 검색·평가 장치가 중심이 아니다.

## 공개 예정 항목

- `OqM67QG_Ikk` — 영상 원제: From fork() to Fleet: Designing an Agent Sandbox Cloud — Abhishek Bhardwaj, OpenAI — 업로드 날짜 2026-07-08, 공개 20260713, 상태 `is_upcoming`
- `xg1zNlzw7Jk` — 영상 원제: Claws Out: Securing and Building with OpenClaw - Nick Taylor, Pomerium — 업로드 날짜 2026-04-09, 공개 20260711, 상태 `is_upcoming`

## 자료 무결성

- 정식 출처: `SRC-0800355B8885`
- 정식 번들: `raw/sources/SRC-0800355B8885/ai-engineer-memory-wiki-audit-bundle-2026-07-12.json`
- 번들 SHA-256: `bea5e7289f0022af81ca1ec81de44e624c32a93ada4ae7e94354cb3450623980`
- 매니페스트: `ai-engineer-2026-04-01_to_2026-07-12-manifest.json`
- 매니페스트 SHA-256: `15c1ba8fe98eecb2224bc68c9576929f3e0ac83d33606b0eda3e3a7176509807`
- 직접 검토: `ai-engineer-direct-caption-review.json`
- 직접 검토 SHA-256: `9a9df8415e9a2aeb8eede2348e72bdcdf5beaab6f98a65dedfe8dc1d5ff6e16d`

manifest 자체가 264행으로 된 정식 메타데이터·분류 스냅샷이다. 영상별 임시 메타데이터와 자막 경로는 의도적으로 넣지 않았으며, 해당 해시와 보안 입수 ID는 보존했다.
