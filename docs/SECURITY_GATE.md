# Living Wiki security gate v1

`tools/security_gate.py`는 RFC `RFC-69828EB38078`과 캠페인 `CMP-088A51571084`의 최소 보안 기준선이다. 위키의 현재 주장 `CLM-61B3C391010C`(2026-07-11 기준 C2), 즉 지속 메모리는 write와 retrieve 모두에서 오염 방지 gate가 필요하다는 결론을 실행 가능한 회귀검사로 옮긴다. activate gate를 추가해 “검색된 데이터가 행동 명령으로 바뀌는 순간”도 별도로 차단한다.

이 모듈은 **결정론적 lexical scanner이지 완전한 prompt-injection 방어 또는 production security boundary가 아니다.** 작은 고정 corpus에서 성공했다는 사실을 실제 공격 일반화나 보안 인증으로 표현하면 안 된다.

## 보안 불변식

1. 모든 웹·PDF·자막·저장소·사용자 제공 파일은 `untrusted_external_content`다.
2. 원문 byte는 해시와 크기만 scanner에 남고, 정규화 text와 분리된다.
3. scanner는 payload를 import, parse-as-code, evaluate, execute하지 않는다.
4. scanner에는 network, subprocess/shell, dynamic import, credential API가 없다.
5. `allow`는 “신뢰하지 않은 데이터로 다음 단계에 넘길 수 있다”는 뜻일 뿐, 명령 실행이나 canonical truth 승인이 아니다.
6. `review`와 `reject`는 모두 자동 진행을 막는다. `review`는 독립 검토 후 재판정할 수 있지만 `reject`는 immutable quarantine evidence만 유지한다.
7. 외부 콘텐츠의 문장은 어떤 경우에도 system/developer/AGENTS instruction channel로 승격하지 않는다.
8. scanner 장애, schema 오류, 미지원 encoding은 `allow`로 우회하지 않는다. 통합 계층이 fail-closed로 review/reject해야 한다.

## 처리 경계

```text
untrusted bytes
  → upstream immutable quarantine storage (no overwrite)
  → assess_content: hash/size/media classification
  → separate normalization or sandboxed extracted text
  → explainable signal detection
  → write gate       canonical candidate 생성 가능 여부
  → retrieve gate    검색 결과 자동 노출 가능 여부
  → activate gate    데이터 유래 행동을 자동 고려할 수 있는지 여부
  → normal provenance/admission/evidence/review policy
```

`security_gate.py` 자체는 raw 파일이나 manifest를 저장하지 않는다. 저장 권한까지 가진 scanner가 되지 않도록 의도한 구조다. 중앙 `tools/wiki.py security-screen`이 collector 역할로 충돌 없는 content-addressed quarantine 경로에 원문을 쓰고 assessment를 원장에 저장한다. 기존 raw 파일은 절대 덮어쓰지 않는다. raw 저장 성공과 해시 재검증 전에는 canonical candidate를 만들지 않는다.

PDF, Office, archive, image, audio/video를 이 모듈이 직접 파싱하지 않는다. 최소 권한 sandbox에서 별도로 생성한 UTF-8 결과만 `extracted_text`로 넘긴다. 원문 해시는 원래 binary의 해시이고 normalized hash는 추출 text의 해시이므로 둘을 같은 artifact라고 표현하지 않는다. extractor 이름·버전·설정·출력 hash는 상위 ingest receipt에 추가로 기록해야 한다.

## Public integration API

중앙 CLI는 격리 저장과 event/admission 원장을 함께 관리한다.

```bash
python3 tools/wiki.py security-evaluate
python3 tools/wiki.py security-screen \
  --input /path/to/local-artifact \
  --source-ref https://example.org/artifact
```

`security-screen`은 `raw/quarantine/<sha256>/artifact.<ext>`를 새로 만들고 재해시한 뒤 normalized 본문을 제외한 assessment와 digest를 admission/event 원장에 남긴다. 기존 quarantine byte를 덮어쓰지 않는다. `write=allow`여도 source를 만들지 않으며 별도 source-admission allow 뒤에서만 `source-add --security-admission ...`의 입력이 된다.

