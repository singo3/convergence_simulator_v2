# Stage 8A.3.1 ローカル実行ガイド

## 事前条件

プロジェクト直下で、`.venv/bin/python`、Python 3.12以上、`main` branch、clean working treeを確認する。resumeは作成時と現在のGit HEAD、dirty-state digest、規範仕様fingerprint、project/package、Python/platform、Stage 8A.1/8A.2/8A.3/8A.3.1 versionが一致しない場合に停止する。外部network、OpenAI、Codex、ChatGPT、外部LLM/APIは使用しない。

## plan-only

standardのactual simulation sessionsは10,800、logical comparison sessionsは17,280である。plan-onlyはsimulationやrun directoryを作らない。

```bash
.venv/bin/python -m symbiotic_sim_v2 \
  --headless-fatigue-recovery-sigma-factorial-validation \
  --validation-preset standard \
  --plan-only
```

macOSでは`疲労回復探索幅_追加検証_計画確認.command`を開く。

## smoke

smokeは3 user types×2 participants×4 sessionsを4 conditionsのautonomousで実行す96 sessionsと、participantごと1回のshared random 24 sessions、合計120 actual sessionsである。

```bash
.venv/bin/python -m symbiotic_sim_v2 \
  --headless-fatigue-recovery-sigma-factorial-validation \
  --validation-preset smoke \
  --output-directory artifacts/fatigue_recovery_sigma_factorial_smoke
```

smokeは実装・配線・artifactの確認用で、MVP条件選択の根拠にしない。

## standard / robust

standardはactual 10,800 sessions、robustはactual 54,000 sessionsである。次のどちらかで実行できる。

```bash
.venv/bin/python -m symbiotic_sim_v2 \
  --headless-fatigue-recovery-sigma-factorial-validation \
  --validation-preset standard

.venv/bin/python -m symbiotic_sim_v2 \
  --headless-fatigue-recovery-sigma-factorial-validation \
  --validation-preset robust
```

macOSの`疲労回復探索幅_追加検証_標準.command`と`_堅牢.command`は事前条件とplanを確認し、`STANDARD`または`ROBUST`の確認入力後にだけ開始する。stdout/stderrはrunの`logs/launcher_stdout_stderr.log`へ保存する。

## resume

SIGINT/SIGTERM受信後はparticipantまたはparticipant-conditionのatomic boundaryまでで停止する。completed jobとshared-random cacheを再実行せず、cache checksumを再検証する。

```bash
.venv/bin/python -m symbiotic_sim_v2 \
  --headless-fatigue-recovery-sigma-factorial-validation \
  --resume artifacts/fatigue_recovery_sigma_factorial/<run_id>
```

macOSでは`疲労回復探索幅_追加検証_再開.command <run_directory>`を使う。launcherは`fatigue_recovery_sigma_factorial_manifest_v1`とmanifest/plan/checkpointの存在を確認する。

## option

`--base-master-seed`、`--participants-per-type`、`--maximum-sessions`、`--output-directory`、`--retain-details compact|representative|all`を指定できる。`all`はsmokeに限定される。A/B/C/Dは固定matrixで、Stage 8A.3の`--conditions-json`と`--validation-config`は受け付けない。

## 成果確認

runの`checkpoint.json`が`phase=completed`、`analysis_complete=true`、`report_complete=true`であることを確認する。主reportは`report/report.html`、participant別は`report/participants/`、user-type別は`report/user_types/`にある。`digests.json`で保存artifactのSHA-256を確認できる。`condition_recommendation.json`は透明gateのsimulation-only出力で、正式仕様の自動採用ではない。
