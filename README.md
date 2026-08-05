# 環境共生型デジタル生命シミュレーター v2

環境共生型デジタル生命システムの各componentを、同じ決定論的な仮想時間上で段階的に検証するPythonプロジェクトです。

- Stage 1「時間・イベント配送基盤」: 完成
- Stage 2「外部刺激を受けない仮想ユーザー」: 完成
- Stage 3「仮想Polar H10」: 完成
- Stage 4「Garden入力層とセッションシグナル」: 完成
- Stage 5A「1体のデジタル生命・第1周」: 完成
- Stage 5B「3生命・資格競争・第2周」: 完成
- Stage 5B.1「Garden出力境界・qualified B実効時刻補正」: 完成
- Stage 6「Garden Light Mapper・仮想光点滅device」: 完成
- Stage 7「固定反応特性を持つ光応答仮想ユーザー」: 完成
- Stage 7.1「物理光刺激の監査segmentとresponse dynamics epochの分離」: 完成
- Stage 5C「3Bundle関係記憶探索・確認型候補採否」: 完成
- Stage 8A「固定好みユーザー・複数セッション収束ラボ」: 完成
- Stage 8A.1「固定好み・疲労／探索幅・収束条件ラボ」: 完成
- Stage 8A.2「自動条件探索・堅牢候補抽出」: 完成
- Stage 8A.3「自律・反応切離しプラセボ・ランダムRMSSD個人内適応検証」: 完成
- 現在のGUI主対象: Stage 8A.1、現在のheadless検証主対象: Stage 8A.3

正式な信号経路は次のとおりです。

```text
仮想ユーザー
  → HeartbeatEvent
  → 仮想Polar H10
  → RriMeasurementEvent
  → Garden入力層
  → GardenInputSignalEvent (N, S)
  → red / green / blueの独立した第1周: Nd, W, P, V, B, tau
  → 各tauを個別touch時刻へ写像
  → DigitalLifeTouchEvent (ID, B)
  → Garden出力資格層（actual arrivalでholder決定・保持）
  → GardenQualifiedBEvent v2（holder touchと同じeffective time）
  → Garden Light Mapper（Hue=360F, BPM=10+155T）
  → LightCommandEvent = I
  → Virtual PC Light Device（continuous sine phase）
  → LightStimulusStateEvent（Stage 7の正式光入力）
  → 固定Hue/BPM preference・一次遅れresponse
  → 平均RRI・呼吸性RRI変動幅
  → 将来のHeartbeatEvent
  → H10 / Gardenへ閉ループ
  → round finalize（全touch確認・feedback同期）
  → holder ID + 各生命自身のB
  → 各生命の第2周: G, E, q, 関係記憶C_i
  → Bundle 0 anchor評価 / holdまたは最大1つのtrial
  → Bundle 1仮評価 / Bundle 2同一candidate確認またはanchor復帰
  → acceptまたはrollback（更新kは次signalから有効）
```

仮想ユーザーの正式出力は `HeartbeatEvent` だけです。仮想Polar H10は隣接するheartbeatの正式時刻差をraw RRIとして測定し、RRIを含む `RriMeasurementEvent` だけを正式出力します。H10はartifact判定、RMSSD、N、Nd、Wを扱いません。

Garden入力層は `RriMeasurementEvent` だけをraw inputとし、artifactを除いた評価windowのRRIから実RMSSDとNを求めます。正式な1秒シグナル `GardenInputSignalEvent` はNとSを出力します。Stage 5Aのデジタル生命はこのformal signalと評価metadata eventだけを受け、Nd、W、P、V、B、tauを計算します。

Stage 5BではG、E/q第2周、touch配送、3生命の資格競争を接続しました。Stage 5B.1では生命由来touchをID/Bだけのv2境界へ絞り、active qualified Bをholder touchの実到着時刻に出力します。Stage 6はこのformal eventだけを入力に、FをHue、Tをblink BPMへ写像し、仮想時計から連続sine位相を解析的に再構成します。Stage 7は `LightStimulusStateEvent` だけを光入力として固定Hue/BPM嗜好と一次遅れresponseを評価し、将来の心拍間隔生成へ接続します。Stage 7.1は物理parameterが変わる監査segmentとtargetが変わるresponse dynamics epochを分離し、同targetの光変更でresponseをresetしません。光からRMSSD、N、Nd、Wを直接更新しません。

Stage 5Cは、各生命内部の `adaptive_random_search_confirmed_v1` をこの閉ループの第2周へ接続します。Bundle 0で `W_anchor_session` を初めて設定し、生得探究心cと `sigma_min/max`、`epsilon_accept`、`p_explore_min`、決定論的Hash方向でhold/exploreします。trialは `reflect01` でF/Tだけを連続探索し、A/Dを固定します。Bundle 1は仮評価に過ぎず、Bundle 2で同じcandidateをstrictに確認した場合だけ正式採用します。G=0生命はcandidate採否やk_anchor更新を行いません。persistent stateとsession-local stateを分離し、更新kは次signalからBへ反映します。

Stage 8AはStage 5C public factoryを1session単位で再利用し、正常終了後の`k_anchor/q/E/trial_count/session_count`を次sessionへ引き継ぎます。baselineと`W_anchor_session`は毎session取り直します。仮想ユーザーのsingle/multi-peak好みはrun中に固定し、生理noiseだけを決定論的なsession seedで変化させます。一次収束は1sessionを独立票とする「同じDigital Life + 近いHue/BPM」の直近4有効session中3sessionです。1sessionの3Bundleを独立票にしません。latest outlierを許容し、収束後もStage 5Cの探索を停止しません。各Bundleの実提示k/B/Hue/BPMはsegment監査として残しますが票にはしません。observed convergenceとhidden landscape truth alignmentは分離され、どちらもDigital Life、Runtime、Gardenへ入力されません。truth分類は`response_gap=max(0, global maximum match - medoid match)`を使い、threshold以下を`correct_convergence`、超過を`stable_suboptimal`、未収束を`not_converged`、flat型を`no_preference_control`とします。nearest peakのsigma正規化距離もsimulation-only診断です。

Stage 8A.1はStage 8Aとv2.0 reference armを変更せず、experimental armだけに「180 active signals後の選出生命疲労target」、正常session終了時の非選出生命E=0全回復、参照sigmaへの共通倍率を注入します。固定user type v2に対し、生命優勢、cross-life BPM共通帯、生命別multi-attractor、temporary outlier/return、機械的rotation、W天井を独立診断します。収束後も探索を続け、診断結果をCoreへ返しません。paired replicateはcondition ID、fatigue、sigmaをseedに含めず、単一の「最良条件スコア」を作りません。experimental manifestは`formal_spec_adoption=false`を明記します。

Stage 8A.2はStage 8A.1 runnerをコピーせず再利用する、完全ローカルCPUのheadless実験オーケストレーションです。coarse→refine→confirmで条件を段階的に絞り、paired seed、condition横断reference cache、atomic checkpoint/resume、95% Wilson区間、Pareto frontier、robust/specialist候補、自己完結型`report.html`を生成します。OpenAI、Codex、ChatGPT、外部LLM、外部API、networkを呼びません。候補をDigital Life、Runtime、Gardenへ返さず、`formal_spec_adoption=false`のままtrade-offを保存します。robust gateを通る候補がない場合は無理に一位を作らず`no_robust_candidate`とblockerを出します。

