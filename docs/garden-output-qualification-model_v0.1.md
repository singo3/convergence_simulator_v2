# Garden出力資格model v0.1

## 境界

`relax_with_light_garden_output_qualification_v0_1` はStage 5BのGUI非依存Garden出力資格層です。生命由来の正式入力は `digital_life_touch_event_v1` のID、role、signal識別子、Bだけです。GardenはP、V、tau、touch offset、N、Nd、W、E、q、k、G、順位、評価値を受け取りません。

Runtimeからはsignal整合性とSによる保持・解放のため、signal index/time、S、session status、closing、finalize timeだけをround metadataとして受け取ります。

## assignment・hold・release

- 初期holderはnullです。
- holderがnullかつS=1の最初の実到着touchでholderを割り当てます。
- S=1中は後続touchでもholderを変更しません。
- holder保持中もred、green、blueの3体すべてから毎signalのtouchを受信・記録します。
- S=1 finalizeで3touch、holder自身のcurrent B、全生命Bが揃わなければ明示的なincomplete errorにします。
- 通常のS=0ではtouchを受けません。
- 240秒closingでは解放前holderと各生命のlast-active Bをfeedbackへ使用し、3体の第2周完了後、priority 90でholderをnullへ解放します。

同一microsecondだけID辞書順のtie-breakが作用します。通常はschedulerによるactual arrival time/orderが唯一のassignment根拠です。

## returned own B

active signalでは、各recipientへその生命が同signalでtouchしたBをそのまま返します。他生命のB、G、P/V/tauは含めません。closingでは各生命自身の直前active touch Bを返します。Bはclip、正規化、再生成せず、往復不一致をerrorにします。

`garden_interoceptive_feedback_event_v1` をrecipientだけへrouteし、各生命が自己IDとholder IDからGを計算します。

## qualified B output

`garden_qualified_b_event_v1` は次Stageとの正式境界です。

- S=1: active、holder ID、そのsignalでholderから実到着したB
- S=0: inactive、holder null、B null

Stage 5BはHue、blink BPM、saturation、brightness、光波形、Iを計算しません。Stage 6はこのeventを入力として光の物理信号を生成します。

model stateは `garden_qualification_state_v1`、touch schemaは `digital_life_touch_event_v1`、feedback schemaは `garden_interoceptive_feedback_event_v1` です。
