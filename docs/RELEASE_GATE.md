# Living Wiki v4.3 릴리스 게이트

`tools/release_gate.py`는 v4 하네스의 결정론적·읽기 전용 핵심 게이트다. 이 모듈은 `tools/wiki.py`를 가져오지 않으며 저장소를 수정하거나 네트워크·프로세스를 실행하지 않는다. 중앙 제어 계층이 구조·사건 연결·OKF·단위 테스트 결과를 주입하면, 모듈이 보정, 보안 자료 집합, 협업·실행환경 fixture와 영수증 해시 연결을 직접 재평가해 핵심 여섯 게이트를 만든다. `tools/wiki.py release-check`는 여기에 메모리 제어와 한국어 문서 계약을 더해 최종 여덟 게이트 보고서를 만든다.

## 판정 범위

통합 보고서에는 여덟 개의 필수 게이트가 있다.

1. `structural_and_ledger`: 중앙 validator가 주입한 오류가 0인가
2. `okf_bundle`: OKF core와 Living Wiki profile 오류가 0인가
3. `calibration`: gold fixture report가 결정론적이고 C0–C4를 확률로 재해석하거나 trust policy를 수정하지 않는가
4. `security`: 고정 공격/정상 corpus에서 attack success와 benign rejection이 0이고 payload/network/credential invariant가 0인가
5. `runtime`: 사람과 Agent가 같은 협업 envelope를 통과하고 permission fixture, bounded plan, receipt chain, side-effect invariant가 유효한가
6. `regression_tests`: 호출자가 명시적으로 주입한 test 결과가 성공했고 test 수가 1개 이상이며 격리된 v3.1 rollback rehearsal이 통과했는가
7. `memory_feedback_lifecycle_hygiene`: 고정된 메모리 피드백·생명주기 fixture와 명시적 시각의 위생 관찰이 결정론적이고 읽기 전용이며 신뢰·상태·내용을 자동 변경하지 않는가
8. `korean_documentation_contract`: `SPEC-KO-DOCS-001`에 따른 한국어 문서 검사가 현재 저장소와 생성 예정 릴리스 보고서에서 모두 통과하는가

어느 하나라도 실행되지 않았으면 성공으로 간주하지 않는다. `None` findings와 unit-test 결과 부재는 각각 `validator_not_evaluated`, `regression_tests_not_evaluated`로 실패한다.

GitHub 전달은 현재 이 여덟 개를 바꾸거나 아홉 번째 통합 게이트를 이미 제공한다고 주장하지 않는다. 여덟 게이트와 전체 단위 테스트가 먼저 통과한 뒤 별도의 delivery preflight가 정확한 저장소·기준 SHA·토큰 안전 계약·명시적 변경 manifest·위험 분류를 검사한다. PR의 비밀 없는 원격 workflow가 같은 저장소 품질 명령을 다시 실행하며, 자동 병합 후보는 check 결과와 base/head/tree SHA를 병합 직전 재확인한다.

## 통과의 정확한 의미

모든 gate가 통과하면 다음 값이 나온다.

```json
{
  "passed": true,
  "readiness": "closed_loop_harness_fixed_fixture_passed",
  "production_certified": false,
  "calibration_status": "pilot_regression_only",
  "security_status": "fixed_corpus_regression_only"
}
```

이 결과는 **로컬 bounded control plane과 현재 고정 fixture의 회귀검사가 통과했다**는 뜻이다. 다음을 뜻하지 않는다.

- C0–C4의 경험적 확률 calibration 완료
- 보지 못한 semantic prompt injection에 대한 production 보안 인증
- 외부 연구 실행기, 실시간 상태 등록부 어댑터, 자격증명 중개기 또는 GitHub 전달의 운영 환경 인증
- 영수증 작성자 신원 인증이나 여러 writer의 직렬화 보장

보고서는 조건과 관계없이 `production_certified=false`를 유지한다. 현재 calibration fixture가 100건 미만이면 hard failure가 아니라 `pilot_fixture_below_100_record_empirical_calibration_target` 경고를 남긴다. 따라서 하네스 기능은 릴리스할 수 있지만 empirical calibration 완성으로 표현할 수 없다.