Stage 8A.3は固定反応地形を持つ複数仮想参加者について、本人のRMSSDが将来選択へ入る`autonomous_closed_loop`、別participantのautonomous formal光系列を再生する`response_decoupled_yoked_replay`、RMSSD非依存の`pure_random_open_loop`をpaired比較します。同時点の光−RMSSD反応と、過去ΔRMSSD→将来life/Hue/BPM選択のlagged couplingを分離し、past-sessions-only model、165点counterfactual、selection enrichment、one-step prediction、participant-level paired effectを出力します。Wはsession-local監査値に限定し、セッション間はΔRMSSDで比較します。participant別、user type平均、全体平均、相関図をinline SVGの自己完結HTMLに保存し、`no_clear_effect`を正当な結果とします。

現在の `ideal_polar_h10_rri_device_v0_1` は、誤差・欠損・遅延なしの理想的な入力デバイスを表すsimulation assumptionです。実機Polar H10のBLE GATT packet、firmware、電波、pairing、Polar SDKを再現するpacket-level emulatorではありません。

## 実装済み

### Stage 1

- integer microsecondsの `SimulationClock`
- deterministic `EventScheduler` と `SimulationEngine`
- `(scheduled_time_us, priority, sequence)` のevent ordering
- pause/resume/reset、1秒step、1-event step、bounded max batch
- QTimerと正式な仮想時計の分離
- 後方互換の20秒time demoとdigest

### Stage 2

- immutable `VirtualUserConfig`
- `baseline_virtual_user_physiology_v0_1`
- SHA-256/Box-Mullerによるstateless named random source
- payloadを `user_id` / `beat_index` だけに限定したheartbeat event
- reset・速度・描画回数に依存しないheartbeat列
- 真のRRI、瞬時HR、rolling RMSSD 30秒、full-run RMSSDの開発用診断
- 仮想ユーザーchart/table、headless JSON、内部真値診断CSV

Stage 2のRRI、RMSSD、内部変動成分は仮想ユーザー内部の開発用診断です。H10測定値またはGarden入力信号として使用しません。

### Stage 3

- immutable `PolarH10Config` と `RriMeasurementRecord`
- GUI非依存の `PolarH10Component`
- `HeartbeatEvent.scheduled_time_us` だけを測定する理想RRI device
- 最初のheartbeatは非出力、2拍目以降は隣接時刻差をraw RRIとして出力
- `heartbeat(40) → rri_measurement(50) → simulation_complete(100)` の同時刻順序
- VirtualUserとH10を接続する共通factoryと決定論的reset
- true RRIとの一致比較、RRI/error chart、最近の測定table
- Stage 3 headless JSONとH10開発診断CSV
- Stage 1・Stage 2のCLI、schema、digestを維持する回帰テスト

### Stage 4

- immutable `GardenInputConfig` と `relax_with_light_garden_input_v0_1`
- GUI非依存の `GardenInputComponent`
- 正式な `RriMeasurementEvent` だけを受けるstrict input boundary
- 300〜2000 msと直近最大15件の有効RRI中央値によるartifact分類
- 30秒evaluation windowごとの実RMSSD、固定式のN、quality判定
- baseline 60秒 + 3 bundle・計180秒の240秒session
- 1秒周期の `GardenInputSignalEvent`（N、S）と評価確定event
- baseline固定、rejected評価のN非更新、baseline無効時の明示policy
- Garden入力GUI、240秒headless JSON、3種類の診断CSV、決定論的digest
- Stage 1〜3のCLI、schema、digestを維持する回帰テスト

### Stage 5A

- immutable `DigitalLifeConfig` とred/green/blueの3つのsimulation fixture
- GUI非依存の `SingleDigitalLifeComponent`
- `GardenInputSignalEvent` と `GardenEvaluationFinalizedEvent` だけを受けるformal boundary
- baseline相対Nd、独立した情動評価W、`Phi_P` によるP
- Stage 5A中は保持するE=0/q=0.5、N/q/EからのV
- 固定kと生命固有 `Phi_B`、論理到達値tau
- baseline/revision/rejected評価の一回限りの適用と240秒closing処理
- 1体のデジタル生命GUI、240秒headless JSON、2種類の開発診断CSV
- Stage 4のevent stream/digestとStage 1〜4のCLI/schema/CSVを維持する回帰テスト

### Stage 5B

- red / green / blueの独立stateと同じGarden N/Sの個別演算
- `three_digital_life_runtime_v0_2` とtauのinteger-microseconds個別配送
- role/P/V/tauを含めずID/Bだけを運ぶ `digital_life_touch_event_v2`
- actual arrivalだけによるholder assignment、S=1中の保持、closing第2周後の解放
- recipient自身のBだけを返す `garden_interoceptive_feedback_event_v1`
- 各生命内のID照合によるG、毎signalのE更新、新規有効BundleかつG=1だけのq更新
- 全生命で固定kと `deferred_to_stage_5c`
- 次Stage境界の `garden_qualified_b_event_v2`（Hue/BPM/Iは未実装）
- 6 tab GUI、240秒headless JSON、4種類のCSV、5種類のStage 5B digest
- Stage 1〜5A CLI/schema/digest/CSVを維持する回帰テスト

### Stage 5B.1

- Runtime/session rosterからGardenへ参加IDを注入し、Garden coreの固定ID→role表を除去
- `qualified_b_on_holder_touch_v0_1` によりactive Bをholder touchと同じmicrosecond・priority 65で出力
- `effective_time_us` をqualified B v2のformal payloadと診断recordへ明示
- inactive commandはsignal time、active commandはcurrent signalのholder touch Bを使用
- round finalizeはqualified Bを再出力せず、全touch確認・feedback・第2周同期だけを担当
- touch order、holder、G、E、q、k、feedback時刻、closing releaseをStage 5Bから維持

### Stage 6

- `relax_with_light_b_to_i_mapper_v0_1`、`relax_with_light_pc_hsv_sine_mapping_v0_1`、`light_command_event_v1`
- `Hue=360F`、`blink_BPM=10+155T`、Saturation 100%、Value 35〜50%のsine波
- A/Dはsource Bとして保存するが光parameterへ不使用
- `virtual_pc_light_device_v0_1` とabsolute virtual-timeのcontinuous phase
- same command/Hue/BPM変更時のphase継続、inactive後のactiveだけreset
- `continuous_phase_integrator_v0_1`、`hold_until_next_command_v0_1`、`light_off_black_v0_1`
- 半開区間 `light_stimulus_segment_v1` と `fixed_virtual_grid_20ms_v0_1` 診断
- Stage 7正式境界 `light_stimulus_state_event_v1`
- 20ms固定virtual grid診断、headless JSON、4種類CSV、7タブGUI
- GUI previewは校正済み物理光ではなく、Stage 6単体ではHeartbeat/RRIを変えない

### Stage 7

