# Stage 5A: 1体のデジタル生命・第1周

## 目的

Stage 5Aは、Stage 4のGarden入力層が正式に配送するNとSを1体のデジタル生命が知覚し、1秒ごとに第1周の `Nd`、`W`、`P`、`V`、`B`、`tau` を計算する段階である。GUI非依存のcoreを、Stage 1のinteger-microseconds時計とStage 2〜4の既存経路に接続する。

現在のproject versionは `0.5.0`、Digital Life model versionは `single_digital_life_first_round_v0_1` である。

## 規範、fixture、開発診断の区別

### v2.0規範から実装した範囲

- GardenのN/Sを正式境界から受ける。
- Nをsession baseline相対のNdへ変換する。
- Ndを情動系がWへ評価する。MVPでは値は `W = Nd` だが、別field・別function・別概念とする。
- 生得値とSからP、N/q/EからV、kと生命固有写像 `Phi_B` からB、P/Vから論理到達時間 `tau` を計算する。
- 有効評価revisionごとにNd/Wを1回だけ更新する。

規範ソースのfingerprintとversion tupleは [規範スコープ](normative-scope.md) を参照する。本文書は規範仕様を置き換えない。

### Simulation fixtureと実装上の選択

- 標準scenarioは240秒、1体、標準roleはgreenである。
- `life-red`、`life-green`、`life-blue` とrole別F範囲は、再現可能なsimulation fixtureである。実在生命のIDや個体定義ではない。
- GUIの5 tab、role selector、CSV、canonical JSON digest、event priority、handler wiringは実装・検証手段である。

### 開発用診断

`DigitalLifeFirstRoundRecord`、`DigitalLifeEvaluationUpdateRecord`、snapshot、digest、GUI table/chart、CSVは観測用である。これらはGardenまたは後続componentへ配送する正式system signalではない。

## Input boundary

Digital Life coreが受ける正式eventは次の2種類だけである。

| event | source | priority | 用途 |
| --- | --- | ---: | --- |
| `GardenEvaluationFinalizedEvent` | `garden_input` | 25 | 新評価のID、quality、revisionなどのmetadata |
| `GardenInputSignalEvent` | `garden_input` | 30 | 正式なN/S状態と評価revision |

NとSの知覚値は `GardenInputSignalEvent` からのみ取得する。`GardenEvaluationFinalizedEvent` は新評価の由来とreject診断を紐付けるmetadataであり、そのhandler内でNd/Wを更新しない。

Digital Lifeは下記を参照しない。

- `GardenInputComponent` の内部stateやGardenのrecord class
- VirtualUser/H10 component、heartbeat record、RRI measurement record
- raw RRI、RMSSD、artifact判定の内部値
- GUI、CSV、scheduler heap

formal eventに含まれるwindow件数、RMSSD、artifact率などの診断fieldも、Digital Lifeの計算には使用しない。boundary parserは参照を許可されたfieldだけをimmutable DTOへ射影する。

## 責務と非責務

Stage 5Aの責務は、単一生命のconfig・生得profile・保持stateと、1秒signalごとの第1周計算、evaluation revision管理、immutableな観測recordである。

Stage 5Aは次を実装しない。

- Garden出力層、Gの受信、第2周
- 3生命の資格競争、勝者・順位・holder決定
- touch eventの配送、ID/BのGarden送信、実到達時刻の予約
- E/q/kのlive更新
- `W_anchor_session`、`k_trial`、探索方向、adoption
- 光出力、光刺激、仮想ユーザーの刺激応答

`G_status` は `not_connected`、`second_round_connected` はfalse、`touch_dispatched` と `touch_dispatched_count` は0/falseのままである。G未接続を `G=0` とみなさない。

## 第1周の計算

### NからNd、NdからW

新しい有効Nのrevisionでのみ次を計算する。

```text
Nd = clip01(0.5 + (N_current - N_baseline_session) / (2 * delta_n))
delta_n = 0.10

W = EmotionalEvaluation(Nd) = Nd  # Stage 5A MVP mapping
```

Ndは直前Nではなくsession baseline相対である。Digital LifeはNをRMSSDから再計算しない。Wは値がNdと同じでも情動系の評価結果として別に保持する。

### Pと `Phi_P`

```text
p_i = 0.35 + 0.30 * Hash01(digital_life_id, "handle-distance")
P   = 1 - S * (1 - p_i)
```

