# Stage 5C: 3Bundle関係記憶探索・確認型候補採否

## 目的

Stage 5Cは、各Digital Life内部の関係記憶 `C_i` を既存の3Bundle閉ループの第2周へ接続する。1回の240秒sessionで現在の `k_anchor` を評価し、生命自身がholdまたは最大1つのtrialを選び、同じtrialの2回の有効評価で改善を確認した場合だけ正式採用する。

```text
Bundle 0: k_anchorのセッション内評価 -> hold / explore
Bundle 1: k_trialの第1評価          -> confirmation / return
Bundle 2: 同じk_trialの確認        -> accept / rollback
          またはk_anchorの復帰評価
```

baseline終了時の `W=0.5` はanchor評価ではない。`W_anchor_session` は資格生命がBundle 0の新しい有効評価を処理したときに初めて設定する。

## 規範仕様とversion

唯一の規範仕様は `symbiotic-digital-life-signal-loop-concept_v2.0.md` であり、本Stageでは第25章「関係記憶の生得写像C_i」、第26章「3bundleの完全な状態遷移」、第27章「更新・維持・引継ぎ一覧」を直接実装根拠とする。

| 項目 | version |
| --- | --- |
| document | `v2.0` |
| profile | `symbiotic_signal_loop_reference_v1_0` |
| algorithm | `adaptive_random_search_confirmed_v1` |
| persistent state schema | `relation_memory_state_v2` |
| adaptive component model | `adaptive_relation_memory_connected_life_v0_1` |
| relation update timing policy | `relation_update_effective_next_signal_v0_1` |

Stage 5Cのimmutable診断recordは次のversionに固定する。

| record | schema version |
| --- | --- |
| intrinsic profile | `relation_memory_intrinsic_profile_v1` |
| persistent state | `relation_memory_persistent_state_record_v1` |
| session state | `relation_memory_session_state_record_v1` |
| relation transition | `relation_memory_transition_record_v1` |
| adaptive second round | `adaptive_digital_life_second_round_record_v1` |
| adaptive signal | `adaptive_digital_life_signal_record_v1` |

v2.0が規定するCore式・閾値・状態遷移と、本simulatorが具体化するpolicyは混同しない。特に、極小normの正F軸fallback、Bundle 1 evaluation reject後の同一trial維持、更新済みkの次signal適用はversion管理された **simulation implementation assumption** である。詳細は [algorithm実装](adaptive-random-search-confirmed-v1-implementation.md) と [next-signal policy](relation-update-next-signal-policy_v0.1.md) を参照する。

## Core責務と境界

`AdaptiveConnectedDigitalLifeComponent` はStage 5Bの第1周、touch、feedback、G、E/q更新を再利用し、関係記憶遷移をfeedback第2周で並列的に確定する。各生命は他生命のk、W、candidate、好みを参照しない。

- candidate生成・採否・rollbackは各Digital Life Coreの責務である。
- Runtimeは各tauをtouch時刻へ写像し、feedbackをrouteするが、candidateを生成・選択しない。
- Gardenはactual arrivalでholderを管理するが、関係記憶stateを知らず、candidateを生成・選択しない。
- formal touch payloadとqualified B境界はStage 5B.1のままである。関係記憶の診断値をGardenへ流さない。
- VirtualUser、H10、Garden入力component、Light response config、仮想ユーザーのpreferred Hue/BPMを関係記憶Coreから参照しない。
- off-center presetの診断上の最適点はGUI表示だけに限定し、探索計算へ渡さない。

## persistent stateとsession-local state

長期保持値はimmutableな `RelationMemoryPersistentState` として入出力する。

| field | 初期値 | 概念scope | closing後 |
| --- | --- | --- | --- |
| `k_anchor` | `[0.5, 0.5, 0.5, 0.5]` | Digital Life Core | 正式採用時だけ更新 |
| `q` | `0.5` | Digital Life Core | 既存規則で引き継ぐ |
| `e` | `0.0` | user_garden | 既存規則で引き継ぐ |
| `trial_count` | `0` | Digital Life Core | candidate生成時だけ増加 |
| `session_count` | `0` | Digital Life Core | 正常closing完了時に全生命で1増加 |

Eを1つのpersistent recordへ格納しても、Eの `user_garden` scopeとk/q/counterのDigital Life Core scopeは概念上区別する。厳密なvalidationとstate I/Oは [relation-memory-state-v2 contract](relation-memory-state-v2-simulation-contract.md) に定める。

`W_anchor_session`、`k_trial`、`W_trial_1`、`W_trial_2`、探索判定、方向、phase、adoption/rollback結果はsession-local stateである。session開始時にresetし、値を次sessionの候補比較に持ち越さない。監査recordとしてexportすることと、比較stateとして引き継ぐことは別である。

