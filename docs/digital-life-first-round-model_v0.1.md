# Digital Life first-round model v0.1

## 文書の位置付け

本書はStage 5Aで1体のデジタル生命に実装した第1周モデルの再現仕様である。唯一の規範仕様v2.0の代替ではなく、v2.0から実装した式とStage 5Aのsimulation fixture・診断方法を分けて固定する。

| 項目 | version |
| --- | --- |
| Project | `0.5.0` |
| Model | `single_digital_life_first_round_v0_1` |
| Config schema | `digital_life_config_v1` |
| First-round record schema | `digital_life_first_round_record_v1` |
| Evaluation-update record schema | `digital_life_evaluation_update_record_v1` |
| Normative document | `v2.0` |
| Profile | `symbiotic_signal_loop_reference_v1_0` |
| Algorithm | `adaptive_random_search_confirmed_v1` |
| State schema | `relation_memory_state_v2` |

## 値の分類

| 分類 | 値 | Stage 5Aでの意味 |
| --- | --- | --- |
| Intrinsic / 生得 | ID、role、`p_i`、birth phase、F/A/T/D範囲 | configから決定し、run中は不変 |
| Holding / 保持 | baseline/current N、Nd、W、E、q、`k_anchor`、`k_current`、revision | 有効評価または後続Stageの状態更新対象 |
| Activity / 活動 | P、V、B、tau、touch eligibility | formal signalごとに現在の保持値から再計算 |
| Diagnostic / 診断 | first-round/evaluation record、snapshot、digest、CSV | 再現性と観測のための内部記録 |

componentがsnapshot表示のためP/V/B/tauの直近値をstateに保存していても、モデル上は各signalで計算するactivityである。first-round/evaluation recordはGardenへの正式信号ではない。

## 単位と範囲

| 値 | 単位/範囲 | 備考 |
| --- | --- | --- |
| `scheduled_time_us`, `signal_time_us` | integer microseconds | 正式な仮想時刻 |
| CSVの `signal_time_seconds` | seconds | microsecondsからの観測用導出値 |
| S、G | 0または1 | GはStage 5Aで未接続 |
| N、Nd、W、P、E、q、V | 無次元、0〜1 | N/Vはbaseline確定前null |
| k、B | `[F,A,T,D]` の無次元ベクトル | Fは1周を1とする比率 |
| `delta_n` | Nと同じ無次元スケール | 0.10 |
| `epsilon_tau` | 無次元 | 0.000001 |
| birth phase、tau | 無次元、0〜1 | 秒やmicrosecondsではない |
| revision、signal index | boolでない非負整数 | revision 0は有効N未確定 |

## Configとsimulation fixture

`DigitalLifeConfig` はimmutableで、unknown/missing field、version不一致、bool-as-number、非有限値、range不整合を拒否する。標準fixtureは次の3体である。

| role | fixture ID | F min | F max | initial B F |
| --- | --- | ---: | ---: | ---: |
| red | `life-red` | 0/360 | 10/360 | 5/360 |
| green | `life-green` | 120/360 | 130/360 | 125/360 |
| blue | `life-blue` | 245/360 | 255/360 | 250/360 |

共通値は `A=0.5`、`T_min=0`、`T_max=1`、`D=0.5`、`initial_k_anchor=[0.5,0.5,0.5,0.5]` である。fixture IDは規範が定める実在IDではなく、決定的検証用のsimulation fixtureである。

## Hash01と生得値

`Hash01(key_1, key_2, ...)` は次の手順で作る。

1. 各引数を文字列化する。
2. colon `:` で連結し、UTF-8にencodeする。
3. SHA-256 digestの先頭6 byteをunsigned big-endian 48-bit整数として読む。
4. `2^48 - 1` で割る。

Python組み込み `hash()` は使用しない。

```text
p_i         = 0.35 + 0.30 * Hash01(digital_life_id, "handle-distance")
birth_phase = 0.000001 * Hash01(digital_life_id, "birth-phase")
```

| role | `p_i` | birth phase |
| --- | ---: | ---: |
| red | 0.5941575588300965 | 1.2028150370395393e-07 |
| green | 0.4083874184184465 | 4.1353168607465e-08 |
| blue | 0.5356119367762356 | 7.72104874991789e-07 |

完全なSHA-256中間値、binary64表現、その他のpure function vectorは [Stage 5A reference vectors](conformance/stage-05a-reference-vectors.json) に固定する。

## 初期状態

```text
E                              = 0.0
q                              = 0.5
k_anchor                       = [0.5, 0.5, 0.5, 0.5]
k_current                      = k_anchor
N_baseline_session             = null
N_current                      = null
Nd                             = 0.5
W                              = 0.5
P                              = 1.0
V                              = null
B                              = Phi_B(k_anchor)
tau                            = null
G_status                       = not_connected
last_processed_signal_index    = null
last_evaluation_revision       = 0
baseline_initialized           = false
new_valid_evaluation_count     = 0
second_round_connected         = false
touch_dispatched_count         = 0
```

