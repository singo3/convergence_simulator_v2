# relation_update_effective_next_signal_v0.1

## Status

`relation_update_effective_next_signal_v0_1` は、feedback第2周で更新した `k_current` / `k_anchor` をどのsignalのBから有効にするかを固定する **simulation implementation assumption** である。v2.0は第1周、touch、feedback、第2周の論理的順序と `B=Phi_B(k)` を規定するが、integer-microsecond schedulerでの具体的な適用seamは定めない。

本policyはv2.0の候補採否式を変更せず、同一signal内の因果の循環を防ぐ。

## 不変条件

1. signal `n` の第1周は、開始時の `k_current_before` から `B_presented=Phi_B(k_current_before)` を一度だけ計算する。
2. touch payloadとGardenから返るrecipient自身のBは、その第1周Bと一致する。
3. feedback第2周でq、E、関係記憶遷移を同じbefore stateから独立計算する。
4. そのsignalで `k_current_after` が変わっても、B、P、V、tau、touch、qualified Bを再計算・再配送しない。
5. `k_current_after` は次のsignal `n+1` の第1周で初めて `Phi_B`へ入る。
6. 新しい有効evaluation revisionがないsignalで、保持中のWを再使用してq/k遷移を重複実行しない。

## atomic second-round transition

```text
before = (q_before, E_before, k_current_before, k_anchor_before, session_state_before)

E_after = update_E(E_before, S, G)
q_after = update_q(q_before, W, G, evaluation_metadata)
relation_after = update_relation_memory(
    k_current_before,
    k_anchor_before,
    session_state_before,
    W,
    G,
    evaluation_metadata,
)

commit_atomically(E_after, q_after, relation_after)
```

`C_i` はq_after/E_afterを入力にしない。q更新とE更新はk_afterを使わない。「並列的に確定」とはthread並列を意味せず、同じimmutable before stateから独立に導出した後、1つのsecond-round commitとして反映する意味である。

## 3Bundleの時間因果

| signal boundary | first round / 提示B | second round | 更新後kの初回使用 |
| --- | --- | --- | --- |
| baseline revision 1 | persistent `k_anchor` | W=0.5をanchor評価にしない | 変更なし |
| 120秒 | old anchor B | Bundle 0 Wでhold/explore、必要なら `k_current=trial` | 121秒signal |
| 180秒 | Bundle 1で維持したtrial/anchor B | Bundle 1でconfirmation/returnを確定 | 181秒signal |
| 240秒 | Bundle 2で維持したtrial/anchor B | accept/rollback、session finalize | 次sessionがある場合の最初signal |

120秒の第2周でtrialを生成しても、120秒signalのqualified Bやlight commandはold anchor由来のままである、121秒のholding signalがtrial由来Bを最初に出す。180秒でreturnを決めた場合も、Bundle 2用anchor Bは181秒から有効になる。

240秒はclosing signalである。Bundle 2の新しいevaluation revisionをrelease前holderの第2周へ適用し、accept/rollbackとpersistent state finalizeを完了した後にholderを解放する。Stage 5Cは後続sessionを自動開始しないため、240秒の更新済みkから実際の次signal Bを生成しない。後続sessionで使うはStage 8の責務である。

## event orderingと境界

正式時刻はinteger microsecondsを使い、schedulerの `(scheduled_time_us, priority, sequence)` による既存順序を維持する。本policyはGardenのRRI evaluation window、touch arrival、holder assignment、qualified B effective time、LightStimulusStateEventの時刻を変更しない。同一signalで更新後kから新しいtouchを追加scheduleしない。

## 監査と検証

adaptive signal recordは次を分離保存する。

- `k_anchor_before`、`k_current_before`、`k_presented`、`b_presented`
- `relation_phase_before/after`
- `k_current_after`、`k_anchor_after`
- `candidate_effective_next_signal`
- q/E before/after

testは120/121、180/181、240秒の境界、same-signal Bの不変、returned Bとfirst-round Bの一致、q/E/kのbefore-state独立性、evaluation revisionの一回限りの適用、step/velocity/reset/GUI/CSVによる不変を確認する。

## 非目標

本policyはBを早く出すためのfeedbackまたは第2周を前倒しせず、Gardenのround finalize境界を変えない。複数session runner、次sessionのbaseline lifecycle、収束判定、moving preferenceはStage 5Cの対象外である。