counterの意味も分離する。`trial_count` はpersistentでcandidate生成時だけ1増加し、`session_count` はpersistentで正常closing完了時に全生命が1増加する。`k_current_transition_count` はanchor→trialまたはtrial→anchorなど一時的な提示位置変更の診断countである。`k_anchor_update_count` はBundle 2の正式採用時だけ1増加し、temporary trial、rejection、rollbackを数えない。Stage 5Cの `k_update_count` はこの正式anchor更新回数を意味し、Stage 5Bの既存recordの意味は変更しない。

## 生得profileとcandidate

既存の決定論的 `Hash01` を使い、root seed、Python `hash`、`random`、NumPy RNGを使わない。

```text
c_i                 = Hash01(ID_i, "curiosity")
sigma_min,i         = 0.02 + 0.04*c_i
sigma_max,i         = 0.25 + 0.30*c_i
epsilon_accept,i    = 0.07 - 0.04*c_i
p_explore_min,i     = 0.10 + 0.20*c_i
r(W)                = clip01(2*W - 1)
sigma_i             = sigma_min,i + (sigma_max,i-sigma_min,i)*(1-r(W_anchor_session))
p_explore,i         = p_explore_min,i + (1-p_explore_min,i)*(1-r(W_anchor_session))
u_explore            = Hash01(ID_i, "C", "explore", session_count_used)
explore              = u_explore < p_explore
```

`<`はstrictであり、等値はholdとする。探索時はincrement前の `trial_count` でF/T方向を生成し、正規化した `xi=[xi_F,0,xi_T,0]` とsigmaからcandidateを一度だけ作る。

```text
k_trial,F = reflect01(k_anchor,F + sigma*xi_F)
k_trial,A = k_anchor,A
k_trial,T = reflect01(k_anchor,T + sigma*xi_T)
k_trial,D = k_anchor,D
```

`reflect01(x)=1-abs(1-mod_positive(x,2))` を使い、clipへの置換や25セルへの丸めを行わない。F/Tだけを探索し、A/Dはbit-for-bitで維持する。candidate生成で `trial_count` を1増加するが、`k_anchor` はまだ更新しない。

## 3Bundle state machine

phase語彙は `anchor_evaluation`、`hold`、`trial`、`confirmation`、`return_anchor`、`trial_unconfirmed`、`accepted`、`rejected`、`completed_non_holder`、`completed_bundle0_rejected` に固定する。adoption resultは `pending`、`hold`、`accepted`、`rejected_bundle1_threshold`、`rejected_after_confirmation`、`unconfirmed_evaluation_reject`、`bundle0_evaluation_rejected`、`non_holder_no_adaptation`、`no_candidate`、`rolled_back_at_session_end` だけを使う。似た語彙をGUIまたはCSVだけで追加しない。

### baseline

baseline revisionは `Nd=W=0.5`、`k_current=k_anchor`で開始する。`W_anchor_session=null`、`anchor_evaluated=false`を維持し、hold/explore判定、candidate生成、counter更新を行わない。

### Bundle 0: anchor evaluation

G=1生命の新しい有効評価で、現在Wを `W_anchor_session` へ保存する。sigma、`p_explore`、`u_explore` を1回確定し、strict `<` でhold/exploreを決める。holdではBundle 1/2もanchorを提示し、exploreでは1つのcandidateを生成する。

Bundle 0がrejectedなら `W_anchor_session` を設定せず、candidateを生成せず `hold` でanchorを維持する。adoption resultは `bundle0_evaluation_rejected`、closing後のfinal phaseは `completed_bundle0_rejected` とする。G=0生命も成果比較を始めない。

### Bundle 1: trial evaluation

trialの新しい有効評価で次のstrict条件を判定する。

```text
W_trial_1 > W_anchor_session + epsilon_accept
```

成立すればBundle 2も同じtrialを提示する `confirmation` へ進む。非成立なら `return_anchor` へ進み、Bundle 2はold anchorを再提示する。閾値と完全一致、微小改善、同値、低下はすべて基準未達である。Bundle 1の1評価だけで正式採用しない。

### Bundle 2: confirmation or return

confirmation中は同じ `k_trial` を再評価し、次の2条件がともにstrictに成立する場合だけ正式採用する。

```text
W_trial_2 > W_anchor_session
mean(W_trial_1, W_trial_2) > W_anchor_session + epsilon_accept
```

成功時は `k_anchor=k_trial`、失敗時はold anchorへrollbackする。候補のWがbaseline 0.5以上であることは追加条件ではない。現在anchorに対する再現可能な段階的改善は、両方のWが0.5未満でも採用可能である。

`return_anchor` で有効なBundle 2評価を得たときは `anchor_return_W` として監査し、session内の `W_anchor_session` を更新してよいが、次sessionへは持ち越さない。

## evaluation reject、G=0、closing

