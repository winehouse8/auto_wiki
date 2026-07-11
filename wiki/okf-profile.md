---
type: OKF Profile
title: Living Wiki OKF profile
description: How this OKF v0.1 bundle maps its epistemic and governance extensions.
resource: https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md
tags: [okf, interoperability, profile]
timestamp: '2026-07-12T12:00:00+09:00'
okf_version: '0.1'
spec_status: Draft
bundle_boundary: wiki/
claim_ids: [CLM-7FDAF2F91E73, CLM-952258184EF2, CLM-F526A53CB69F]
---

# Living Wiki OKF profile

The `wiki/` directory is the portable Open Knowledge Format bundle. The repository around it is the control plane and is intentionally outside the bundle boundary.

# Conformance

- Every non-reserved Markdown document has YAML frontmatter with a non-empty `type`.
- `index.md` and `log.md` are reserved and remain frontmatter-free.
- Cross-links use standard Markdown links.
- Directory indexes provide progressive disclosure.
- External evidence appears under `# Citations` where applicable.
- Unknown producer extension keys must be preserved by consumers.

# Living Wiki extensions

OKF v0.1 deliberately leaves taxonomy, storage, query infrastructure, trust, and governance to producers. This bundle uses allowed frontmatter extensions:

| Key | Meaning |
|---|---|
| `claim_ids` | Canonical IDs in `../state/claims.json` |
| `source_id` | Canonical source record in `../state/sources.json` |
| `source_level` | Scoped S0-S4 source evidence maturity |
| `lifecycle_status` | Draft/active/contested/superseded state |
| `generated` | Deterministically generated derived view |
| `okf_version` | Pinned format version for this profile document |

These keys extend OKF; they are not claims that the v0.1 specification defines trust or provenance semantics.

# Object mapping

| Living Wiki object | OKF representation | Canonical control-plane record |
|---|---|---|
| Concept/synthesis/position | Typed concept Markdown | claim links in frontmatter/body |
| External source | `sources/src-*.md`, `type: Reference` | `state/sources.json` |
| Atomic claim | `claims/clm-*.md`, `type: Claim` with evidence table | `state/claims.json` |
| Actor | `actors/actor-*.md`, `type: Actor` | `state/actors.json` |
| Review | `reviews/rev-*.md`, `type: Review` | `state/reviews.json` |
| Research campaign | `campaigns/cmp-*.md`, `type: Research Campaign` | `state/campaigns.json` |
| Collaboration record | `collaborations/col-*.md`, `type: Collaboration Record` | `state/collaborations.json` |
| Admission decision | `admissions/adm-*.md`, `type: Admission Decision` | `state/admissions.json` |
| Runtime receipt | `runs/run-*.md`, `type: Runtime Receipt` | `state/runs.json` and external receipt ledger |
| Trust/governance | Typed producer-policy concepts | `config/` and `governance/` |
| Event | Reserved human-readable `log.md` summary | `state/events.jsonl` hash chain |
| Navigation/history | Reserved `index.md` / `log.md` | regenerated from canonical state |

# Boundary rationale

OKF is the interoperable knowledge exchange layer, not the entire runtime. JSON ledgers, raw/quarantine artifacts, evaluator snapshots, receipts, secrets, and executable tooling stay outside the bundle. Actor, source, claim, review, campaign, collaboration, admission, runtime, trust, and governance records are one-way projections; the exporter does not invent or raise their status. An OKF-only consumer can still read the knowledge; a Living-Wiki-aware consumer can follow extension IDs into stronger provenance and governance data. Direct edits to generated concepts are not imported back into canonical state in v4.

# Known limitation

The official specification is version 0.1 and marked Draft as of 2026-07-11. This repository pins the profile and tests it locally; future breaking OKF changes require a migration RFC rather than silent rewrites.

# Citations

[1] [Google Cloud announcement: How the Open Knowledge Format can improve data sharing](https://cloud.google.com/blog/products/data-analytics/how-the-open-knowledge-format-can-improve-data-sharing)
[2] [Official Open Knowledge Format v0.1 specification](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md)
