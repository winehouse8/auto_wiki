# AI Engineer memory/wiki channel audit — 2026-04-01..2026-07-12

## Counts

- Date-range tab listings after ID dedupe: **264**
- Completed/viewable research denominator: **262** = 251 regular + 11 livestream replays; Shorts 0
- Upcoming scheduled premieres excluded from denominator: **2**
- Screening: direct 34, adjacent 32, excluded 196
- Direct caption attempts: 34/34; retrieved 34; security allow 31, reject 3
- Review dispositions: promote 14, defer 17, exclude-after-transcript 3

`promote` means worthy of source admission/counter-search or already used as a bounded S2 lead. It does not mean the claim is true or independently validated.

## Scope and reproducibility

- Tabs: `/videos`, `/streams`, `/shorts`, `/podcasts`; podcast tab exposed one playlist container, not a period video row.
- Every 11-character video ID was deduplicated. Title, date, status, type, and channel identity were re-read from each video page.
- Classification was a frozen semantic adjudication using the rule IDs embedded in every manifest row.
- Two tab-listed items were future premieres (`is_upcoming`) and therefore are not videos that could be watched at the snapshot.
- Captions were untrusted data. No credentials/cookies were used and no caption instruction was executed.
- Caption bodies are not included in this report or canonical source because redistribution rights were not established. The security gate may retain content-addressed bytes in ignored local quarantine; they are neither tracked nor promoted. Three oversized/security-rejected event captions were not used for transcript conclusions; only public description chapter metadata was used.

## Direct-candidate review

