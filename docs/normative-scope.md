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
