# Codex作業規約

- 作業開始前に規範仕様 `/Users/sawadashingo/ONTELOPE/21_RICOH/共同研究/自律確認MVP/symbiotic-digital-life-signal-loop-concept_v2.0.md` の存在、size、SHA-256、version tupleを確認する。不一致は `SPEC_MISSING` または `SPEC_CHANGED` として停止し、別名・旧版へfallbackしない。
- GUI非依存engineとGUIを分離する。`domain` と `simulation` へQt/PyQtGraph依存を入れず、widgetからscheduler内部heapを操作しない。
- 正式な仮想時刻はfloat秒ではなくinteger microsecondsで保持する。変換helperは `simulation/time_utils.py` に集約する。
- event orderingは `(scheduled_time_us, priority, sequence)` の昇順とし、sequenceを登録順の単調増加整数として決定性を守る。
- roadmapを1工程ずつ実装し、明示されたStageの後続componentを先回り実装しない。
- v2.0に記載された規範と、GUI・scheduler・diagnostic scenarioなどsimulation上の実装仮定を区別して文書化する。
- RuntimeへP/V中央比較、勝者・順位決定などのシステム固有ロジックを入れない。
- 規範仕様ファイル自体を変更しない。旧シミュレーターからコードをコピーしない。
- commit、push、PR作成はユーザーから明示指示があるまで行わない。
