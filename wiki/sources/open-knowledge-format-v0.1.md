---
type: Reference
title: Open Knowledge Format v0.1 Draft
description: Official OKF structure, conformance rules, extension model, and limits relevant to Living Wiki.
resource: https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md
tags: [okf, specification, interoperability]
timestamp: '2026-07-11T23:55:00+09:00'
source_id: SRC-477696BD1807
source_level: S3
claim_ids: [CLM-7FDAF2F91E73, CLM-952258184EF2, CLM-F526A53CB69F]
---

# Open Knowledge Format v0.1 Draft

## Source status

- Official repository: `GoogleCloudPlatform/knowledge-catalog`
- Specification status: Version 0.1 — Draft
- Release/tag: none observed as of 2026-07-11
- License of official `okf/` directory: Apache-2.0
- Repository commit inspected: `d44368c15e38e7c92481c5992e4f9b5b421a801d`
- `SPEC.md` blob: `55d0a46cc988e99aa35cd027964d6278a4f93f35`
- Local snapshot SHA-256: `b9655e607346dbbdc6de21190e9a953313eda6a7eba68d4d272a65975940ad6e`

## Normative core used here

1. A bundle is a hierarchical directory of Markdown files.
2. Every non-reserved Markdown concept has parseable YAML frontmatter.
3. `type` is the only required core field and must be non-empty.
4. `index.md` and `log.md` are reserved filenames.
5. Standard Markdown links express cross-concept relationships.
6. Producer extension fields are permitted and unknown fields should be preserved.

## Deliberate non-goals

OKF does not prescribe a fixed type taxonomy, storage/query runtime, or replacement for domain schemas. It also does not define Living Wiki's claim confidence, source credibility, actor identity, evidence independence, review, poisoning defense, or self-evolution governance.

## Implementation caveat

The official reference agent is a proof of concept rather than the format itself. Its internal document model is stricter than the minimal spec in some paths, so this Wiki includes the recommended `title`, `description`, and `timestamp` fields as well as required `type`.

# Citations

[1] [Official Open Knowledge Format v0.1 specification](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/d44368c15e38e7c92481c5992e4f9b5b421a801d/okf/SPEC.md)
[2] [Google Cloud announcement](https://cloud.google.com/blog/products/data-analytics/how-the-open-knowledge-format-can-improve-data-sharing)
[3] [Official OKF README and reference implementation](https://github.com/GoogleCloudPlatform/knowledge-catalog/tree/d44368c15e38e7c92481c5992e4f9b5b421a801d/okf)