`holder`、qualification ID、`k_trial`、`W_anchor_session`、exploration、adoptionのstateは持たない。初期W=0.5やbaseline完了時のW=0.5を `W_anchor_session` として保存しない。

## 基本pure function

### `clip01`

```text
clip01(x) = min(1, max(0, x))
```

非有限値とboolを拒否する。個別configの不正値を黙ってclipするためのvalidationではない。

### NからNd

```text
Nd = clip01(0.5 + (N_current - N_baseline_session) / (2 * delta_n))
delta_n = 0.10
```

Ndはsession baseline相対値であり、直前Nとの差ではない。Nがbaselineから+0.10ならNd=1、+0.05なら0.75、同値なら0.5、-0.05なら0.25、-0.10なら0となる。

### NdからW

```text
W = EmotionalEvaluation(Nd)
EmotionalEvaluation(x) = x  # MVP v0.1
```

Ndはbaseline相対の状態値、Wは情動系による評価値である。v0.1の数値写像は同じだが、schema、record、digest、functionで別に扱う。

## Pと `Phi_P`

```text
P = Phi_P(S, p_i)
  = 1 - S * (1 - p_i)
```

S=0でP=1、S=1でP=`p_i` である。`p_i` は生得値、Pは各signalのactivityである。PとVをRuntimeで中央比較し、勝者や順位を決めない。

## Eとq

Stage 5Aのlive値は常に次である。

```text
E = 0.0
q = 0.5
```

Gと第2周が未接続のため、live componentはE/q更新functionを呼び出さない。後続Stage用のpure reference functionだけを次の式で実装し、単体testする。

```text
eta_E = 1 - 0.85^(1/180)
rho_E = 1 - 0.90^(1/180)

E_next = clip01(
  E + eta_E * S * G * (1-E) - rho_E * (1-S*G) * E
)

W_plus(W)  = clip01((W - 0.55) / 0.45)
W_minus(W) = clip01((0.45 - W) / 0.45)

q_next = clip01(
  q + G * (0.20 * W_plus(W) * (1-q) - 0.20 * W_minus(W) * q)
)
```

Gは0/1のみ、q更新は新しい有効評価でのみ呼ぶという上位契約が必要である。その契約はStage 5Aのlive scenarioでは未接続である。

## V

```text
V = clip01(((N_current + q) / 2) * (1 - E))
```

Nがnullの間はVもnullである。N確定後は各signalで計算する。Stage 5AではE/qが変化しないため、Nが同じならVも同じになる。

## k、B、`Phi_B`

Stage 5Aでは `k_current = k_anchor = [0.5,0.5,0.5,0.5]` を保持する。

```text
B = Phi_B(k)
  = B_min + (B_max - B_min) * k  # element-wise [F,A,T,D]
```

role別にF範囲だけが異なり、A/Dは0.5固定、Tは0〜1である。Bは現在kから決まる活動値であり、MVP v0.1でWを直接加算・乗算しない。

## tau

```text
tau_base = P / (P + V + epsilon_tau)
tau      = clip01(tau_base + birth_phase)
```

S=1かつVが利用可能な場合だけ計算する。S=0でPは1になるが、tauはnullである。tauは論理的な到達位置/時間指標であり、schedulerのtimestampへ変換しない。Stage 5Aは `tau` に基づくtouch eventをscheduleしない。

## Evaluation revision契約

- baselineの最初の有効signalでrevision 1を適用し、baseline/current Nと `Nd=W=0.5` を初期化する。
- baseline後はrevisionが最後の適用値より増えた場合だけ、baseline相対Nd/Wを更新する。
- rejected evaluationはrevision、N、Nd、W、新評価件数を更新しない。
- 有効evaluation metadataをpendingとして保持し、次のformal signalのID/revision/Nと一致したときに適用する。
- revision増分は常に1とは限らない。rejectedを挟んでも、Gardenが正式に通知したrevisionを受理する。
- 240秒のrevision 4はclosing S=0でもNd/Wへ適用し、その後P=1、tau=nullを計算する。

## Stage 5Aの制約と既知の限界

- 1体、1回の240秒session、第1周だけを扱う。
- 標準統合scenarioはStage 2の仮想ユーザー、理想H10、Stage 4 Garden入力層というsimulation fixtureに依存する。
- Gは値0ではなく未接続。第2周、E/q/kのlive更新、Garden出力層は未実装である。
- 3生命、資格競争、holder、touch order、勝者/順位、実際のtouch配送は未実装である。
- `W_anchor_session`、bundle関係記憶探索、`k_trial`、adoptionはStage 5C以降である。
- tauは0〜1の論理値であり、実時間の遅延、送信時刻、物理到達時刻を表さない。
- first-round/evaluation record、CSV、GUI、digestは診断であり、Stage 5Bの正式入出力契約ではない。

次工程Stage 5Bで3生命とGarden資格競争・第2周を新しい契約として追加する。Stage 5Aの実装を「Gやtouchが0の簡易実装」と解釈しない。