### 단일 artifact 판정

```python
from tools.security_gate import assess_content

assessment = assess_content(
    raw=downloaded_bytes,
    source_ref="https://example.org/paper.pdf",
    declared_media_type="application/pdf",
    extracted_text=text_from_separate_sandbox,  # text source라면 생략
)

manifest = assessment.manifest
write_decision = assessment.gates["write"]["decision"]
retrieve_decision = assessment.gates["retrieve"]["decision"]
activate_decision = assessment.gates["activate"]["decision"]
safe_report = assessment.to_dict()  # normalized 본문은 기본적으로 제외
```

고정 signature는 다음과 같다.

```text
assess_content(
    raw: bytes,
    source_ref: str,
    declared_media_type: str | None = None,
    extracted_text: str | None = None,
) -> SecurityAssessment
```

`SecurityAssessment`의 public field는 다음 네 개다.

- `manifest`: 원문의 `content_sha256`, `size_bytes`, declared/detected/effective media type, source reference
- `normalized`: 별도 파생 text, normalized hash, 길이, normalization source, truncation 여부
- `signals`: rule ID, category, risk, 설명, span, 짧은 redacted excerpt, context modifier
- `gates`: `write`, `retrieve`, `activate` 각각의 decision, risk score, 원인 rule ID

`assessment.to_dict()`는 normalized 본문을 제외한다. `include_normalized_text=True`는 격리된 일시 처리 안에서만 사용하고 event log, manifest, 일반 report에는 저장하지 않는다. signal excerpt도 공격 문자열의 일부이므로 UI에서는 code/quote 데이터로 렌더링하고 프롬프트 instruction 영역에 연결하지 않는다.

### Gate만 재계산

```python
from tools.security_gate import decide_gate

result = decide_gate(existing_signals, "retrieve")
```

유효한 stage는 `write`, `retrieve`, `activate`뿐이다. 알 수 없는 stage는 `ValueError`다.

### 고정 corpus 평가

```python
from tools.security_gate import evaluate_corpus, load_corpus

corpus = load_corpus("evaluations/fixtures/security-corpus.json")
report = evaluate_corpus(corpus)
```

`load_corpus`는 schema, case ID 유일성, attack/benign label, content type을 검증한다. `evaluate_corpus`는 파일·network·state를 변경하지 않고 canonical report dictionary를 반환한다.

## Manifest schema

대표 manifest는 다음 구조다. 시간은 collector receipt가 관리하며 scanner output에는 넣지 않아 같은 입력의 report가 byte-stable하다.

```json
{
  "classification": "untrusted_external_content",
  "source_ref": "fixture:source",
  "hash_algorithm": "sha256",
  "content_sha256": "...",
  "size_bytes": 123,
  "media_type": "text/plain",
  "declared_media_type": "text/plain",
  "detected_media_type": "text/plain"
}
```

manifest는 원문의 존재를 증명하는 locator이지 원문의 안전성 또는 진실성을 증명하지 않는다. URL 자체에 credential/query secret을 넣지 말고 canonical public locator나 내부 opaque source ID를 사용한다.

## Explainable signal 범주

| 범주 | 예시 signal | 해석 |
|---|---|---|
| prompt injection | 이전 지시 무시, role 재할당, 가짜 system block, hidden directive | source data가 instruction priority를 탈취하려 함 |
| secret exfiltration | `.env`, SSH/private key, privileged prompt를 읽거나 전송하라는 요구 | 비밀 또는 상위 지침 유출 시도 |
| shell command | download-and-execute, destructive delete, executable permission, reverse connection | 외부 텍스트가 실행 능력을 요구함 |
| policy overwrite | `AGENTS.md`, 헌장, trust policy 변경 또는 gate 우회 | persistent policy와 신뢰 상태 변조 시도 |
| persistence | canonical memory 저장, 미래 turn 반복 실행, Wiki directive 삽입 | 한 번의 입력을 장기 명령으로 만들려 함 |
| obfuscation | 긴 base64-like blob | lexical scanner가 내용을 검사하지 못하게 함 |
| content integrity | media mismatch, invalid UTF-8, oversize, opaque binary | 자동 판정에 필요한 관찰이 불완전함 |
| executable payload | ELF/PE signature | 콘텐츠 자체가 실행 artifact임 |