- `stationary_light_responsive_virtual_user_v0_2` とimmutableな `LightResponseConfig`
- formal inputは `LightStimulusStateEvent`、formal outputは既存 `HeartbeatEvent` だけ
- holder/source B/signal IDを除いた `physical_light_stimulus_projection_v0_1`
- 円環Hue距離とHue/BPM Gaussian積によるrun中固定のpreference
- onset 8秒・recovery 12秒の解析的な `first_order_light_response_v0_1`
- responseから呼吸性RRI変動幅と平均RRIだけを変更する生理連成
- Stage 2と同じroot seed、named random stream、beat-index key、clamp、丸め
- heartbeat開始時sampleと、予約済みheartbeatをrescheduleしない因果policy
- gain 0でStage 6 formal streamを再現する `light_insensitive_control`
- `physical_light_parameter_signature_v0_1` による物理監査segment v2と、target変更だけで分割するresponse dynamics epoch v1
- 241 light receipts、physical audit segment、response dynamics epoch、2401件100ms sample、responsive heartbeat診断
- 8-tab GUI、headless JSON、5種類のStage 7 CSV、独立reference vectors
- 実データ未校正のsimulation assumption。moving preferenceは未実装

### Stage 5C

- `adaptive_relation_memory_connected_life_v0_1` による各生命独立の関係記憶C_i
- `c_i=Hash01(ID_i,"curiosity")` から導く `sigma_min/max`、`epsilon_accept`、`p_explore_min`
- `r(W_anchor_session)` による探索幅sigmaと探索確率、`session_count` による決定論的hold/explore
- increment前 `trial_count` とexact Hash keyで生成するF/T方向
- `reflect01`を使う連続F/T candidate、A/D完全固定、25セル丸めなし
- baseline W=0.5をanchorにせず、Bundle 0でanchor評価、Bundle 1でtrial仮評価、Bundle 2で同一trial確認またはanchor復帰
- strict thresholdと有効trial評価2回を要求する正式採用、未確認・reject・confirmation失敗時のrollback
- 1session最大1candidate、G=0のcandidate/k更新禁止、candidate生成時だけの `trial_count` 増加
- q/E/kを同じbefore stateから第2周で並列的に確定し、更新kを次signalから使う `relation_update_effective_next_signal_v0_1`
- immutable persistent stateとsession-local stateの分離、strict JSON import/export、Stage 8向けstate seam
- 9-tab GUI、single-session headless JSON、5種類CSV、独立reference vectors、pure state-machine全分岐fixture
- Stage 5C public factory自体はsingle-session contractを維持

### Stage 8A

- `multi_session_relation_memory_runner_v0_1`による独立240秒engineの連結
- 正常sessionだけのstrict persistent-state commitと、error時のnon-commit停止
- 毎sessionのbaseline、`W_anchor_session`、trial/holder/light/response local state reset
- `stationary_preference_landscape_v0_1`と固定6 user type（単峰、広/狭、弱反応、二峰、flat control）
- SHA-256先頭unsigned 32-bitによる`deterministic_per_session_physiology_seed_v0_1`
- final committed holder anchorをsession代表値にする`multi_session_outcome_v1`
- same-life限定の円環Hue/BPM距離、全pairwise subset、3-of-4 rolling majority
- latest outlier、loss/reconvergence、cluster switch、post-convergence探索の監視
- observed convergenceと`stationary_landscape_truth_alignment_v0_1`の完全分離
- strict multi-session state JSON resume、6 CSV、canonical digest、全タイプ比較
- moving preference、係数tuning、Monte Carloは未実装

### Stage 8A.1

- `fatigue_exploration_convergence_lab_v0_1`と`stage_08a1_fatigue_sigma_experiment_v0_1`
- v2.0係数reference armとexperimental full-recovery armの分離
- session fatigue targetからの飽和型`eta_selected`導出、参照rhoの維持
- 3生命closing第2周完了後のcomponent-owned非選出E=0全回復
- reference sigmaへの0.25〜1.50倍の共通倍率、`p_explore`/`epsilon_accept`不変
- neutral/Gaussian軸を持つ固定user type v2と6preset
- life dominance、cross-life common BPM、life-specific multi-attractorの構造診断
- early 3-of-4、outlier return、mechanical rotation、W ceiling、simulation-only truth alignment
- single-condition runner、strict state JSON、paired condition grid、個別trade-off aggregate
- moving preference、sigma以外の係数tuning、formal adoption、Monte Carloは未実装

### Stage 8A.2

- `fatigue_sigma_auto_search_v0_1`と`coarse_refine_confirm_search_v0_1`
- smoke / quick / standard / robustの事前budget計算と、上限超過時の非clipエラー
- Stage 8A.1 `FatigueSigmaSingleConditionRunner`の直接再利用（simulation core再実装なし）
- conditionを混ぜないpaired replicate seedと、user/session/seed/fingerprint単位のreference cache
- canonical job ID、checksummed job result、strict code/spec fingerprint
- atomic checkpoint、exclusive lock、SIGINT/SIGTERM安全境界、completed job skip resume
- user type横断worst/mean、flat safety、rotation、W ceiling、速度、outlier復帰の同時評価
- 95% Wilson intervalと連続値のcount/mean/median/min/max/Q1/Q3
- transparent candidate gate、Pareto rank、lexicographic robust ranking、5種specialist
- self-contained inline CSS/SVG HTML report、CSV/JSON schema、macOS launcher
- OpenAI/API/network/Qtなし、formal adoptionなし、moving preferenceなし

### Stage 8A.3

- `adaptive_placebo_rmssd_validation_v0_1`と3 armのimmutable contract
- 9種の固定user type、participant間response-strength差、arm-independent physiology seed
- autonomous cohort先行、donor≠targetのcyclic same-type yoke、checksummed exact replay
- condition/RMSSDをkeyに含めないdeterministic random holder/Hue/BPM
- immutable BundleOutcome/SessionOutcome、baseline pairing監査、ΔRMSSD主尺度
- contemporaneousとlaggedの分離、past-only 3 model、165 counterfactual、prospective enrichment
- paired arm effect、permutation null、session-block/participant bootstrap、`no_clear_effect`を含む補助分類
- participant 3-panel session×BPM×actual-Hue×life-shape図、user type/全体/相関図
- atomic checkpoint/resume、donor checksum検証、self-contained HTML/CSV/JSON
- Stage 8A.1/8A.2基盤の再利用、OpenAI/API/network/Qtなし、moving preferenceなし

## Requirements / setup

- Python 3.12以上
- PySide6 / Qt Widgets
- PyQtGraph / NumPy
- pytest / pytest-qt
- Ruff

Stage 8A.2固定検証環境はPython 3.13.4、PySide6 6.11.1、PyQtGraph 0.14.0、NumPy 2.5.1、pytest 9.1.1、pytest-qt 4.5.0、Ruff 0.16.1です。

プロジェクト直下の `.venv` をStage間で再利用します。

```bash
python3.13 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e '.[dev]'
```

## GUI起動

```bash
.venv/bin/python -m symbiotic_sim_v2
```

macOSでは、汎用launcher `環境共生型デジタル生命シミュレーターv2を起動.command` をダブルクリックできます。`時間シミュレーターを起動.command` も後方互換用に維持しています。

GUI上部には共通の実行状態があり、Stage 8A.1の疲労・探索幅ラボを先頭にしながら既存tabをすべて維持します。ラボ内は「単一条件」「条件比較」「収束構造」「実験manifest・回帰」の4 sub-tabです。