S=0でP=1、S=1でP=`p_i` である。`p_i` は生得固定値、Pは各signalで再計算する活動値である。RuntimeはP/Vの中央比較を行わない。

### E、q、V

Stage 5Aのlive scenarioではGが未接続のため、全signalで `E=0.0`、`q=0.5` を保持する。

```text
V = clip01(((N_current + q) / 2) * (1 - E))
```

baseline確定前はNがnullのためVもnullである。確定後は各signalでVを再計算する。E/q更新のpure functionは後続Stageの参照用に単体実装しているが、Stage 5A componentは呼び出さない。

### k、`Phi_B`、B

```text
k_anchor  = [0.5, 0.5, 0.5, 0.5]
k_current = k_anchor
B         = B_min + (B_max - B_min) * k_current  # element-wise
```

Bの成分順は `[F, A, T, D]` である。A/Dは0.5固定、T範囲は0〜1、F範囲はrole presetで異なる。Stage 5Aでkは変化せず、BをWで直接変調しない。

### tau

```text
birth_phase = 0.000001 * Hash01(digital_life_id, "birth-phase")
tau_base    = P / (P + V + epsilon_tau)
tau         = clip01(tau_base + birth_phase)
epsilon_tau = 0.000001
```

S=1かつVが利用可能な場合だけtauを計算する。S=0またはV=nullではtau=nullである。tauは0〜1の無次元の論理到達時間であり、秒やmicrosecondsではない。`touch_enabled` は計算上のeligibilityにすぎず、touch配送を意味しない。

## Revision処理

1. `GardenEvaluationFinalizedEvent` で、有効評価はrevisionとIDによるpending metadataとして保存する。
2. rejected評価はrevisionを進めず、`applied=false` / `evaluation_rejected` の診断recordだけを追加する。
3. 直後の `GardenInputSignalEvent` でrevision増加を検出し、evaluation ID、revision、Nの対応を検証してNd/Wを適用する。
4. 同じrevisionの後続1秒signalではNd/Wを再評価せず、evaluation update recordも追加しない。
5. duplicate/rollback signal、duplicate evaluation ID、schema不整合は黙って無視せず例外にする。

evaluationは閉じたwindow、同時刻signalは次phaseを表すため、両者の `bundle_index` は一致しない場合がある。対応付けにbundle indexだけを使わない。

## Baseline初期化と240秒closing

60秒のbaseline評価後、revision 1のformal signalでbaseline/current Nを受け、`Nd=W=0.5` として初期化する。このW=0.5は `W_anchor_session` ではない。Bundle関係記憶のanchor評価はStage 5C以降である。

| 時刻 | evaluation | signal revision | 主な処理 |
| ---: | --- | ---: | --- |
| 60秒 | baseline | 1 | baseline初期化、Nd/W=0.5 |
| 120秒 | Bundle 0 | 2 | baseline相対Nd/W更新 |
| 180秒 | Bundle 1 | 3 | baseline相対Nd/W更新 |
| 240秒 | Bundle 2 | 4 | closingでもNd/W更新、その後P=1、tau=null |

240秒のformal evaluationはpriority 25、closing signalはpriority 30である。したがってBundle 2 revision 4を先に適用し、その後S=0の活動値を記録する。

## Resetと決定性

Stage 5A factoryはStage 4 factoryを再利用し、formal evaluation/signal handlerを各1回だけ登録する。scenario resetはVirtualUser、H10、Garden入力層、Digital Lifeをまとめてresetし、handlerを再登録しない。Digital Lifeは新規eventをscheduleしないため、Stage 4の1059件のevent streamとfull event digestは不変である。

`run_until_end`、1秒step、1-event step、速度、batch、snapshot/chart頻度、CSV export、config JSON round-trip、resetの違いでfirst-round/evaluation-update digestは変化しない。

## GUI

GUIは次の5 tabを持ち、標準表示は「デジタル生命」tabである。

1. デジタル生命
2. Garden入力層
3. 仮想ユーザー
4. Polar H10
5. 時間・event診断

デジタル生命tabは、N/baseline/Nd/W、P/V/tau、E/q、k/Bの4 chart、現在値、生得profile、1秒signal table、evaluation update tableを表示する。tau=nullは0に変換せず欠損として描画する。role presetはred/green/blueから選べるが、変更はscenarioがstoppedのときだけ可能である。

```bash
.venv/bin/python -m symbiotic_sim_v2
.venv/bin/python -m symbiotic_sim_v2 --life-role red
```

