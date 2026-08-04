# Stage 8A.2 output schemas v0.1

主要versionはmanifest `fatigue_sigma_auto_search_manifest_v1`、plan `fatigue_sigma_auto_search_plan_v1`、job `fatigue_sigma_auto_search_job_v1`、checkpoint `fatigue_sigma_auto_search_checkpoint_v1`、recommendation `fatigue_sigma_recommendation_v1`、report `fatigue_sigma_auto_search_report_v1`である。

## Top-level

- `search_manifest.json`: immutable config、code/spec fingerprint、offline/no-LLM flags、`formal_spec_adoption=false`
- `search_plan.json`: phase、条件、user type、replicate、sessions、最大budget、絞込みhistory
- `checkpoint.json`: job status、attempt、checksummed result path、completed/planned sessions
- `jobs.jsonl`: canonical job ID順のimmutable job definitions
- `runtime_summary.json`: status、phase、job/session数、elapsed、report path

## Results

`results/`にはphase 1/2/3、全replicate、全condition、user type breakdown、flat safety、rotation、W ceiling、Pareto、robust、specialist、reference比較、blockerのCSVと`recommended_conditions.json`を出す。未実行phaseもheaderだけのCSVを持つ。

割合はsuccess/total/rate/lower95/upper95、連続値はcount/mean/median/min/max/q1/q3を持つ。nested構造はCSV cell内canonical JSONで表す。NaN/Infinityは禁止する。

## Retention

- `compact_summary`: replicate summaryとdigestだけ
- `phase3_full`: Phase 3のStage 8A.1 detached detailsを追加（既定）
- `all_full`: 全jobのdetached detailsを追加

SimulationEngine event ledgerは保存しない。failed jobは最小error auditを`failed_jobs/`へ保存する。reference cacheはuser type、session数、replicate seed、fingerprint、reference versionsをkeyとし、conditionを含まない。
