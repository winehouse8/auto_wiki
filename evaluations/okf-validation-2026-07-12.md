# OKF validation — 2026-07-12

## Scope

- Bundle boundary: `wiki/`
- Pinned format: Open Knowledge Format v0.1 Draft
- Producer profile: Living Wiki v4
- Control plane outside bundle: JSON ledgers, raw/quarantine, receipts, evaluation artifacts, tools, secrets

## Result

- OKF concept documents: 92
- Core errors/warnings: 0 / 0
- Living Wiki profile errors/warnings: 0 / 0
- State projection parity: source 35, claim 26, actor 2, review 0, campaign 5, RFC 1, collaboration 1, admission 1, run 1

Commands:

```bash
/opt/homebrew/bin/python3.13 tools/wiki.py render --actor agent:codex
/opt/homebrew/bin/python3.13 tools/wiki.py okf-validate
/opt/homebrew/bin/python3.13 tools/wiki.py validate
```

This validates format, links, required metadata, event/state invariants, and projection parity. It does not certify the truth of claims or the safety of external content.
