# Stage 8A.1 疲労・探索幅・収束条件ラボ

Stage 8A.1は、固定好みユーザーに対する疲労と探索幅の条件比較、および観測された収束構造の診断を行うGUI非依存の実験層である。`fatigue_exploration_convergence_lab_v0_1`は規範仕様v2.0の正式Profileを更新しない。すべてのexperiment manifestは`formal_spec_adoption=false`を保持する。

## Reference armとexperimental arm

`v2.0 reference arm`は、Stage 8Aの疲労蓄積・回復式、生命固有の`sigma_min/max`、探索幅倍率1.0、非選出生命をsession終了時に全回復しないpolicyを維持する。Stage 8Aのpublic factory、CLI、JSON、digest、CSV、GUI contract、3-of-4 evaluator、user type v1も変更しない。v2 user typeを使う比較は「同じ固定好みに対するv2.0係数参照arm」であり、Stage 8A user type v1の実行結果そのものとは呼ばない。

`stage_08a1_fatigue_sigma_experiment_v0_1`は次の3項目だけをsimulation assumptionとして変更する。

- 選出生命の1session疲労target
- 非選出生命の正常session終了時の全回復
- 参照sigmaに対する共通倍率

`p_explore_min`、`epsilon_accept`、q係数、P/V/tau mapping、RMSSD→N、`delta_N`、3Bundle構造、candidate確認規則は変更しない。F/Tだけを`reflect01`で探索し、A/Dを固定する。

## 条件と実行単位

immutableな`FatigueSigmaCondition`は固定user type v2、選出時fatigue target、非選出回復率1.0、sigma multiplier、4〜100session、master seed、policy/schema versionをstrictに保持する。既定値は`green_hue_dominant_broad_bpm`、target 0.05、multiplier 1.0、24session、seed 20260802である。unknown/missing/duplicate field、boolの数値化、非有限値、version不一致は拒否する。

single-condition runnerはStage 5C single-session factoryを1sessionずつ実行し、正常終了したfinal stateだけを次sessionへcommitする。baseline、N/Nd/W、`W_anchor_session`、trial、holder、light/response stateは毎session resetする。errorまたは未完了sessionでは、全回復を含むfinal stateをcommitしない。state JSONは条件、完了履歴、persistent state、versionをstrictに保存する。

grid runnerは条件ごと、replicateごとにrunner、component、persistent state、収束履歴を分離する。総実行予定数は`conditions × replicates × maximum_sessions`で、30000を超える設定はclipせず拒否する。cancelはsessionまたはcondition境界でのみ確定し、途中conditionを完了扱いしない。収束後もmaximum sessionsまで探索を続ける。

## 収束診断

`structured_convergence_diagnostics_v0_1`は正常なsession outcomeを1票とし、次の独立診断を保持する。

- life dominance: 直近8有効sessionで6回以上の同一生命、最大1連続outlierまで許容
- common BPM: 生命IDとHueを無視し、直近8sessionのうち6件以上が20 BPM帯に入るsubset
- life-specific multi-attractor: 直近18session内で生命別に再現する20 BPM帯、帯間隔20 BPM以上
- one-gap continuity、temporary outlier/return、mechanical rotation
- Stage 8A 3-of-4の`early_single_life_pattern_signal`

life dominanceは生命IDを第一条件とし、Hue完全一致を要求しない。common BPMは異なる生命を横断できる。multi-attractorは生命別の複数帯を1clusterへ圧縮しない。summary classificationは各flagから導く説明用分類であり、単一の「最良スコア」は作らない。

mechanical rotationはholder switch、3生命異なる3-session window、A→B→A、A→B→C→A、dominant-life return、同一生命間隔、session開始Eとswitchの関係を監査する。flat controlで強い構造が出た場合は`spurious_structure_in_flat_control`として分離する。

## Hidden truthとW天井

observed evaluatorが読むのはholder ID、final committed BPM、表示用Hue、validity、session orderだけである。hidden peak、preference match、expected structure、response gapはsimulation-only truth evaluatorが観測診断の後にだけ読む。truth結果はDigital Life、Runtime、Garden、fatigue/sigma policyへ返さない。

W天井診断は`W_anchor_session >= 1-epsilon_accept`、数学的にBundle 1仮採用が不可能な件数、trial W天井、candidate/provisional/confirmation/accept件数を記録する。結果は`exploration_identifiable`、`exploration_partly_saturated`、`exploration_blocked_by_W_ceiling`のいずれかである。この診断を理由に`epsilon_accept`、`delta_N`、その他の係数を書き換えない。

## 出力と決定性

single runとgridは条件、trajectory、structured convergence、truth、mechanical rotation、W天井、persistent stateをJSONとCSVで保存する。CSVは`stage_08a1_conditions.csv`、`stage_08a1_fatigue_trajectory.csv`、`stage_08a1_sigma_trajectory.csv`、`stage_08a1_session_pattern_trajectory.csv`、`stage_08a1_structured_convergence_history.csv`、`stage_08a1_replicate_results.csv`、`stage_08a1_condition_summaries.csv`、`stage_08a1_grid_heatmap.csv`である。manifestは`stage_08a1_experiment_manifest.json`である。

digestはUTF-8、`sort_keys=true`、`allow_nan=false`、compact separatorsのcanonical JSONから作る。session-by-session/batch、reset、GUI/headless、CSV有無、state JSON round-trip、paired replicate再実行、grid iteration order変更で一致する。

## 実装しないもの

moving/time/context-dependent preference、疲労による好み中心移動、`p_explore`倍率、`epsilon_accept`変更、q更新率変更、convergenceによるCore制御、係数のformal adoption、大規模Monte Carlo、Web/DB/network/MLはStage 8A.1の範囲外である。

詳細policyは[疲労policy](experimental-fatigue-policy_v0.1.md)、[sigma policy](scaled-reference-sigma-policy_v0.1.md)、[構造収束診断](structured-convergence-diagnostics_v0.1.md)、[固定user type v2](stationary-user-type-profiles_v2.md)、[paired seed](paired-replicate-seed-policy_v0.1.md)、[出力schema](stage-08a1-experiment-output-schemas.md)を参照する。
