# AI Engineer 2026 메모리·위키 연구 감사 보고서

작성일: 2026-07-12  
채널 조사 범위: 2026-04-01–2026-07-12 (양 끝 날짜 포함)  
대상: [AI Engineer 공식 YouTube 채널](https://www.youtube.com/@aiDotEngineer/videos), channel ID `UCLKPca3kwwd-B59HNr-_lvA`  
하네스 적용 결정: [RFC-5D91E03B5BC5](../governance/proposals/rfc-5d91e03b5bc5-living-wiki-v4-1-memory-hygiene-and-controlled-learning.md), `implemented`  

## 0. 결론

조사 시점에 채널의 공개 tab 네 곳을 교차 열거해 기간 내 목록 행 264개를 확인했다. 이 중 2개는 아직 시청할 수 없는 예약 premiere였으므로 연구 분모에서 제외했다. 완료·시청 가능 영상 262개는 일반 영상 251개, livestream replay 11개, Shorts 0개다. 고정한 개별 영상 제목·설명과 명시적 상호배타 규칙을 적용해 34개를 memory·Wiki·second brain·persistent knowledge에 **직접 관련**, 32개를 retrieval·context engineering·평가처럼 **인접 관련**, 나머지 196개를 이번 질문과 무관한 것으로 분류했다. 직접 후보 34개는 모두 자막 입수를 시도해 34개를 입수했고, 보안 gate `allow` 31개만 자막 구간을 사용했으며 `reject` 3개는 공개 metadata만 검토했다. 이는 채널 전체의 불변 역사나 영상 내용의 진실 판정이 아니라, 2026-07-12에 관찰 가능한 공개 상태에 대한 content-addressed 선별 snapshot이다.

최종적으로 새 YouTube 영상 7개를 S2 lead로 admission했고, 기존 AI Research OS 발표 1개를 함께 재검토했다. 저자 preprint 1개와 서로 다른 연구 그룹의 ACL 2026 논문 3개를 원출처 교차검토에 사용했다. **어떤 영상·제품의 성능 주장도 Wiki claim의 효능 사실로 승격하지 않았다.** 영상은 설계 질문과 구현 단서를 찾는 lead이며, 같은 발표자·회사·제품의 영상, 블로그, 문서, 저장소는 형식이 달라도 하나의 독립성 그룹으로 계산했다.

연구에서 채택한 것은 특정 vendor 제품이나 graph/vector architecture가 아니라 다음의 제한된 운영 원칙이다.

- Agent 실패는 조사 우선순위 신호이지 지식의 사실성 증명이 아니다.
- retrieval 이후 결과와 staleness를 감사 가능하게 기록하되 trust, C-level, source level, ranking, 삭제를 자동 변경하지 않는다.
- stale 표시는 경고이며 거짓 판정이 아니다.
- append-only log는 감사와 재투영의 기록이지만 외부 세계 전체 상태는 아니므로 snapshot, version, digest, side-effect receipt가 별도로 필요하다.
- 사용자는 `wiki-first`, `fresh-check`, `strict-evidence`처럼 과거 기억에 의존하는 정도를 명시적으로 조절할 수 있어야 한다.
- lifecycle은 삭제보다 `deprecated`, `superseded`, `invalidated`, `archived`와 replacement 관계를 우선한다.

반대로 graph DB, vector DB, learned memory policy, vendor utility score를 자동 epistemic ranking이나 자동 삭제 근거로 쓰는 방안은 채택하지 않았다.

## 1. 상태 기준과 재현 방법

### 1.1 저장소 상태 기준

매 turn bootstrap에 따라 먼저 `wiki/index.md`를 읽고 관련 concept, claim, source 원장을 확인했다. 최종 render의 index는 이 연구의 source·claim·implemented RFC·feedback을 포함한 canonical state를 가리킨다. 이 보고서를 닫은 시점의 규모는 47개 source와 33개 claim이다. 아래 평가는 파생 Wiki와 다음 canonical 원장을 함께 기준으로 한다.

- `state/sources.json`
- `state/claims.json`
- `state/admissions.json`
- `state/proposals.json`
- `state/memory_feedback.json`
- `state/events.jsonl`
- 구현 완료된 `governance/proposals/rfc-5d91e03b5bc5-living-wiki-v4-1-memory-hygiene-and-controlled-learning.md`

초기 설계 조사 단계에서는 네 신규 해석 claim이 `C0/open`으로 생성됐다. 이후 전체 하네스 통합 단계에서 canonical `evaluate`를 실행한 결과 세 claim은 C2, log 경계 claim은 C1이 됐다. 전수감사의 coverage·분류·자막 절차 claim 세 개는 한 번의 agent audit에만 의존하므로 모두 C1이다. 독립 review는 여전히 0이므로 C3/C4로 승격하지 않았고, RFC 승인을 factual review로 세지 않았다.

### 1.2 채널 열거

조사 절차는 다음과 같다.

1. 공식 handle과 channel ID를 함께 확인했다.
2. `/videos`, `/streams`, `/shorts`, `/podcasts` 공개 tab을 각각 열거하고 video ID로 중복 제거했다.
3. 기간 필터를 `2026-04-01 <= upload_date <= 2026-07-12`로 고정하고 예약 premiere는 목록에는 남기되 완료·시청 가능 연구 분모에서 제외했다.
4. 264개 행 각각의 날짜·제목·설명·상태는 개별 player metadata로 다시 확인하고 metadata hash를 고정했다.
5. 고정한 제목·설명에 문서화한 직접/인접/제외 규칙을 적용했다. 직접 후보 34개 모두의 자동 자막 입수를 시도하고 각각 보안 영수증과 `promote`, `defer`, `exclude` 처분을 남겼다.
6. 보안 gate가 거부한 3개 자막은 override하지 않고 공개 metadata chapter만 사용했다. 자막 재배포 권리가 확인되지 않아 caption body는 canonical bundle에서 제외했다.
7. 직접 후보와 중요 인접 후보에서 발표자, 소속, 설명의 외부 링크, 원 논문·공식 저장소·제품 문서를 추적했다.
8. messenger와 message를 별도 평가하고, 제품 판매자·방법 저자·평가 주체가 같으면 같은 independence group으로 묶었다.
9. 반증 검색과 publication status 확인 후에만 source admission을 수행했다.

같은 시점의 점검 명령 예시는 다음과 같다. 이는 외부 콘텐츠를 실행한다는 뜻이 아니라 공개 metadata를 읽는 절차다.

```bash
yt-dlp --flat-playlist --dump-single-json \
  'https://www.youtube.com/@aiDotEngineer/videos'

yt-dlp --flat-playlist --dump-single-json \
  'https://www.youtube.com/@aiDotEngineer/streams'

yt-dlp --skip-download \
  --print '%(id)s\t%(upload_date)s\t%(title)s' \
  'https://www.youtube.com/watch?v=VIDEO_ID'
```

### 1.3 분류 결과

| 분류 | 수 | 포함 기준 | 대표 예시 | 처리 |
|---|---:|---|---|---|
| 직접 관련 | 34 | 장기·지속 메모리, 지식 기반·Wiki, 세컨드 브레인, 맥락 생명주기·위생, 실패 기반 학습, 사건 원장 기반 연속성을 직접 주장하거나 복합 행사 metadata에 명시적 관련 장이 있음 | 원제: *Demand-Driven Context*, *The Log Is The Agent*, *Turn 10,994 Notes Into Memory*, *Continual Learning for AI Agents* | 자막 입수 34/34, 보안 허용 31·거부 3, 처분 승격 14·보류 17·제외 3. 그중 신규 S2 출처 입수 7개와 기존 S2 재검토 1개 |
| 인접 관련 | 32 | RAG·검색, MCP·Skill 맥락, 장문 맥락·캐시, 평가·관찰성이 핵심이며 지속 Wiki 자체는 부차적 | 원제: *How we taught agents to use good retrieval*, *RAG is dead, right??*, *Agentic Search for Context Engineering*, *MCP = Mega Context Problem* | 설계 반론과 후속 조사 단서로만 보존 |
| 제외 | 196 | UI 생성, 음성·영상, 일반 코딩 시연, 배포, 영업·행사 소개 등 이번 연구 질문에 직접 답하지 않음 | 개별 제목 생략 | 증거로 사용하지 않음 |
| 완료·시청 가능 합계 | 262 | 조사 시점 공개 탭에서 중복을 제거하고 기간 필터를 통과한 완료 항목: 일반 영상 251, 실시간 방송 재생 11, Shorts 0 |  | 의미 분류의 분모 |
| 예약 공개 | 2 | 기간 내 목록에는 나타났지만 스냅샷 시점에 아직 시청 불가 |  | 명세표에는 보존하고 연구 분모에서는 제외 |
| 목록 행 합계 | 264 | 완료·시청 가능 262 + 예약 공개 2 |  |  |

34개와 32개는 관련성 분류이지 신뢰 등급이 아니다. 전체 264개 행, 분류 규칙·이유, per-video metadata hash, direct-candidate security receipt와 처분은 `SRC-0800355B8885`의 immutable bundle에 저장했다. bundle SHA-256은 `bea5e7289f0022af81ca1ec81de44e624c32a93ada4ae7e94354cb3450623980`이다. 이 agent 단독 분류 claim은 `CLM-0733D26931D2` C1이며, 독립 재분류 전에는 더 높이지 않는다.

34개 직접 후보의 영상별 날짜·제목·규칙·보안 admission ID·정확한 timestamp 또는 metadata locator·처분은 [전수 직접 후보 감사표](AI_ENGINEER_DIRECT_VIDEO_AUDIT_2026.md)에 모두 공개했다. 이 표의 `promote`는 후속 source admission·counter-search 가치가 있다는 뜻이며 사실성이나 C-level 승격을 뜻하지 않는다.

### 1.4 열거 한계

- 삭제·비공개·unlisted 영상은 현재 채널 목록으로 복원할 수 없다.
- 공개 tab과 Atom feed를 교차 확인했어도 YouTube가 노출하지 않는 항목과 과거 metadata 변경 이력은 복원할 수 없다.
- 제목·설명·게시 metadata는 채널 운영자가 변경할 수 있다.
- YouTube UI의 지역·시간대와 metadata API의 날짜가 하루 다를 수 있다. 예를 들어 RELAI 영상은 Pacific 기준 `2026-07-04`로 보일 수 있으나 현재 원장은 Seoul 기준 게시일 `2026-07-05`를 사용한다.
- 완료 영상 262개 모두의 자막을 읽은 것은 아니다. 모든 영상은 제목·설명으로 선별했고 직접 후보 34개의 자막만 입수·검토했으므로 분류 규칙의 false negative가 남을 수 있다.
- 검색 순위, 조회 수, 좋아요, 발표자의 유명세는 claim support로 사용하지 않았다.

## 2. 등록 출처 감사표

| 출처 ID | 자료·날짜 | 수준·독립성 그룹 | 보존·상태 | 이 보고서에서의 역할 |
|---|---|---|---|---|
| `SRC-0800355B8885` | AI Engineer 채널 감사 bundle, 2026-07-12 스냅샷 | S2, `youtube-ai-engineer-channel-audit-2026-07-12` | JSON 원문 보존, SHA-256 `bea5e…3980` | 264개 전수 목록, 262개 분모, 34/32/196 분류, 34개 자막 게이트·처분의 범위 근거, 단일 Agent 분류라 C1 한정 |
| `SRC-F55FED177366` | [Demand-Driven Context 영상](https://www.youtube.com/watch?v=_QAVExf_1uw), 2026-05-05 | S2, `ddc-authors` | 메타데이터 전용, 공개 영상 | 방법 발견 단서, 같은 저자 preprint와 독립 아님 |
| `SRC-AD0B1D50C531` | 원제 [Continual Learning for AI Agents](https://www.youtube.com/watch?v=2IxD9OB3XuQ) 영상, 2026-07-05 | S2, `relai-vcl` | 메타데이터 전용, 공개 영상 | 재실행과 회귀 중심 하네스 원칙의 단서 |
| `SRC-03641BCFC467` | 원제 [How Lovable self-improves every hour](https://www.youtube.com/watch?v=KA5kPbdkK2E) 영상, 2026-06-02 | S2, `lovable-self-improvement` | 메타데이터 전용, 공개 영상 | 운영 피드백 순환 사례 |
| `SRC-2E2EA9C214C1` | 원제 [The Log Is The Agent](https://www.youtube.com/watch?v=UPwGaM2MKHY) 영상, 2026-06-25 | S2, `omnara-log-agent` | 메타데이터 전용, 공개 영상 | 사건 기록과 외부 상태 경계의 단서 |
| `SRC-3F8E6D0FDE7E` | 원제 [How we solved Context Management in Agents](https://www.youtube.com/watch?v=esY99nYXxR4) 영상, 2026-05-10 | S2, `arize-alyx-context` | 메타데이터 전용, 공개 영상 | 절단·요약·검색 가능한 외부 저장 실패의 단서 |
| `SRC-7409811C56EB` | 원제 [Context Is the New Code](https://www.youtube.com/watch?v=bSG9wUYaHWU) 영상, 2026-05-03 | S2, `tessl-context-lifecycle` | 메타데이터 전용, 공개 영상 | 맥락 수명주기의 틀 |
| `SRC-9BADA4274C74` | 원제 [User Signal Dies at the Retrieval Boundary](https://www.youtube.com/watch?v=Jx4ZFEAq6bY) 영상, 2026-06-28 | S2, `starlight-utility-memory` | 메타데이터 전용, 공개 영상 | 결과 피드백 문제의 단서, 효용 자동 순위화는 거부 |
| `SRC-1C96ABEBBA41` | 원제 [Turn 10,994 Notes Into Memory](https://www.youtube.com/watch?v=ZRM_TfEZcIo) 영상, 2026-06-26 | S2, `ai-research-os-authors` | 학회 실무자 발표, 불변 스냅샷 없음 | `raw→index→Wiki`와 지속 합성의 기존 씨앗 |
| `SRC-54D07435EB56` | 원제 [Demand-Driven Context](https://arxiv.org/abs/2603.14057) 사전공개 논문, 2026-03-14 | S2, `ddc-authors` | 사전공개본, 메타데이터 전용 | 영상의 원 방법·한계 확인, 동료검토 아님 |
| `SRC-AF06BCDC1ED2` | 원제 [How Memory Management Impacts LLM Agents](https://aclanthology.org/2026.acl-long.27/) 논문, ACL 2026 | S3, `xiong-memory-management` | 동료검토됨, CC BY 4.0 추출 본문 보존 | 오류 메모리 재사용·후속 피드백의 독립 실증 근거 |
| `SRC-9639A8245BE8` | 원제 [Agentic Memory](https://aclanthology.org/2026.acl-long.981/) 논문, ACL 2026 | S3, `agemem-authors` | 동료검토됨, 원문은 게이트에서 미승격 | 명시적 메모리 생명주기 작업의 연구 맥락 |
| `SRC-F9BA839FA59D` | 원제 [Controllable Memory Usage](https://aclanthology.org/2026.acl-long.670/) 논문, ACL 2026 | S3, `steem-memory-control` | 동료검토됨, CC BY 4.0 추출 본문 보존 | 앵커링과 사용자 메모리 의존도 제어 근거 |

S2는 “틀렸다”는 뜻이 아니라 저자·실무자의 직접 설명이지만 독립적인 효과 검증이 부족하다는 뜻이다. S3 논문도 해당 benchmark와 주장 범위에 대한 강한 원출처일 뿐, factual Wiki 전체에 그대로 일반화되지 않는다.

## 3. 심층 후보 목록 비판적 분석

### 3.1 Demand-Driven Context — 실패를 지식 공백 신호로 사용

- 영상 원제: [Demand-Driven Context: A Methodology for Coherent Knowledge Bases Through Agent Failure](https://www.youtube.com/watch?v=_QAVExf_1uw), 2026-05-05 — Agent 실패를 지식 공백 신호로 다룬 발표
- 발표자: Raj Navakoti, 발표상 IKEA Digital 실무자
- 원 방법: [arXiv preprint 2603.14057](https://arxiv.org/abs/2603.14057), 2026-03-14
- 구현: [ea-toolkit/ddc](https://github.com/ea-toolkit/ddc)
- 발표 자료: [rajnavakoti.com presentation](https://rajnavakoti.com/presentations/ai-engineer-workshop/)
- 원장: 영상 `SRC-F55FED177366`, preprint `SRC-54D07435EB56`; 둘 다 `ddc-authors`이므로 독립 근거 1그룹

**Messenger.** 실제 enterprise knowledge 문제를 다룬 방법 저자이고 공개 preprint·repository·worked example을 제공한다. 반면 저자 자신이 방법을 홍보하고 스스로 평가한다. 발표 당시 직함과 현재 공개 profile의 직함도 다를 수 있으므로 소속은 `as-of` 날짜를 붙여야 한다.

**Message.** 미리 거대한 문서 체계를 만들지 않고 실제 문제 해결에서 Agent가 실패한 지점을 기록한 뒤, 사람이 최소한의 누락 지식을 검증·추가하고 Git/Markdown으로 graduation하는 방식이다. 사람을 단순 승인자가 아니라 원인 확인과 context 경계 설정에 참여시키는 점은 이 Wiki 철학과 맞는다.

**검증이 필요한 정확한 주장.**

- Agent failure가 knowledge gap을 신뢰성 있게 식별하는가, 아니면 tool·planning·permission·model failure를 지식 문제로 오인하는가.
- demand-driven human curation이 top-down documentation이나 자동 context optimization보다 정확하고 비용 효율적인가.
- 20–30회 cycle 뒤 수렴한다는 가설이 다른 조직·domain에서도 성립하는가.
- worked example의 9회 cycle·46 entity는 설명용 사례인지 독립 평가인지.
- 저장소에서 언급되는 50-ticket 평가의 `4.49 vs 3.20`, `Cohen's d=1.84`, `p<.001`에 대해 manuscript, task sampling, rubric, assessor blindness, raw result가 공개되는가.

**한계와 결정.** preprint는 §3.5에서 convergence를 검증되지 않은 가설로 남기고, 인간 expert 의존·큐레이션 주관성·PR review 이외의 dispute resolution 부재를 인정한다. repository의 “peer-reviewed research” 표현은 공개된 arXiv status와 구분해야 한다. 따라서 failure-driven **우선순위화**만 채택했고 자동 graduation·convergence·효능은 채택하지 않았다.

### 3.2 Continual Learning for AI Agents — 재생 가능한 실패에서 최소 변경

- 영상 원제: [Continual Learning for AI Agents: From Failures to Durable Improvements](https://www.youtube.com/watch?v=2IxD9OB3XuQ), 2026-07-05 — 실패를 지속 개선으로 전환하는 발표
- 발표자: `Soheil Feizi`, 메릴랜드 대학교 교수이자 `RELAI` 창업자·최고과학책임자(`CSO`)
- 공식 설명: [Principles of Continual Learning for AI Agents](https://relai.ai/blog/principles-of-continual-learning-for-ai-agents)
- 제품: [RELAI](https://relai.ai/)
- 원장: `SRC-AD0B1D50C531`, independence group `relai-vcl`

**Messenger.** 관련 분야 연구 경력을 가진 학자라는 전문성이 높다. 동시에 평가 대상 제품의 창업자이므로 RELAI 성능 수치는 founder self-report다. 발표·회사 블로그·제품 페이지는 독립 근거로 나누지 않는다.

**Message.** 실패를 replay 가능한 환경으로 재구성하고, 수정 위치를 model·harness·memory 중에서 고르며, 과거 task regression을 유지하고, 가장 작은 durable change를 적용해야 한다는 네 원칙을 제시한다. 이는 기존 `failure → minimal RFC → fixed benchmark → rollback` loop를 강화하는 유용한 설계 언어다.

**검증이 필요한 정확한 주장.**

- production log와 feedback으로 실패의 인과 조건을 얼마나 충실히 재현할 수 있는가.
- “agent가 잊지 않았음을 증명”하는 holdout·frozen regression이 benchmark contamination과 evaluator drift를 막는가.
- 발표에서 언급한 Meridian `87→97` 평균 score 개선의 dataset, 기간, evaluator, repeated trial.
- 회사가 제시하는 `15–40% task-success uplift`, 최대 `80% token` 절감, day-to-minutes 개선의 공개 protocol과 비용·회귀 결과.

**한계와 결정.** 공개 paper, code, independent benchmark를 찾지 못했다. 제품 수치는 승격하지 않고 replay, regression, smallest-change 원칙만 RFC의 proposal template과 acceptance gate에 반영했다.

### 3.3 Lovable — 운영 마찰을 PR 후보로 바꾸는 인간 승인 순환

- 영상 원제: [How Lovable self-improves every hour](https://www.youtube.com/watch?v=KA5kPbdkK2E), 2026-06-02
- 발표자: Benjamin Verbeek, Lovable agent team
- 공식 글: [We gave our agent a vent tool](https://lovable.dev/blog/we-gave-our-agent-a-vent-tool)
- 원장: `SRC-03641BCFC467`, independence group `lovable-self-improvement`

**Messenger.** 실제 product telemetry와 운영 failure에 접근한 insider이며 false positive와 human review를 공개했다. 동시에 Lovable의 “self-improving agent”를 홍보하는 당사자다.

**Message.** stuck session과 unblocked session을 비교하고, agent가 friction을 vent channel로 보내며 debugging agent가 cluster·deduplicate해 PR을 제안한다. 자동 개선이라고 부르지만 실제 merge와 위험 판단에는 사람이 남아 있다.

**검증이 필요한 정확한 주장.**

- 하루 약 200,000 project라는 분모와 측정 기간·중복 project 정의.
- vent message 약 20%가 mergeable PR로 이어졌다는 판정 기준.
- 자동 PR false-positive 약 50%, 하루 약 10개 merged fix의 사람 review 비용과 regression rate.
- holdout 배치·randomization과 비교군 품질.
- vent spike가 incident alert보다 먼저 나타난 사례의 sensitivity와 false alarm.

**한계와 결정.** raw telemetry, code, benchmark가 공개되지 않았다. 또한 model·feature가 바뀌면 과거 context가 stale해지는 “context rot”을 발표 자체가 인정한다. failure clustering과 audit-only outcome feedback은 채택했지만 자동 PR merge, 성공 신호에 따른 trust 승격, stale knowledge 자동 삭제는 거부했다.

### 3.4 The Log Is The Agent — 사건 로그와 외부 상태의 경계

- 영상 원제: [The Log Is The Agent](https://www.youtube.com/watch?v=UPwGaM2MKHY), 2026-06-25
- 발표자: Ishaan Sehgal, Omnara CEO
- 현재 제품: [Omnara](https://www.omnara.com/)
- 글 미러 원제: [The Log Is The Agent](https://dev.to/dailycontext/the-log-is-the-agent-5096)
- 과거 저장소: [omnara-ai/omnara](https://github.com/omnara-ai/omnara), 2026-02-02 archived
- 원장: `SRC-2E2EA9C214C1`, independence group `omnara-log-agent`

**Messenger.** agent infrastructure를 직접 만드는 product builder다. 동시에 현재 구현이 공개되지 않은 상업 서비스의 CEO이며, archived repository는 현 제품 architecture의 증거가 아니다.

**Message.** append-only log를 권위 있는 실행 역사로 보고 projection과 compaction을 파생 view로 취급한다. durability, resume, fork, audit에는 좋은 출발점이다.

**검증이 필요한 정확한 주장.**

- log만으로 agent를 완전히 reconstruct·resume할 수 있는가.
- 모델·도구·프롬프트·설정 버전, 작업 공간과 커밋되지 않은 파일, 자격증명 상태, 네트워크 응답, 외부 서비스 부작용을 어디까지 스냅샷으로 남기는가.
- replay idempotency, multi-writer ordering, retry와 irreversible action receipt를 어떻게 보장하는가.
- compaction 뒤에도 원래 사건과 privacy/retention 요구를 동시에 지킬 수 있는가.

**한계와 결정.** 발표 05:36–06:32도 외부 side effect와 world state가 log 밖에 있음을 인정한다. 따라서 “log가 곧 agent”라는 강한 동일시는 거부했다. append-only audit log와 projection 원칙은 유지하되 resume·rollback에는 snapshot/version/digest/side-effect receipt를 요구한다.

### 3.5 Arize — 작업 맥락 위생과 검색 가능한 외부 저장

- 영상 원제: [How we solved Context Management in Agents](https://www.youtube.com/watch?v=esY99nYXxR4), 2026-05-10
- 발표자: Sally-Ann DeLucia, Arize
- 공식 글 원제: [How to manage LLM context windows for AI agents](https://arize.com/blog/how-to-manage-llm-context-windows-for-ai-agents/), [Context management in agent harnesses](https://arize.com/blog/context-management-in-agent-harnesses/) — Agent 맥락 창과 하네스의 맥락 관리를 다룬 글
- 원장: `SRC-3F8E6D0FDE7E`, independence group `arize-alyx-context`

**Messenger.** 장기 실행 agent를 운영한 product team으로서 구체적인 failure mode에 직접 접근한다. 그러나 Arize의 agent·observability 제품을 설명하는 vendor source다.

**Message.** naive truncation은 continuity를 깨고, LLM summary는 미래에 필요한 세부를 예측할 수 없어 lossy하며, ID를 남긴 middle truncation과 retrievable memory, message deduplication, subagent 격리가 더 낫다는 production lesson이다.

**검증이 필요한 정확한 주장.**

- ID 기반 middle truncation이 head/tail truncation이나 structured summary보다 미래 task success를 높이는가.
- summary 손실의 분포와 어떤 정보가 미래에 필요할지 예측 불가능하다는 범위.
- high-volume task에서 subagent가 가장 좋은 일반 해법인가.
- 장기 세션 평가의 작업, 모델, 표본 크기, 원시 비교 결과, 비용.

**한계와 결정.** 공개 code와 comparative benchmark가 없다. 전체 Wiki memory policy로 일반화하지 않고 working-context에서 원문 locator를 남기는 retrievable spill, deduplication, long-session regression이라는 제한된 구현 원칙만 채택 후보로 삼았다.

### 3.6 Tessl CDLC — 맥락을 버전이 있는 자료로 관리

- 영상 원제: [Context Is the New Code](https://www.youtube.com/watch?v=bSG9wUYaHWU), 2026-05-03
- 발표자: Patrick Debois, Tessl
- 공식 글: [Context Development Lifecycle](https://tessl.io/blog/context-development-lifecycle-better-context-for-ai-coding-agents/)
- 원장: `SRC-7409811C56EB`, independence group `tessl-context-lifecycle`

**Messenger.** DevOps와 개발 lifecycle 경험이 깊은 실무자다. 동시에 Tessl이 context·skill tooling을 판매하므로 발표와 글은 상업적으로 이해가 연결된 한 그룹이다.

**Message.** context를 `Generate → Evaluate → Distribute → Observe`하는 versioned, tested, security-scanned, observable artifact로 본다. “무한 context”가 충돌·rot·governance를 해결하지 않는다는 지적은 중요하다.

**검증이 필요한 정확한 주장.**

- CDLC를 적용한 agent가 미적용 agent보다 품질·비용·회귀 측면에서 나은가.
- context conflict와 rot를 어떤 deterministic rule과 benchmark로 감지하는가.
- distribution과 observability가 knowledge compounding을 실제로 만드는가.

**한계와 결정.** 공개 controlled evaluation이 없다. branded lifecycle의 효능은 거부하고, versioning·평가·배포·관측의 일반 lifecycle 원칙만 비파괴 hygiene RFC와 연결했다.

### 3.7 효용 피드백 — 결과 신호를 검색에 돌려보내되 신뢰와 분리

- 영상 원제: [User Signal Dies at the Retrieval Boundary](https://www.youtube.com/watch?v=Jx4ZFEAq6bY), 2026-06-28
- 발표자: Sonam Pankaj, 제안 retrieval 제품의 CEO/co-founder
- 원장: `SRC-9BADA4274C74`, independence group `starlight-utility-memory`

**Messenger.** retrieval product의 failure와 feedback boundary를 직접 설계한 당사자다. 동시에 utility-ranking의 효과를 주장하는 vendor founder다.

**Message.** retrieval 뒤의 성공·실패 신호가 다음 retrieval에 돌아가지 않으므로 memory가 실제 유용성을 학습하지 못한다고 보고 outcome-weighted utility를 제안한다. 발표는 cold-start, noisy label, drift, hyperparameter, credit assignment 문제를 공개한다.

**검증이 필요한 정확한 주장.**

- outcome-weighted ranking이 similarity-only baseline보다 task success를 높이는가.
- 결과 label이 retrieval item의 인과 기여를 구분할 수 있는가.
- model·task·user 변화에서 utility가 얼마나 빨리 stale해지는가.
- 악의적·편향된 feedback이 source authority와 factual trust를 오염시키지 않는가.

**한계와 결정.** 독립 benchmark가 없는 vendor proposal이다. 결과 신호를 audit용 memory-feedback ledger에 기록하는 것은 채택했지만, utility로 ranking·C-level·source level을 자동 변경하거나 evidence를 삭제하는 것은 명시적으로 거부했다.

### 3.8 AI Research OS — 영속 종합의 씨앗이지 완결된 신뢰 시스템은 아님

- 영상: [Turn 10,994 Notes Into Memory](https://www.youtube.com/watch?v=ZRM_TfEZcIo), 2026-06-26
- 발표자: Paul Iusztin, Louis-François Bouchard
- 공개 구현: [iusztinpaul/ai-research-os-workshop](https://github.com/iusztinpaul/ai-research-os-workshop)
- 상업적 연결: [Agent Engineering 강좌](https://academy.towardsai.net/courses/agent-engineering)
- 원장: `SRC-1C96ABEBBA41`, independence group `ai-research-os-authors`

**Messenger.** 실제 file-based research OS를 공개하고 한계를 설명한 제작자들이다. 발표, repository, 유료 강좌는 같은 저자 집단이므로 성능 corroboration 세 건이 아니다.

**Message.** immutable raw, generated index, mutable Wiki를 분리하고 query 때마다 모든 원문을 재합성하지 않고 concept·comparison을 지속 materialized view로 유지한다. 현재 Living Wiki의 시작점과 직접 연결된다.

**검증이 필요한 정확한 주장.**

- 10,994 notes 입력과 18개월 일상 사용 범위.
- file-based raw→index→Wiki가 어떤 규모·task에서 vector/graph retrieval보다 token-efficient한가.
- persistent synthesis가 반복 비용을 줄이면서 semantic drift와 evidence laundering을 억제하는가.
- provenance, source ranking, compaction이 미완성인 상태에서 장기 정확도가 유지되는가.

**한계와 결정.** 공개 repository는 구현 사실에 강하지만 독립 효능 평가가 아니다. 파일 기반 inspectability와 persistent synthesis는 유지하되 atomic claim, exact locator, source independence, security admission, RFC/release gate를 별도 control plane으로 보완했다. RAG·vector·graph를 배제하는 이분법도 채택하지 않았다.

## 4. 중요하지만 admission하지 않은 후보

다음 자료는 직접/인접 후보 66개 안에서 설계 가치가 있었지만, 이번 bounded pass에서 원출처·효능·license를 충분히 검증하지 못했거나 기존 RFC에 필요한 새 독립 근거를 제공하지 않아 개별 source로 등록하지 않았다. `promote` 처분 14개도 “후속 검증 가치가 높은 lead”라는 뜻이지 claim 신뢰 승격이 아니다.

| 날짜 | 자료 | 전달자·메시지와 이해상충 | 미채택 이유 |
|---|---|---|---|
| 2026-07-10 | [Understanding is the new bottleneck — Geoffrey Litt, Notion](https://www.youtube.com/watch?v=WkBPX-oDMnA), [작성자의 글](https://www.geoffreylitt.com/2026/07/02/understanding-is-the-new-bottleneck.html) | 인간 이해·quiz·micro-world를 강조하는 product/design practitioner; Notion bias를 직접 공개 | 인간 참여 원칙에는 유용하지만 comprehension 향상에 대한 controlled evidence가 없음 |
| 2026-05-16/28/29 | 원제 [Connecting the Dots](https://www.youtube.com/watch?v=eW_vxrjvERk), [Decision-Aware Agents](https://www.youtube.com/watch?v=abvQEhvRI_c), [Decision Traces](https://www.youtube.com/watch?v=B9h9ovW5H9U) 영상 — Neo4j | 그래프 데이터베이스 공급자가 개체·의사결정 추적 메모리를 제안; [agent-memory](https://github.com/neo4j-labs/agent-memory)는 공개 | 세 영상·블로그·저장소가 모두 한 공급자 그룹이며 그래프 우월성과 근거 충실도의 독립 평가가 없음 |
| 2026-05-03 | [Mergeable by default — Peter Werry, Unblocked](https://www.youtube.com/watch?v=5ID22ACI7IM) | vendor가 code·docs·tickets·conversation context 결합을 설명 | `2.5h/21M tokens → 25m/10M` 단일 vendor task의 protocol·반복·quality rubric가 없음 |
| 2026-06-26 | [A Genius With Amnesia — Victor Savkin, Nx](https://www.youtube.com/watch?v=jVjt-2g8NMY) | Nx/Polygraph creator가 cross-repo graph와 persistent session을 설명 | current memory implementation과 permission·handoff correctness를 독립 재현할 수 없음 |
| 2026-06-08 | [Why More Context Makes Your Agent Dumber — Nupur Sharma, Qodo](https://www.youtube.com/watch?v=EcqMYoIV57A) | Qodo vendor가 lost-in-the-middle와 layered context engine을 제안 | Qodo benchmark의 task·model·raw data·ablation이 공개되지 않음 |
| 2026-07-07 | 원제 [How we taught agents to use good retrieval — Hanna Lichtenberg, Mixedbread](https://www.youtube.com/watch?v=1IdzkRVmWAA) 영상 | 검색 공급자의 범위 제한 다중 질의 순환 | 관련성 개선과 전달자·출처 신뢰성 개선은 다른 문제이며 독립 벤치마크가 없음 |
| 2026-06-09 | [RAG is dead, right?? — Kuba Rogut, Turbopuffer](https://www.youtube.com/watch?v=UM6sFg_jdlE) | vector search vendor가 Cursor 사례를 소개 | Cursor의 [자체 semantic-search 평가](https://cursor.com/blog/semsearch)는 task 구성·model parity·retention metric 검증이 더 필요 |

Graph context는 추후 retrieval routing option이 될 수 있지만 claim admission을 우회하거나 graph centrality를 신뢰도로 바꾸면 안 된다. vector similarity도 relevance 신호일 뿐 사실성 신호가 아니다.

## 5. 원 논문 교차검토와 학술 발표 상태

### 5.1 DDC 사전 공개 논문은 동료 심사를 거친 독립 확증이 아니다

`SRC-54D07435EB56`은 [arXiv:2603.14057](https://arxiv.org/abs/2603.14057)의 저자 원문이므로 발표 내용과 limitation 확인에는 영상보다 강하다. 그러나 `publication_status=preprint`, S2이고 영상과 같은 `ddc-authors`다. 따라서 영상과 논문을 독립 evidence 두 그룹으로 세지 않았다. preprint가 명시한 “convergence is unvalidated”를 보존했고, repository의 peer-reviewed 표현을 status 승격에 사용하지 않았다.

### 5.2 오류 메모리는 반복될 수 있다

`SRC-AF06BCDC1ED2`, [How Memory Management Impacts LLM Agents](https://aclanthology.org/2026.acl-long.27/)는 ACL 2026 main conference peer-reviewed primary study다. pp. 623–625와 627–630에서 experience-following, 잘못된 memory의 error propagation, misaligned replay와 downstream outcome label을 실험한다. 이는 “성공한 기억은 자동으로 더 신뢰해도 된다”가 아니라 **기억 재사용이 오류를 증폭할 수 있으므로 결과를 별도 감사해야 한다**는 제한된 결론을 지지한다.

적용 한계는 논문의 agent task와 factual Wiki가 동일하지 않다는 점이다. 이 연구를 근거로 Wiki source를 자동 삭제하거나 C-level을 내리는 것은 범위를 넘는다.

### 5.3 메모리 수명주기 동작의 존재와 Wiki 자동화의 효능은 다르다

`SRC-9639A8245BE8`, [Agentic Memory](https://aclanthology.org/2026.acl-long.981/)는 ACL 2026 main conference peer-reviewed paper다. store, retrieve, update, summarize, discard를 명시적인 action으로 다룬다. 이는 memory hygiene가 first-class operation이 될 수 있다는 연구 맥락을 제공한다.

그러나 learned policy와 dialogue benchmark가 source provenance, claim contradiction, legal retention을 가진 Living Wiki의 자동 lifecycle을 검증하지는 않는다. 특히 discard action을 원문 삭제 권한으로 일반화하지 않았다.

### 5.4 사용자가 메모리 의존도를 제어해야 한다

`SRC-F9BA839FA59D`, [Controllable Memory Usage](https://aclanthology.org/2026.acl-long.670/)는 ACL 2026 main conference peer-reviewed primary study다. pp. 14699–14701과 14705–14707에서 all-or-nothing memory 사용이 과거에 anchoring되거나 역사를 충분히 쓰지 못하는 문제를 다루고, fresh-start부터 high-fidelity까지 사용자가 개입하는 방식을 비교한다.

이는 personalized interaction 연구이므로 factual Wiki 품질을 직접 증명하지 않는다. 다만 과거 memory를 삭제하지 않고 retrieval reliance를 조절하는 `fresh-check` UX의 근거로 제한적으로 채택했다.

### 5.5 발표 상태와 출처 레벨 요약

| 자료 | 공개 상태 | 독립성 | 말할 수 있는 것 | 말할 수 없는 것 |
|---|---|---|---|---|
| DDC 사전공개 논문 | arXiv 사전공개본, S2 | 영상과 같은 저자 그룹 | 방법 정의, 작동 예시, 저자가 명시한 한계 | 수렴·효능의 독립 재현 |
| ACL 2026 long.27 논문 | 주 학회 동료검토, S3 | DDC·공급자와 독립 | 오류 메모리 재사용과 결과 피드백의 실험적 위험 | Wiki 자동 삭제·신뢰 변경의 정당성 |
| ACL 2026 long.981 논문 | 주 학회 동료검토, S3 | 다른 저자 그룹 | 명시적 메모리 작업을 평가할 수 있음 | 학습된 폐기 정책의 Wiki 적용 효능 |
| ACL 2026 long.670 논문 | 주 학회 동료검토, S3 | 다른 저자 그룹 | 메모리 앵커링과 사용자 의존도 제어 | 사실형 Wiki의 정확도 개선 |

## 6. 신규 주장과 현재 신뢰 경계

| 주장 ID | 현재 상태 | 연결 증거 | 채택한 경계 | 아직 증명되지 않은 것 |
|---|---|---|---|---|
| `CLM-95A38CACF2CD` | C2/지지됨 | `SRC-54D07435EB56`·`SRC-AF06BCDC1ED2` 지지, `SRC-F55FED177366` 맥락 | 실패를 조사 우선순위 신호로 사용하고 독립 증거와 재실행 뒤에만 승격 | 실패가 곧 지식 공백이라는 인과 판단과 DDC 수렴·효율 |
| `CLM-F79558D817DF` | C2/지지됨 | `SRC-AF06BCDC1ED2` 지지, 나머지 연결 출처는 맥락 | 하류 결과·시간 상태를 감사하되 신뢰·삭제와 분리 | 효용 순위의 효과, 자동 노후 판정과 자동 폐기 |
| `CLM-EC52C0576A28` | C2/지지됨 | `SRC-F9BA839FA59D` 지지 | 새 출발을 삭제가 아닌 독립 재조사 검색 정책으로 구현 | 개인화 벤치마크 결과의 사실형 Wiki 일반화 |
| `CLM-207429D54323` | C1/지지됨 | `SRC-2E2EA9C214C1` 지지, PROV-O 출처 맥락 | 기록은 감사 원장이며 외부 상태에는 스냅샷·버전·다이제스트·영수증 필요 | 기록만으로 Agent 신원과 전체 실행 상태를 복원한다는 주장 |
| `CLM-F5982AA50A01` | C1/지지됨 | `SRC-0800355B8885` JSON 범위 필드 | 목록 264와 완료·시청 가능 분모 262, 예약 2를 구분 | 삭제·비공개·미등록 영상 또는 미래 metadata 상태 |
| `CLM-0733D26931D2` | C1/지지됨 | `SRC-0800355B8885` 규칙·행별 분류·metadata 해시 | 직접 34·인접 32·제외 196이라는 감사 가능한 단일 Agent 선별 | 독립 분류자 간 일치도나 영상 내용의 진실성 |
| `CLM-F63FA5329493` | C1/지지됨 | `SRC-0800355B8885` 보안 영수증 34개와 검토 처분 | 자막 처리 범위와 거부 우회 없음 | 자막 입수가 곧 내용 신뢰성 또는 재배포 권리를 뜻한다는 주장 |

C1/C2는 “확정된 진실”이 아니라 현재 traceable evidence의 성숙도다. 특히 동일 Agent가 source를 조사하고 claim을 작성한 것은 independent review로 세지 않는다. RFC 승인은 구현 범위의 승인이지 각 외부 효능 claim의 진실성 승인도 아니다.

## 7. RFC-5D91E03B5BC5에 채택한 것

승인된 RFC는 연구 결과 중 로컬·additive·가역적이고 기존 trust invariant를 보존하는 부분만 채택한다.

1. **감사 전용 메모리 피드백 원장**
   - actor, 사용된 claim/source, outcome, 시간 상태를 추적한다.
   - raw user query를 저장하지 않는다.
   - feedback은 ranking, C-level, source level, claim status, 삭제 권한의 입력이 아니다.

2. **읽기 전용 결정론적 메모리 위생**
   - configured staleness와 lifecycle 상태를 report한다.
   - 같은 fixed time과 state에서는 byte-identical report가 나와야 한다.
   - staleness는 review warning이며 사실의 거짓 판정이나 trust 감점이 아니다.

3. **비파괴 lifecycle**
   - `active`, `deprecated`, `superseded`, `invalidated`, `archived` 전이를 reason·replacement와 함께 기록한다.
   - raw artifact와 append-only event를 삭제하거나 덮어쓰지 않는다.

4. **사용자 memory mode**
   - `wiki-first`: 기존 Wiki를 출발점으로 사용한다.
   - `fresh-check`: 부트스트랩은 수행하되 기존 합성 결론을 괄호에 두고 독립 조사한 뒤 비교하며 과거 기록은 삭제하지 않는다.
   - `strict-evidence`: 합성보다 exact claim·locator·source status를 우선한다.
   - 어떤 모드도 `wiki/index.md` bootstrap과 source admission을 우회하지 않는다.

5. **Failure/replay 기반 harness proposal**
   - proposal은 관찰된 failure, replay 방법, 수정할 최소 layer, frozen regression, rollback을 적어야 한다.
   - 사람이 승인한 RFC도 release gate와 rollback rehearsal 전에는 구현 완료로 간주하지 않는다.

6. **Log와 외부 state 분리**
   - event log는 감사·projection의 권위 있는 기록이다.
   - file/service/side effect 재개에는 snapshot, version, digest, receipt가 추가로 필요하다.

## 8. 명시적으로 거부하거나 유보한 것

| 제안 | 결정 | 이유 |
|---|---|---|
| YouTube 영상 주장을 사실 주장으로 직접 승격 | 거부 | S2 실무자·공급자 단서이며 방법·원 결과·독립 재현 부족 |
| 같은 회사의 영상·블로그·문서·저장소를 여러 독립 근거로 집계 | 거부 | 공통 저자·데이터·상업적 이해관계로 상관 오류 가능 |
| DDC 실패에서 지식 자동 생성·졸업 | 거부 | 실패 원인이 지식 부족이라는 보장이 없고 수렴은 preprint도 미검증으로 명시 |
| 성공률·클릭·사용자 신호 기반 효용 자동 순위화 | 거부 | 잡음 라벨, 기여도 할당, 피드백 조작, 출처 권위와 관련성 혼동 |
| 피드백으로 C-level·출처 레벨 자동 변경 | 거부 | 결과 유용성은 주장 사실성·독립성·출처 추적성의 대체물이 아님 |
| 노후 표지 기반 자동 무효화·삭제 | 거부 | 오래됨은 거짓과 다르며 역사적·범위 제한 주장일 수 있음 |
| 학습된 메모리 폐기를 원문·Wiki 삭제 권한으로 사용 | 거부 | 논문 벤치마크 범위를 넘어 출처 추적성과 보존을 훼손 |
| “기록만이 Agent다”를 문자 그대로 채택 | 거부 | 외부 파일, 서비스 상태, 자격증명과 부작용이 기록 밖에 존재 |
| 그래프 DB를 기본 진실 계층으로 전환 | 유보 | 개체·연결 추출 오류와 근거 충실도가 미검증이며 현재 결정론적 원장이 더 감사 가능 |
| vector similarity를 credibility/trust ranking으로 사용 | 거부 | similarity는 relevance이지 truth가 아님 |
| graph/vector/utility를 통한 claim 자동 승격 | 거부 | 어떤 retrieval 구조도 admission·counter-search·독립성 gate를 우회할 수 없음 |
| vendor 수치와 one-off demo를 production benchmark로 채택 | 거부 | dataset, repetition, evaluator, 비용, negative result가 공개되지 않음 |

Graph와 vector retrieval 자체를 영구 금지한 것은 아니다. Wiki가 커져 deterministic index가 병목이 될 때 hybrid retrieval이나 graph routing을 별도 benchmark로 비교할 수 있다. 다만 그것은 **찾는 방법**이며, claim의 신뢰도를 정하는 방법이 아니다.

## 9. 자막·라이선스·보안 결정

외부 자막·PDF·repository의 문장은 지시가 아니라 untrusted data로 처리했다. 자막 안의 command, credential 요구, 정책 변경 문구를 실행하지 않았다.

### 9.1 YouTube 자료

- 직접 후보 34개 모두의 공개 auto-caption 입수를 시도해 34개를 입수하고 각각 `security-screen` receipt를 남겼다. 31개는 `allow`, 3개는 `reject`였고 override하지 않았다.
- `ADM-A9C0E203A5C3`, `ADM-D876BB4A014D`, `ADM-9AD3913E71DD`로 reject된 세 장시간 event 자막은 transcript 결론에 사용하지 않고 공개 metadata chapter만 사용했다. reject는 내용이 거짓이라는 판정이 아니라 크기·보안 정책 경계다.
- 34개 자막의 재배포 권리가 확인되지 않아 caption body는 canonical source에 넣지 않았다. 대신 SHA-256, byte size, gate decision, locator, disposition만 `SRC-0800355B8885`에 보존했다. 분석 가능하다는 사실과 raw caption을 저장·재배포할 권리는 다르다.
- 개별 영상 source 7개는 계속 metadata-only다. 전수감사 bundle은 자막 본문이 아니라 metadata와 audit receipt를 보존하는 별도 derived dataset이다.
- 기존 `SRC-1C96ABEBBA41`의 과거 timestamp 분석도 이번 전수감사 receipt로 보완했지만, 원 video source 자체에 caption artifact를 소급 첨부하지 않았다.
- security `allow`는 내용이 참이라는 판정이 아니고, metadata-only는 영상이 거짓이라는 판정도 아니다.

### 9.2 논문

- DDC PDF는 screening했지만 reuse license가 확정되지 않아 `SRC-54D07435EB56`을 metadata-only로 유지했다.
- ACL 논문은 official proceedings와 CC BY 4.0 status를 확인했다.
- `SRC-AF06BCDC1ED2`와 `SRC-F9BA839FA59D`는 page marker가 있는 추출 text와 SHA-256을 보존했다. 원 PDF는 size gate를 통과하지 않아 promotion하지 않았다.
- `SRC-9639A8245BE8`의 PDF와 추출 text는 security gate에서 거부됐고 override하지 않았다. 이는 논문의 학술적 거짓 판정이 아니라 artifact promotion 정책 결정이다. 따라서 이 source에는 현재 보존된 exact raw span이 없다는 한계를 표시한다.

## 10. 남은 검증 질문과 종료 조건

다음 연구는 source 수를 늘리는 것보다 채택된 원칙의 반증 가능성을 높여야 한다.

1. **Failure-driven curation 비교 평가**
   - 질문: failure 기반 큐레이션이 가장 강한 반대 evidence recall을 낮추지 않으면서 active context를 줄이는가?
   - 비교: 하향식 문서, 단순 추가, DDC 유사 큐레이션.
   - 종료: 맹검 평가 기준, 동일 작업 집합, 품질·토큰·인간 소요 시간, 반대 증거 재현율 공개.

2. **Replay와 frozen regression**
   - 질문: 실제 failure를 재현하고 최소 harness change가 기존 task를 잊지 않았음을 보일 수 있는가?
   - 종료: 환경 해시, 모델·도구 버전, 결정론적 fixture, 유보 집합 오염 감사, 롤백 예행연습.

3. **피드백 선택 편향**
   - 질문: 성공 session만 기록되거나 noisy user label이 반복될 때 audit ledger가 echo chamber를 탐지하는가?
   - 종료: no-op control, negative feedback, missing-outcome 비율, actor·model별 slice를 포함한 report.

4. **Staleness 의미 검증**
   - 질문: 신선도 설정 `fast`, `normal`, `slow`의 경고가 실제로 낡은 주장을 얼마나 찾고 역사적 사실을 얼마나 오탐하는가?
   - 종료: adjudicated corpus와 precision/recall. 이 전까지 staleness는 warning only다.

5. **사람의 메모리 통제**
   - 질문: `fresh-check`가 anchoring을 줄이면서 시간·비용과 사실 정확도를 감당 가능한 수준으로 유지하는가?
   - 종료: wiki-first/fresh-check/strict-evidence 비교, comprehension·error detection·time 측정.

6. **Retrieval architecture 비교**
   - 질문: 규모가 커질 때 deterministic index, vector, graph, hybrid가 어떤 query에서 이득인가?
   - 종료: 같은 claim ledger와 admission gate 위에서 recall, exact-locator precision, latency, cost, poisoning resistance 비교. 어떤 결과도 trust auto-ranking 권한을 갖지 않는다.

## 11. 최종 판단

AI Engineer 채널은 최신 실무 문제와 구현 pattern을 빠르게 발견하는 데 가치가 높지만, 영상 다수는 발표자 회사의 production account이자 제품 주장이다. 따라서 채널 자체를 “신뢰할 수 있는 messenger” 한 덩어리로 처리하면 안 된다. 각 영상마다 발표자의 전문성, 원자료 접근, 이해상충을 평가하고, message의 방법·데이터·재현성·한계를 별도로 평가해야 한다.

이번 연구가 하네스에 준 가장 중요한 변화는 “더 많은 memory”가 아니라 **memory를 안전하게 의심하고 늙게 하고 비교하는 제어면**이다. 실패는 질문을 만들고, feedback은 감사를 만들며, staleness는 review를 촉발한다. 그러나 어느 것도 스스로 사실을 만들거나 trust를 높이거나 원문을 지울 권한은 없다. 이 경계가 `RFC-5D91E03B5BC5`의 승인 범위이며, 독립 review가 없는 새 claim을 C3/C4로 올리지 않은 이유다.