| Date | Video | Rule | Caption gate | Locator | Disposition | Theme |
|---|---|---|---|---|---|---|
| 2026-07-11 | [Chat and citations won't save your vertical AI - Atul Ramachandran, Filed Inc](https://www.youtube.com/watch?v=RGiXcVxSD3s) | `D1_PERSISTENT_MEMORY_LEARNING` | allow `ADM-26C5AF515293` | 00:08:51 | **exclude** | skills encode repeatable vertical-domain practice; explicit memory wording was not found in the inspected caption window |
| 2026-07-11 | [Develop at Idea Velocity - Jeffrey Lee-Chan, Snapchat](https://www.youtube.com/watch?v=9arM9b7JgOo) | `D1_PERSISTENT_MEMORY_LEARNING` | allow `ADM-6926D3A55A13` | 00:01:27 | **defer** | an agent uses prior requests as conversational task context |
| 2026-07-05 | [Continual Learning for AI Agents: From Failures to Durable Improvements - Soheil Feizi, RELAI](https://www.youtube.com/watch?v=2IxD9OB3XuQ) | `D1_PERSISTENT_MEMORY_LEARNING` | allow `ADM-67D31B298783` | 00:04:27 | **promote** | failures require replayable grading, smallest durable change, and regression control |
| 2026-06-29 | [Your Agent Failed in Prod. Good Luck Reproducing It. - Tisha Chawla & Susheem Koul, Microsoft](https://www.youtube.com/watch?v=Lc8zRh9muoY) | `D4_LOG_REPLAY_SNAPSHOT` | allow `ADM-D75EF9A9C881` | 00:05:39 | **promote** | record/replay supports debugging nondeterministic agent failures without demanding bitwise determinism |
| 2026-06-28 | [User Signal Dies at the Retrieval Boundary - Sonam Pankaj, StarlightSearch](https://www.youtube.com/watch?v=Jx4ZFEAq6bY) | `D1_PERSISTENT_MEMORY_LEARNING` | allow `ADM-4A136815DF3E` | 00:04:32 | **promote** | downstream outcomes are proposed as utility signals for memory retrieval, with drift and noisy-label caveats |
| 2026-06-26 | [A Genius With Amnesia - Victor Savkin, Nx](https://www.youtube.com/watch?v=jVjt-2g8NMY) | `D1_PERSISTENT_MEMORY_LEARNING` | allow `ADM-E9B6861EF116` | 00:03:18 | **defer** | cross-repository agents otherwise start each session blank and make the human act as memory |
| 2026-06-26 | [Turn 10,994 Notes Into Memory - Paul Iusztin, Decoding AI & Louis-François Bouchard, Towards AI](https://www.youtube.com/watch?v=ZRM_TfEZcIo) | `D2_WIKI_SECOND_BRAIN_KB` | allow `ADM-A501A17F7383` | 00:18:36 | **promote** | immutable raw files feed an index and a persistent Wiki synthesis layer |
| 2026-06-25 | [The Log Is The Agent - Ishaan Sehgal, Omnara](https://www.youtube.com/watch?v=UPwGaM2MKHY) | `D4_LOG_REPLAY_SNAPSHOT` | allow `ADM-50C544F56457` | 00:05:38 | **promote** | append-only agent history enables projections, while compaction is lossy and external state remains outside the log |
| 2026-06-11 | [Your Attention Is the Bottleneck, Not Your Agents — Zack Proser, WorkOS](https://www.youtube.com/watch?v=so9l_MwS2yg) | `D1_PERSISTENT_MEMORY_LEARNING` | allow `ADM-7C5B47E01BC5` | 00:13:22 | **defer** | conversation history is mined to improve the system and generate missing skills |
| 2026-06-08 | [Why More Context Makes Your Agent Dumber and What to Do About It — Nupur Sharma, Qodo](https://www.youtube.com/watch?v=EcqMYoIV57A) | `D3_DECISION_CONTEXT_LIFECYCLE` | allow `ADM-34CA627510FB` | 00:24:51 | **defer** | context overload, iterative retrieval, PR history, and accepted/rejected feedback influence later suggestions |
| 2026-06-03 | [AI Engineer Melbourne 2026 Keynote Livestream \| Day 1](https://www.youtube.com/watch?v=wjXowoQ7E8c) | `D5_MIXED_EVENT_EXPLICIT_MEMORY_SEGMENT` | allow `ADM-406441F17CC7` | 01:01:26 | **defer** | a dedicated event chapter addresses why coding agents forget and contrasts memory architecture with context windows |
| 2026-06-03 | [BDD, ADR, PRD, WTF: Capturing Decisions for Humans and AI Alike — Michal Cichra, Safe Intelligence](https://www.youtube.com/watch?v=504PvfXou5Y) | `D3_DECISION_CONTEXT_LIFECYCLE` | allow `ADM-B26ADBF1D827` | 00:07:47 | **promote** | ADRs preserve why and git hooks/CI enforce durable rules outside the prompt |
| 2026-06-02 | [How Lovable self-improves every hour — Benjamin Verbeek, Lovable](https://www.youtube.com/watch?v=KA5kPbdkK2E) | `D1_PERSISTENT_MEMORY_LEARNING` | allow `ADM-106F0474E838` | 00:10:35 | **promote** | model and feature changes rapidly stale injected knowledge; review and holdouts are used before pruning |
| 2026-05-30 | [How I deleted 95% of my agent skills and got better results — Nick Nisi, WorkOS](https://www.youtube.com/watch?v=vy7o1g2iHY8) | `D1_PERSISTENT_MEMORY_LEARNING` | allow `ADM-2F43A5943C09` | 00:09:29 | **promote** | large generated skill context hurt measured performance; evaluation justified aggressive pruning |
| 2026-05-29 | [Why your agents need decision traces, not just documents — Zach Blumenfeld, Neo4j](https://www.youtube.com/watch?v=B9h9ovW5H9U) | `D3_DECISION_CONTEXT_LIFECYCLE` | allow `ADM-4E2204EE1B5B` | 00:03:02 | **defer** | context graphs retain entities and decision traces so past reasoning can be retrieved as precedent |
| 2026-05-28 | [Context Graphs for Explainable, Decision-Aware AI Agents — Andreas Kollegger & Zaid Zaim, Neo4j](https://www.youtube.com/watch?v=abvQEhvRI_c) | `D3_DECISION_CONTEXT_LIFECYCLE` | allow `ADM-0247698C16F8` | 00:15:25 | **defer** | decisions, actions, and rationale are written back as precedent for later agents |
| 2026-05-28 | [Most Enterprise Agentic Projects Are Doomed, Here's Why — Jess Grogan-Avignon & Jack Wang, Accenture](https://www.youtube.com/watch?v=AGkzpxMdPn8) | `D1_PERSISTENT_MEMORY_LEARNING` | allow `ADM-97ED3E1E1042` | 00:17:39 | **defer** | a vendor frames product corrections and user behavior as a compounding living memory |
| 2026-05-25 | [Bounded Autonomy: Between Free Will and Determinism — Angus J. McLean, Oliver](https://www.youtube.com/watch?v=t4359sKBu4w) | `D1_PERSISTENT_MEMORY_LEARNING` | allow `ADM-822099EBE7B5` | 00:10:38 | **exclude** | memory and compaction appear only as an experimental harness suggestion in a broader autonomy talk |
| 2026-05-22 | [Fast Models Need Slow Developers — Sarah Chieng, Cerebras](https://www.youtube.com/watch?v=TeGsFFNqRLA) | `D1_PERSISTENT_MEMORY_LEARNING` | allow `ADM-26ED4B6C1FB6` | 00:15:50 | **promote** | a four-file external memory lets new sessions resume bounded goals |
| 2026-05-16 | [Connecting the Dots with Context Graphs — Stephen Chin, Neo4j](https://www.youtube.com/watch?v=eW_vxrjvERk) | `D3_DECISION_CONTEXT_LIFECYCLE` | allow `ADM-39C0AB129AD1` | 00:13:21 | **defer** | a graph carries policies and reasoning behind past decisions, not only retrieved facts |
| 2026-05-16 | [AIE Singapore Day 1 ft. Minister, NanoClaw, OpenAI, Google, Vercel, Cursor & more](https://www.youtube.com/watch?v=_xQnSNlBP_w) | `D2_WIKI_SECOND_BRAIN_KB` | reject `ADM-A9C0E203A5C3` | description chapter 00:41:40 | **defer** | metadata identifies a second-brain workflow chapter emphasizing personal understanding and accountability |
| 2026-05-13 | [Self-Training Agents: Hermes Agent, HF Traces, Skills, MCP & Finetuning  — Merve Noyan, Hugging Face](https://www.youtube.com/watch?v=OV56RddyFuU) | `D1_PERSISTENT_MEMORY_LEARNING` | allow `ADM-B8D27F426710` | 00:07:56 | **exclude** | memory management is a short Hermes-agent segment inside a broad Hugging Face ecosystem talk |
| 2026-05-12 | [Give Your Agent a Computer — Nico Albanese, Vercel](https://www.youtube.com/watch?v=wflNENRSUb4) | `D1_PERSISTENT_MEMORY_LEARNING` | allow `ADM-EA135A102802` | 00:57:20 | **defer** | persistent sandbox files and deterministic retrieval are proposed for core memory and conversation history |
| 2026-05-11 | [Viktor: AI Coworker That Lives in Slack — Fryderyk Wiatrowski](https://www.youtube.com/watch?v=ohKt066uFhg) | `D1_PERSISTENT_MEMORY_LEARNING` | allow `ADM-D8754BF4E2EB` | 00:07:12 | **defer** | multi-user Slack-agent memory raises isolation and scaling problems |
| 2026-05-10 | [Two Roads to Durable Agents: Replay vs. Snapshot — Eric Allam, CEO, Trigger.dev](https://www.youtube.com/watch?v=svCnShDvgQg) | `D4_LOG_REPLAY_SNAPSHOT` | allow `ADM-A08A794959D5` | 00:09:35 | **promote** | context-log durability and execution-state durability require different mechanisms; snapshots restore compute state |
| 2026-05-10 | [How we solved Context Management in Agents — Sally-Ann Delucia](https://www.youtube.com/watch?v=esY99nYXxR4) | `D6_WORKING_CONTEXT_MEMORY_STORE` | allow `ADM-844E8A203EC9` | 00:06:15 | **promote** | naive truncation and summarization lose reasoning; retrievable spill and long-session evaluation are proposed |
| 2026-05-05 | [Demand-Driven Context: A Methodology for Coherent Knowledge Bases Through Agent Failure](https://www.youtube.com/watch?v=_QAVExf_1uw) | `D2_WIKI_SECOND_BRAIN_KB` | allow `ADM-128EFD21AA6C` | 00:16:05 | **promote** | failed tasks expose knowledge gaps, followed by human validation before knowledge-base graduation |
| 2026-05-03 | [Context Is the New Code — Patrick Debois, Tessl](https://www.youtube.com/watch?v=bSG9wUYaHWU) | `D3_DECISION_CONTEXT_LIFECYCLE` | allow `ADM-636C5C91C52C` | 00:03:04 | **promote** | context is treated as a versioned generate-evaluate-distribute-observe lifecycle |
| 2026-05-03 | [Mergeable by default: Building the context engine to save time and tokens — Peter Werry, Unblocked](https://www.youtube.com/watch?v=5ID22ACI7IM) | `D3_DECISION_CONTEXT_LIFECYCLE` | allow `ADM-1A2153BDCA9A` | 00:15:42 | **defer** | organizational history and prior decisions help resolve conflicting context for agents |
| 2026-05-02 | [I Gave an AI Agent the Keys to My Life (Here's What Happened) — Radek Sienkiewicz (@velvetshark-com)](https://www.youtube.com/watch?v=sJ2jc7leKBk) | `D1_PERSISTENT_MEMORY_LEARNING` | allow `ADM-38279B46494C` | 00:01:02 | **defer** | a personal agent builds on long-lived activity memory, illustrating permission and autonomy risk |
| 2026-04-28 | [Building your own software factory — Eric Zakariasson, Cursor](https://www.youtube.com/watch?v=rnDm57Py54A) | `D1_PERSISTENT_MEMORY_LEARNING` | allow `ADM-66CFC9AEBA45` | 00:30:15 | **defer** | a plugin extracts reusable rules from agent transcripts as continual learning |
| 2026-04-21 | [AIE Miami Day 2 ft. Cerebras, OpenCode, Cursor, Arize AI, and more!](https://www.youtube.com/watch?v=DeM_u2Ik0sk) | `D5_MIXED_EVENT_EXPLICIT_MEMORY_SEGMENT` | reject `ADM-D876BB4A014D` | description chapters 02:27:02 / 05:17:08 / 05:35:07 | **defer** | metadata exposes separate decision-trace, agentic-memory, and continuous-learning chapters in a mixed event |
| 2026-04-09 | [AIE Europe Keynotes & OpenClaw ft Deepmind, OpenAI, Vercel, @pragmaticengineer , @mattpocockuk](https://www.youtube.com/watch?v=O_IMsEg91g8) | `D5_MIXED_EVENT_EXPLICIT_MEMORY_SEGMENT` | reject `ADM-9AD3913E71DD` | description schedule 12:20pm | **defer** | metadata advertises a memory-architecture/formal-verification session in a mixed event |
| 2026-04-08 | [Cognitive Exhaust Fumes, or: Read-Only AI Is Underrated — Šimon Podhajský, Head of AI, Waypoint](https://www.youtube.com/watch?v=u0TOSBbAw7c) | `D2_WIKI_SECOND_BRAIN_KB` | allow `ADM-36EFCA0F7453` | 00:01:12 | **promote** | a read-only personal intelligence layer finds cross-source patterns without write authority |

## Rule definitions

- `A1_RETRIEVAL_RAG_INDEX`: Retrieval/search/RAG/indexing is central, but durable evidence-governed Wiki memory is not.
- `A2_EVAL_OBSERVABILITY_REPRODUCTION`: Evaluation, observability, feedback, or reproducibility is central and informs the harness indirectly.
- `A3_SKILL_CONTEXT_PACKAGING`: Skills or context packaging are central; persistent factual memory is secondary.
- `A4_SOURCE_DISCOVERY_RESEARCH`: Research/source access is central; it informs ingestion rather than durable memory itself.
- `D1_PERSISTENT_MEMORY_LEARNING`: Central subject is persistent agent memory, memory hygiene, or durable learning from prior runs.
- `D2_WIKI_SECOND_BRAIN_KB`: Central subject or explicit event chapter is a Wiki, knowledge base, second brain, or personal intelligence layer.
- `D3_DECISION_CONTEXT_LIFECYCLE`: Central subject is durable decision/context artifacts, their lifecycle, provenance, or later reuse.
- `D4_LOG_REPLAY_SNAPSHOT`: Central subject is append-only history, replay, snapshot, or restoration of agent state.
- `D5_MIXED_EVENT_EXPLICIT_MEMORY_SEGMENT`: Mixed livestream contains an explicitly titled memory/second-brain/decision-trace chapter.
- `D6_WORKING_CONTEXT_MEMORY_STORE`: Central subject is working-context preservation with a retrievable memory store.
- `X0_UPCOMING_NOT_VIEWABLE`: Scheduled premiere was listed in the tab but not viewable at the audit snapshot.
- `X1_HARDWARE_OR_MODEL_MEMORY`: Memory-like wording refers to hardware/model capacity rather than durable agent knowledge.
- `X2_NON_WIKI_PERSONA_MEMORY`: Memory wording concerns entertainment/persona continuity rather than research/Wiki knowledge.
- `X3_MIXED_EVENT_NO_QUALIFYING_CHAPTER`: Mixed livestream has no explicit qualifying memory/Wiki/second-brain chapter in metadata.
- `X4_OUT_OF_SCOPE`: Title and description do not make durable memory/Wiki/second-brain or an adjacent retrieval/evaluation mechanism central.

## Upcoming rows

- `OqM67QG_Ikk` — From fork() to Fleet: Designing an Agent Sandbox Cloud — Abhishek Bhardwaj, OpenAI — upload date 2026-07-08, release 20260713, status `is_upcoming`
- `xg1zNlzw7Jk` — Claws Out: Securing and Building with OpenClaw - Nick Taylor, Pomerium — upload date 2026-04-09, release 20260711, status `is_upcoming`

## Artifact integrity

- Canonical source: `SRC-0800355B8885`
- Canonical bundle: `raw/sources/SRC-0800355B8885/ai-engineer-memory-wiki-audit-bundle-2026-07-12.json`
- Bundle SHA-256: `bea5e7289f0022af81ca1ec81de44e624c32a93ada4ae7e94354cb3450623980`
- Manifest: `ai-engineer-2026-04-01_to_2026-07-12-manifest.json`
- Manifest SHA-256: `15c1ba8fe98eecb2224bc68c9576929f3e0ac83d33606b0eda3e3a7176509807`
- Direct review: `ai-engineer-direct-caption-review.json`
- Direct review SHA-256: `9a9df8415e9a2aeb8eede2348e72bdcdf5beaab6f98a65dedfe8dc1d5ff6e16d`

The manifest itself is the canonical 264-row metadata/classification snapshot. Temporary per-video metadata and caption paths are intentionally not embedded; their hashes and security admission IDs are retained.
