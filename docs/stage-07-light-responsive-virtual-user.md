# Stage 7: 固定反応特性を持つ光応答仮想ユーザー

## 目的

Stage 7は、Stage 6の正式な光出力を仮想ユーザーの将来の心拍間隔へ戻す、最初の閉ループ実装である。仮想ユーザーは提示されたHueと点滅BPMに対する固定特性を持つ。光はRMSSD、N、Nd、Wを直接変更せず、心拍生成の平均RRIと呼吸性RRI変動幅だけへ作用する。

このモデルは実データで校正されていないsimulation assumptionであり、医学的予測モデルではない。

## 正式境界

- 正式入力: `LightStimulusStateEvent` (`light_stimulus_state_event_v1`) と自分が出力した `HeartbeatEvent`
- 正式出力: 既存schemaの `HeartbeatEvent` だけ
- H10入力: `HeartbeatEvent.scheduled_time_us` だけ
- Garden入力: H10が正式出力した `RriMeasurementEvent` だけ

responsive heartbeat record、light receipt、physical audit segment、response dynamics epoch、100ms sampleは開発診断であり、H10、Garden、Digital Lifeへ配送しない。

## システム境界

```text
LightStimulusStateEvent
  -> 物理光projection
  -> 固定Hue/BPM適合度
  -> 一次遅れR(t)
  -> 平均RRI・呼吸性変動幅
  -> HeartbeatEvent
  -> H10の時刻差RRI
  -> GardenのRMSSD/N
  -> Digital Life / Garden出力 / Light
```

## 物理光projectionとprovenance除外

`PhysicalLightStimulus`は実効時刻、active、render Hue、Saturation、Value中心/振幅/最小/最大、BPM、waveform、開始phaseだけを保持する。holder ID、source B、signal index、Digital Life状態、touch・資格metadataは保持しない。

formal event由来のprovenanceは監査用receiptへ別保存できるが、preference関数とphysiology関数へ渡さない。全receiptの `provenance_used_by_physiology` は `false` である。

## 固定嗜好

run開始時の `LightResponseConfig` をrun中ずっと使用する。Hueは円環距離、Hue/BPMはそれぞれGaussian、総合適合度は積で求める。inactive時の適合度とtargetは0である。好みと異なる光を負の反応にはしない。

## response targetと一次遅れ

activeかつenabledならtargetはpreference match、その他は0である。targetが一定の区間では次式を解析的に評価する。

```text
R(t) = target + (R_start - target) * exp(-(t - start) / tau)
```

targetが上がるときは8秒のonset、下がるときは12秒のrecoveryを使用する。入力時刻でresponseをjumpさせない。Stage 7.1では同一targetの再通知や対称なHue変更でresponse dynamics epochを分割せず、物理parameterが変わる場合だけ別の監査segmentを開始する。GUI timerや高頻度response eventは使わない。

## Stage 7.1の分離監査

`physical_light_parameter_signature_v0_1` はactive、render Hue、Saturation、Valueの中心/振幅/下限/上限、BPM、waveformをexact equalityで比較する。effective time、開始phase、holder、source B、signal index、event IDは含めない。

`light_response_segment_v2` は実際の物理parameter変更、または予期外のtarget-only変更で分割する監査recordである。`light_response_dynamics_epoch_v1` はresponse target、境界response、time constantだけを保持し、targetがexactに変わる場合だけ分割する。物理変更とtarget変更はreceiptとGUIで別のflag/markerとして監査する。詳細は [Stage 7.1監査分離](stage-07-1-physical-audit-response-epochs.md) を参照する。

## 生理連成

heartbeat開始時刻のresponse `R_t` から次だけを変更する。

```text
effective_mean_rri_ms = base_mean_rri_ms + 15 * R_t
effective_respiratory_amplitude_ms = base_amplitude_ms + 30 * R_t
```

slow wave、AR(1)連続変動、beat jitter、clamp、microsecond丸め、root seed、named random stream、beat index keyはStage 2と同じである。responseが0、またはcontrol presetのgainが0ならStage 2計算結果とbit-for-bitで一致する。

## 心拍因果性

policyは `sample_light_response_at_heartbeat_start_v0_1` である。時刻 `t_n` のheartbeatで `R(t_n)` をsampleし、区間 `[t_n, t_(n+1))` を決める。light stateを受けても予約済みheartbeatをcancel・rescheduleしない。同時刻ではpriority 40のheartbeatがpriority 67のlight stateより先で、旧responseを使う。

## control

`light_insensitive_control` はreceiptを記録する一方、平均RRI gainと呼吸性gainがともに0である。同じ `VirtualUserConfig`、root seed、random keyでStage 6のheartbeat、H10、Garden、Digital Life、Lightのformal streamを再現する。

## 閉ループfactory

`create_light_responsive_closed_loop_simulation()` は既存Stage 4/5B.1/6 assemblyの内部注入seamを使用する。既存public factoryは従来componentを注入して同じ挙動を維持し、Stage 7だけがresponsive userと `LightStimulusStateEvent` handlerを追加する。

## GUI / headless / CSV

通常GUIは8 tabで、先頭に光応答特性・response・生理作用・Garden正式RMSSD/Nを表示する。設定変更は停止/reset状態に限定する。実光previewは既定OFFのままである。

headless:

```bash
.venv/bin/python -m symbiotic_sim_v2 \
  --headless-light-responsive-user-demo \
  --light-response-preset aligned_green_center
```

診断CSVはreceipt、physical audit segment、response dynamics epoch、responsive heartbeat、100ms fixed-grid sampleの5種類である。CSV exportはsimulation stateやdigestを変更しない。

## 検証

独立reference vectors、pure physical signature、4通りの分割matrix、response連続性、strict event projection、因果fixture、control比較、240秒integration、execution mode、digest、CSV、architecture、GUIを検証する。Stage 1〜6のdigestとStage 4〜6 CSV、Stage 7のformal event/heartbeat/physiology結果は回帰固定する。

## Stage 5C interface

Stage 7は現在のqualified B/light系列を受けるだけで、candidate、`k_trial`、adoption、convergence、関係記憶探索を持たない。次工程のStage 5Cは既存qualified B境界の上流を拡張し、光応答ユーザーの正式入出力境界を変更しない。
