# Human-MVP condition comparison v0.1

## 目的

このpolicyは実人間による将来の自律確認MVPで使う条件の候補を、simulation結果から透明に比較する。不透明な単一総合scoreを作らず、`v2_reference`をbaseline candidateとする。条件の正式仕様への自動採用ではない。

## 条件ごとの表示値

- nonflat 8 typesの平均autonomous−random late ΔRMSSDがすべてstrict `> 0`か
- worst user-type effectとtype-specific failures
- positive nonflat participants / 80とpositive rate
- nonflat mean、95% participant bootstrap interval、participant間標準偏差
- flat-control arm difference
- selection enrichment、lagged coupling
- W-ceiling blocked rate、invalid rate、holder-switch rate

## alternativeのpreference gate

alternativeを`preferred_for_human_mvp`候補にするには次をすべて満たす。

1. nonflat 8 typesすべてのlate ΔRMSSD arm差がstrict positive
2. flat-controlのabsolute arm差が0.25 ms以下
3. positive participant countが`v2_reference`以上
4. nonflat mean effectが`v2_reference`以上
5. worst-type effectが`v2_reference`から0.25 msを超えて悪化しない
6. participant間標準偏差が`v2_reference`から0.25 msを超えて悪化しない
7. selection enrichmentまたはlagged couplingの少なくとも一方が`v2_reference`から0.05を超えて悪化しない

全gateを満たすalternativeがなければ`v2_reference_remains_preferred`とする。複数が通過した場合は透明な辞書順タイブレークを伴うnonflat meanとpositive countでreport候補を1つ表示するが、正式採用はしない。

## 判定語彙

- `preferred_for_human_mvp`
- `viable_tradeoff`
- `type_specific_risk`
- `no_advantage_over_reference`
- `insufficient_or_ambiguous`

smokeのようにnonflat 8 typesが揃わないrunはalternativeを`insufficient_or_ambiguous`とし、referenceを上書きしない。

## 安全境界

recommendation JSONは`opaque_composite_score_used=false`、`automatic_formal_adoption=false`、`formal_spec_adoption=false`、`simulation_only=true`を明示する。出力は人間のレビュー用であり、Core、係数、探索、session停止を自動変更しない。実人間での有効性や医療効果を主張しない。
