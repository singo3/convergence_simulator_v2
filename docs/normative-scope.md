# 規範スコープ

## 唯一の規範仕様

- 絶対パス: `/Users/sawadashingo/ONTELOPE/21_RICOH/共同研究/自律確認MVP/symbiotic-digital-life-signal-loop-concept_v2.0.md`
- size: `65759 bytes`
- SHA-256: `9707de5c07cbcb20603436b374f6a563b5d908206096f2a2204384ae91b22c73`
- `document_version`: `v2.0`
- `profile_version`: `symbiotic_signal_loop_reference_v1_0`
- `algorithm_version`: `adaptive_random_search_confirmed_v1`
- `state_schema_version`: `relation_memory_state_v2`

実装開始時に上記fingerprintとversion tupleが一致することを確認した。規範仕様ファイル自体は変更しない。

## v2.0から参照した事項

- Relax with Light MVPでは `1セッションシグナル = 1秒` である（本文1.1、20.1）。Stage 1の1秒tickは、将来この周期を載せる時間基盤であり、現時点ではセッションシグナルSとして扱わない。
- Runtime SDKは時計、論理的な処理順序、各系の独立実行、配送・返送、状態更新完了や評価eventの同期などを担う実行基盤である（本文1.4、11.2）。Stage 1はこのうち時計、順序、event配送の共通土台だけを作る。
- RuntimeはP/Vを中央比較し、勝者または順位を決める審判ではない（本文1.4、10.1、11.2）。Stage 1 engineに勝者選択ロジックは置かない。

## 規範と実装上の選択の境界

PySide6/Qt WidgetsのGUI、PyQtGraphタイムライン、heap priority queue、整数microsecondsのevent scheduler、20秒のDemo、速度モード、GUI batch件数・wall-time budget、canonical JSON digestは今回の検証目的に合わせた **実装上の選択** であり、v2.0規範そのものではない。

Demoの `clock_tick`、`demo_marker`、`demo_same_time_a/b`、`simulation_complete` は診断eventである。S、baseline、bundle、P/V、生命、Garden、H10、光刺激などの意味を持たせていない。

## Stage 2仮想ユーザーとの境界

`baseline_virtual_user_physiology_v0_1` はv2.0規範ではなく、Stage 2用にversion管理するsimulation assumptionである。v2.0はユーザー内部の生理生成式を規定せず、システム境界から見たブラックボックスとして扱う。

Stage 2でv2.0から参照したのは、ユーザー、H10、Garden入力層、Runtimeなどの責務を混同しないシステム境界だけである。呼吸性sin波、slow wave、AR(1)、jitter、parameter既定値、clamp、diagnostic RMSSDは実装上の仮定であり、v2.0の規範値ではない。

Stage 2の正式出力はheartbeat発生時刻だけである。Stage 2単体はH10 RRI測定、Garden入力層、artifact処理、N生成を実装しない。内部真値RRI/RMSSDをH10またはGarden信号として使用しない。

## Stage 3仮想Polar H10との境界

v2.0では、入力デバイスであるPolar H10の正式出力はRRIである。H10はRMSSD、N、Nd、Wを計算せず、artifact判定、baseline、セッション信号S、evaluation qualityの確定も担わない。RRI絶対範囲、直近有効RRIの中央値との偏差、artifact率、RMSSD、N、baseline、S生成は将来のGarden入力層の責務である。

Stage 3は、`HeartbeatEvent` の隣接する正式時刻差からraw RRIを測定し、`RriMeasurementEvent` を出力する入力デバイス境界を実装する。`ideal_polar_h10_rri_device_v0_1` の「正確な観測、noiseなし、lossなし、delayなし」という具体設計、integer microseconds、event priority 50、canonical JSON digest、GUI、CSVは **simulation assumptionまたは実装上の選択** であり、v2.0規範そのものではない。