1. 疲労・探索幅ラボ: user type v2、fatigue target、sigma multiplier、session×BPM×Hue、E/sigma trajectory、構造収束、paired grid
2. 固定仮想ユーザータイプ: 固定peak、physiology gain、hidden diagnostic heatmapと生命別出力可能Hue帯
3. 複数セッション収束: Stage 8A設定/操作、state card、holder/Hue-BPM/k/support/action/truth chart
4. 関係記憶探索: 現在または直近sessionの3生命profile/state、F/T探索、3Bundle transition、persistent before/after
5. 光応答仮想ユーザー: 物理光、preference、response、生理作用、Garden正式RMSSD/N、receipt/heartbeat表
6. 光点滅シミュレーター: current HSV/phase、opt-in preview、waveform、parameter、command/segment表
7. 3生命・資格競争: 3状態card、tau/touch、G/holder、E/q、P/V、B、touch/第2周table
8. Garden出力資格層: holder timeline、資格規則、qualified B、qualification table
9. Garden入力層: phase/S、RRI/artifact、RMSSD/N、N/S、RRI・評価table
10. 仮想ユーザー心拍: Stage 2互換の内部真値診断
11. Polar H10: ideal mode固定条件、raw RRI、真値比較、誤差、測定table
12. 時間・イベント診断: timeline、実行済みevent log、wall/virtual time診断

Stage 8A/8A.1設定はstopped/reset時だけ変更できます。Stage 8A.1は1session step/run all/pause/reset、reference比較、state JSON保存/読込、CSV、grid progress/cancelを備えます。hidden heatmapはsimulation-only診断であり、Digital Lifeの探索入力ではありません。

仮想ユーザー設定は開始前またはreset後だけ変更できます。Stage 5Aの1体専用GUI/role fixtureも後方互換として残します。H10にはnoise、latency、packet loss、artifact rateなどの調整parameterはありません。Garden入力・出力のモデル値とpolicyは固定設定として表示し、GUIからscheduler内部heapを操作しません。

## Headless

Stage 1 time demo（後方互換）:

```bash
.venv/bin/python -m symbiotic_sim_v2 --headless-demo
.venv/bin/python -m symbiotic_sim_v2 --headless-time-demo
```

Stage 2標準180秒scenario:

```bash
.venv/bin/python -m symbiotic_sim_v2 --headless-virtual-user-demo
```

Stage 3標準180秒scenario:

```bash
.venv/bin/python -m symbiotic_sim_v2 --headless-h10-demo
```

Stage 4標準240秒scenario:

```bash
.venv/bin/python -m symbiotic_sim_v2 --headless-garden-input-demo
```

Stage 5A標準greenの240秒scenario:

```bash
.venv/bin/python -m symbiotic_sim_v2 --headless-single-life-demo
```

red/green/blueのroleを指定できます。

```bash
.venv/bin/python -m symbiotic_sim_v2 --headless-single-life-demo --life-role blue
```

Stage 5Bの3生命・資格競争・第2周:

```bash
.venv/bin/python -m symbiotic_sim_v2 --headless-three-life-competition-demo
```

Stage 6のGarden Light Mapper・仮想光device:

```bash
.venv/bin/python -m symbiotic_sim_v2 --headless-light-device-demo
```

Stage 7の光応答閉ループ:

```bash
.venv/bin/python -m symbiotic_sim_v2 \
  --headless-light-responsive-user-demo \
  --light-response-preset aligned_green_center
```

Stage 5Cの3Bundle関係記憶探索:

```bash
.venv/bin/python -m symbiotic_sim_v2 \
  --headless-relation-memory-demo \
  --light-response-preset off_center_green
```

initial stateを指定しない場合は3生命のfresh stateを使います。Stage 8向けのpersistent-state seamをstrict JSONで確認できます。

```bash
.venv/bin/python -m symbiotic_sim_v2 \
  --headless-relation-memory-demo \
  --light-response-preset off_center_green \
  --initial-relation-state-json initial-relation-state.json \
  --export-final-relation-state-json final-relation-state.json
```

IDの欠落/不一致、unknown/missing field、範囲外値、bool counter、非有限値、version不一致を拒否します。Stage 5C出力は後方互換の `single_session_only=true`、`multi_session_not_implemented=true`、`convergence_evaluated=false` を維持します。

Stage 8Aの固定好みmulti-session run:

```bash
.venv/bin/python -m symbiotic_sim_v2 \
  --headless-multi-session-convergence-demo \
  --stationary-user-type green_narrow_moderate \
  --maximum-sessions 24 \
  --convergence-window 4 \
  --convergence-required 3 \
  --master-seed 20260802
```

`--session-seed-policy`、Hue/BPM tolerance、truth gapを指定できます。`--initial-multi-session-state-json`と`--export-final-multi-session-state-json`で厳密にresumeでき、resume時は保存state内の設定がauthoritativeです。`--compare-all-stationary-user-types`は同じconfigで6タイプを独立比較します。出力は`stationary_preference=true`、`moving_preference=false`、`convergence_is_diagnostic_only=true`、`exploration_continues_after_convergence=true`、`v2_coefficients_modified=false`、`multi_session=true`、`Monte_Carlo=false`を明示します。

Stage 8A.1単一条件:

```bash
.venv/bin/python -m symbiotic_sim_v2 \
  --headless-fatigue-sigma-lab-demo \
  --stationary-user-type-v2 green_hue_dominant_broad_bpm \
  --selected-session-fatigue-target 0.05 \
  --sigma-multiplier 1.0 \
  --maximum-sessions 24 \
  --master-seed 20260802 \
  --compare-reference-arm
```

Stage 8A.1 paired condition grid:

```bash
.venv/bin/python -m symbiotic_sim_v2 \
  --headless-fatigue-sigma-grid-demo \
  --stationary-user-type-v2 green_hue_dominant_broad_bpm \
  --fatigue-targets 0.03,0.05,0.08,0.10,0.15 \
  --sigma-multipliers 0.50,0.75,1.00,1.25,1.50 \
  --maximum-sessions 24 \
  --replicates 5 \
  --master-seed 20260802
```

`--experiment-preset quick|standard|detailed`、`--initial-experiment-state-json`、`--export-final-experiment-state-json`、`--export-experiment-csv`を使えます。`detailed`は明示選択した軸とreplicateを60 sessionsで実行し、30,000 session上限はclipせず拒否します。出力は`stationary_preference=true`、`moving_preference=false`、`unselected_full_recovery=true`、`convergence_is_diagnostic_only=true`、`exploration_continues_after_convergence=true`、`p_explore_modified=false`、`epsilon_accept_modified=false`、`q_coefficients_modified=false`、`v2_reference_arm_available=true`、`formal_spec_adoption=false`、`Monte_Carlo=false`を明示します。

Stage 8A.2 plan-only（simulation実行・directory作成なし）:

```bash
.venv/bin/python -m symbiotic_sim_v2 \
  --headless-fatigue-sigma-auto-search \
  --search-preset standard \
  --plan-only
```

実装確認用smoke（32 experimental session runs）:

