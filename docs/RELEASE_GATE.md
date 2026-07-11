# Living Wiki v4 release gate

`tools/release_gate.py`는 v4 하네스의 결정론적·읽기 전용 통합 gate다. 이 모듈은 `tools/wiki.py`를 import하지 않으며 저장소를 수정하거나 network/process를 실행하지 않는다. 중앙 control plane이 구조·event-chain·OKF·단위 테스트 결과를 주입하면, 모듈이 calibration, security corpus, collaboration/runtime fixture, receipt hash chain을 직접 재평가해 하나의 보고서로 합친다.

## 판정 범위

통합 보고서에는 여섯 hard gate가 있다.

1. `structural_and_ledger`: 중앙 validator가 주입한 오류가 0인가
2. `okf_bundle`: OKF core와 Living Wiki profile 오류가 0인가
3. `calibration`: gold fixture report가 결정론적이고 C0–C4를 확률로 재해석하거나 trust policy를 수정하지 않는가
4. `security`: 고정 공격/정상 corpus에서 attack success와 benign rejection이 0이고 payload/network/credential invariant가 0인가
5. `runtime`: 사람과 Agent가 같은 협업 envelope를 통과하고 permission fixture, bounded plan, receipt chain, side-effect invariant가 유효한가
6. `regression_tests`: 호출자가 명시적으로 주입한 test 결과가 성공했고 test 수가 1개 이상이며 격리된 v3.1 rollback rehearsal이 통과했는가

어느 하나라도 실행되지 않았으면 성공으로 간주하지 않는다. `None` findings와 unit-test 결과 부재는 각각 `validator_not_evaluated`, `regression_tests_not_evaluated`로 실패한다.

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
- 외부 executor, live status-registry adapter, credential broker 또는 publication path 인증
- 영수증 작성자 신원 인증이나 여러 writer의 직렬화 보장

보고서는 조건과 관계없이 `production_certified=false`를 유지한다. 현재 calibration fixture가 100건 미만이면 hard failure가 아니라 `pilot_fixture_below_100_record_empirical_calibration_target` 경고를 남긴다. 따라서 하네스 기능은 릴리스할 수 있지만 empirical calibration 완성으로 표현할 수 없다.

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

## Receipt 판정

release gate는 runtime과 같은 canonical JSON SHA-256 규칙으로 `prev_receipt_hash`와 `receipt_hash`를 확인한다. 다음은 hard failure다.

- 영수증 파일 부재·parse 오류·chain/hash 불일치
- release evidence 영수증이 0건
- `planned`, `dry_run`, `review_required`, `blocked` 영수증의 `side_effect_count > 0`
- `external.research.plan` action이 side effect를 실행했다고 표시됨
- `deny` 또는 `review` permission action이 side effect를 실행함

검증은 의도적인 재서명 공격, writer 인증, file locking을 해결하지 않는다. 실제 여러 writer 운용 전에는 서명과 transactional append/locking을 별도로 추가해야 한다.

## 테스트

```bash
python3 -m unittest tests.test_release_gate -v
python3 -m unittest discover -s tests -v
```

전용 테스트는 deterministic output, fail-closed injection, pilot calibration 표기, security 기준선, receipt tamper/side-effect 탐지, actor parity, permission/budget, 독립 CLI exit code, network/process import 부재를 고정한다.