H10 coreは仮想ユーザーの `HeartbeatRecord` や生理モデル内部stateを参照しない。GUI、CSV、headless JSONが示す内部真値との誤差比較は、理想H10の測定実装を確認する開発用診断である。Gardenへの正式信号は `RriMeasurementEvent` だけであり、Garden入力層自体はStage 3では未実装である。

## Stage 4 Garden入力層との境界

v2.0でGarden入力層が担う規範上の責務は、H10が出力するRRIを受け、RRI artifact判定、評価区間ごとのRMSSD、固定式によるN、baseline、1秒周期のセッションシグナルSを生成し、後続のデジタル生命へ渡すことである。v2.0のRelax with Light参照値として、300〜2000 msのRRI絶対範囲、直近有効RRI中央値から20%を超える偏差、artifact率5%/10%、RMSSD 15〜80 msのN正規化、30秒discardと30秒evaluation、baseline 60秒と3 bundle・計180秒、1秒シグナルを使用する。

Stage 4はこのうち、正式な `RriMeasurementEvent` の受信、artifact分類、評価window内の実RMSSD計算、`N = clip01((RMSSD_ms - 15) / 65)`、session baselineの確定と固定、評価quality、NとSを含む `GardenInputSignalEvent`、評価metadataの `GardenEvaluationFinalizedEvent`、GUI・headless・診断CSVを実装する。CSVや仮想ユーザー内部真値はGardenの正式入力ではない。artifactを補間せず、discard/outsideのRRIを評価RMSSDへ含めない。

Ndはデジタル生命の状態、Wは情動系の値であり、Stage 4 Garden入力層には実装しない。デジタル生命、Garden出力層、光刺激、ユーザー刺激応答も後続Stageの責務である。

v2.0は、window境界をまたぐRRIをどのwindowへ所属させるかを明示していない。Stage 4の `measurement_end_time`、すなわち `RriMeasurementEvent.scheduled_time_us` を半開区間へ当てはめる方式は **simulation implementation assumption** である。詳細は [RRI window membership policy v0.1](rri-window-membership-policy_v0.1.md) に分離する。

v2.0はbaseline評価が無効だった場合の再試行や後続bundleの扱いを固定していない。Stage 4の `keep_s_zero_and_skip_main_evaluations`、すなわち時間は240秒まで進めるがSを0に保ち、main evaluationをrejectedとしてNを更新しない方式も **simulation implementation assumption** である。これは生理・信号処理の規範値ではなく、別versionで交換可能な失敗時policyである。

## Stage 5Aの単一Digital Life・第1周との境界

Stage 5Aでv2.0から実装したのは、1体のデジタル生命がGardenの正式eventからN/Sを知覚し、第1周のNd、W、P、V、B、tauを計算する範囲だけである。N/S状態は `GardenInputSignalEvent`、評価の由来・quality・revisionは `GardenEvaluationFinalizedEvent` から受ける。Digital LifeはGardenのcomponent/state/record、VirtualUser/H10のcomponent/record、raw RRI、RMSSD、artifact内部値を参照しない。

Stage 5Aは、session baseline相対のNd、Ndと別概念のW、`Phi_P`、N/q/EによるV、`Phi_B(k)`、P/Vによる論理到達値tau、有効評価revisionごとの更新を実装する。MVPではWの数値写像はNdと同じだが、責務、field、function、recordを分ける。baseline初期化時のW=0.5を `W_anchor_session` として保存しない。

`life-red`、`life-green`、`life-blue` とrole別F範囲、240秒の単一生命scenario、標準green選択は再現性のための **simulation fixture** である。これらのIDをv2.0が規定する実在個体IDとみなさない。integer-microseconds schedulerへのhandler登録、GUIのrole selector、first-round/evaluation-update digestも実装上の選択である。

`DigitalLifeFirstRoundRecord`、`DigitalLifeEvaluationUpdateRecord`、snapshot、GUI表示、headless JSON、CSVは **開発用診断** であり、Gardenや後続componentへ配送する規範signalではない。Stage 5AのDigital Lifeは正式外部出力eventを発行しない。tauは0〜1の論理値であり、microsecondsの配送予約ではない。