```bash
.venv/bin/python -m symbiotic_sim_v2 \
  --headless-fatigue-sigma-auto-search \
  --search-preset smoke \
  --output-directory artifacts/auto_search_smoke
```

標準探索と堅牢探索はCodex作業中には実行せず、push後に利用者がローカルTerminalまたは`.command`から実行します。

```bash
.venv/bin/python -m symbiotic_sim_v2 \
  --headless-fatigue-sigma-auto-search --search-preset standard

.venv/bin/python -m symbiotic_sim_v2 \
  --headless-fatigue-sigma-auto-search --search-preset robust
```

中断したrunは、stdoutに表示されたrun directoryを指定してstrictに再開します。code/spec fingerprintまたはschemaが異なる場合は`AUTO_SEARCH_CODE_CHANGED`等で停止し、勝手に続行しません。

```bash
.venv/bin/python -m symbiotic_sim_v2 \
  --headless-fatigue-sigma-auto-search \
  --resume artifacts/auto_search/<run_id>
```

macOSでは`自動条件探索_計画確認.command`、`自動条件探索_標準.command`、`自動条件探索_堅牢.command`、`自動条件探索_再開.command`を使用できます。成果物はrun directoryの`results/`、`report/report.html`、`checkpoint.json`へ保存されます。詳しくは[ローカル実行ガイド](docs/auto-search-local-execution-guide.md)を参照してください。

Stage 8A.3 plan-onlyとsmoke:

```bash
.venv/bin/python -m symbiotic_sim_v2 \
  --headless-adaptive-placebo-validation \
  --validation-preset standard \
  --plan-only

.venv/bin/python -m symbiotic_sim_v2 \
  --headless-adaptive-placebo-validation \
  --validation-preset smoke \
  --output-directory artifacts/adaptive_placebo_validation_smoke
```

smokeは48 target sessionsの実装確認だけです。standard/robust本検証はCodex作業中には実行せず、push後に利用者がローカルで実行します。

```bash
.venv/bin/python -m symbiotic_sim_v2 \
  --headless-adaptive-placebo-validation --validation-preset standard

.venv/bin/python -m symbiotic_sim_v2 \
  --headless-adaptive-placebo-validation --validation-preset robust

.venv/bin/python -m symbiotic_sim_v2 \
  --headless-adaptive-placebo-validation \
  --resume artifacts/adaptive_placebo_validation/<run_id>
```

`--conditions-json`、`--validation-config`、`--base-master-seed`、`--participants-per-type`、`--maximum-sessions`、`--permutation-count`、`--retain-details`を使えます。macOS launcherは`自律プラセボ検証_計画確認.command`、`_標準.command`、`_堅牢.command`、`_再開.command`です。外部networkは不要で、run directoryの`report/report.html`とparticipant別HTMLをローカルで開けます。詳細は[Stage 8A.3ローカル実行ガイド](docs/stage-08a3-local-execution-guide.md)を参照してください。

`off_center_green` と `light_insensitive_control` も指定できます。いずれもreal-time待機をせずJSONを標準出力します。package versionは `0.13.0` です。既存JSON contractを変えないため、Stage 3/4/5A/5B.1/6/7.1/8A/8A.1/8A.2 headlessの `project_version` は各Stageの固定値を意図的に維持します。

既存Stage 1〜5A JSONは変更しません。Stage 5B JSONはholder、生命別E/q/G/k、touch/feedback/qualified B件数と分離digestを表示し、探索状態、Hue、BPM、I、光波形を含めません。

## 開発用CSV export

Stage 2の仮想ユーザー内部真値:

```bash
.venv/bin/python -m symbiotic_sim_v2 --headless-virtual-user-demo --export-virtual-user-csv virtual_user_true_heartbeat_diagnostics.csv
```

Stage 3のH10 raw測定と独立診断比較:

```bash
.venv/bin/python -m symbiotic_sim_v2 --headless-h10-demo --export-h10-csv polar_h10_rri_measurement_diagnostics.csv
```

Stage 4 Garden入力層はGUIとheadless helperから次の3種類を保存できます。

- `garden_input_rri_classification_diagnostics.csv`
- `garden_input_evaluations.csv`
- `garden_input_signals.csv`

headlessで3ファイルを同じdirectoryへ保存する例:

```bash
.venv/bin/python -m symbiotic_sim_v2 --headless-garden-input-demo \
  --export-garden-input-csv artifacts/csv/stage-04
```

Stage 5AのDigital LifeはGUIとheadless helperから次の2種類を保存できます。

- `single_digital_life_first_round_diagnostics.csv`
- `single_digital_life_evaluation_updates.csv`

headlessで2ファイルを保存する例:

```bash
.venv/bin/python -m symbiotic_sim_v2 --headless-single-life-demo \
  --export-single-life-csv artifacts/csv/stage-05a
```

Stage 5Bは次の4ファイルを保存します。

- `stage_05b_digital_life_touches.csv`
- `stage_05b_garden_qualification.csv`
- `stage_05b_qualified_b_outputs.csv`
- `stage_05b_digital_life_second_round.csv`

```bash
.venv/bin/python -m symbiotic_sim_v2 --headless-three-life-competition-demo \
  --export-three-life-competition-csv artifacts/csv/stage-05b
```

Stage 6は次の4ファイルを保存します。

- `stage_06_light_commands.csv`
- `stage_06_light_stimulus_states.csv`
- `stage_06_light_stimulus_segments.csv`
- `stage_06_light_waveform_samples_20ms.csv`

```bash
.venv/bin/python -m symbiotic_sim_v2 --headless-light-device-demo \
  --export-light-device-csv artifacts/csv/stage-06
```

Stage 7.1は次の5ファイルを保存します。

- `stage_07_light_stimulus_receipts.csv`
- `stage_07_light_response_segments.csv`
- `stage_07_response_dynamics_epochs.csv`
- `stage_07_light_responsive_heartbeats.csv`
- `stage_07_light_response_samples_100ms.csv`

```bash
.venv/bin/python -m symbiotic_sim_v2 \
  --headless-light-responsive-user-demo \
  --light-response-preset aligned_green_center \
  --export-light-responsive-user-csv artifacts/csv/stage-07
```

Stage 5Cは次の5ファイルを保存します。

- `stage_05c_relation_memory_intrinsic_profiles.csv`
- `stage_05c_relation_memory_transitions.csv`
- `stage_05c_adaptive_digital_life_signals.csv`
- `stage_05c_relation_memory_persistent_states.csv`
- `stage_05c_relation_memory_session_summary.csv`

```bash
.venv/bin/python -m symbiotic_sim_v2 \
  --headless-relation-memory-demo \
  --light-response-preset off_center_green \
  --export-relation-memory-csv artifacts/csv/stage-05c
```

Stage 8Aは次の6ファイルを保存します。

- `stage_08a_stationary_user_types.csv`
- `stage_08a_session_outcomes.csv`
- `stage_08a_convergence_history.csv`
- `stage_08a_pattern_trajectory.csv`
- `stage_08a_persistent_state_trajectory.csv`
- `stage_08a_user_type_comparison.csv`

```bash
.venv/bin/python -m symbiotic_sim_v2 \
  --headless-multi-session-convergence-demo \
  --maximum-sessions 24 \
  --export-multi-session-csv artifacts/csv/stage-08a
```

