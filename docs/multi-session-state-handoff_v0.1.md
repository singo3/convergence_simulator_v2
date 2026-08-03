# Multi-session state handoff v0.1

runner versionは`multi_session_relation_memory_runner_v0_1`、run state schemaは`multi_session_relation_state_v1`である。Stage 5Cのstrict `relation_memory_state_v2` documentを、正常完了session間だけで受け渡す。

## 引き継ぐstate

- `k_anchor`
- `q`
- user_garden scopeの`E`
- `trial_count`
- `session_count`
- profile / algorithm / state schema metadata

## 毎session再取得・resetするstate

- `N_baseline_session`、`N_current`
- `Nd=0.5`、`W=0.5`
- `W_anchor_session=null`
- `k_trial`、`W_trial_1`、`W_trial_2`
- adaptation phase、exploration decision
- Garden holder、touch order
- light command/phaseとresponse dynamics

`W_anchor_session`は新sessionのBundle 0でanchorを提示した有効評価から初めて設定する。異なるbaselineのWを直接比較しない。inter-session gapや日単位E回復式は追加せず、新session冒頭60秒の既存S=0期間だけが既存E回復を進める。

1sessionごとに新しいengine/component群を生成する。正常な240秒closingと3生命のfinal persistent stateを検証してstateをcommitする。baseline有効性、holder存在、final anchorの物理光変換可能性は一次収束票の`valid_for_convergence`を決める。それらが不成立でもengineが正常closingしたsessionはinvalid historyとして正常なfinal stateをcommitし、後続sessionへ進む。errorまたは未完了の場合のみ、outcomeをinvalid/errorとして記録し、直前の確定stateを維持して次sessionへ進まない。

各`SessionOutcome`はfull initial/final persistent stateを保持する。JSON resumeではuser type、convergence config、versions、3生命ID、`next_session_index`、outcome件数に加え、session nのfinalとsession n+1のinitialをexact比較する。比較対象は`k_anchor`だけでなく`q`、`E`、`trial_count`、`session_count`、全version metadataである。未完了attempt後に別sessionを置くstate、未commitなのにcurrent stateを進めたstateも拒否する。

CLIで`--initial-multi-session-state-json`を指定した場合は保存stateの設定をauthoritativeとし、parserの既定値で上書きしない。GUI、CSV、pause、1件ずつ実行、batch実行、JSON round-tripで確定結果とdigestを変えない。