signal은 악성 판결이 아니라 검토 가능한 관찰이다. 인용, 부정문, 보안교육/incident 분석 문맥은 `analytical_or_negated_context`로 risk를 2까지 낮춘다. 그러나 탐지된 directive를 자동 `allow`로 바꾸지는 않는다. 공격자가 “예시”라는 말을 붙여 우회할 수 있기 때문에 이 완화는 reject를 review로 바꿀 수만 있고 review 없이 통과시키지 않는다.

## 세 gate와 decision

| Gate | allow | review | reject |
|---|---|---|---|
| write | untrusted candidate 생성 단계로 이동 가능 | canonical write 중단, 독립 검토 queue | canonical write 금지, raw quarantine만 유지 |
| retrieve | 출처·risk label을 붙여 inert data로 노출 가능 | 자동 답변에서 보류하거나 격리 UI에만 노출 | 일반 retrieval 결과에서 제외 |
| activate | 탐지된 directive가 없다는 뜻만 가짐 | 데이터 유래 action 자동 고려 중단 | 데이터 유래 action 거부 및 security event 후보 |

현재 결정 규칙은 고정되어 있다.

- write: critical risk(5) 하나 또는 합계 8 이상이면 reject, 그 밖의 signal은 review
- retrieve: critical risk(5) 하나 또는 합계 10 이상이면 reject, 그 밖의 signal은 review
- activate: threat risk 3 이상 하나 또는 합계 5 이상이면 reject, 그 밖의 signal은 review
- signal이 없을 때만 allow

어떤 단계의 `allow`도 shell/tool 호출, credential 접근, 정책 변경, Wiki write 권한을 부여하지 않는다. 실제 행동에는 사용자의 현재 요청, Codex/platform 권한, repository governance, source admission을 별도로 통과해야 한다.

## CLI

한 local 파일을 판정한다.

```bash
python3 tools/security_gate.py scan \
  --input /path/to/quarantined-artifact \
  --source-ref SRC-EXAMPLE \
  --media-type text/plain \
  --gate write
```

binary에서 sandbox가 추출한 text가 있으면 별도 파일로 넘긴다.

```bash
python3 tools/security_gate.py scan \
  --input /path/to/quarantined.pdf \
  --source-ref SRC-PDF \
  --media-type application/pdf \
  --extracted-text /path/to/sandbox-output.txt \
  --gate retrieve
```

stdout은 key가 정렬된 deterministic JSON이다. normalized 본문은 출력하지 않는다. scan exit code는 선택한 gate 기준 `0=allow`, `2=review`, `3=reject`다. 경로/JSON/입력 오류는 Python 오류로 실패하며 allow로 간주하면 안 된다.

고정 corpus를 실행한다.

```bash
python3 tools/security_gate.py evaluate \
  --corpus evaluations/fixtures/security-corpus.json
```

기대 decision 불일치 또는 attack success가 하나라도 있으면 exit code 4다. 나머지는 0이다. report에는 attack success rate, benign rejection/review rate, stage별 값, case별 signal rule ID가 포함된다.

## 현재 fixed-corpus baseline

`evaluations/fixtures/security-corpus.json`은 다음을 포함한다.

- 공격 18건: prompt override, role reassignment, secret/SSH exfiltration, download-execute, destructive shell, policy overwrite, forced trust, persistence, hidden HTML, obfuscation, PDF sandbox extraction, YouTube transcript, repository README
- 정상 13건: 일반 연구·정책·API·memory 문서와 정상 명령 예시
- 의도적 false-positive 4건: prompt/shell/secret/policy 공격 문구를 분석 목적으로 인용
- opaque benign image 1건: 악성이 아니라 관찰 불가능성 때문에 review