## HeadlessとCSV

標準greenの240秒run:

```bash
.venv/bin/python -m symbiotic_sim_v2 --headless-single-life-demo
```

role指定:

```bash
.venv/bin/python -m symbiotic_sim_v2 \
  --headless-single-life-demo \
  --life-role blue
```

Digital Lifeの開発用CSVも同時に書き出す例:

```bash
.venv/bin/python -m symbiotic_sim_v2 \
  --headless-single-life-demo \
  --export-single-life-csv artifacts/csv/stage-05a
```

出力は次の2ファイルである。

- `single_digital_life_first_round_diagnostics.csv`
- `single_digital_life_evaluation_updates.csv`

CSVは正式eventではなく、exportの有無はstateやdigestを変えない。

## Conformance reference

標準green fixtureの評価境界値を次に固定する。値は実装本体から期待値を生成せず、独立reference dataと照合する。

| 時刻 | revision | S | N | Nd/W | P | V | tau |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 60秒 | 1 | 1 | 0.1641195720593294 | 0.5 | 0.4083874184184465 | 0.3320597860296647 | 0.5515408729267095 |
| 120秒 | 2 | 1 | 0.17783395762886722 | 0.5685719278476892 | 0.4083874184184465 | 0.3389169788144336 | 0.546479994436101 |
| 180秒 | 3 | 1 | 0.16342965068696474 | 0.4965503931381767 | 0.4083874184184465 | 0.3317148253434824 | 0.5517979450383652 |
| 240秒 | 4 | 0 | 0.17184501115930495 | 0.5386271954998778 | 1.0 | 0.3359225055796525 | null |

標準green runの固定digestは次である。

- first round: `661c2c74942d6b217a635fb4f2cb142bee8cff2e0e842cd21ccdd511682028b8`
- evaluation update: `f7bf973cc20a2af77ccd7b38fa0e2407801353890a23cc1b3e30e9d7feeba4c3`
- full event: `34b18fa72f51cd5cccf9ef7107000d0ef2fdeeb4f62c3e8d7f0ae3de1cd19b72`

digestのcanonical projection keyはversioned record field名に合わせる。first-roundは `signal_index`、`signal_time_us`、`digital_life_id`、`role`、`phase`、`bundle_index`、`s`、`n_current`、`n_baseline_session`、`valid_evaluation_revision`、`is_new_valid_evaluation`、`nd`、`w`、`p`、`e`、`q`、`v`、`k_current`、aggregate `b`、`tau`、`g_status`、`touch_dispatched` を使う。evaluation-updateは `evaluation_id`、`evaluation_kind`、`bundle_index`、`event_time_us`、`quality`、`is_valid`、`n_revision`、`n`、`n_baseline_session`、`previous_nd`、`new_nd`、`previous_w`、`new_w`、`applied`、`skip_reason` を使う。JSONはkey sort、compact separator、NaN禁止でSHA-256化する。

Hash01のnumerator、UTF-8、SHA-256、binary64、role別 `p_i` / birth phase、全pure function vectorは [Stage 5A reference vectors](conformance/stage-05a-reference-vectors.json) をsource of truthとする。

## Tests

```bash
.venv/bin/python -m compileall -q src tests
QT_QPA_PLATFORM=offscreen .venv/bin/pytest -q
.venv/bin/ruff check .
.venv/bin/python -m symbiotic_sim_v2 --headless-single-life-demo
QT_QPA_PLATFORM=offscreen \
  .venv/bin/python -m symbiotic_sim_v2 --smoke-test --auto-close-ms 3500
```

config、Hash01、pure function、role別写像、boundary parser、revision/reject、baseline/closing、reset、execution mode、digest、CSV、GUI、architecture分離を検証する。独立参照値は [Stage 5A reference vectors](conformance/stage-05a-reference-vectors.json) に固定し、本体実装を呼ぶだけの自己参照testとしない。

## Stage 5B interface

Stage 5A時点でDigital Lifeからの正式外部出力eventはない。first-round recordやCSVを将来のGarden入力に転用してはならない。

次工程Stage 5Bは、現在のformal Garden event boundaryと第1周計算を維持した上で、3生命、Garden資格競争、Gと第2周の正式interfaceを新しいStageとして設計する。これらはStage 5Aで実装済みではない。関係記憶の3 bundle探索はさらに後続のStage 5Cである。