G、Garden出力層、touch配送、第2周、3生命の資格競争、holder・勝者・順位決定、E/q/kのlive更新、関係記憶探索は未実装である。`G_status=not_connected` は `G=0` の代用値ではない。E/q更新のpure functionは後続Stageの参照用に単体実装されるが、Stage 5Aのlive componentには接続されない。

## Stage 5Bの3生命・資格競争・第2周との境界

Stage 5Bでv2.0から接続したCore範囲は、3体のデジタル生命による独立した第1周、自律touch、実際の到着順によるGarden資格付与と保持、自己IDとholder IDの照合によるG、E/qの第2周、およびholderのBを次Stageへ渡す `GardenQualifiedBEvent` までである。Runtimeは各生命を同期するが、P/Vを中央比較せず、勝者や順位を決定しない。Gardenが生命由来の正式入力として受け取るのは実到着したIDとBのみである。

v2.0はtauを0〜1の論理到達値として定義するが、integer microsecondsへの写像は定義しない。`tau_to_microsecond_touch_delivery_v0_1` のoffset式、finalize予約時刻、および同一microsecondでの辞書順ID登録は **simulation implementation assumption** である。この配送policyはtauの大小をRuntimeに比較させるものではない。

Gardenの `first_touch_when_empty`、`while_s_is_1`、closing第2周完了後のrelease、各recipientへその生命自身のBだけを返す方式も、Stage 5Bでversion管理するGarden出力資格modelの実装仕様である。240秒closingではBundle 2の新しい有効revisionを第1周で適用し、release前holderを含むfeedbackで第2周を完了した後だけholderを解放する。

Stage 5Bではkを初期値のまま固定し、3 bundle関係記憶探索、trial/adoption、k更新はStage 5Cの責務とする。Hue、blink BPM、saturation、brightness、光波形Iの生成はStage 6の責務であり、Stage 5Bは実装しない。

## Stage 5B.1の出力境界・時刻補正との境界

v2.0のCoreから維持する正式境界は、Digital LifeがGardenへ個体IDとBをtouchし、Gardenがactual arrivalによって資格を扱い、qualified Bを後続componentへ渡すことである。`digital_life_touch_event_v2`からroleを除き、GardenがID/Bとsignal識別metadataだけを受ける構造は、この責務分離を明確化する。roleは標準3生命fixtureをGUIで識別するRuntime側の診断情報であり、Garden coreのformal inputまたは個体対応表ではない。

参加IDをRuntime/session rosterからGarden configへ注入する構成、3 IDのlexical正規化、priority 60/65/70、holder touchと同じ`effective_time_us`でactive qualified Bを発行する`qualified_b_on_holder_touch_v0_1`は **simulation implementation assumption** である。v2.0はqualified Bを発行する正確なmicrosecondを規定していない。

Stage 5B.1のround finalizeは全touch、発行済みqualified B、holder Bの整合を検証し、feedbackと第2周を同期する。qualified Bの早期発行はholder、G、E、q、k、feedback時刻、第2周時刻、240秒closing帰属とreleaseを変更しない。

`garden_qualified_b_event_v2`はStage 6へのformal interfaceであり、active時はholder touch時刻、inactive時はsignal時刻をeffective timeとして明示する。関係記憶探索とk更新はStage 5Cまで実装しない。

## Stage 6のB→Iと仮想光deviceとの境界

v2.0が定めるRelax with Lightの規範範囲は、Garden出力層が資格holderの `B=[F,A,T,D]` から `I=M_garden(B)` を作り、`Hue_degree=360F`、`blink_BPM=10+155T`、Saturation 100%、HSV Value 35〜50%、sine波をfeedback deviceが提示することである。PC出力でA/Dを使用しないことも参照仕様として維持する。

