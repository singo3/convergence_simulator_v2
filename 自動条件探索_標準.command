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
print -- "Preset: standard"
print -- "実行予定session数を含む計画:"
.venv/bin/python -m symbiotic_sim_v2 \
  --headless-fatigue-sigma-auto-search \
  --search-preset standard \
  --plan-only

print -- ""
read -r "CONFIRMATION?標準探索をローカルCPUで開始するには STANDARD と入力してください: "
if [[ "$CONFIRMATION" != "STANDARD" ]]; then
  print -- "キャンセルしました。"
  exit 0
fi

OUTPUT_BASE="artifacts/auto_search"
CAPTURE_BASE="artifacts/auto_search-launcher-logs"
mkdir -p "$OUTPUT_BASE" "$CAPTURE_BASE"
CAPTURE_PATH="$CAPTURE_BASE/standard-$(date -u +%Y%m%dT%H%M%SZ)-$$.log"
BEFORE_PATH="$CAPTURE_PATH.before"
AFTER_PATH="$CAPTURE_PATH.after"
find "$OUTPUT_BASE" -mindepth 1 -maxdepth 1 -type d -print | LC_ALL=C sort > "$BEFORE_PATH"

set +e
.venv/bin/python -m symbiotic_sim_v2 \
  --headless-fatigue-sigma-auto-search \
  --search-preset standard \
  --output-directory "$OUTPUT_BASE" 2>&1 | tee "$CAPTURE_PATH"
COMMAND_STATUS=${pipestatus[1]}
set -e

find "$OUTPUT_BASE" -mindepth 1 -maxdepth 1 -type d -print | LC_ALL=C sort > "$AFTER_PATH"
RUN_DIRECTORY="$(comm -13 "$BEFORE_PATH" "$AFTER_PATH" | head -n 1)"
rm -f "$BEFORE_PATH" "$AFTER_PATH"
if [[ -n "$RUN_DIRECTORY" && -d "$RUN_DIRECTORY" ]]; then
  mkdir -p "$RUN_DIRECTORY/logs"
  mv "$CAPTURE_PATH" "$RUN_DIRECTORY/logs/launcher_stdout_stderr.log"
  REPORT_PATH="$RUN_DIRECTORY/report/report.html"
  print -- "Run directory: $RUN_DIRECTORY"
  print -- "report.html: $REPORT_PATH"
else
  print -u2 -- "Run directoryを特定できません。console log: $CAPTURE_PATH"
fi
exit "$COMMAND_STATUS"
