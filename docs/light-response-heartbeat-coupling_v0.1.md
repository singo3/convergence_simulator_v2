# Light Response–Heartbeat Coupling v0.1

## Scope

`light_response_rsa_mean_rri_coupling_v0_1` は、光responseを次の心拍間隔生成へ接続するStage 7 simulation assumptionである。RMSSD、N、Nd、Wを直接計算・変更しない。

## Mean RRI coupling

```text
base_mean_rri_ms = 60000 / mean_heart_rate_bpm
effective_mean_rri_ms = base_mean_rri_ms
                      + maximum_mean_rri_increase_ms * R_t
```

標準最大増加は15msである。

## Respiratory sinus arrhythmia coupling

```text
effective_amplitude_ms = base_respiratory_amplitude_ms
                       + maximum_respiratory_amplitude_gain_ms * R_t

respiratory_component_ms = effective_amplitude_ms
                         * sin(2*pi*respiratory_frequency_hz*time_seconds)
```

標準baseは35ms、最大gainは30msである。

## Unchanged physiology

slow wave式、AR(1) persistence/innovation、beat jitter、RRI clamp、half-up microsecond丸めはStage 2と同じである。root seed、`correlated_innovation` / `beat_jitter` stream名、beat-index keyを変えず、新しい乱数streamやlight-config hashを加えない。response 0ではStage 2の既存計算をそのまま使用し、bit-for-bit一致を守る。

## Heartbeat-start sampling

`sample_light_response_at_heartbeat_start_v0_1` はheartbeat `t_n` で `R(t_n)` をsampleし、次の `[t_n, t_(n+1))` を決める。受信済みlight stateは将来のintervalだけに影響し、すでにschedulerへ入った次heartbeatをrescheduleしない。

heartbeatとlight stateが同時刻ならpriority 40のheartbeatがpriority 67より先で、旧responseをsampleする。新light stateは次のheartbeat開始以降に使われる。

## Formal downstream path

responsive userは従来payloadの `HeartbeatEvent` だけを出す。H10が隣接時刻差からraw RRIを測り、GardenがRRI windowからRMSSDとNを計算する。responsive diagnosticsはこのformal pathへ入らない。

## Calibration limitation

係数と時定数は実データ未校正で、医学的意味や効果量を主張しない。将来の校正modelは別version・別設定として管理する。