Stage 6はこの範囲を `GardenQualifiedBEvent v2 -> LightCommandEvent -> LightStimulusStateEvent` のGUI非依存境界として実装する。MapperはDigital LifeやP/V/tau/W/E/q/k/Gを参照せず、DeviceはLightCommand以外の上流componentを参照しない。

v2.0が明示しないformal Hue 360のGUI描画用modulo、位相開始点、same-commandのphase reset、BPM/Hue変更時のphase継続、command保持、inactive黒、priority 66/67、event/schemaの具体形、GUI fps、20ms固定grid samplingは、それぞれversion管理した **simulation implementation assumption** である。QColor/sRGB preview、CSV、`LightStimulusSegment`、fixed-grid waveform sample、canonical digestは開発・監査用診断であり、校正済み物理光量またはStage 7へ配送するformal signalではない。

Stage 6はcommand境界ごとに `light_stimulus_state_event_v1` を1件出力し、このeventだけを将来Stage 7の正式光入力境界とする。Stage 6自身はVirtualUserのHeartbeat/RRI、RMSSD、N/Nd/Wを光で変化させない。Stage 5Cの関係記憶探索も未実装である。

## Stage 7の固定光応答仮想ユーザーとの境界

v2.0が定める規範上のuser loopは、feedback deviceが刺激Iをユーザーへ提示し、ユーザーの次の生理入力がH10、Garden、Digital Lifeへ戻る責務境界である。Stage 7はこの境界を `LightStimulusStateEvent -> HeartbeatEvent -> H10 RRI -> Garden RMSSD/N` として接続する。正式な光入力はStage 6 deviceの `light_stimulus_state_event_v1` だけ、正式なユーザー出力は既存 `HeartbeatEvent` だけである。

`stationary_hue_bpm_gaussian_preference_v0_1` の固定Hue/BPM特性、Gaussian幅、積によるmatch、`first_order_light_response_v0_1` の8秒onset/12秒recovery、平均RRI最大15ms増加、呼吸性RRI変動幅最大30ms増加、heartbeat開始時sampling、priority 40/67の因果policyは、v2.0が具体的な生理式として定めていない **simulation assumption** である。実データ未校正であり、医学的効果量を表さない。

holder ID、source B、signal indexは物理projection・preference・physiologyから除外し、監査receiptのprovenanceだけに保持する。preferenceは1 run中固定で、moving preference、履歴依存、負反応を実装しない。Light receipt、physical audit segment、response dynamics epoch、responsive heartbeat record、100ms sample、GUI chart、CSV、digestは開発診断である。

Stage 7.1の物理signature対象field、exact equality、`physical_stimulus_parameter_change_v0_1`、`split_audit_on_physical_change_keep_response_on_same_target_v0_1`、監査segmentとresponse dynamics epochの分離はv2.0にない **simulation implementation assumption** である。formal eventと生理式は変更せず、物理parameterが変わってもtargetが同じなら一次遅れepochを継続する。

光responseが変更するのは将来のheartbeat intervalを生成する平均RRIと呼吸性成分だけである。H10は引き続きheartbeat正式時刻差からraw RRIを測定し、GardenがRRIからRMSSDとNを計算する。光からRMSSD、N、Nd、Wを直接変更しない。予約済みheartbeatをlight receipt時にrescheduleせず、Stage 2と同じroot seed、named random stream、beat-index keyを使用する。gain 0のcontrolはStage 6 formal streamを再現する。

Stage 7はcandidate、`k_trial`、adoption、convergence、関係記憶探索を持たず、kを固定する。これらは次工程Stage 5Cの責務である。

## Stage 5Cの3Bundle関係記憶探索との境界

Stage 5Cがv2.0から実装する規範範囲は第25〜27章である。生命固有の `c_i=Hash01(ID_i,"curiosity")`、cから導く `sigma_min/max`、`epsilon_accept`、`p_explore_min`、`W_anchor_session`に応じたsigmaと探索確率、`session_count`を使うhold/explore、`trial_count`を使うF/T方向、`reflect01`による連続candidate、1session最大1candidate、Bundle 0 anchor評価、Bundle 1仮評価、Bundle 2での同一trial確認・anchor復帰、正式採用・rollback、G=0の採否禁止、persistent/session-local stateの区別を対象とする。

