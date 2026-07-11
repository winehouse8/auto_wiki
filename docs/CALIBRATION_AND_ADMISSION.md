# Calibration and source admission evaluator

`tools/calibration.py`는 RFC-69828EB38078의 calibration·source admission 부분을 구현한 **읽기 전용 평가 모듈**이다. 기존 `config/trust-policy.json`의 C0–C4/S0–S4 규칙을 바꾸거나 canonical ledger를 직접 수정하지 않는다. 결과는 승격 명령이 아니라 이후 `tools/wiki.py` 또는 인간 검토자가 소비할 결정론적 보고서다.

## 빠른 실행

중앙 원장과 event chain에 귀속하는 운영 command는 다음과 같다.

```bash
python3 tools/wiki.py calibration-run
python3 tools/wiki.py admission-check --candidate /path/to/candidate.json
```

저장소 루트에서 고정 benchmark 전체를 실행한다.

```bash
python3 tools/calibration.py report \
  --input evaluations/fixtures/calibration-gold.json
```

기계 간 byte-for-byte 비교가 필요하면 single-line JSON을 사용한다.

```bash
python3 tools/calibration.py report \
  --input evaluations/fixtures/calibration-gold.json \
  --small-n 5 \
  --compact
```

identifier만 점검할 수도 있다.

```bash
python3 tools/calibration.py canonicalize doi 'https://doi.org/10.1000/ABC'
python3 tools/calibration.py canonicalize url 'https://example.org/a?utm_source=x&v=1#part'
python3 tools/calibration.py canonicalize repository 'git@github.com:Owner/Repo.git'
```

보고서는 실행 시각·호스트 경로·난수를 넣지 않는다. 같은 JSON fixture와 옵션은 같은 stdout을 만든다. `benchmark_sha256`는 key 순서를 정규화한 fixture 전체의 SHA-256이다. 실패는 stderr에 JSON을 쓰고 exit code `2`를 반환한다.

## 1. Ordinal calibration 계약

C0–C4는 **증거 성숙도의 순서척도**다. C2가 60% 또는 C4가 95%라는 뜻이 아니며, 이 모듈도 그런 매핑을 생성하지 않는다. 보고서의 `p_correct`는 고정 benchmark를 평가한 뒤 관찰한 다음 조건부 비율일 뿐이다.

```text
P(correct | Wiki가 부여한 C-level, domain, 이 benchmark의 표본)
```

`correct`는 `predicted_label`이 독립 adjudication으로 확정한 gold label과 같은지를 뜻한다. gold label은 다음 다섯 개다.

- `supported`: 정의한 범위와 기준 시점에서 지지됨
- `contradicted`: 직접 반증이 더 강함
- `mixed`: 범위·하위집단·시점에 따라 지지와 반증이 공존함
- `insufficient`: 판단할 근거가 부족함
- `obsolete`: 과거에는 맞았을 수 있으나 현재 claim으로 사용할 수 없음

이 label은 C-level과 직교한다. 예를 들어 C3로 승격된 claim이 gold set에서는 `contradicted`일 수 있고, 그것이 calibration 실패 사례다. `p_correct`를 다시 C-level 승격 입력으로 사용하면 순환 평가가 되므로 금지한다. 승격은 계속 기존 trust-policy gate만 사용한다.

### Gold adjudication

각 record는 최소 두 개의 독립 `reviewer_group` 투표를 가진다.

```json
{
  "id": "GOLD-001",
  "domain": "science",
  "level": "C2",
  "predicted_label": "supported",
  "adjudications": [
    {"reviewer_group": "human:a", "label": "supported"},
    {"reviewer_group": "agent:independent", "label": "supported"}
  ]
}
```

동일 reviewer group의 동일 투표가 중복되면 하나만 세고 `duplicate_votes_ignored`에 기록한다. 동일 group이 서로 다른 label을 제출하면 독립성이 불명확하므로 item을 disputed로 만든다. 서로 다른 group 간에는 strict majority가 있어야 확정한다. 동률이거나 독립 group이 둘 미만이면 disputed다. 논쟁을 의도적으로 보존할 item은 `"benchmark_status": "disputed"`로 고정할 수 있다.

Disputed item은 삭제하지 않고 adjudication 목록과 coverage에 남지만 accuracy 분모에서 제외한다. `predicted_label: null`인 abstention도 resolved gold 수와 abstention 수에는 남고 accuracy 분모에서는 제외한다. 따라서 보고서는 다음을 별도로 제공한다.

- 전체, resolved, disputed, abstained, scorable record 수
- resolved item 중 prediction coverage
- 전체, level별, domain별 empirical correctness
- 모든 C-level × 관찰 domain 조합의 `p_correct_given_level_domain`
- 95% Wilson score interval
- `small_n_threshold`보다 작은 모든 셀의 명시적 `small_n: true`

