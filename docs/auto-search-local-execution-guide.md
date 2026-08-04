# Stage 8A.2 ローカル実行ガイド

本探索はOpenAI/Codex/ChatGPT/API/networkを使わず、`.venv`のローカルPythonとCPUだけで動く。最初に計画を確認する。

```bash
.venv/bin/python -m symbiotic_sim_v2 \
  --headless-fatigue-sigma-auto-search \
  --search-preset standard \
  --plan-only
```

smokeは32 sessionの実装確認専用で、候補妥当性を示さない。

```bash
.venv/bin/python -m symbiotic_sim_v2 \
  --headless-fatigue-sigma-auto-search \
  --search-preset smoke \
  --output-directory artifacts/auto_search_smoke
```

push後の本探索:

```bash
.venv/bin/python -m symbiotic_sim_v2 \
  --headless-fatigue-sigma-auto-search \
  --search-preset standard
```

robustは明示的に選ぶ場合だけ実行する。

```bash
.venv/bin/python -m symbiotic_sim_v2 \
  --headless-fatigue-sigma-auto-search \
  --search-preset robust
```

Ctrl+C 1回で安全停止を要求する。stdoutのrun directoryを使って再開する。

```bash
.venv/bin/python -m symbiotic_sim_v2 \
  --headless-fatigue-sigma-auto-search \
  --resume artifacts/auto_search/<run_id>
```

macOS launcherは`自動条件探索_計画確認.command`、`自動条件探索_標準.command`、`自動条件探索_堅牢.command`、`自動条件探索_再開.command`である。全launcherはproject直下へ移動し、`.venv`、Python 3.12+、main branch、clean worktreeを確認する。standard/robust launcherはplanと予定session数を表示し、実行前に`STANDARD`または`ROBUST`の明示確認を求める。stdout/stderrはrun directoryの`logs/launcher_stdout_stderr.log`へ保存し、resume launcherは入力pathのmanifest、plan、checkpoint、schemaを検証する。自動でbrowserを開かない。

完了後は`report/report.html`をブラウザで手動表示する。status、weak user type、flat safety、rotation、W ceiling、Pareto trade-off、replicate uncertainty、次の追加検証を確認する。結果は正式Profileへ自動採用されない。