Stage 8A.1は次の8 CSVと1 manifestを保存します。

- `stage_08a1_conditions.csv`
- `stage_08a1_fatigue_trajectory.csv`
- `stage_08a1_sigma_trajectory.csv`
- `stage_08a1_session_pattern_trajectory.csv`
- `stage_08a1_structured_convergence_history.csv`
- `stage_08a1_replicate_results.csv`
- `stage_08a1_condition_summaries.csv`
- `stage_08a1_grid_heatmap.csv`
- `stage_08a1_experiment_manifest.json`

```bash
.venv/bin/python -m symbiotic_sim_v2 \
  --headless-fatigue-sigma-lab-demo \
  --export-experiment-csv artifacts/csv/stage-08a1
```

GUIからも診断CSVを保存できます。H10 CSVのraw device output列と `diagnostic_true_rri_*` / `absolute_error_us` / `match` 列は責務上分離され、`diagnostic_notice` 列で開発用比較であることを明示します。GardenはCSVではなく `RriMeasurementEvent` を直接受信し、Digital LifeもCSVではなくGarden formal eventを受信します。CSV exportの有無はsimulation結果とdigestを変えません。

## Formal event boundaries

`HeartbeatEvent`:

```json
{
  "event_type": "heartbeat",
  "source": "virtual_user",
  "priority": 40,
  "scheduled_time_us": 855679,
  "payload": {
    "user_id": "virtual-user-001",
    "beat_index": 1
  }
}
```

`RriMeasurementEvent`:

```json
{
  "event_type": "rri_measurement",
  "source": "polar_h10",
  "priority": 50,
  "scheduled_time_us": 855679,
  "payload": {
    "device_id": "polar-h10-sim-001",
    "user_id": "virtual-user-001",
    "measurement_index": 0,
    "previous_beat_index": 0,
    "current_beat_index": 1,
    "previous_heartbeat_time_us": 0,
    "current_heartbeat_time_us": 855679,
    "rri_us": 855679,
    "rri_ms": 855.679,
    "event_schema_version": "rri_measurement_event_v1"
  }
}
```

`rri_us` がcanonicalな値で、`rri_ms` は導出値です。H10 payloadへtrue RRI、RMSSD、N/Nd/W、artifact、内部生理成分を入れません。

Garden入力層はこの `RriMeasurementEvent` だけを受け、1秒周期の `GardenInputSignalEvent` に `n_current` と `s` を載せます。評価確定時の件数、artifact率、RMSSD、N、qualityは `GardenEvaluationFinalizedEvent` へ記録します。正式なsignal payloadにNdとWはありません。

Stage 5A Digital Lifeの正式入力はこの `GardenInputSignalEvent` と `GardenEvaluationFinalizedEvent` だけです。N/Sはsignalからのみ取得し、evaluation eventはID/quality/revisionの由来metadataとして使用します。Gardenのcomponent/record、RRI、RMSSD、artifact内部値を参照しません。Stage 5A Digital Lifeに正式外部出力eventはなく、first-round/evaluation-update recordは開発用診断です。

Stage 5B.1の正式touch v2はID、signal識別metadata、Bだけを含み、role、P、V、tauは含みません。参加IDはRuntime/session rosterからGardenへ注入され、Garden coreはroleを参照せずactual arrival orderだけでholderを決めます。active `GardenQualifiedBEvent` v2はholder touchの実到着時刻を `effective_time_us` として同じmicrosecondに出力され、round finalizeでは再出力されません。Stage 6 Mapperはこのeventだけから `LightCommandEvent=I` を作り、Deviceは同時刻の `LightStimulusStateEvent` と半開区間segmentを作ります。各生命へのfeedbackと第2周は従来どおりround finalize後です。

Stage 5Cはformal event schemaを増やさず、このfeedback第2周を関係記憶遷移の入力境界とします。candidate、W anchor/trial、profile、persistent/session state、transition recordはDigital Life内部の監査値で、touchまたはGarden formal payloadへ入れません。Runtime/Gardenはcandidate生成や採否に関与しません。

Stage 8A/8A.1もformal event schemaを増やしません。`SessionOutcome`、rolling/structured convergence、truth alignment、multi-session state、fatigue/sigma trajectory、heatmap、比較表はすべてsimulation診断です。Digital Lifeがhidden peak、convergence state、session historyを受け取る経路はありません。

## Stage 4 Garden input model

### 時間構造とS

| 仮想時刻 | role | S（baseline有効時） | evaluation |
| --- | --- | ---: | --- |
| `[0, 30)` 秒 | baseline discard | 0 | なし |
| `[30, 60)` 秒 | baseline evaluation | 0 | baseline |
| `[60, 90)` 秒 | Bundle 0 discard | 1 | なし |
| `[90, 120)` 秒 | Bundle 0 evaluation | 1 | Bundle 0 |
| `[120, 150)` 秒 | Bundle 1 discard | 1 | なし |
| `[150, 180)` 秒 | Bundle 1 evaluation | 1 | Bundle 1 |
| `[180, 210)` 秒 | Bundle 2 discard | 1 | なし |
| `[210, 240)` 秒 | Bundle 2 evaluation | 1 | Bundle 2 |
| `240` 秒 | closing/outside | 0 | なし |

baselineは30秒discard + 30秒evaluationです。各bundleも30秒discard + 30秒evaluationで、3 bundleのmain sessionは180秒、全体は240秒です。0〜240秒を1秒間隔で出力するため、標準runのN/S signalは241件です。

### RRI artifact

分類は次の順序です。

1. `rri_us < 300_000`: `too_short`
2. `rri_us > 2_000_000`: `too_long`
3. 有効historyが5件以上なら、直近最大15件の中央値からの偏差が20%を超える値: `median_deviation`
4. それ以外: valid

300〜2000 msの両端と偏差20%ちょうどはvalidです。artifactはraw値のまま記録し、clipも補間もせず、valid historyと評価RMSSDから除外します。validなdiscard/outside RRIは中央値historyへ入りますが、評価windowのRMSSDには使いません。historyはwindow境界でresetしません。

### RMSSD、N、quality

各evaluation window内の有効RRIを時刻順に `r_1, ..., r_K` とすると、RMSSDは次の実計算です。前windowとの境界差は含めません。

```text
RMSSD = sqrt((Σ[i=2..K] (r_i - r_(i-1))^2) / (K - 1))
```

canonicalなmicrosecondsで計算して結果をmillisecondsへ変換し、2件未満ならnullです。有効RRIが5件未満、またはartifact率が10%を超えるevaluationはrejectedです。artifact率が5%を超え10%以下ならlow confidence、それ以下ならvalidです。5%ちょうどはvalid、10%ちょうどはlow confidenceです。

validまたはlow-confidence evaluationのNはbaselineを入力にせず、固定式だけで計算します。

```text
N = clip01((RMSSD_ms - 15) / (80 - 15))
  = clip01((RMSSD_ms - 15) / 65)
```

baseline evaluationが有効ならそのNを `n_baseline_session` と `n_current` に設定し、session中のbaselineは固定します。以後の有効bundle評価はcurrent Nだけを更新します。rejected評価ではN、baseline、revisionを更新しません。

