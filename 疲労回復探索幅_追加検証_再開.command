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

RUN_DIRECTORY="${1:-}"
if [[ -z "$RUN_DIRECTORY" ]]; then
  read -r "RUN_DIRECTORY?resumeするrun directory pathを入力してください: "
fi
if [[ ! -d "$RUN_DIRECTORY" ]]; then
  print -u2 -- "ERROR: run directoryがありません: $RUN_DIRECTORY"
  exit 1
fi
if [[ ! -f "$RUN_DIRECTORY/validation_manifest.json" || ! -f "$RUN_DIRECTORY/validation_plan.json" || ! -f "$RUN_DIRECTORY/checkpoint.json" ]]; then
  print -u2 -- "ERROR: manifest、plan、checkpointのどれかがありません。"
  exit 1
fi

.venv/bin/python - "$RUN_DIRECTORY/validation_manifest.json" <<'PY'
import json
import sys
from pathlib import Path

manifest = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
if manifest.get("schema_version") != "fatigue_recovery_sigma_factorial_manifest_v1":
    raise SystemExit("ERROR: factorial validation manifest schemaが一致しません。")
PY

print -- "Project: $PROJECT_DIRECTORY"
print -- "Python: $(.venv/bin/python --version 2>&1)"
print -- "Run directory: $RUN_DIRECTORY"
print -- "Planned actual simulation sessions: $(.venv/bin/python -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["planned_session_runs"])' "$RUN_DIRECTORY/checkpoint.json")"

mkdir -p "$RUN_DIRECTORY/logs"
CAPTURE_PATH="$RUN_DIRECTORY/logs/launcher_resume_stdout_stderr_$(date -u +%Y%m%dT%H%M%SZ).log"
set +e
.venv/bin/python -m symbiotic_sim_v2 \
  --headless-fatigue-recovery-sigma-factorial-validation \
  --resume "$RUN_DIRECTORY" 2>&1 | tee "$CAPTURE_PATH"
COMMAND_STATUS=${pipestatus[1]}
set -e

print -- "report.html: $RUN_DIRECTORY/report/report.html"
exit "$COMMAND_STATUS"
