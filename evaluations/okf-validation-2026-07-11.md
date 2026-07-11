# OKF export validation — 2026-07-11

Harness: 3.1.0  
Pinned spec: OKF 0.1 Draft  
Bundle: `wiki/`

## Conformance result

```text
OKF v0.1 bundle: wiki/ (75 concept documents)
OKF core and Living Wiki profile validation passed with 0 warning(s).
```

The 75 concepts are accompanied by 11 reserved `index.md`/`log.md` files, for 86 Markdown files total.

## Projection parity

| Object | Canonical state | Generated OKF concepts |
|---|---:|---:|
| Sources | 31 | 31 |
| Claims | 18 | 18 |
| Actors | 2 | 2 |
| Reviews | 0 | 0 |
| Campaigns | 5 | 5 |

Curated synthesis/reference/concept/policy documents account for the remaining concepts.

## Idempotence check

`python3 tools/wiki.py render --no-log` was run twice. SHA-256 manifests of all 86 Markdown files were byte-identical; `diff` returned no differences.

Manifest-list SHA-256 for this run:

```text
d3a0f55e6e925ad4bd2dd817cd38b545153b68f1cd5b94fec5b83a3b6c5815a5
```

The normal `render` command records a new audit event, so `log.md` intentionally changes. `--no-log` is the pure projection mode used for idempotence tests.

## Known limits

- The validator enforces the pinned v0.1 core plus the stricter Living Wiki profile; it is not an official Google conformance suite.
- The official project exposes no standalone conformance CLI as of the pinned revision.
- The fallback YAML validator accepts the flat producer profile used here; PyYAML, when present, performs strict YAML parsing.
- Semantic citation entailment, trust calibration, and memory-poisoning resistance are separate evaluations and remain pending.

