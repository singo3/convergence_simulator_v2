# adaptive_random_search_confirmed_v1 実装

## Statusと規範根拠

`adaptive_random_search_confirmed_v1` は規範仕様v2.0第25〜27章の関係記憶探索algorithmである。本文書はそのStage 5C参照実装を記述する。Coreの係数、Hash key、strict閾値、最大1candidate、F/Tのみの連続探索、Bundle 2確認はv2.0を根拠とする。

次は規範が具体値まで定めていないsimulation implementation assumptionである。

| policy | 実装上の選択 |
| --- | --- |
| `positive_f_axis_on_near_zero_direction_norm_v0_1` | direction norm `<=1e-12`で `xi=[1,0,0,0]` |
| `keep_same_trial_for_bundle2_but_require_two_valid_trial_evaluations_v0_1` | Bundle 1 reject後も同じtrialをBundle 2へ保持するが、1回の有効評価だけでは採用しない |
| `relation_update_effective_next_signal_v0_1` | feedback第2周で変更したkは次signalのBから使う |

## 入力と生得profile

探索処理が受け取るは、自己のID、persistent/session state、正式feedbackから得たG、新しい評価のquality/W/bundle metadataである。他生命のstate、Garden内部record、RMSSD/artifact、VirtualUserの好みは入力ではない。

生得profileはIDから一度決まり、sessionやGUI設定で変更しない。

```text
c_i                = Hash01(ID_i,"curiosity")
sigma_min,i        = 0.02 + 0.04*c_i
sigma_max,i        = 0.25 + 0.30*c_i
epsilon_accept,i   = 0.07 - 0.04*c_i
p_explore_min,i    = 0.10 + 0.20*c_i
```

`Hash01`は既存のcanonical implementationを再利用する。Python組込み `hash`、stateful RNG、NumPy RNG、VirtualUser用root seedは使わない。

## anchor状態に応じた探索

```text
r(W) = clip01(2*W-1)
```

`W<=0.5`で `r=0`、`W=1`で `r=1` となる。これを使い、低いanchor状態では広く毎session探索し、良いanchor状態では距離と頻度を下げる。

```text
sigma = sigma_min + (sigma_max-sigma_min)*(1-r(W_anchor_session))
p_explore = p_explore_min + (1-p_explore_min)*(1-r(W_anchor_session))
u_explore = Hash01(ID_i,"C","explore",session_count_used)
```

```text
u_explore < p_explore  -> explore
otherwise              -> hold
```

strict `<` を使い、等値はholdである。`session_count_used` はsession開始時のpersistent valueで固定し、closingの第2周完了まで増加しない。sigmaと方向はcandidate生成時に1回だけ確定し、後のWでcandidateを動かさない。

## 探索方向とreflect01

increment前の `trial_count` を `trial_index_used` とする。

```text
u_F = 2*Hash01(ID_i,"C","direction",trial_index_used,"F")-1
u_T = 2*Hash01(ID_i,"C","direction",trial_index_used,"T")-1
norm = sqrt(u_F^2+u_T^2)
```

`norm>1e-12`では `xi=[u_F/norm,0,u_T/norm,0]` とする。`norm<=1e-12`の具体的fallbackは `xi=[1,0,0,0]` である。v2.0は決定論的fallbackを要求するが方向は固定していないため、この軸とthresholdは `positive_f_axis_on_near_zero_direction_norm_v0_1` の実装仮定である。

candidateのunit intervalへの戻し方はclipではなく反射である。

```text
reflect01(x) = 1 - abs(1 - mod_positive(x,2))
```

Python implementationはfinite numberだけを受け付け、正のmodulo意味を固定する。`reflect01(1.2)=0.8`、`reflect01(-0.2)=0.2`、`reflect01(2.2)=0.2` である。bool、NaN、infinityを拒否する。

## candidate生成

```text
raw = k_anchor + sigma*xi
k_trial = [reflect01(raw_F), k_anchor_A, reflect01(raw_T), k_anchor_D]
```

連続 `[0,1]^4` を保持し、F/Tだけを変更する。A/Dは完全一致し、25セルに量子化しない。candidate生成直後は `k_current=k_trial` とするが、persistent `k_anchor` はまだold anchorである。`trial_count` はこの生成のみで1増加する。hold、G=0、evaluation reject、confirmation、rollbackで追加増加しない。

