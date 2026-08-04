# Stationary user type profiles v2

`stationary_preference_landscape_v0_2` / `stationary_user_type_profile_v2`はStage 8A.1の固定好みsimulation assumptionである。profileはrun開始時に固定し、session index、時刻、bundle、holder、source B、life ID、k/W/q/E、疲労、履歴、収束状態で変化しない。presetの自由編集UIとmoving preferenceは実装しない。

## Axis modeと合成

各peakのHue/BPM軸は`gaussian`または`neutral`を独立に持つ。Gaussian軸はpreferred valueとsigmaが必須で、neutral軸は両値がnull、matchが常に1である。Hue Gaussianは円環距離を使う。

```text
hue_term = gaussian(circular hue distance) or 1
bpm_term = gaussian(BPM distance) or 1
peak_match = peak_weight * hue_term * bpm_term
preference_match = max(all peak matches)
```

hidden profileは仮想ユーザのlight responseとsimulation-only truth/heatmapにだけ使う。Digital Life、Runtime、Garden、fatigue/sigma policyの探索演算へ渡さない。すべてのresponsive presetはmaximum RSA gain 16 ms、maximum mean RRI increase 6 ms、Stage 7参照onset/recoveryを使う。

## Presets

| user type ID | peak | expected structure |
|---|---|---|
| `green_hue_dominant_broad_bpm` | Hue 125±3°、BPM neutral、weight 1 | life dominant / `life-green` |
| `bpm_common_100_hue_neutral` | Hue neutral、BPM 100±12、weight 1 | BPM common |
| `three_life_bpm_equal` | red 5°/55、green 125°/100、blue 250°/145、Hue sigma 3°、BPM sigma 10、weight 1 | 3 life-specific attractors |
| `three_life_bpm_green_dominant` | 上記3峰、red/blue weight 0.75、green 1 | weighted multi-attractor / `life-green` dominant |
| `green_single_peak_narrow` | Hue 129±1.5°、BPM 125±10、weight 1 | single life + single pattern |
| `flat_control` | peakなし、生理gain 0 | no preference control |

これらの数値を期待する実行結果へ寄せるために調整しない。W飽和、未収束、予想外のローテーションが生じた場合も診断結果として保存する。GUIのhidden heatmapは「シミュレーターだけが知る固定反応傾向」であり、探索入力ではない。
