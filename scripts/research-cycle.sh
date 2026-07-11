#!/usr/bin/env sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT"

python3 tools/wiki.py next-task
printf '\n'
printf '%s\n' '--- Agent prompt ---'
cat prompts/research-cycle.md

if [ "${WIKI_AGENT_CMD:-}" != "" ]; then
  printf '\n%s\n' "Running configured agent command: $WIKI_AGENT_CMD"
  exec sh -c "$WIKI_AGENT_CMD" < prompts/research-cycle.md
fi

printf '\n%s\n' 'Set WIKI_AGENT_CMD to a trusted local agent runner to execute; without it this script is a safe dry run.'

