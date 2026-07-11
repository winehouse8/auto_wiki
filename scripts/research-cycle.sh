#!/usr/bin/env sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT"

if [ "${WIKI_NOW:-}" != "" ]; then
  python3 tools/wiki.py interest-seed --now "$WIKI_NOW"
  python3 tools/wiki.py run-plan --now "$WIKI_NOW" --max-campaigns 1 --max-actions 1
else
  python3 tools/wiki.py interest-seed
  python3 tools/wiki.py run-plan --max-campaigns 1 --max-actions 1
fi

python3 tools/wiki.py next-task
printf '\n'
printf '%s\n' '--- Agent prompt ---'
cat prompts/research-cycle.md

printf '\n%s\n' 'Planning only: this script never invokes a shell-configured external Agent.'
printf '%s\n' 'Use the emitted RUN/ACT record with an explicitly authorized executor, then attach its result with run-action-report.'
