# Stage 1の規範スコープ

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
