# Stationary user type landscapes v0.1

`stationary_preference_landscape_v0_1`はStage 8A専用の固定simulation assumptionである。peak modelは`stationary_gaussian_peak_v0_1`、multi-peak結合は`maximum_weighted_peak_response_v0_1`、profile schemaは`stationary_user_type_profile_v1`である。

## peak式

```text
hue_distance = min(abs(hue-preferred_hue), 360-abs(hue-preferred_hue))

peak_match = peak_weight
  * exp(-0.5 * (hue_distance/hue_sigma)^2)
  * exp(-0.5 * ((blink_bpm-preferred_bpm)/blink_sigma)^2)

preference_match = max(peak_match_1, peak_match_2, ...)
```

inactiveまたはpeakなしは0で、結果範囲は0..1である。session index、時刻、bundle、holder、source B、Digital Life ID、k/W/q/E、履歴、収束状態を入力しない。

## 固定preset

| ID | peak | RSA gain / mean RRI gain |
|---|---|---:|
| `green_broad_strong` | 129°, 125 BPM, sigma 5°/35, weight 1 | 30 / 15 ms |
| `green_narrow_moderate` | 129°, 125 BPM, sigma 1.5°/12, weight 1 | 16 / 6 ms |
| `red_broad_moderate` | 7°, 70 BPM, sigma 4°/35, weight 1 | 18 / 7 ms |
| `blue_broad_weak` | 252°, 120 BPM, sigma 5°/40, weight 1 | 8 / 3 ms |
| `red_blue_dual_peak` | red-local 6°/70/2.5°/25/0.75、blue-global 252°/120/2.5°/20/1 | 18 / 7 ms |
| `flat_control` | peakなし | 0 / 0 ms |

既定は`green_narrow_moderate`である。これらは特定runを収束させるために調整する値ではなく、比較用の固定fixtureである。Stage 7/7.1の既存single-Gaussian public factoryとdigestは変更せず、Stage 8Aだけがprivate preference evaluator seamを使う。

heatmapとtruth alignmentはシミュレーターだけが知る診断である。peak、weight、preference matchを探索計算へ渡さない。
