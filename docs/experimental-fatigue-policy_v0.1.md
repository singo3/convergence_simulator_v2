# Experimental fatigue policy v0.1

`selected_session_saturating_fatigue_v0_1`と`unselected_full_recovery_at_session_end_v0_1`はStage 8A.1 experimental armだけに適用するsimulation assumptionである。v2.0 reference armの`eta_E=1-0.85^(1/180)`、`rho_E=1-0.90^(1/180)`、session終了時に非選出生命を全回復しない挙動は変更しない。`formal_spec_adoption=false`である。

## Session targetからのeta導出

GUIとconditionの`f_selected`は、E=0から180 active signalsすべてでS=1かつG=1だったときのactive phase終了目標値である。1signal係数ではない。

```text
eta_selected = 1 - (1 - f_selected)^(1/180)

E_next = clip01(
  E
  + eta_selected * S * G * (1 - E)
  - rho_reference * (1 - S*G) * E
)

rho_reference = 1 - 0.90^(1/180)
```

`f_selected=0`で蓄積は0、`0.05`でE=0から180回後に0.05、`0.15`で参照etaと一致する。E>0では残り余地`1-E`への飽和型蓄積となる。baselineとclosingのS=0は参照rhoで回復する。したがって`E_after_active`とclosing第2周後の`E_before_session_end_policy`は別の値として記録する。

既存`calculate_e_next()`は参照ETA/RHOを使う後方互換APIとして保持する。係数を受け取る拡張seamだけをexperimental componentが使う。

## 非選出生命の全回復

正常sessionのactive phaseで`G=1`だったsignal数を生命ごとに数える。

```text
if selected_active_signal_count == 0:
    final_E = 0
else:
    final_E = E_after_closing_second_round
```

適用境界はBundle 2評価処理と3生命全てのclosing第2周が完了した後、final persistent stateの確定前である。Garden holderのreleaseと同じclosing barrier内に置き、現sessionのholder競争に遡及させない。次sessionのinitial stateから効果が現れる。

この判定はAdaptive Digital Lifeの状態系policyに注入する。multi-session runnerが取得済みfinal stateのEを後処理で書き換えない。convergence evaluatorも回復を実行しない。q、`k_anchor`、`trial_count`、`session_count`はresetしない。1signalでも選出された生命は全回復の対象外である。error/未完了sessionは回復後stateをcommitしない。

## 監査記録

生命ごとに`E_at_session_start`、`E_before_baseline`、`E_after_baseline`、`E_after_active`、`E_before_session_end_policy`、`E_after_session_end_policy`、`selected_active_signal_count`、`full_recovery_applied`、policy versionを保存する。選出生命の蓄積と非選出生命の全回復をGUI/CSVで別々に診断できる。