## 確認型状態遷移

| phase | 入力 | 条件 | 次phase / 提示 |
| --- | --- | --- | --- |
| `anchor_evaluation` | Bundle 0 valid、G=1 | `u_explore < p_explore` | `trial` / candidate |
| `anchor_evaluation` | Bundle 0 valid、G=1 | otherwise | `hold` / anchor |
| `anchor_evaluation` | Bundle 0 reject | 採否不成立 | `hold` / anchor（closingで `completed_bundle0_rejected`） |
| `trial` | Bundle 1 valid | `W_trial_1 > W_anchor+epsilon_accept` | `confirmation` / same trial |
| `trial` | Bundle 1 valid | otherwise | `return_anchor` / old anchor |
| `trial` | Bundle 1 reject | valid trial=0 | `trial_unconfirmed` / same trial |
| `confirmation` | Bundle 2 valid | 2条件ともtrue | `accepted` / trialをanchor化 |
| `confirmation` | Bundle 2 valid | either false | `rejected` / old anchor |
| `confirmation` | Bundle 2 reject | 確認不成立 | `rejected` / old anchor |
| `return_anchor` | Bundle 2 valid | anchor復帰評価 | old anchor維持 |
| `trial_unconfirmed` | Bundle 2 valid/reject | 2 valid trial未達 | old anchorへrollback |

Bundle 1仮採用はstrictに次を要求する。

```text
W_trial_1 > W_anchor_session + epsilon_accept
```

Bundle 2正式採用はstrictに次の両方を要求する。

```text
W_trial_2 > W_anchor_session
mean(W_trial_1,W_trial_2) > W_anchor_session + epsilon_accept
```

等値はすべてfalseである。Bundle 1ではpersistent anchorを更新せず、Bundle 2で同一candidateの再現性を確認する。Wのabsolute baseline比較を追加しないため、anchorに対する十分な改善なら `W_trial_1/2<0.5` でも採用可能である。

## evaluation rejectの参照policy

v2.0は、candidate評価中のreject後に残りbundleで同じcandidateを再評価してよいが、2回の有効candidate評価がなければ正式採用しないと定める。Stage 5Cはこれを次の具体policyに固定する。

```text
keep_same_trial_for_bundle2_but_require_two_valid_trial_evaluations_v0_1
```

Bundle 1 rejectで `W_trial_1` を設定せず、candidateを再生成せず、`trial_unconfirmed`で同じtrialをBundle 2へ保持する。Bundle 2がvalidでも有効評価は1回なので採用せず、old anchorへrollbackする。Bundle 2 rejectでも同様である。rejectでq/k_anchorを更新せず、`trial_count` を追加増加しない。

## G、並列更新、session finalize

G=0生命はcandidate生成も採否も行わず、k/trial_countを維持する。Eは従来どおり毎signalで更新し、qは更新しない。G=1生命も、q、E、kを同じbefore stateから独立計算して第2周の終了で原子的に反映する。

240秒closingはBundle 2の最新評価を処理してから、未解決candidateをold anchorへrollbackする。正常完了時だけ `session_count` を1増加し、`k_trial` をactive stateから破棄する。session中のWは監査できるが、次sessionの比較値としては引き継がない。

## 決定性とreference vectors

全record digestはUTF-8、`sort_keys=true`、`allow_nan=false`、compact separatorのcanonical JSONから計算する。run-to-end、1秒step、1-event step、速度mode、reset、snapshot頻度、GUI、preview、CSV export、persistent-state JSON round-tripで結果を変えない。

独立期待値は [Stage 5C reference vectors](conformance/stage-05c-reference-vectors.json) に固定する。生得profile、`r(W)`、sigma/probability境界、strict比較、Hash方向、fallback、reflect、candidate、counter、全state-machine分岐を生産実装と独立に検証する。

## 非目標

Stage 5Cは1回のsingle sessionだけを実行する。strictなpersistent-state I/OはStage 8の手動引継ぎinterfaceだが、multi-session runner、長期収束判定、sustained convergence、Monte Carlo、探索係数tuning、A/D探索、25セル離散化、moving preference、学習済みpreferenceは実装しない。
