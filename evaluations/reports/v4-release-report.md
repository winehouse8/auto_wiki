# Living Wiki v4 release report

- Result: **PASS**
- Readiness: `closed_loop_harness_fixed_fixture_passed`
- Production certified: **false**
- Calibration: `pilot_regression_only`
- Security: `fixed_corpus_regression_only`
- Component fingerprint: `b1158d93cdf3bfc35376012ec3fdc560e2885203285278aad178d22d4424d5d0`

| Gate | Result | Errors | Warnings |
|---|---|---:|---:|
| structural_and_ledger | PASS | 0 | 36 |
| okf_bundle | PASS | 0 | 0 |
| calibration | PASS | 0 | 1 |
| security | PASS | 0 | 2 |
| runtime | PASS | 0 | 1 |
| regression_tests | PASS | 0 | 0 |

## Interpretation

이 판정은 로컬 control plane과 고정 fixture의 회귀 통과를 뜻한다. 장기 empirical calibration, 보지 못한 semantic attack, live external executor, credential/publication 경로를 인증하지 않는다.
