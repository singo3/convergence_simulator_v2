# Scaled reference sigma policy v0.1

`scaled_reference_sigma_v0_1`はStage 8A.1 experimental armの探索幅だけを変更するsimulation assumptionである。v2.0参照Profileが定める生命固有curiosityとW依存式を先にそのまま評価する。

```text
sigma_min_reference,i = 0.02 + 0.04*c_i
sigma_max_reference,i = 0.25 + 0.30*c_i

sigma_reference,i(W) = sigma_min_reference,i
  + (sigma_max_reference,i - sigma_min_reference,i)
  * (1 - r(W_anchor_session))

sigma_effective = sigma_multiplier * sigma_reference
```

`sigma_multiplier`の範囲は0.25〜1.50である。1.0は参照sigmaとbinary64値が一致する。curiosityによる生命間差とWによる広狭を保持し、candidate生成時に1回だけeffective sigmaを確定する。同session内でcandidateを動かさない。

`p_explore`、`p_explore_min`、`epsilon_accept`、方向Hash key、`trial_count`、反射関数`reflect01`、A/D固定を変更しない。condition ID、condition hash、fatigue target、sigma multiplierをexplore/direction/random seedに混入しない。探索対象はF/Tだけである。

監査は`reference sigma_min/max`、`reference sigma at W`、multiplier、effective sigma、candidate delta F/T、実際のdelta Hue/BPM、accepted/rejectedを記録する。実装結果から倍率を自動tuningせず、formal Profileへ採用しない。