- rejected evaluationではN/Wを新規評価とみなさず、q/k_anchorを更新しない。既存candidateのrejectで `trial_count` を追加増加せず、新candidateも生成しない。
- Bundle 1 rejectでは同じtrialをBundle 2へ維持するが、有効trial評価が1回だけなので正式採用せずrollbackする。これは `keep_same_trial_for_bundle2_but_require_two_valid_trial_evaluations_v0_1` という参照実装policyである。
- Bundle 2 rejectは確認不成立としてold anchorへrollbackする。
- G=0生命は第1周、touch、E更新を従来どおり行うが、candidate生成、trial_count増加、k_current/k_anchor更新、採否、q更新を行わない。
- 240秒closingはBundle 2評価をrelease前holderの第2周へ適用し、採否・復帰を確定した後にholderを解放する。未確認candidateはrollbackし、active `k_trial` を破棄する。
- 正常closing完了時だけ全生命の `session_count` を1増加し、final immutable persistent stateをcommit済みとして公開する。runtime errorや異常終了では正式final stateを出力しない。

## q、E、kの並列更新と時間因果

同じfeedback第2周で、E、q、relation memory遷移を同じbefore stateから独立計算し、原子的に反映する。`C_i` はq_after/E_afterを使わず、q/E更新もk_afterを使わない。同じsignal内の第1周Bとreturned Bは維持し、関係記憶更新後の `k_current` は次signalの `Phi_B(k)` から使う。

| boundary | 第1周が提示するk | 第2周の関係記憶処理 | 変更のkが最初に有効なsignal |
| --- | --- | --- | --- |
| 120秒 | old anchor | Bundle 0でhold/explore確定 | 121秒 |
| 180秒 | Bundle 1用anchor/trial | provisional/return確定 | 181秒 |
| 240秒 | Bundle 2用anchor/trial | accept/rollbackとfinalize | 次sessionの最初signal |

詳細は [relation_update_effective_next_signal_v0_1](relation-update-next-signal-policy_v0.1.md) を参照する。

## 診断・GUI・headless・CSV

通常GUIは「関係記憶探索」を第1tabに追加し、既存8tabを維持する。GUIはimmutable state/recordだけを描画し、候補生成または採否を再計算しない。F/T空間、Wとstrict threshold、3Bundle timeline、transition、persistent before/afterを分離表示する。

GUIは次の境界説明を明示する。

> Bundle 0で現在のanchorを評価し、holdまたはtrialを決めます。trialはBundle 1で仮評価し、Bundle 2で同じcandidateを確認した場合だけ正式採用します。

> baseline終了時のW=0.5はanchor評価ではありません。

> 候補生成と採否は資格生命自身の関係記憶C_iが行います。RuntimeやGardenは候補を選びません。

`off_center_green` で仮想ユーザーの診断上の最適点を表示する場合は、「最適点はシミュレーター診断専用で、Digital Lifeの探索計算には渡されません。」を併記する。

```bash
python -m symbiotic_sim_v2 \
  --headless-relation-memory-demo \
  --light-response-preset off_center_green
```

`--initial-relation-state-json PATH` でstrictな3生命persistent stateを注入し、`--export-final-relation-state-json PATH` で正常closing後のstateを保存できる。このI/Oは次工程の手動引継ぎseamであり、複数sessionを自動実行するrunnerではない。headless JSONは `single_session_only=true`、`multi_session_not_implemented=true`、`convergence_evaluated=false` を明示する。

Stage 5Cの追加CSVは次の5ファイルである。

- `stage_05c_relation_memory_intrinsic_profiles.csv`
- `stage_05c_relation_memory_transitions.csv`
- `stage_05c_adaptive_digital_life_signals.csv`
- `stage_05c_relation_memory_persistent_states.csv`
- `stage_05c_relation_memory_session_summary.csv`

intrinsic profile、adaptive signal、relation transition、final persistent state、session summaryは個別にcanonical digest化する。CSV export、GUI描画、step/velocity mode、reset、state JSON round-tripはsimulation結果を変えない。

## 検証とStage 8 interface

unit testはpersistent validation、生得写像、`r(W)`、sigma/probability境界、strict比較、`reflect01`、Hash方向、F/T candidate、counterを検証する。pure state-machine fixtureはhold、accepted、Bundle 1 threshold fail、confirmation fail、mean fail、Bundle 0/1/2 reject、G=0、incremental improvementを独立に覆う。integration testは240秒閉ループ、next-signal因果、state I/O、digest、CSV、Stage 1〜7.1回帰を確認する。

Stage 8向けに提供するは、strictにvalidatedされたinitial/final `RelationMemoryPersistentState` のimmutable入出力interfaceだけである。Stage 5Cは常に **single-session only** で、複数sessionの自動連結、session間baseline/W比較、長期収束・sustained convergence判定、Monte Carlo、係数tuningを実装または評価しない。