### 明示的なimplementation policies

v2.0は境界をまたぐRRIの所属を明示していません。Stage 4は `measurement_end_time`、すなわち `RriMeasurementEvent.scheduled_time_us` を半開区間へ当てはめます。30秒ちょうどはbaseline evaluation、60秒ちょうどはBundle 0 discard、240秒ちょうどはoutsideです。これはsimulation implementation assumptionです。

v2.0はbaseline無効時のretryを規定していません。Stage 4は `keep_s_zero_and_skip_main_evaluations` を採用し、S=0とN=nullを維持したまま240秒まで進め、main evaluationsをrejectedとしてNを更新しません。これもsimulation implementation assumptionです。

## Stage 5A Digital Life first-round model

新しい有効evaluation revisionを受けたときだけ、Garden signalのNと固定session baselineからNdを更新し、情動系がWを評価します。MVPで値は `W=Nd` ですが、別概念・別fieldです。

```text
Nd = clip01(0.5 + (N_current - N_baseline_session) / (2 * 0.10))
P  = 1 - S * (1 - p_intrinsic)
V  = clip01(((N_current + q) / 2) * (1 - E))
B  = Phi_B(k_current)
tau = clip01(P / (P + V + 0.000001) + birth_phase)  # S=1のみ
```

Stage 5AでE=0、q=0.5、`k_current=[0.5,0.5,0.5,0.5]` をlive更新しません。S=0でP=1、tau=nullです。240秒closingではBundle 2 revisionをNd/Wへ先に適用した後、S=0のP/tauを記録します。Gは `not_connected`、touch配送は0件です。

## Stage 5B competition and second-round model

3生命は同じN/Sを受けますが互いの内部値を参照しません。Runtimeは各tauを個別touch時刻へ写像するだけで、Gardenがactual arrivalからholderを決めます。holderはS=1中固定ですが全生命が毎signal touchします。active qualified Bはそのsignalのholder touch時刻から有効で、round finalizeは全touchを確認してfeedbackと第2周を同期します。各生命はID照合でGを計算し、毎signal Eを更新し、新規有効Bundle評価かつG=1だけqを更新します。更新E/qは次signalから使用し、kは固定です。240秒ではinactive commandを出し、Bundle 2を解放前holderへ帰属してからreleaseします。

## Stage 5C confirmed relation-memory model

Stage 5CはStage 5Bの処理を複製せず再利用し、各生命の第2周へ独立な `adaptive_random_search_confirmed_v1` を追加します。baselineのW=0.5はanchorにせず、G=1生命のBundle 0有効評価で初めて `W_anchor_session` を保存します。

```text
r(W) = clip01(2W-1)
sigma = sigma_min + (sigma_max-sigma_min)*(1-r(W_anchor_session))
p_explore = p_explore_min + (1-p_explore_min)*(1-r(W_anchor_session))
u_explore = Hash01(ID,"C","explore",session_count_used)
explore iff u_explore < p_explore
```

exploreではincrement前 `trial_count` からHash方向を作り、`reflect01`でF/Tだけを変更します。Bundle 1は `W_trial_1 > W_anchor_session+epsilon_accept` で同一trial確認へ進み、Bundle 2は `W_trial_2>W_anchor_session` かつtrial平均がanchor+epsilonをstrictに超えるときだけ `k_anchor` を更新します。それ以外はold anchorへrollbackします。

q/E/kは同じbefore stateから独立導出し、第2周で原子的に反映します。同じsignalのBを更新後kで再計算せず、次signalから `Phi_B(k)` へ使います。persistentに引き継ぐ `k_anchor/q/E/trial_count/session_count` と、sessionごとにresetするW/trial/phaseを分離します。詳細は [Stage 5C設計](docs/stage-05c-confirmed-relation-memory-search.md) を参照してください。

## Stage 6 B→I and virtual light model

Stage 6のMapperは `GardenQualifiedBEvent v2` だけを受け、`Hue=360F`、`BPM=10+155T`、Saturation=1.0、Value=`0.425+0.075sin(2πphase)` の `LightCommandEvent` を生成します。A/Dはsource Bとして保存しますが光parameterに使いません。

F=1のformal Hueは360.0のまま保持します。render Hueの0.0へのmodulo、event priority/schema、位相開始・継続、command hold、inactive black、segment、20ms sampling、GUI previewは、v2.0が具体化していないStage 6のversion管理されたsimulation implementation assumptionです。

Virtual Light Deviceはcommandを次commandまで保持し、integer microsecondsのabsolute virtual timeからphase/Valueを解析的に求めます。same commandやBPM/Hue変更でphaseをresetせず、inactiveからactiveのみphase 0へresetします。inactiveは黒、formal outputは `LightStimulusStateEvent`、監査記録は半開区間 `LightStimulusSegment` です。

## Deterministic digest baselines

- Stage 1: `1c4217065fa29316e7ead83c4d604e87f9fe8fe46e82b689b5566dbc9890598d`
- Stage 2 heartbeat: `4c039f5f1b5cc3cd78682cca890a8a6ec70510a52b4ad4addeabcb0ecd3ae765`
- Stage 2 diagnostic: `ef0bc8c644e8b5f6fc2c3b58ef825491e49e005bc0c6c22a9f0c62c66168cd8f`
- Stage 2 full event: `761a2dc6b2b03c4d538a85d95160f2ecc731e301a1362006ee97ea575872bddb`

Stage 3 measurement digestは `scheduled_time_us` とcanonicalな `rri_us` を含み、導出可能な `rri_ms` とscheduler識別子 `event_id` を除外します。

Stage 4はRRI artifact分類、4 evaluation、241件のN/S signal、full event列をそれぞれcanonical JSON化したdigestを分離します。固定値をREADMEへ重複記載せず、headless結果と回帰testをsource of truthとします。実行mode、reset、snapshot・chart頻度、CSV export、config JSON round-tripはdigestを変えません。

Stage 5Aは241件のfirst-round recordと、新しい有効評価またはrejected評価に対応するevaluation-update recordのdigestを分けます。Digital Lifeは新規eventを発行しないため、Stage 4とStage 5Aのfull event digestは同じです。roleを変えてもVirtualUser/H10/Gardenの結果は不変で、生命固有のP/B/tauとfirst-round digestだけが変化します。

Stage 5B.1はtouch、qualification、qualified B、feedback、生命別second roundを別々にdigest化します。標準runはtouch 540、feedback 723、active/inactive output 180/61、assignment/release各1です。touch/qualified B/full event digestはv2 schemaと補正時刻を反映し、qualification/feedback/second roundの意味は維持します。run-to-end、step、速度、reset、snapshot頻度、GUI、CSV exportは結果を変えません。

Stage 6はcommand、stimulus state、segment、20ms fixed-grid waveform、full eventを分離digest化します。標準runは241 command/state、240 segment、12001 sampleで、run mode、reset、snapshot頻度、GUI preview、CSV exportに対して同一です。固定値は [Stage 6 reference vectors](docs/conformance/stage-06-reference-vectors.json) をsource of truthとし、[Stage 6設計文書](docs/stage-06-light-blink-simulator.md) に監査用一覧を記載します。