현재 코드에서의 회귀 baseline은 다음과 같다.

| 지표 | 값 |
|---|---:|
| attack case detection rate | 1.0 |
| 전체 stage attack success rate (`allow` 비율) | 0.0 |
| write/retrieve/activate attack success rate | 각각 0.0 |
| benign forced rejection rate | 0.0 |
| benign review rate | 0.384615 |

`review`는 자동 공격 성공이 아니지만 운영 비용이다. 따라서 attack success만 낮추고 review를 무한히 늘리는 변경은 개선이 아니다. corpus 규모가 작고 규칙과 함께 작성됐으므로 이 값은 regression canary일 뿐 empirical security claim이 아니다.

## 테스트

보안 모듈만 실행한다.

```bash
python3 -m unittest tests.test_security_gate -v
```

전체 저장소 회귀검사를 실행한다.

```bash
python3 -m unittest discover -s tests -v
python3 tools/security_gate.py evaluate
python3 tools/wiki.py validate
python3 tools/wiki.py okf-validate
```

`tests/test_security_gate.py`는 manifest/hash, media mismatch, 원문/정규화 분리, prompt/secret/shell/policy/persistence 탐지, write/retrieve/activate 판정, binary/executable/oversize, false positive, deterministic report/CLI, attack success와 benign rejection 지표, network/process capability 부재를 검사한다.

## 통합 시 fail-closed 절차

1. collector가 외부 byte를 content-addressed quarantine에 새 파일로 쓴다.
2. 저장된 byte를 다시 읽어 manifest hash와 일치하는지 확인한다.
3. binary parser는 별도 sandbox와 제한된 자원으로 실행한다. scanner에게 parser 실행 권한을 주지 않는다.
4. `assess_content` 오류가 나면 case를 review queue로 보내고 canonical write/retrieval/activation을 멈춘다.
5. write가 allow여도 source-admission gate 뒤의 candidate만 만든다. C-level/source-level을 올리지 않는다.
6. retrieve 결과에 manifest hash, source ID, gate decision, signal ID를 함께 전달한다. signal을 떼어낸 text만 모델에 보내지 않는다.
7. activate는 사용자 요청에서 독립적으로 다시 검사한다. source가 제안한 action을 사용자 승인으로 오해하지 않는다.
8. review actor는 원 claim/source 작성자와 독립성을 기록한다. review 결과와 override 이유는 append-only event/receipt에 남긴다.
9. reject된 raw를 삭제하지 않는다. 접근 통제된 quarantine에서 hash와 provenance를 유지해 재현과 rule 개선에 사용한다.

## 알려진 한계와 우회 가능성

이 scanner만으로는 다음을 방어할 수 없다.

- 동의어, 은어, 다국어, 문장 분할을 사용한 semantic prompt injection
- 짧은 조각을 여러 문서·turn에 나눠 결합하는 공격
- base64 외 암호화·압축·homoglyph·steganography와 adversarial image/audio/video
- PDF/Office/archive parser 취약점과 sandbox escape
- 정상 명령처럼 보이는 domain-specific excessive agency
- 오염된 trusted source, dependency, citation graph, retrieval ranking
- 모델이 signal label이나 quoted payload 자체를 instruction으로 오해하는 경우
- reviewer 또는 별도 verifier가 같은 공격에 취약한 경우
- 알려진 pattern을 피하도록 fixture에 과적합한 공격
- 실제 secret 값이 excerpt/source reference/event log로 새는 모든 경우

lexical rule은 recall과 false-positive 비용 사이의 초기선일 뿐이다. production 방어에는 parser sandbox, 최소 권한, immutable provenance, content security policy, retrieval label 전파, model/tool 권한 분리, adversarial semantic verifier, independent review, canary secret, audit receipt, rollback, 주기적 새로운 holdout corpus가 함께 필요하다. fixture를 수정해 실패를 숨기지 말고 새 공격을 먼저 holdout으로 재현한 뒤 최소 rule 또는 architecture 변경을 RFC로 제안한다.