Coreの係数、Hash key、strict `<` / `>`、A/D固定、F/Tのみの連続探索、Bundle 2 confirmation必須、`trial_count`のcandidate生成時増加、`session_count`の正常session確定時増加はv2.0の規範である。baseline終了時の `W=0.5` はanchor評価ではなく、`W_anchor_session` はBundle 0の有効anchor評価で初めて設定し、next sessionへは比較値として引き継がない。

次の具体policyはv2.0のCoreではなく、Stage 5Cのversion管理された **simulation implementation assumption** である。

- `positive_f_axis_on_near_zero_direction_norm_v0_1`: v2.0が具体方向を固定しない極小norm fallbackを、`norm<=1e-12`の正F軸に固定する。
- `keep_same_trial_for_bundle2_but_require_two_valid_trial_evaluations_v0_1`: Bundle 1 evaluation reject後は同じtrialをBundle 2へ維持するが、有効trial評価が1回なら採用せずrollbackする。v2.0の「残りbundleで同じ候補を再評価してよい」を本参照分岐に固定したものである。
- `relation_update_effective_next_signal_v0_1`: feedback第2周で変更したkを次signalの `Phi_B(k)` から使い、同一signal内のBを再計算しないinteger-microsecond simulation上のseamである。

Stage 5Cの`AdaptiveConnectedDigitalLifeComponent`、immutable record/schema、JSON/CSV/digest、off-center診断fixture、GUIのF/T最適点、方向norm threshold、state-machineの監査語彙は開発・検証用の具体実装である。診断上の仮想ユーザー最適kをDigital Life Coreへ渡さず、RuntimeとGardenはcandidateを生成・選択しない。

strict persistent-state I/OはStage 8が初期値と正常final stateを受け渡すためのseamである。Stage 5Cが実行するのは単一の240秒sessionだけであり、複数sessionの自動連結、baseline再取得lifecycle、session間W比較、長期収束・sustained convergence判定、Monte Carlo、係数tuningは未実装・未評価である。

## Stage 8Aの固定好み・複数セッション収束診断との境界

Stage 8Aがv2.0から引き継ぐ規範範囲は、第20.6節、第25.4節、第25.18節、第27章にあるsession間state lifecycleである。正常な240秒closingの後だけ`k_anchor`、`q`、user_garden scopeの`E`、`trial_count`、`session_count`とversion metadataを次sessionへ渡す。各sessionでは`N_baseline_session`を再取得し、N/Nd/W、`W_anchor_session`、`k_trial`、trial評価、adaptation phase、exploration decision、資格holder、light/responseのsession-local stateをresetする。異なるbaselineで得たWを直接比較しない。追加のinter-session gapや日単位E回復は導入せず、新session冒頭の既存S=0期間で既存E回復式だけを適用する。

次はv2.0規範ではなく、Stage 8Aでversion管理する **simulation diagnostic assumption** である。

- fixed single/multi-peak stationary preference landscapeと6つのdiagnostic preset
- master seed、user type ID、session indexのSHA-256先頭unsigned 32-bitによるsession physiology seed
- 完了sessionを独立票とし、同じ生命かつ近いHue/BPMの直近4有効session中3sessionを初期収束条件とするrolling majority
- 全pairwise距離を満たすbounded subset探索、cluster medoid、outlier/loss/reconvergence監視
- observed convergenceとhidden landscape truth alignmentの分離

1session内の3Bundleは同じ資格holderを共有するため、一次収束の独立票にはしない。session代表patternはclosing後に正式保存されたholderの`k_anchor`から算出し、trial中の一時光は監査だけへ残す。convergence evaluatorとtruth diagnosticはDigital Life、Runtime、Garden、candidate、holder、k、q、E、`p_explore`、sigma、session停止条件へ値を返さない。収束後も現行v2.0の探索をmaximum sessionsまで継続する。

