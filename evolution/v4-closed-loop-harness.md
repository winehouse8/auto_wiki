# v4 — Closed-loop human–Agent research harness

## Why v4 exists

v3.1 had a provenance-aware ledger, governed campaigns, and a portable OKF bundle, but the research loop was still open. Calibration was not measured, source admission and poisoning checks were not writer gates, human direction lacked one shared lifecycle object, recurring interests could stop after the last campaign, and no single release decision combined structural, security, runtime, and regression evidence.

`RFC-69828EB38078` authorized an additive v4 control plane. It did not authorize external publication, credential use, paid work, raw deletion, or silent trust-policy changes.

## Implemented loop

1. `collaboration-add` records human and Agent direction/correction/lead/objection with the same schema.
2. `interest-seed` turns cadence-due interest questions into bounded campaigns. It does no research.
3. `run-plan` emits only `external.research.plan` actions and a hash-chained receipt. Runtime side effects stay zero.
4. `security-screen` stores a content-addressed quarantine copy, separates normalized text, and evaluates write/retrieve/activate gates without executing payloads.
5. `admission-check` canonicalizes source identity, checks provenance/status/counter-search, clusters likely dependency, and returns allow/review/reject.
6. `source-add` requires an event-anchored source-admission allow. File-backed sources also require a matching SHA-256 security allow.
7. Atomic claims, exact evidence locators, independent review, contradiction retention, evaluation, render, and OKF validation remain the epistemic core.
8. `search` and `impact` provide deterministic lexical retrieval and dependency/conflict candidates; neither makes semantic truth decisions.
9. `run-action-report` attributes external results, accounts campaign budget only on completed reports, and anchors a report digest. The report remains explicitly `unverified_report`.
10. `release-check` combines structural/event validation, OKF core/profile validation, pinned calibration/security/runtime fixtures, receipt-chain checks, and the actual unit-test result.

## Additive state and projection migration

v4 adds canonical ledgers for `collaborations`, `admissions`, and `runs`. Their generated OKF views live under `wiki/collaborations/`, `wiki/admissions/`, and `wiki/runs/`. JSON, quarantine artifacts, executable code, secrets, and receipts remain outside the `wiki/` bundle.

Existing v3.1 source records are not rewritten to pretend that they passed a gate which did not exist. Exactly 35 pre-v4 source IDs are listed in `migrations/v3.1-source-grandfather.json`. The manifest file hash is pinned in the validator. An admission-less source outside that finite set is a hard error. Grandfathering neither upgrades trust nor supplies a missing immutable artifact.

The source grandfather manifest SHA-256 is:

```text
6c7ecd0c7a99a679534de7ca265fb3254b4091720c98f168619c6cf60c792dac
```

## Pinned regression fixtures

The release gate rejects silent fixture weakening. It pins canonical JSON hashes rather than treating any easier replacement corpus as equivalent.

| Fixture | Pinned canonical SHA-256 | Meaning |
|---|---|---|
| calibration | `7d3674bb803f1f23bf67c1191d3b017f3b22df1b5a2d26fe6eedda9b3726782d` | 15-case smoke/pilot only |
| security | `38c337f61795f67ee7b0893b3bb81f19ebab7368136a1657022882ae56f30eea` | 31-case lexical regression corpus |
| runtime | `e5e6da8aa314d89f6e8e6f65351d105773f827b1c24dfb957c3eb5c5dd02521a` | actor parity, permission, schedule, receipt scenarios |

Changing a fixture requires an explicit RFC, new benchmark evidence, and an updated pinned hash. A change that merely removes failing cases is not an improvement.

## Rollback contract and rehearsal

Rollback disables v4 commands and uses the committed v3.1 control plane against the preserved core state; it does not delete v4 events, raw artifacts, admission decisions, or receipts. The v3.1 code ignores the additive state files. Derived `wiki/` views may be regenerated from whichever control-plane version is active.

The rehearsal procedure is:

1. export committed v3.1 (`d18213a78376c0543a0aa590a3db7fcf7022c187`) to an isolated temporary directory;
2. copy the current core v3-compatible ledgers and immutable raw artifacts into that directory;
3. run the v3.1 `render --no-log`, `validate`, and `okf-validate` there;
4. verify the live workspace was not changed;
5. discard the temporary directory.

The release report records the actual rehearsal result. A rollback is an operational fallback, not a deletion or history rewrite. New v4-only collaboration/admission/run state remains available for later forward recovery.

## Release meaning and limits

A passing v4 report uses readiness `closed_loop_harness_fixed_fixture_passed` and always says `production_certified=false`.

Known limits remain:

- empirical calibration has 15 pilot items, not the designed 100-item independently adjudicated set;
- fixed lexical rules do not cover unseen semantic, multilingual, multimodal, parser, or multi-turn attacks;
- live Crossref/NCBI/GitHub status adapters are contracts/official-source research, not deployed network adapters;
- canonical independent claim reviews are still absent, so C3/C4 remain empty;
- BM25-like search is not semantic retrieval and conflict detection produces candidates only;
- external executor, credential broker, publication path, signature, and multi-writer locking are not certified;
- event and receipt hashes detect mutation but do not authenticate actor identity.

These are open operational and empirical research goals, not reasons to relabel fixed-fixture results as production evidence.
