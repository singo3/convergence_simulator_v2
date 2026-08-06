# Stage 8A.3.1 疲労回復方式 × 探索幅の2×2追加検証

## 位置づけ

Stage 8A.3.1は規範仕様v2.0のCoreを変更しないsimulation-onlyの追加検証層である。Stage 8A.3の固定仮想participant、`BundleOutcome`、`SessionOutcome`、ΔRMSSD、past-only lagged analysis、participant集計、inline SVG report、atomic checkpoint/resumeを再利用する。Digital Life Core、Runtime、Garden、Stage 8A.3のyoked armを作り直さない。

新規versionは次のとおり。

- validation model: `fatigue_recovery_sigma_factorial_validation_v0_1`
- factorial condition: `fatigue_recovery_sigma_factorial_condition_v1`
- fatigue factor: `fatigue_recovery_factor_v0_1`
- sigma factor: `exploration_width_factor_v0_1`
- shared random comparator: `shared_condition_independent_random_comparator_v0_1`
- analysis: `participant_paired_two_by_two_factorial_analysis_v0_1`
- recommendation: `human_mvp_condition_comparison_v0_1`
- report: `fatigue_recovery_sigma_factorial_report_v0_1`

`document_version=v2.0`、`profile_version=symbiotic_signal_loop_reference_v1_0`、`algorithm_version=adaptive_random_search_confirmed_v1`、`state_schema_version=relation_memory_state_v2`は維持する。

## 2要因と4条件

選出生命の疲労targetは4条件とも0.15で、

```text
eta_selected = 1 - (1 - 0.15)^(1/180)
             = 1 - 0.85^(1/180)
```

とv2.0参照etaに完全一致する。session中の回復は全条件で`rho_E = 1 - 0.90^(1/180)`である。差分は「非選出生命を正常session closingでE=0へ全回復するか」と「参照sigmaの倍率」だけである。

| ID | session-end recovery | sigma | 既存経路 |
|---|---|---:|---|
| A `v2_reference` | gradual reference only | 1.0 | Stage 8A.3 referenceとgolden一致 |
| B `v2_recovery_sigma050` | gradual reference only | 0.5 | 新条件 |
| C `full_recovery_sigma100` | unselected full recovery | 1.0 | 新条件 |
| D `provisional_f15_sigma050` | unselected full recovery | 0.5 | Stage 8A.3 provisionalとgolden一致 |

全回復policyは正常240秒sessionのclosing第2周でDigital Life componentが適用する。runnerのfinal-state後処理でEを書き換えない。error/未完了sessionは回復を含むstateをcommitしない。正常終了時もq、k、`trial_count`、`session_count`はresetしない。

## armとpaired保証

主要比較は`autonomous_closed_loop` 対 `pure_random_open_loop`である。Stage 8A.3の`response_decoupled_yoked_replay`はそのまま維持するが、この2×2では実行しない。

participant profile、response-strength、physiology seed、session indexは4条件とarmでpairedにする。condition ID、recovery、sigma、arm、結果をphysiology seedに入れない。random output seedにもcondition、recovery、sigmaを入れない。

pure randomはparticipantごと1回だけ物理simulationを実行し、checksummed resultを4条件のlogical comparisonへ参照させる。cache keyはparticipant ID、user type、physiology seed、maximum sessions、random-output version、code fingerprintだけである。

## 実行量

| preset | autonomous | shared random | logical comparison | actual simulation |
|---|---:|---:|---:|---:|
| smoke | 96 | 24 | 192 | 120 |
| standard | 8,640 | 2,160 | 17,280 | 10,800 |
| robust | 43,200 | 10,800 | 86,400 | 54,000 |

standardは9 user types×10 participants×24 sessions、robustは9×20×60である。plan-onlyは4種のcountを分けて表示し、simulation stateを作らない。

## 観測と成果物

跨sessionの主要生理尺度は`bundle RMSSD - baseline RMSSD`のΔRMSSDである。異なるbaselineで得たWを主尺度として直接比較しない。contemporaneous light−RMSSDと過去RMSSD→将来選択のlagged adaptationを分離し、historyにcurrentsessionとfuture sessionを入れない。hidden preference truthをobserved coupling、history model、selectionに入れない。

run directoryにcondition、participant、shared-random physical rows、autonomous rows、logical comparison、participant差、factorial effect、recommendation、invalid data、digest、checkpoint、logを保存する。`report/report.html`、participant別HTML、user-type別HTMLは外部CSS/JavaScript/networkを必要としない。

## 対象外

moving preference、個人ごとのpreference center変更、yoked再設計、`p_explore`、`epsilon_accept`、q、P/V/tau、RMSSD→N、session/Bundle時間、Web、DB、network、LLM、formal adoptionは対象外である。本結果は仮想participantのsimulationであり、実人間への有効性を主張しない。