표본이 0인 셀은 `p_correct`와 `wilson_95`가 `null`이다. 작은 표본에도 Wilson 구간은 표시하지만 `small_n` 경고를 제거하지 않는다. 현재 fixture 15개는 코드 경로와 실패 유형을 고정하는 smoke benchmark이며 실제 정확도를 일반화하기 위한 100개 gold set을 대신하지 않는다.

## 2. Canonical identifier와 독립성 cluster

### Canonicalization

`canonicalize_doi`는 `doi:`, `https://doi.org/`, 대소문자 차이를 하나의 lowercase DOI로 만든다. `canonicalize_url`은 다음 보수적 규칙을 적용한다.

- HTTP(S) 절대 URL만 허용
- scheme·host 소문자화와 IDNA host 정규화
- default port, fragment, `utm_*`, `fbclid`, `gclid` 등 추적 query 제거
- 의미 query는 보존하고 key/value 순으로 정렬
- URL 안의 username/password 거부
- network redirect, canonical HTML tag, paywall 접근은 수행하지 않음

`canonicalize_repository`는 GitHub, GitLab, Bitbucket의 HTTPS repository root로 정규화한다. GitHub의 `/tree`, `/commit`, `.git`, scp-style SSH 표기는 같은 repository identity가 된다. GitLab nested group은 보존한다. 이 identity는 repository 전체의 중복 탐지용이며 특정 commit snapshot의 동일성을 뜻하지 않는다. commit 수준 provenance는 별도 SHA/locator로 보존해야 한다.

### Independence heuristic

`cluster_independence(sources)`는 union-find로 다음 강한 신호만 연결한다.

1. 같은 canonical DOI, URL, repository 또는 content SHA-256
2. `derived_from`이 기존 source ID를 명시
3. 같은 `origin_url`
4. 정규화한 title·게시일·`quoted_origin`이 모두 같은 derived fingerprint

publisher나 author가 같다는 이유만으로 합치지 않는다. 결과에는 cluster별 members, 연결 이유, deterministic `IC-*` ID, source membership이 들어간다. 잘못된 identifier는 전체 평가를 중단시키지 않고 `identity_errors`에 남으며 admission 단계에서 reject된다.

이 clustering은 후보 탐지다. 서로 같은 연구팀이라는 사실, 같은 모델 family, 데이터셋 공유, 보도자료 재인용 같은 인식론적 의존성을 완전히 추정하지 못한다. 반대로 명시적 파생 관계라도 기사에 독립 취재가 추가됐을 수 있다. 따라서 결과의 warning대로 canonical `independence_group` 변경은 인간/RFC 검토를 거쳐야 한다.

## 3. Status registry adapter

live service와 평가기를 결합하지 않기 위해 다음 read-only interface를 둔다.

```python
from tools.calibration import StatusRegistryAdapter

class MyRegistry(StatusRegistryAdapter):
    name = "my-versioned-registry"

    def lookup(self, source):
        return {
            "adapter": self.name,
            "matches": [],
            "status": "not_found"
        }
```

status entry를 찾았을 때는 `active`, `corrected`, `superseded`, `retracted`, `withdrawn`, `unknown` 중 하나를 반환한다. 여러 identifier가 서로 다른 상태라면 terminal 상태를 우선하는 보수적 결정을 사용해야 한다.

`FixtureStatusRegistry`는 network를 전혀 사용하지 않는 reference adapter다. `evaluations/fixtures/calibration-gold.json`에 active, corrected, retracted control이 들어 있으며 DOI 표기 변형도 canonical key로 조회한다. 실제 Crossref, Crossmark, Retraction Watch, PubMed, publisher status page adapter는 다음 조건을 추가로 지켜야 한다.

- registry 이름과 schema/version을 결과에 기록
- 요청/응답 snapshot 또는 hash와 조회 시각을 외부 run receipt에 보존
- timeout이나 rate limit을 `active`로 오인하지 않고 `unknown/not_found`로 반환
- registry 한 곳의 무응답을 철회 부재의 증거로 취급하지 않음
- live network 결과를 고정 regression fixture와 분리

## 4. Counter-search와 admission decision

`counter_search_coverage`는 결론의 품질 점수가 아니라 필수 탐색 축의 완료 여부를 측정한다. 기본 축은 다음 세 개다.

- `origin`: 원출처·upstream material을 추적했는가
- `status`: 정정·철회·대체·버전을 확인했는가
- `contradiction`: claim을 반증할 자료를 별도로 찾았는가

각 check는 문자열 또는 `{"dimension": "status", "completed": true}` 형식이다. 모듈은 쿼리 수를 독립 증거 수로 세지 않고, 검색 결과가 옳았다고 보증하지 않는다.

`admission_decision`의 결과는 세 단계다.

