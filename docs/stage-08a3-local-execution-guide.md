# Stage 8A.3 local execution guide

Stage 8A.3はローカルCPUだけで実行し、OpenAI、Codex、ChatGPT、外部LLM/API、network serverを使用しない。実行前にmain branch、clean working tree、`.venv/bin/python`を確認する。

## 計画確認

```bash
.venv/bin/python -m symbiotic_sim_v2 \
  --headless-adaptive-placebo-validation \
  --validation-preset standard \
  --plan-only
```

plan-onlyはdirectoryやcheckpointを作らず、standardは12,960、robustは64,800 target session runsを表示する。上限超過はclipせず拒否する。

## smoke

```bash
.venv/bin/python -m symbiotic_sim_v2 \
  --headless-adaptive-placebo-validation \
  --validation-preset smoke \
  --output-directory artifacts/adaptive_placebo_validation_smoke
```

smokeは2 types × 2 participants × 4 sessions × 3 arms = 48 target sessionsの実装確認で、有効性を示さない。Codex作業中に実行してよい本Stageのrunはsmokeだけである。

## standard / robust

```bash
.venv/bin/python -m symbiotic_sim_v2 \
  --headless-adaptive-placebo-validation --validation-preset standard

.venv/bin/python -m symbiotic_sim_v2 \
  --headless-adaptive-placebo-validation --validation-preset robust
```

standard/robust本検証はpush後に利用者が実行する。明示conditionは`--conditions-json PATH`、全configは`--validation-config PATH`。`--base-master-seed`、`--participants-per-type`、`--maximum-sessions`、`--permutation-count`、`--retain-details compact|representative|all`で上書きできる。`compact`はevent ledgerを保存せず、`representative`は各user typeのparticipant index 0だけを保存する。巨大化を防ぐため`all`はsmoke presetだけで使用できる。

## resume

```bash
.venv/bin/python -m symbiotic_sim_v2 \
  --headless-adaptive-placebo-validation \
  --resume artifacts/adaptive_placebo_validation/<run_id>
```

resumeはspec/code/platform fingerprint、manifest/plan/checkpoint、completed result checksum、全donor sequence checksumをstrictに検証する。completed participant/armを重複実行しない。SIGINT/SIGTERMはparticipant完了境界でgraceful cancelする。

run directory直下にmanifest、plan、checkpoint、必須14種にcontemporaneous指標を加えた15種CSV、digests、`report/report.html`、participant別HTML、logを保存する。`compact`では全sessionの巨大event ledgerを保存しない。macOSでは`self-contained`launcherの `自律プラセボ検証_計画確認.command`、`_標準.command`、`_堅牢.command`、`_再開.command`を使える。
