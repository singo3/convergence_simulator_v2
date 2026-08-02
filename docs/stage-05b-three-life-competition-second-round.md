# Stage 05B — 3生命・資格競争・第2周

## 目的とCore対応

Stage 5BはStage 5Aの第1周を `life-red`、`life-green`、`life-blue` の3体へ独立に適用し、tauによる自律touch、Garden資格処理、ID照合によるG、E/q第2周までを接続します。規範仕様はv2.0、profileは `symbiotic_signal_loop_reference_v1_0`、algorithmは `adaptive_random_search_confirmed_v1`、state schemaは `relation_memory_state_v2` のままです。

```text
GardenInputSignalEvent (same N/S)
  -> three independent first rounds (Nd/W/P/V/B/tau)
  -> Runtime maps each tau to its own future touch event
  -> Garden receives actual ID/B arrivals
  -> holder ID + each recipient's own B
  -> each life calculates G and updates E/q
  -> updated E/q is used from the next signal
```

## 3生命の独立性

各生命は別のcomponent/stateを持ち、E、q、k、N、Nd、W、P、V、B、tau、Gを共有しません。同じGarden formal eventを受けますが、他生命のsnapshot、P/V/B/tau/E/qを参照しません。第1周はStage 5Aのcomponentとpure functionsを再利用し、Stage 5A factory、CLI、CSV、digest、GUIを残します。

## Runtimeとtouch

Runtime modelは `three_digital_life_runtime_v0_1` です。`DigitalLifeTouchIntent` はRuntime内部だけのimmutable valueで、Gardenへ渡しません。S=1かつV/tau利用可能時のみ正式touchを予約します。

RuntimeはP/Vを中央比較せず、winnerや順位を作らず、tauを個別touch時刻へ写像するだけです。microsecond policyと同時刻tie-breakは [tau-touch-delivery-policy_v0.1.md](tau-touch-delivery-policy_v0.1.md) に分離しています。

正式 `digital_life_touch` payloadはID、role、signal index/time、B、schemaだけです。P、V、tau、offset、N/Nd/W、E/q/k/Gを含めません。

## Garden qualificationとfeedback

Garden modelは `relax_with_light_garden_output_qualification_v0_1` です。最初の実到着でholderを一度だけ割り当て、S=1の3bundleを通じて保持します。全生命はholder保持中も180 active signalすべてでtouchします。詳細は [garden-output-qualification-model_v0.1.md](garden-output-qualification-model_v0.1.md) を参照してください。

Gardenは各生命へholder IDとその生命自身のBだけを返します。feedbackにGは含めず、recipient componentだけへrouteします。

## G、E、q、k

各生命は `G_i = 1` iff 自己IDとholder IDが一致、そうでなければ0として毎signal再計算します。

Eは毎signalの第2周で次式により更新します。

```text
E_next = clip01(E + eta_E*S*G*(1-E) - rho_E*(1-SG)*E)
eta_E  = 1 - 0.85^(1/180)
rho_E  = 1 - 0.90^(1/180)
```

qは新しい有効Bundle評価かつG=1の場合だけ次式を適用します。baseline、rejected、重複revision、G=0では更新しません。

```text
q_next = clip01(q + G * (0.20*W_plus(W)*(1-q) - 0.20*W_minus(W)*q))
```

E/q更新後に同signalのV/B/tauを再計算しません。更新値は次signalから利用します。kは全生命 `(0.5,0.5,0.5,0.5)` のままで、recordへ `deferred_to_stage_5c` を残します。

## 240秒closingとevent ordering

closingではBundle 2 evaluation(priority 25)、Garden signal(30)、no-touch finalize(31)、inactive qualified B(75)、解放前holder付きfeedback(80)、3生命第2周、holder release(90)、simulation complete(100)の順です。holder生命がBundle 2のWでqを更新してから解放します。closing second-round recordにはG=1が残り、最終snapshotのholder/Gはnull/0です。

通常active signalはsignal(30)、各touch(60)、finalize(70)、qualified B(75)、feedback(80)の順で、すべて次signalより前に完了します。前round未完了で次signalを受けた場合はsynchronization errorです。

## 出力、GUI、headless

通常GUIは6 tab（3生命、Garden出力、Garden入力、仮想ユーザー、Polar H10、時間診断）です。3生命カード、tau/touch、G/holder、E/q、P/V、B、touch/second-round表を表示し、診断領域は縦スクロールできます。GUIはimmutable snapshot/recordだけを読み、計算を再実装しません。

```bash
python -m symbiotic_sim_v2 --headless-three-life-competition-demo
```

標準240秒fixtureはtouch 540、feedback 723、qualified B 241（active 180 / inactive 61）、assignment/release各1です。結果としてgreenが最初に到着しますが、holderはhard-codeせずactual arrivalから決まります。

CSVはtouch、qualification、qualified B、second roundの4ファイルです。各digestはrun-to-end、step、速度、reset、GUI/headless、CSV有無に依存しません。独立期待値は [stage-05b-reference-vectors.json](conformance/stage-05b-reference-vectors.json) で確認します。

## 後続interface

Stage 5Cは本Stageのclosing評価帰属と第2周recordを境界に、k_trial、W_anchor_session、候補確認・採用など3bundle関係記憶探索を追加します。Stage 6は `GardenQualifiedBEvent` を唯一のGarden出力入力としてHue/BPM/I/光波形を実装します。本Stageには探索状態も光物理写像もありません。