user preferenceはrun中に完全固定する。moving preference、時間・気温・疲労依存、context別anchorはStage 8Bまで未実装である。v2.0の探索係数は変更せず、係数tuningとMonte CarloもStage 8Aでは実装しない。固定preset、heatmap、truth classification、CSV、GUI chart、digestはsimulation-only診断であり、隠れたpeakを探索入力へ用いない。

## Stage 8A.1の疲労・探索幅・収束条件実験との境界

Stage 8A.1は、v2.0参照Profileに対して正式採用する係数変更ではない。`formal_spec_adoption=false`、`base_profile_version=symbiotic_signal_loop_reference_v1_0`、`experiment_profile_version=stage_08a1_fatigue_sigma_experiment_v0_1`をmanifestに固定する。v2.0 reference armはStage 8Aの参照eta/rho、生命固有`sigma_min/max`、sigma multiplier 1.0、session終了時の非選出全回復なしを完全に維持する。

Stage 8A.1 experimental armが変更するのは次の3項目だけである。

- 180 active signals後の目標値から1signalの`eta_selected`を導出する選出生命疲労
- 正常sessionのclosing第2周完了後、final state確定前に非選出生命だけをE=0にするcomponent-owned policy
- v2.0参照sigmaへの0.25〜1.50の共通倍率

selected fatigueのE式の構造と`rho_E=1-0.90^(1/180)`は維持する。全回復はmulti-session runnerがfinal Eを後処理で改変する方式ではない。error/未完了sessionでは回復を含むstateをcommitしない。`p_explore`、`epsilon_accept`、q係数、P/V/tau mapping、RMSSD→N、`delta_N`、3Bundle構造、candidate確認規則、Hash方向、F/Tのみ探索・A/D固定は変更しない。規範仕様第30章にある疲労蓄積・回復率とsigma範囲の残る検証事項を実験するための層であり、係数の正式採用を意味しない。

fixed user type v2、paired replicate、structured convergence、mechanical rotation、W-ceiling、condition grid、truth alignment v2、GUI/CSV/JSON/digestはStage 8A.1の **simulation diagnostic assumption** である。observed evaluatorはhidden peakを読まず、診断結果をDigital Life、Runtime、Garden、fatigue/sigma policyへ返さない。condition/fatigue/sigma/convergence値をpaired random seedへ入れない。

preferenceはrun中に固定する。moving/time/context/fatigue-dependent preference、`p_explore`倍率、収束による探索停止や係数変更、単一最良スコア、大規模Monte Carlo、formal Profile採用は未実装である。

## Stage 8A.2の自動条件探索・堅牢候補抽出との境界

Stage 8A.2はStage 8A.1の`FatigueSigmaSingleConditionRunner`をそのまま呼び出す **simulation-onlyの実験orchestration層** である。coarse→refine→confirm、paired replicate、reference cache、checkpoint/resume、Wilson区間、Pareto frontier、robust/specialist ranking、CSV/JSON/HTML reportはすべて検証・観測用の実装上の選択である。Digital Life Core、Runtime、Garden、v2.0 reference Profileは変更せず、候補・収束・診断結果をシミュレーションへ返さない。

`formal_spec_adoption=false`を全runで維持する。探索条件はpaired random seedに混入せず、`p_explore`、`epsilon_accept`、q係数、P/V/tau、RMSSD→N、`delta_N`を変更しない。hidden preference/truthはpost-hocのsimulation-only評価に限り、Digital Life、Runtime、Gardenの入力にしない。moving preferenceはStage 8Bまで未実装である。

条件の比較は不透明な単一総合スコアで潰さず、方向付きの複数目的、Pareto支配関係、gate判定、弱点とtrade-offを保存する。balanced robust gateを通る候補がないときは、代替の「最良」を捏造せず`no_robust_candidate`とblockerを報告する。OpenAI、Codex、ChatGPT、外部LLM、外部API、networkは使用しない。
