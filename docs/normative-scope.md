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
