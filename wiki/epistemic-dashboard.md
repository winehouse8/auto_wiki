---
type: Epistemic Dashboard
title: 인식론 대시보드
description: 정규 원장에서 파생한 주장·출처의 증거 성숙도 현황.
tags: [trust, provenance, claims]
timestamp: '2026-07-12T03:10:01+00:00'
generated: true
---

<!-- tools/wiki.py가 자동 생성함. 직접 수정하지 마세요. -->
# 인식론 대시보드

신뢰 레벨은 진실 확률이 아니라 현재 증거 성숙도의 파생 표시다. 상세 근거는 `state/claims.json`과 `state/sources.json`을 확인한다.

## 주장

| ID | 레벨 | 증거 상태 | 생명주기 | 주장 | 지지 그룹 | 반박 그룹 |
|---|---:|---|---|---|---:|---:|
| `CLM-1EB8BD726482` | C2 | supported | active | 지속적으로 편집되는 Wiki는 영향받은 의존성만 좁게 수정한 뒤 전체 불변조건과 사실 회귀를 다시 검사해야 한다. | 2 | 0 |
| `CLM-25D2398ACBF4` | C2 | supported | active | Codex의 프로젝트 지침 결합 용량 기본값은 32 KiB이며, 한도에 도달하면 추가 지침 파일을 더하지 않는다. | 1 | 0 |
| `CLM-3B0EC9C26226` | C2 | supported | active | AGENTS.md 변경 내용을 확실히 반영하려면 새 Codex 명령 또는 새 TUI 세션을 시작해야 하며, project_doc_fallback_filenames에 등록되지 않은 대체 파일명은 자동 지침 탐색 대상이 아니다. | 1 | 0 |
| `CLM-409FCD3D2B82` | C2 | supported | active | Codex는 매 실행 시작 시 프로젝트 경로 탐색과 별도로 CODEX_HOME(기본 ~/.codex)의 전역 지침을 읽으며, non-empty AGENTS.override.md가 있으면 그것을 사용하고 그렇지 않으면 AGENTS.md를 사용한다. | 1 | 0 |
| `CLM-4A3051A018DC` | C2 | supported | active | 출처의 권위와 평판은 검색 우선순위와 검토 깊이를 정하는 prior로 쓸 수 있지만 개별 주장의 증거를 대체할 수 없다. | 2 | 0 |
| `CLM-61B3C391010C` | C2 | supported | active | 지속 메모리를 쓰는 Agent는 수집 시점과 검색 시점 모두에 오염 방지 gate가 필요하다. | 2 | 0 |
| `CLM-6DDD53332A40` | C2 | contested | active | 원문 snapshot은 감사 가능한 증거이지 자동으로 참인 source of truth가 아니다. | 2 | 1 |
| `CLM-6ED77E226EF7` | C2 | supported | active | 검색된 문맥에 대한 충실성, 현실 세계의 사실성, 출처 자체의 신뢰도는 서로 다른 평가 대상이다. | 2 | 0 |
| `CLM-7FDAF2F91E73` | C2 | supported | active | OKF v0.1 conformance는 비예약 Markdown의 parseable YAML frontmatter와 non-empty type, 그리고 예약 index.md/log.md 구조를 핵심 필수 조건으로 둔다. | 1 | 0 |
| `CLM-860EB3D6AAEB` | C2 | supported | active | 자료의 주제 관련도는 해당 자료의 신뢰도나 그 자료를 인용한 답변의 사실성을 보장하지 않는다. | 2 | 0 |
| `CLM-952258184EF2` | C2 | supported | active | OKF v0.1은 claim confidence, source credibility, actor governance, 저장 및 검색 인프라를 정의하지 않으므로 Living Wiki는 이를 producer extension과 외부 control plane으로 보완해야 한다. | 1 | 0 |
| `CLM-95A38CACF2CD` | C2 | supported | active | Agent 실패는 어떤 지식 공백을 조사할지 우선순위화하는 신호가 될 수 있지만, 실패 원인이나 새 지식의 사실성을 스스로 증명하지 않으므로 독립 근거 검증과 재현 가능한 재시도 뒤에만 Wiki 지식으로 승격해야 한다. | 2 | 0 |
| `CLM-99AE239A5BA3` | C2 | supported | active | Crossref는 Retraction Watch의 retraction 및 일부 correction·expression-of-concern 데이터를 production REST API와 공개 dataset으로 제공하며, REST 결과의 update-to와 source 필드로 update 유형과 provenance를 구분한다. | 1 | 0 |
| `CLM-A49ACF085321` | C2 | supported | active | GitHub REST commit 조회는 commit SHA와 signature verification 객체를 제공하므로 코드 출처를 가변 branch 이름보다 특정 commit에 고정하고 검증 메타데이터를 기록할 수 있다. | 1 | 0 |
| `CLM-B97B5BE5E324` | C2 | supported | active | Codex는 선택된 프로젝트 지침을 루트에서 현재 디렉터리 순으로 결합하므로 더 가까운 디렉터리의 지침이 뒤에 놓여 앞선 지침을 재정의할 수 있다. | 1 | 0 |
| `CLM-CB6E34C87DA3` | C2 | supported | active | 감사 가능한 연구 Wiki의 신뢰 최소 단위는 페이지 전체보다 원자적 주장과 정확한 evidence locator의 연결이어야 한다. | 3 | 0 |
| `CLM-CEBC308C15C4` | C2 | supported | active | GraphRAG의 그래프 구조는 잘못 추출된 triple과 부적절한 community 구성에서 생기는 오류를 자동으로 상쇄하지 못한다. | 1 | 0 |
| `CLM-D2A1B46809DA` | C2 | supported | active | 시간에 따라 변하는 주장은 valid_from, valid_to, as_of, supersedes 같은 시간 범위와 계보를 가져야 한다. | 2 | 0 |
| `CLM-DA4E9F9BA977` | C2 | supported | active | Codex는 작업을 시작하기 전에 지침 체인을 구성하며, 대화형 TUI에서는 보통 실행된 세션마다 한 번만 AGENTS.md 계열 파일을 탐색한다. | 1 | 0 |
| `CLM-DA7C92E9A901` | C2 | supported | active | 효과적인 인간-Agent 공동 연구에는 결과만이 아니라 과정의 관찰 가능성, 실시간 조향, 공유 맥락과 복구 가능한 commitment가 필요하다. | 3 | 0 |
| `CLM-DCFACC957266` | C2 | supported | active | Wiki가 형성한 관점은 사실 원장과 분리하고 가장 강한 반론, 가정, 입장 변경 조건과 개정 이력을 보존해야 한다. | 3 | 0 |
| `CLM-EC52C0576A28` | C2 | supported | active | 사용자는 장기 Wiki 기억에 의존하는 정도를 명시적으로 조절할 수 있어야 하며, fresh-start 모드는 과거 기록 삭제가 아니라 독립 재조사 후 기존 Wiki와 비교하는 retrieval policy로 구현해야 한다. | 1 | 0 |
| `CLM-F2BB537122FE` | C2 | supported | active | NCBI E-utilities는 PubMed와 PMC를 포함한 Entrez 데이터베이스를 검색·연결·조회할 수 있는 공식 공개 API다. | 1 | 0 |
| `CLM-F464CCF0AA1A` | C2 | supported | active | 하네스의 자기진화는 고정된 평가, 최소 변경, 회귀 검사와 rollback을 통과한 제안으로만 승격해야 한다. | 3 | 0 |
| `CLM-F526A53CB69F` | C2 | supported | active | OKF v0.1에는 필수 bundle manifest, JSON Schema, 중앙 type registry가 없으며 type taxonomy와 추가 frontmatter는 producer에게 열려 있다. | 1 | 0 |
| `CLM-F6367BFF8F35` | C2 | supported | active | 불변 원문 위의 지속적 합성 Wiki는 원문 검색을 대체하는 것이 아니라 반복 재합성을 줄이는 보완 계층이다. | 3 | 0 |
| `CLM-F79558D817DF` | C2 | supported | active | 지속 메모리의 유사성이나 최초 성공만으로 재사용 품질을 판단하면 오류·노후 지식이 반복될 수 있으므로, retrieval 이후 결과와 시간 상태를 감사 가능하게 기록하되 그 신호가 claim 신뢰 승격이나 원문 삭제를 자동 수행해서는 안 된다. | 1 | 0 |
| `CLM-FBF709C70CCF` | C2 | supported | active | 같은 제작자 집단의 발표와 구현 저장소는 서로 다른 형식이어도 독립적인 교차검증 두 건으로 세면 안 된다. | 1 | 0 |
| `CLM-FC9028899EE0` | C2 | supported | active | 2026년 한 평가에서 deep-research Agent의 반복 보고서 수정은 기존 내용과 인용 품질의 16~27%를 훼손했다. | 1 | 0 |
| `CLM-FF4A31447E3E` | C2 | supported | active | 프로젝트 지침 탐색에서 Codex는 프로젝트 루트부터 현재 작업 디렉터리까지 내려가며, 각 디렉터리에서 AGENTS.override.md, AGENTS.md, 설정된 fallback 이름 순으로 최대 한 파일을 선택한다. | 1 | 0 |
| `CLM-0733D26931D2` | C1 | supported | active | 고정한 제목·설명과 명시적 상호배타 규칙으로 완료·시청 가능 영상 262개를 의미 선별하면 memory·wiki·second-brain 직접 관련 34개, 인접 32개, 제외 196개로 분류된다. | 1 | 0 |
| `CLM-207429D54323` | C1 | supported | active | append-only Agent log는 감사와 재투영의 권위 있는 기록이어야 하지만 외부 파일·서비스·side effect의 전체 상태는 아니므로 재개와 rollback에는 별도 snapshot, version, digest와 side-effect receipt가 필요하다. | 1 | 0 |
| `CLM-F5982AA50A01` | C1 | supported | active | 2026-07-12 공개 스냅샷에서 AI Engineer 채널의 2026-04-01~2026-07-12 범위 목록은 264개였으며, 이 중 완료·시청 가능 영상은 262개(일반 영상 251, livestream replay 11, Shorts 0)이고 예약 premiere 2개는 연구 분모에서 제외됐다. | 1 | 0 |
| `CLM-F63FA5329493` | C1 | supported | active | 직접 관련 후보 34개 모두에서 자막 입수와 보안 검사를 시도해 34개를 입수했고, 31개는 allow, 3개는 reject였으며, 검토 처분은 promote 14·defer 17·exclude 3이었다; reject 자막은 transcript 결론에 사용하지 않았다. | 1 | 0 |