Stage 7.1はformal heartbeat、responsive heartbeat診断、light receipt、physical audit segment、response dynamics epoch、100ms fixed-grid sample、full eventを分離digest化します。controlはStage 6 heartbeat/formal streamを再現し、responsive presetは同じ乱数keyのまま生理連成だけを追加します。監査分割は物理signatureのexact equality、response epoch分割はtargetのexact equalityで独立に決まります。固定式は [Stage 7 reference vectors](docs/conformance/stage-07-reference-vectors.json) をsource of truthとします。

Stage 5Cはintrinsic profile、adaptive signal、relation-memory transition、final persistent state、session summaryを別々にcanonical digest化します。run-to-end、1秒/1-event step、速度mode、reset、snapshot頻度、preview、GUI/headless、CSV export、state JSON round-tripで一致します。独立期待値は [Stage 5C reference vectors](docs/conformance/stage-05c-reference-vectors.json) をsource of truthとし、既存Stage 1〜7.1のdigest/CSVを変更しません。

Stage 8Aはstationary user type、session outcome、convergence history、multi-session persistent state、type comparisonをcanonical UTF-8 JSONで別々にdigest化します。session-by-session、batch、pause、reset、GUI/headless、CSV有無、state JSON round-trip、同じseed/configで一致します。独立期待値は [Stage 8A reference vectors](docs/conformance/stage-08a-reference-vectors.json) をsource of truthとし、Stage 1〜5Cの既存headless JSON/digest/CSVを変更しません。

Stage 8A.1はexperiment condition、fatigue trajectory、sigma trajectory、structured convergence、replicate result、condition/grid summary、manifest、final experimental stateをcanonical UTF-8 compact JSONで別々にdigest化します。session-by-session/run all、reset、GUI/headless、CSV有無、state JSON round-trip、paired replicate再実行、gridのiteration order変更で一致します。独立期待値は [Stage 8A.1 reference vectors](docs/conformance/stage-08a1-reference-vectors.json) をsource of truthとし、Stage 1〜8Aの既存JSON/digest/CSVを変更しません。

## Test / lint / smoke

```bash
.venv/bin/python -m compileall -q src tests tools
QT_QPA_PLATFORM=offscreen .venv/bin/pytest -q
.venv/bin/ruff check .
QT_QPA_PLATFORM=offscreen .venv/bin/python -m symbiotic_sim_v2 --smoke-test --auto-close-ms 15000
```

テストは既存1798件以上のStage 1〜8A.2回帰に加え、Stage 8A.3のarm/participant/seed/yoke/random contract、Bundle/Session record、past-only model、counterfactual、lagged/prediction/RMSSD/permutation/classification、participant aggregation、inline SVG/HTML、checkpoint/resume、48-session real smoke、CLI/launcher、independent reference vector、no-network/no-Qt境界を確認します。

Stage 5Aの設計境界は [1体のデジタル生命・第1周](docs/stage-05a-single-digital-life-first-round.md)、式と分類は [Digital Life first-round model v0.1](docs/digital-life-first-round-model_v0.1.md) を参照してください。Stage 4の設計境界は [Garden入力層設計](docs/stage-04-garden-input-layer.md)、モデル値は [Garden input model v0.1](docs/relax-with-light-garden-input-model_v0.1.md)、境界所属の仮定は [RRI window membership policy v0.1](docs/rri-window-membership-policy_v0.1.md) にあります。規範との境界は [規範スコープ](docs/normative-scope.md) を参照してください。

Stage 5Bの設計境界は [3生命・資格競争・第2周](docs/stage-05b-three-life-competition-second-round.md)、配送仮定は [tau touch policy](docs/tau-touch-delivery-policy_v0.1.md) にあります。Stage 5B.1の補正は [出力境界・時刻補正](docs/stage-05b1-output-boundary-timing-correction.md)、Garden規則は [Garden output qualification model v0.2](docs/garden-output-qualification-model_v0.2.md)、発行policyは [qualified B emission policy v0.1](docs/qualified-b-emission-policy_v0.1.md) を参照してください。

Stage 6は [光点滅シミュレーター](docs/stage-06-light-blink-simulator.md)、[B→I mapping](docs/b-to-i-light-mapping-model_v0.1.md)、[Virtual Light Device](docs/virtual-light-device-model_v0.1.md)、[continuous phase policy](docs/continuous-phase-policy_v0.1.md) を参照してください。Stage 7/7.1は [光応答仮想ユーザー](docs/stage-07-light-responsive-virtual-user.md)、[Stage 7.1監査分離](docs/stage-07-1-physical-audit-response-epochs.md)、[固定光嗜好](docs/stationary-light-preference-model_v0.1.md)、[一次遅れresponse](docs/first-order-light-response-model_v0.1.md)、[心拍連成](docs/light-response-heartbeat-coupling_v0.1.md) を参照してください。

Stage 5Cは [3Bundle関係記憶探索](docs/stage-05c-confirmed-relation-memory-search.md)、[adaptive algorithm実装](docs/adaptive-random-search-confirmed-v1-implementation.md)、[persistent state contract](docs/relation-memory-state-v2-simulation-contract.md)、[next-signal policy](docs/relation-update-next-signal-policy_v0.1.md) を参照してください。

Stage 8Aは [固定好み・複数セッション収束ラボ](docs/stage-08a-fixed-preference-multi-session-convergence.md)、[rolling majority定義](docs/rolling-majority-convergence-definition_v0.1.md)、[固定user landscape](docs/stationary-user-type-landscapes_v0.1.md)、[state handoff](docs/multi-session-state-handoff_v0.1.md)、[session seed policy](docs/session-physiology-seed-policy_v0.1.md) を参照してください。

Stage 8A.1は [疲労・探索幅・収束条件ラボ](docs/stage-08a1-fatigue-exploration-convergence-lab.md)、[experimental fatigue policy](docs/experimental-fatigue-policy_v0.1.md)、[scaled sigma policy](docs/scaled-reference-sigma-policy_v0.1.md)、[構造収束診断](docs/structured-convergence-diagnostics_v0.1.md)、[固定user type v2](docs/stationary-user-type-profiles_v2.md)、[paired seed policy](docs/paired-replicate-seed-policy_v0.1.md)、[出力schema](docs/stage-08a1-experiment-output-schemas.md) を参照してください。Stage 8A.2は [自動条件探索・堅牢候補抽出](docs/stage-08a2-automatic-condition-search.md) と [ローカル実行ガイド](docs/auto-search-local-execution-guide.md) を参照してください。Stage 8A.3は [自律・プラセボRMSSD個人内適応検証](docs/stage-08a3-adaptive-placebo-rmssd-validation.md)、[yoked contract](docs/yoked-replay-placebo-contract_v0.1.md)、[random contract](docs/pure-random-open-loop-contract_v0.1.md)、[lagged coupling](docs/lagged-rmssd-selection-coupling_v0.1.md)、[past-only model](docs/prospective-history-response-model_v0.1.md)、[participant classification](docs/participant-adaptive-effect-classification_v0.1.md)を参照してください。次はローカルstandard validationと結果レビュー、必要時だけrobust validationであり、その後に **Stage 8B: 変化する好み・追従性** へ進みます。本実装作業でstandard/robustやStage 8Bには進みません。
