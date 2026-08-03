# Stage 7.1: 物理光監査segmentとresponse dynamics epoch

## 目的

Stage 7.1はStage 7の診断・監査境界だけを補正する。実際に知覚される物理光parameterの変更を監査segmentに正確に残しつつ、response targetが同じなら一次遅れresponseをresetしない。これは実測校正済みの生理modelではなく、version管理されたsimulation assumptionである。

## 責務の分離

`LightResponseSegment` (`light_response_segment_v2`) は物理光刺激の半開区間を監査する。現在の物理signatureが変わる場合に分割し、物理signatureが同じでtargetだけが変わる予期外caseでも分割理由を記録する。

`LightResponseDynamicsEpochRecord` (`light_response_dynamics_epoch_v1`) は一次遅れを決めるtarget、response境界値、time constantだけを監査する。Hue、BPM、holder、source B、Digital Life状態は保持しない。targetのexact equalityが崩れた場合にのみ分割する。

## 物理signature

`physical_light_parameter_signature_v0_1` は次の値を順序付きtupleとしてexact比較する。

- active
- render Hue
- Saturation
- Value center / amplitude / min / max
- blink BPM
- waveform

effective time、phase at start、holder、source B、source signal index、receipt/event IDは除外する。これらの値やcontinuous phaseの進行だけでsegmentを分割しない。隠れたtoleranceは使用しない。

## 分割matrix

| physical changed | target changed | audit segment | dynamics epoch |
|---|---|---|---|
| false | false | 継続 | 継続 |
| true | false | 分割 | 継続 |
| true | true | 分割 | 分割 |
| false | true | 理由付きで分割 | 分割 |

いずれの分割でも境界時刻の `response_before` を次状態の開始値とし、同時刻の `response_after` とexactに一致させる。物理変更だけの場合は現在のepoch indexを新しいaudit segmentへ紐づけ、time constantを再設定しない。

simulation endと同時刻に開始するterminal stateは正の長さの区間を持たないため、audit/epoch recordとして保存しない。そのclosing receiptは変更flagと理由を保持し、存在しないrecordを指さないようaudit/epoch linkを `None` とする。その他のreceipt linkは完了時に公開recordのindexへ解決できることを検証する。

## 変更しない境界

formal inputは `LightStimulusStateEvent` v1、formal outputは既存 `HeartbeatEvent` のままである。preference式、一次遅れ式、心拍開始時sample、予約済みheartbeatをrescheduleしない因果policyは変えない。Heartbeat/RRI、RMSSD/N、Nd/W/E/q/k、qualified B、LightCommand、LightStimulusStateEventの値・時刻・配送順を変えない。Stage 5Cのcandidate、trial、adoption、k探索は未実装である。
