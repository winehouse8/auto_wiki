# Claims

* [CLM-0733D26931D2](clm-0733d26931d2.md) - 고정한 제목·설명과 명시적 상호배타 규칙으로 완료·시청 가능 영상 262개를 의미 선별하면 memory·wiki·second-brain 직접 관련 34개, 인접 32개, 제외 196개로 분류된다.
* [CLM-1EB8BD726482](clm-1eb8bd726482.md) - 지속적으로 편집되는 Wiki는 영향받은 의존성만 좁게 수정한 뒤 전체 불변조건과 사실 회귀를 다시 검사해야 한다.
* [CLM-207429D54323](clm-207429d54323.md) - append-only Agent log는 감사와 재투영의 권위 있는 기록이어야 하지만 외부 파일·서비스·side effect의 전체 상태는 아니므로 재개와 rollback에는 별도 snapshot, version, digest와 side-effect receipt가 필요하다.
* [CLM-25D2398ACBF4](clm-25d2398acbf4.md) - Codex의 프로젝트 지침 결합 용량 기본값은 32 KiB이며, 한도에 도달하면 추가 지침 파일을 더하지 않는다.
* [CLM-3B0EC9C26226](clm-3b0ec9c26226.md) - AGENTS.md 변경 내용을 확실히 반영하려면 새 Codex 명령 또는 새 TUI 세션을 시작해야 하며, project_doc_fallback_filenames에 등록되지 않은 대체 파일명은 자동 지침 탐색 대상이 아니다.
* [CLM-409FCD3D2B82](clm-409fcd3d2b82.md) - Codex는 매 실행 시작 시 프로젝트 경로 탐색과 별도로 CODEX_HOME(기본 ~/.codex)의 전역 지침을 읽으며, non-empty AGENTS.override.md가 있으면 그것을 사용하고 그렇지 않으면 AGENTS.md를 사용한다.
* [CLM-4A3051A018DC](clm-4a3051a018dc.md) - 출처의 권위와 평판은 검색 우선순위와 검토 깊이를 정하는 prior로 쓸 수 있지만 개별 주장의 증거를 대체할 수 없다.
* [CLM-61B3C391010C](clm-61b3c391010c.md) - 지속 메모리를 쓰는 Agent는 수집 시점과 검색 시점 모두에 오염 방지 gate가 필요하다.
* [CLM-6DDD53332A40](clm-6ddd53332a40.md) - 원문 snapshot은 감사 가능한 증거이지 자동으로 참인 source of truth가 아니다.
* [CLM-6ED77E226EF7](clm-6ed77e226ef7.md) - 검색된 문맥에 대한 충실성, 현실 세계의 사실성, 출처 자체의 신뢰도는 서로 다른 평가 대상이다.
* [CLM-7FDAF2F91E73](clm-7fdaf2f91e73.md) - OKF v0.1 conformance는 비예약 Markdown의 parseable YAML frontmatter와 non-empty type, 그리고 예약 index.md/log.md 구조를 핵심 필수 조건으로 둔다.
* [CLM-860EB3D6AAEB](clm-860eb3d6aaeb.md) - 자료의 주제 관련도는 해당 자료의 신뢰도나 그 자료를 인용한 답변의 사실성을 보장하지 않는다.
* [CLM-952258184EF2](clm-952258184ef2.md) - OKF v0.1은 claim confidence, source credibility, actor governance, 저장 및 검색 인프라를 정의하지 않으므로 Living Wiki는 이를 producer extension과 외부 control plane으로 보완해야 한다.
* [CLM-95A38CACF2CD](clm-95a38cacf2cd.md) - Agent 실패는 어떤 지식 공백을 조사할지 우선순위화하는 신호가 될 수 있지만, 실패 원인이나 새 지식의 사실성을 스스로 증명하지 않으므로 독립 근거 검증과 재현 가능한 재시도 뒤에만 Wiki 지식으로 승격해야 한다.
* [CLM-99AE239A5BA3](clm-99ae239a5ba3.md) - Crossref는 Retraction Watch의 retraction 및 일부 correction·expression-of-concern 데이터를 production REST API와 공개 dataset으로 제공하며, REST 결과의 update-to와 source 필드로 update 유형과 provenance를 구분한다.
* [CLM-A49ACF085321](clm-a49acf085321.md) - GitHub REST commit 조회는 commit SHA와 signature verification 객체를 제공하므로 코드 출처를 가변 branch 이름보다 특정 commit에 고정하고 검증 메타데이터를 기록할 수 있다.
* [CLM-B97B5BE5E324](clm-b97b5be5e324.md) - Codex는 선택된 프로젝트 지침을 루트에서 현재 디렉터리 순으로 결합하므로 더 가까운 디렉터리의 지침이 뒤에 놓여 앞선 지침을 재정의할 수 있다.
* [CLM-CB6E34C87DA3](clm-cb6e34c87da3.md) - 감사 가능한 연구 Wiki의 신뢰 최소 단위는 페이지 전체보다 원자적 주장과 정확한 evidence locator의 연결이어야 한다.
* [CLM-CEBC308C15C4](clm-cebc308c15c4.md) - GraphRAG의 그래프 구조는 잘못 추출된 triple과 부적절한 community 구성에서 생기는 오류를 자동으로 상쇄하지 못한다.
* [CLM-D2A1B46809DA](clm-d2a1b46809da.md) - 시간에 따라 변하는 주장은 valid_from, valid_to, as_of, supersedes 같은 시간 범위와 계보를 가져야 한다.
* [CLM-DA4E9F9BA977](clm-da4e9f9ba977.md) - Codex는 작업을 시작하기 전에 지침 체인을 구성하며, 대화형 TUI에서는 보통 실행된 세션마다 한 번만 AGENTS.md 계열 파일을 탐색한다.
* [CLM-DA7C92E9A901](clm-da7c92e9a901.md) - 효과적인 인간-Agent 공동 연구에는 결과만이 아니라 과정의 관찰 가능성, 실시간 조향, 공유 맥락과 복구 가능한 commitment가 필요하다.
* [CLM-DCFACC957266](clm-dcfacc957266.md) - Wiki가 형성한 관점은 사실 원장과 분리하고 가장 강한 반론, 가정, 입장 변경 조건과 개정 이력을 보존해야 한다.
* [CLM-EC52C0576A28](clm-ec52c0576a28.md) - 사용자는 장기 Wiki 기억에 의존하는 정도를 명시적으로 조절할 수 있어야 하며, fresh-start 모드는 과거 기록 삭제가 아니라 독립 재조사 후 기존 Wiki와 비교하는 retrieval policy로 구현해야 한다.
* [CLM-F2BB537122FE](clm-f2bb537122fe.md) - NCBI E-utilities는 PubMed와 PMC를 포함한 Entrez 데이터베이스를 검색·연결·조회할 수 있는 공식 공개 API다.
* [CLM-F464CCF0AA1A](clm-f464ccf0aa1a.md) - 하네스의 자기진화는 고정된 평가, 최소 변경, 회귀 검사와 rollback을 통과한 제안으로만 승격해야 한다.
* [CLM-F526A53CB69F](clm-f526a53cb69f.md) - OKF v0.1에는 필수 bundle manifest, JSON Schema, 중앙 type registry가 없으며 type taxonomy와 추가 frontmatter는 producer에게 열려 있다.
* [CLM-F5982AA50A01](clm-f5982aa50a01.md) - 2026-07-12 공개 스냅샷에서 AI Engineer 채널의 2026-04-01~2026-07-12 범위 목록은 264개였으며, 이 중 완료·시청 가능 영상은 262개(일반 영상 251, livestream replay 11, Shorts 0)이고 예약 premiere 2개는 연구 분모에서 제외됐다.
* [CLM-F6367BFF8F35](clm-f6367bff8f35.md) - 불변 원문 위의 지속적 합성 Wiki는 원문 검색을 대체하는 것이 아니라 반복 재합성을 줄이는 보완 계층이다.
* [CLM-F63FA5329493](clm-f63fa5329493.md) - 직접 관련 후보 34개 모두에서 자막 입수와 보안 검사를 시도해 34개를 입수했고, 31개는 allow, 3개는 reject였으며, 검토 처분은 promote 14·defer 17·exclude 3이었다; reject 자막은 transcript 결론에 사용하지 않았다.
* [CLM-F79558D817DF](clm-f79558d817df.md) - 지속 메모리의 유사성이나 최초 성공만으로 재사용 품질을 판단하면 오류·노후 지식이 반복될 수 있으므로, retrieval 이후 결과와 시간 상태를 감사 가능하게 기록하되 그 신호가 claim 신뢰 승격이나 원문 삭제를 자동 수행해서는 안 된다.
* [CLM-FBF709C70CCF](clm-fbf709c70ccf.md) - 같은 제작자 집단의 발표와 구현 저장소는 서로 다른 형식이어도 독립적인 교차검증 두 건으로 세면 안 된다.
* [CLM-FC9028899EE0](clm-fc9028899ee0.md) - 2026년 한 평가에서 deep-research Agent의 반복 보고서 수정은 기존 내용과 인용 품질의 16~27%를 훼손했다.
* [CLM-FF4A31447E3E](clm-ff4a31447e3e.md) - 프로젝트 지침 탐색에서 Codex는 프로젝트 루트부터 현재 작업 디렉터리까지 내려가며, 각 디렉터리에서 AGENTS.override.md, AGENTS.md, 설정된 fallback 이름 순으로 최대 한 파일을 선택한다.
