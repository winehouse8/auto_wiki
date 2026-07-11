# OKF migration campaign — 2026-07-11

Campaign: `CMP-0619AC235CCA`

## User direction

Wiki 구축 시 Open Knowledge Format pattern을 따를 것.

## Primary sources inspected

- Google Cloud announcement
- Official `GoogleCloudPlatform/knowledge-catalog/okf/SPEC.md`
- Official OKF README, example bundles, reference-agent document/index code and tests
- Apache-2.0 license under the official `okf/` directory

## Reproducibility pin

- Repository HEAD: `d44368c15e38e7c92481c5992e4f9b5b421a801d`
- SPEC blob: `55d0a46cc988e99aa35cd027964d6278a4f93f35`
- Local snapshot SHA-256: `b9655e607346dbbdc6de21190e9a953313eda6a7eba68d4d272a65975940ad6e`
- Spec status: `Version 0.1 — Draft`, no release/tag observed on 2026-07-11

## Decision

`wiki/` itself is the dedicated OKF bundle root. The repository root is not an OKF bundle. Canonical claim/source/actor state, raw artifacts, governance, tests, and executable tools stay outside as a control plane.

## Changes

- Typed YAML frontmatter on every non-reserved bundle document
- Standard Markdown links instead of Obsidian wikilinks
- Reserved frontmatter-free indexes and update log
- `okf-profile.md` documenting producer extensions
- `okf-validate` plus global validation integration
- Unit tests for frontmatter parsing
- Harness minor version 3.1.0

## Critical caveats

- OKF has no mandatory manifest, JSON Schema, or type registry.
- Core v0.1 requires only non-empty `type`; recommended metadata is still emitted for broader tool compatibility.
- OKF does not solve credibility, provenance semantics, actor governance, or security.
- Official reference-agent implementation is a proof of concept and is stricter than the minimal spec in parts; it is not the normative format.

