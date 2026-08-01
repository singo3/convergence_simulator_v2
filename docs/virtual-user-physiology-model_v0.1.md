# Virtual user physiology model v0.1

## 位置づけ

model version: `baseline_virtual_user_physiology_v0_1`

これは外部刺激なしheartbeat列を生成するStage 2のsimulation assumptionである。v2.0規範ではなく、実ユーザーの生理を証明せず、医療判断に使用できない。parameterは実データで未校正であり、今後の実測・光応答model設計で変更し得る。

## 時間因果

heartbeat `n` がvirtual time `t_n` に発生した時点で、現在までのAR(1) stateと `(root_seed, stream, n)` だけから次intervalを計算する。未来のinput、RRI diagnostic、RMSSD、N、W、光刺激を参照しない。

```text
t_seconds = t_n_us / 1,000,000
mean_rri_ms = 60,000 / mean_heart_rate_bpm
```

## 成分

呼吸性変動:

```text
f_resp_hz = respiratory_rate_bpm / 60
respiratory_ms = respiratory_amplitude_ms
                 × sin(2π × f_resp_hz × t_seconds)
```

ゆっくりした周期変動:

```text
slow_ms = slow_wave_amplitude_ms
          × sin(2π × slow_wave_frequency_hz × t_seconds + π/3)
```

連続性を持つ自然変動:

```text
innovation_n = Normal(root_seed, "correlated_innovation", n)
z_n = persistence × z_(n-1)
      + sqrt(1 - persistence²) × innovation_n
correlated_ms = correlated_variability_sd_ms × z_n
```

拍ごとの微小変動:

```text
jitter_ms = beat_jitter_sd_ms
            × Normal(root_seed, "beat_jitter", n)
```

合成・clamp:

```text
unclamped_rri_ms = mean_rri_ms + respiratory_ms + slow_ms
                   + correlated_ms + jitter_ms
final_rri_ms = min(max_rri_ms, max(min_rri_ms, unclamped_rri_ms))
rri_us = floor(final_rri_ms × 1000 + 0.5)
next_heartbeat_time_us = t_n_us + rri_us
```

next timeがsimulation endを超える場合は予約しない。endと一致する場合は予約する。心拍時刻はstrictly increasingである。

## Parameters

| Parameter | Default | Unit / range | 意味 |
|---|---:|---|---|
| `duration_seconds` | 180 | s, 10–3600 | scenario duration |
| `mean_heart_rate_bpm` | 70.0 | bpm, 30–200 | 中心的な心拍数 |
| `respiratory_rate_bpm` | 12.0 | breaths/min, 3–40 | 呼吸周期 |
| `respiratory_amplitude_ms` | 35.0 | ms, 0–200 | 呼吸性RRI変動幅 |
| `slow_wave_frequency_hz` | 0.10 | Hz, 0.01–0.20 | slow wave frequency |
| `slow_wave_amplitude_ms` | 10.0 | ms, 0–100 | slow wave amplitude |
| `correlated_variability_sd_ms` | 8.0 | ms, 0–100 | AR(1)成分のscale |
| `correlated_variability_persistence` | 0.85 | `[0,1)` | 前状態の持続性 |
| `beat_jitter_sd_ms` | 2.0 | ms, 0–50 | independent beat jitter scale |
| `min_rri_ms` | 300.0 | ms, ≥250 | clamp lower bound |
| `max_rri_ms` | 2000.0 | ms, >min and ≤3000 | clamp upper bound |
| `root_seed` | 20260802 | integer, 0–2³¹−1 | internal random reproducibility |

全floatはfinite、boolはnumeric valueとして拒否し、不正値をsilent clippingしない。生理的RRIのclampとconfig validationは別責務である。

## Random generation

named key `root_seed:stream_name:sample_index` のUTF-8 bytesをSHA-256でdigest化する。独立した64-bit chunkをopen uniformへ変換しBox-Mullerを適用する。Python `hash()`、module-global `random`、NumPy global RNGを使わない。同じkeyはprocess/platform/呼出順に依存せず同じ値を返す。

呼吸性成分とslow waveはseedで変化しない。correlated/jitter amplitudeが両方0なら、seedを変更してもheartbeat系列は同じである。

## 診断値

HeartbeatRecordに保存するcomponentとRRIは内部真値の開発診断であり、正式なuser outputではない。rolling/full RMSSDは生成modelへfeedbackせず、次heartbeatの決定に使わない。

## 既知の制約と今後の校正

- respiration phaseはscenario開始で固定され、個人差を校正していない。
- slow waveは単一sinusoid、correlated変動は単一AR(1)である。
- 心拍変動の非線形性、姿勢、活動、睡眠、加齢、疾患、measurement artifactを表現しない。
- parameter間の実生理相関や長時間driftを校正していない。
- clampは安全なsimulation boundsで、生理学的artifact判定ではない。

将来の光応答modelでは、外部刺激を明示的inputとして別versionへ拡張し得る。mean RRI、component amplitude/phase、state transitionのどこへ因果的影響を入れるかは実データと別Stageの仕様で決める。Stage 2 modelへ黙って追加せず、model versionを更新し、baseline無刺激controlと比較校正する必要がある。