| 결정 | 현재 evaluator 조건 | canonical writer 의미 |
|---|---|---|
| `reject` | identifier가 없거나 잘못됨, registry가 retracted/withdrawn | canonical claim evidence로 넣지 말고 quarantine/오류 큐 유지 |
| `review` | counter-search 미완료, provenance 미확인, corrected/superseded/unknown, 필수 registry 상태 없음, 기존 source 중복, derived cluster 충돌, 강한 미해결 반증 | 자동 독립 증거로 세지 말고 사람/독립 Agent 검토 |
| `allow` | canonical identity, 명시적 provenance, 필수 counter-search, 적용되는 status gate를 모두 통과하고 중복/파생 충돌 없음 | admission 후보 자격만 획득; source/claim 신뢰 승격은 별도 기존 gate |

정확한 중복 source는 자동 reject하지 않는다. 새 snapshot, correction, license 또는 locator가 유용할 수 있기 때문에 `review`로 보낸다. `allow`도 사실성 보증이나 S-level 부여가 아니다. license, 개인정보, 저작권, prompt injection, MIME/크기 검사는 별도 security ingest gate가 담당한다.

v4 canonical writer는 `source-add --admission ADM-...`을 강제한다. 파일이면 동일 SHA-256의 `security-screen` allow ID도 `--security-admission`으로 전달해야 한다. admission의 top-level/nested decision, canonical ID, record digest와 event anchor가 일치하지 않으면 writer와 validator가 모두 실패한다. admission 이전 35개 source만 pinned migration manifest의 정확한 ID로 grandfather된다.

## 5. Python integration API

공개 함수는 다음과 같다.

```python
from tools.calibration import (
    FixtureStatusRegistry,
    StatusRegistryAdapter,
    admission_decision,
    build_report,
    calibration_report,
    canonicalize_doi,
    canonicalize_repository,
    canonicalize_url,
    cluster_independence,
    counter_search_coverage,
    resolve_gold_record,
    source_identity_keys,
    wilson_interval,
)
```

통합의 권장 경계는 다음과 같다.

```python
fixture = json.loads(path.read_text(encoding="utf-8"))
report = build_report(fixture, small_n_threshold=5)

# report를 evaluation artifact/run receipt에 기록한다.
# allow/review/reject는 canonical source writer에 직접 쓰지 않고
# 기존 actor 권한, trust-policy, event log gate에 입력으로 전달한다.
```

중앙 CLI가 이 파일을 import하기 어렵다면 `python3 tools/calibration.py report ... --compact`를 subprocess로 호출하고 exit code와 stdout hash를 run receipt에 보존할 수 있다. 어느 방식도 다음을 하면 안 된다.

- `p_correct`에서 C-level을 역산
- `allow`만으로 source level 또는 claim confidence를 올림
- heuristic cluster를 canonical independence group에 자동 반영
- disputed gold item을 조용히 삭제
- 실행 시각을 이 deterministic report 안에 주입

실행 시각, actor ID, fixture Git commit, CLI version, report hash는 중앙 scheduler의 append-only event/run receipt에 기록하는 것이 책임 분리에 맞다.

## 6. 검증

이 모듈만 실행한다.

```bash
python3 -m unittest tests.test_calibration -v
```

전체 저장소 회귀검사를 실행한다.

```bash
python3 -m unittest discover -s tests -v
python3 tools/wiki.py validate
python3 tools/wiki.py okf-validate
```

현재 전용 테스트는 43개이며 다음을 고정한다.

- 5개 gold label, majority/tie/명시 disputed, 같은 reviewer group 중복·충돌
- coverage, C-level × domain matrix, Wilson interval, small-n 표시
- DOI/URL/repository 표기 변형과 malformed identifier
- identifier/explicit-origin cluster, publisher-only 오병합 방지
- offline active/corrected/retracted registry control
- allow/review/reject의 모든 branch
- 두 번 실행한 CLI stdout의 byte 동일성

## 7. 알려진 한계와 다음 benchmark

현재 fixture는 harness 회귀평가이지 empirical calibration 결론이 아니다. production 판단 전 다음이 필요하다.

1. 여러 domain과 C0–C4를 층화한 최소 100개 claim, 시간 분할 holdout, 정기 재표본
2. claim 작성자와 독립된 인간/Agent group의 blind adjudication 및 이의 제기 절차
3. exact-label accuracy 외에 class별 confusion matrix와 domain별 error analysis
4. withdrawn/corrected/retracted live adapter의 outage·stale-cache fixture
5. DOI가 없고 canonical URL이 변하는 웹·YouTube·dataset·법령 사례
6. syndicated article, press release, shared dataset/model family의 어려운 independence 사례
7. counter-search의 단순 완료 여부가 아니라 recall과 strongest-counterevidence 발견률 평가
8. gold label 자체가 시간에 따라 obsolete가 되는 benchmark lifecycle과 versioned migration

Wilson interval은 각 record를 독립 Bernoulli trial로 보는 요약이다. 실제 claim은 source family와 domain으로 상관되므로 cluster bootstrap이나 hierarchical model을 대신하지 않는다. 또한 `supported/contradicted/mixed/...` exact match는 오류를 명확히 보여주지만 partial credit을 제공하지 않는다. 이 제한 때문에 보고서는 C-level 자체를 확률로 재해석하거나 trust policy를 자동 변경해서는 안 된다.