## 출처

| ID | 레벨 | 생명주기 | 출판 상태 | 원제 | 독립성 그룹 |
|---|---:|---|---|---|---|
| `SRC-08654E066049` | S4 | active | W3C Recommendation | W3C PROV-O | `w3c-prov-standard` |
| `SRC-0C6123529E07` | S4 | active | living official documentation | NCBI public APIs and Entrez E-utilities | `ncbi-eutilities-official` |
| `SRC-228828E53C40` | S4 | active | living official documentation | OpenAI Codex: Custom instructions with AGENTS.md | `openai-codex-official-docs` |
| `SRC-2A53F0CF2080` | S4 | active | ACL 2026 Long Paper | Beyond Single-shot Writing: Deep Research Agents are Unreliable at Multi-turn Report Revision | `multiturndra-study` |
| `SRC-4E9BB033389D` | S4 | active | peer-reviewed journal article | Dissecting GraphRAG | `dissecting-graphrag-study` |
| `SRC-4F5AF5EE0ADB` | S4 | active | living official documentation | GitHub REST API endpoints for commits | `github-rest-commit-official` |
| `SRC-55630C70A5F7` | S4 | active | official framework | NIST AI Risk Management Framework | `nist-ai-rmf` |
| `SRC-56255EE4508A` | S4 | active | ACL 2026 Long Paper | GenProve: Learning to Generate Text with Fine-Grained Provenance | `genprove-study` |
| `SRC-660F983C8346` | S4 | active | ACL 2026 Long Paper | DeepFact: Co-Evolving Benchmarks and Agents for Deep Research Factuality | `deepfact-study` |
| `SRC-696A976CE094` | S4 | active | EACL 2026 Long Paper | Assessing Web Search Credibility and Response Groundedness in Chat Assistants | `web-credibility-study` |
| `SRC-83F06C506C77` | S4 | active | peer-reviewed journal article | Synthesizing scientific literature with retrieval-augmented language models | `openscholar-study` |
| `SRC-8908754F8F5E` | S4 | active | EMNLP 2024 Main Paper | Co-STORM: Collaborative Information Seeking with Humans and Multi-agent Systems | `costorm-study` |
| `SRC-920AB22F540A` | S4 | active | living official documentation | Crossref Retraction Watch production data documentation | `crossref-retraction-watch-official` |
| `SRC-BC899B3F975F` | S4 | active | Findings ACL 2026 | Faithfulness-Aware Uncertainty Quantification for Fact-Checking RAG Output | `franq-study` |
| `SRC-CC24B88C8C02` | S4 | active | NAACL 2024 Long Paper | STORM: Assisting in Writing Wikipedia-like Articles From Scratch | `storm-study` |
| `SRC-E42CA8C4BD30` | S4 | active | ACL 2026 Long Paper | BadScientist | `badscientist-study` |
| `SRC-064C46D22353` | S3 | active | official announcement | How the Open Knowledge Format can improve data sharing | `google-open-knowledge-format` |
| `SRC-1BE9C681A9BA` | S3 | active | open-source implementation | ai-research-os-workshop | `ai-research-os-authors` |
| `SRC-1F603E3131E8` | S3 | active | ICML 2026 regular paper | UMEM: Unified Memory Extraction and Management Framework for Generalizable Memory | `umem-study` |
| `SRC-25318FE73DEB` | S3 | active | ICLR 2026 Poster | LiveResearchBench | `liveresearchbench-study` |
| `SRC-2779A50E2D01` | S3 | active | ICML 2026 regular paper | SafeSearch: Automated Red-Teaming of LLM-Based Search Agents | `safesearch-study` |
| `SRC-477696BD1807` | S3 | active | Version 0.1 Draft; no release tag as of 2026-07-11 | Open Knowledge Format v0.1 Specification | `google-open-knowledge-format` |
| `SRC-62BFE70FD005` | S3 | active | ACL 2026 System Demo | FactSearch: An Interactive Agentic Fact Search System | `factsearch-study` |
| `SRC-9639A8245BE8` | S3 | active | peer-reviewed ACL 2026 main conference | Agentic Memory: Learning Unified Long-Term and Short-Term Memory Management for Large Language Model Agents | `agemem-authors` |
| `SRC-A754BF8665D0` | S3 | active | ICML 2026 regular paper | A-MemGuard | `a-memguard-study` |
| `SRC-AF06BCDC1ED2` | S3 | active | peer-reviewed ACL 2026 main conference | How Memory Management Impacts LLM Agents: An Empirical Study of Experience-Following Behavior | `xiong-memory-management` |
| `SRC-B6EDC3F41C3A` | S3 | active | Findings ACL 2026 | LEDGER: Scaling Agentic Document Editing with Dependency-aware Graph Retrieval | `ledger-study` |
| `SRC-C204B45C665B` | S3 | active | Findings ACL 2026 | RAG or Learning? Understanding the Limits of LLM Adaptation under Continuous Knowledge Drift | `chronos-study` |
| `SRC-C7AAE78B0CC4` | S3 | active | ICLR 2026 Poster | Collaborative Gym | `collaborative-gym-study` |
| `SRC-CB315D66167D` | S3 | active | ACL 2026 System Demo | Hindsight: Structured Agent Memory that Retains, Recalls, and Reflects | `hindsight-memory-study` |
| `SRC-F9BA839FA59D` | S3 | active | peer-reviewed ACL 2026 main conference | Controllable Memory Usage: Balancing Anchoring and Innovation in Long-Term Human-Agent Interaction | `steem-memory-control` |
| `SRC-03641BCFC467` | S2 | active | published video | How Lovable self-improves every hour | `lovable-self-improvement` |
| `SRC-0800355B8885` | S2 | active | derived audit snapshot | AI Engineer channel memory/wiki audit bundle, 2026-04-01 to 2026-07-12 | `youtube-ai-engineer-channel-audit-2026-07-12` |
| `SRC-1C96ABEBBA41` | S2 | active | conference practitioner talk | Turn 10,994 Notes Into Memory | `ai-research-os-authors` |
| `SRC-2E2EA9C214C1` | S2 | active | published video | The Log Is The Agent | `omnara-log-agent` |
| `SRC-3F8E6D0FDE7E` | S2 | active | published video | How we solved Context Management in Agents | `arize-alyx-context` |
| `SRC-43A6E8A3C217` | S2 | active | preprint | SkillWiki: A Living Knowledge Infrastructure for Agent Skills | `skillwiki-study` |
| `SRC-54D07435EB56` | S2 | active | preprint | Demand-Driven Context: A Methodology for Building Enterprise Knowledge Bases Through Agent Failure | `ddc-authors` |
| `SRC-6D473BE1761E` | S2 | active | preprint | From Untrusted Input to Trusted Memory | `memory-poisoning-study` |
| `SRC-7409811C56EB` | S2 | active | published video | Context Is the New Code | `tessl-context-lifecycle` |
| `SRC-8DAAC6D75C2C` | S2 | active | preprint | A Mechanistic View of Authority Hierarchy in LLM Sycophancy | `authority-sycophancy-study` |
| `SRC-9BADA4274C74` | S2 | active | published video | User Signal Dies at the Retrieval Boundary | `starlight-utility-memory` |
| `SRC-AD0B1D50C531` | S2 | active | published video | Continual Learning for AI Agents: From Failures to Durable Improvements | `relai-vcl` |
| `SRC-C071A29F63E6` | S2 | active | preprint | InterDeepResearch: Enabling Human-Agent Collaborative Information Seeking | `interdeepresearch-study` |
| `SRC-CFB88DDE3FF1` | S2 | active | practitioner idea file | LLM Wiki | `karpathy-llm-wiki` |
| `SRC-F55FED177366` | S2 | active | published video | Demand-Driven Context: A Methodology for Coherent Knowledge Bases Through Agent Failure | `ddc-authors` |
| `SRC-F73B1F038B37` | S2 | active | preregistered preprint | Vector RAG vs LLM-Compiled Wiki | `vector-rag-wiki-study` |