빈 `winehouse8/auto_wiki`의 기준 ref를 만든 일회성 예외는 clean `5f1d7f0`만 `main`에 게시하고 [GitHub 이슈 #1](https://github.com/winehouse8/auto_wiki/issues/1)에 기록하면서 소진했다. 이는 전달 adapter나 자동 병합 성공 증거가 아니다. 첫 사람 검토 통합 PR이 병합된 뒤 별도 무해한 canary PR에서 원격 check와 auto-merge를 전진 검증하기 전까지 live 전달 상태는 미완료다.

## Python 통합

중앙 CLI는 자신의 validator 결과와 실제로 끝난 unit-test 요약을 주입한다.

```python
from tools import release_gate

validation_errors, validation_warnings, counts = validation_findings()
okf_errors, okf_warnings = combined_okf_findings()
actual_test_count = count_from_completed_test_receipt

report = release_gate.evaluate_repository(
    ROOT,
    structural_findings=(validation_errors, validation_warnings, counts),
    okf_findings=(okf_errors, okf_warnings),
    regression_result={
        "passed": True,
        "test_count": actual_test_count,
        "failures": 0,
        "errors": 0,
        "skipped": 0,
        "evidence": "captured test receipt or report hash",
        "rollback_rehearsal_passed": True,
        "rollback_evidence": "isolated v3.1 render/validate/okf receipt hash",
        "rollback_base_commit": "d18213a78376c0543a0aa590a3db7fcf7022c187",
        "rollback_live_workspace_unchanged": True,
    },
)
```

공개된 핵심 API는 다음과 같다.

```python
canonical_json(value, pretty=False)
normalize_findings(findings)
evaluate_calibration_fixture(fixture)
evaluate_security_corpus(corpus)
verify_receipt_chain(receipts)
evaluate_runtime_fixture(fixture, receipts, receipt_read_errors=())
evaluate_regression_result(result)
build_release_report(...)
evaluate_repository(root, ...)
load_receipts(path)
```

`evaluate_repository()`의 기본 입력 경로는 다음과 같다.

- `evaluations/fixtures/calibration-gold.json`
- `evaluations/fixtures/security-corpus.json`
- `evaluations/fixtures/runtime-scenarios.json`
- `evaluations/receipts/receipts.jsonl`

결과에는 실행 시각, 절대 경로, host 정보, 난수가 없으므로 동일 snapshot과 동일 주입 findings에서 byte-stable하다. fixture/report와 receipt sequence의 SHA-256은 비교용 fingerprint로 기록하지만 서명으로 취급하지 않는다.

`evaluate_repository()`는 RFC 승인 시점의 calibration/security/runtime fixture SHA-256을 코드에 고정한다. fixture 내용이 바뀌면 지표가 여전히 좋아 보여도 `*_fixture_hash_drift`로 실패한다. 평가셋 변경은 새 공격·gold 사례의 근거, 과적합 위험, 이전/새 결과 비교를 검토한 뒤 pinned baseline을 명시적으로 갱신해야 한다. 개별 `evaluate_*` API의 expected-hash 인자는 evaluator 자체를 시험할 때만 생략할 수 있다.

## 독립 CLI

모듈은 unit test나 Wiki validator를 subprocess로 실행하지 않는다. 호출자가 JSON 결과를 준비해 넘긴다.

```bash
python3 tools/release_gate.py \
  --root . \
  --structural-findings evaluations/reports/structural-findings.json \
  --okf-findings evaluations/reports/okf-findings.json \
  --regression-result evaluations/reports/unit-test-result.json
```

exit code는 `0=모든 gate 통과`, `4=정상적으로 평가했지만 하나 이상 실패`, `2=입력 파일 오류`다. JSON 파일을 주입하지 않은 독립 실행은 해당 gate를 “실행 안 됨”으로 실패시키며, 현재 상태가 깨끗하다고 추측하지 않는다.

## 영수증 판정

release gate는 runtime과 같은 canonical JSON SHA-256 규칙으로 `prev_receipt_hash`와 `receipt_hash`를 확인한다. 다음은 hard failure다.

- 영수증 파일 부재·parse 오류·chain/hash 불일치
- release evidence 영수증이 0건
- `planned`, `dry_run`, `review_required`, `blocked` 영수증의 `side_effect_count > 0`
- `external.research.plan` action이 side effect를 실행했다고 표시됨
- `deny` 또는 `review` permission action이 side effect를 실행함

검증은 의도적인 재서명 공격, writer 인증, file locking을 해결하지 않는다. 실제 여러 writer 운용 전에는 서명과 transactional append/locking을 별도로 추가해야 한다.

## 격리 원문 검증 프로필

기본 `release-check`는 `strict-local-custody`를 사용해 admission이 가리키는 로컬 격리 payload의 존재와 실제 SHA-256을 요구한다. exact public Git delivery linked worktree와 비밀 없는 PR workflow만 `--quarantine-profile public-clean-clone`을 명시할 수 있다. 이 경우 누락은 엄격한 canonical metadata·보안 manifest·사건 anchor가 모두 맞을 때만 경고이며 보고서는 누락 수와 `quarantine_payload_verified=false`를 기록한다. 이는 부재한 bytes의 보안 재검증이나 source·trust 승격이 아니다.

## 테스트

```bash
python3 -m unittest tests.test_release_gate -v
python3 -m unittest tests.test_github_delivery tests.test_github_delivery_contract -v
python3 -m unittest discover -s tests -v
```

전용 테스트는 deterministic output, fail-closed injection, pilot calibration 표기, security 기준선, receipt tamper/side-effect 탐지, actor parity, permission/budget, 독립 CLI exit code, network/process import 부재를 고정한다. GitHub 전달 테스트는 `no-op|safe|review|block`, exact repository, token 비노출, manifest, 멱등성, drift·실패 check와 사람 검토 PR의 merge 호출 0회를 fake transport로 검증한다. 이 결과는 live GitHub 네트워크나 자격증명 사용 성공을 뜻하지 않는다.
