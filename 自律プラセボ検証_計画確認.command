#!/bin/zsh
set -euo pipefail

PROJECT_DIRECTORY="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)"
cd "$PROJECT_DIRECTORY"

if [[ ! -x .venv/bin/python ]]; then
  print -u2 -- "ERROR: .venv/bin/python がありません。"
  exit 1
fi
if ! .venv/bin/python -c 'import sys; raise SystemExit(sys.version_info < (3, 12))'; then
  print -u2 -- "ERROR: Python 3.12以上が必要です。"
  exit 1
fi
if [[ "$(git branch --show-current)" != "main" ]]; then
  print -u2 -- "ERROR: main branchで実行してください。"
  exit 1
fi
if [[ -n "$(git status --porcelain --untracked-files=all)" ]]; then
  print -u2 -- "ERROR: working treeがcleanではありません。"
  exit 1
fi

print -- "Project: $PROJECT_DIRECTORY"
print -- "Python: $(.venv/bin/python --version 2>&1)"
print -- "Preset: standard (plan-only)"
print -- "予定target session数: 12960"
.venv/bin/python -m symbiotic_sim_v2 \
  --headless-adaptive-placebo-validation \
  --validation-preset standard \
  --plan-only
