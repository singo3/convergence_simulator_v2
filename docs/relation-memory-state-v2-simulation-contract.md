# relation_memory_state_v2 simulation contract

## 目的とscope

このcontractはStage 5Cの1回のsessionへpersistent relation-memory stateをstrictに注入し、正常closing後のfinal stateをimmutableに取得する境界を定める。`relation_memory_state_v2` は規範仕様v2.0第25.4、25.18、27章の保持/reset区分に対応する。simulationのrecord schemaは `relation_memory_persistent_state_record_v1` である。

Stage 5CのI/OはStage 8で複数sessionを引き継ぐためのseamではあるが、本Stage自体はsingle-session onlyである。stateを書き出してもmulti-sessionの自動連結、baseline再取得、session間比較、収束判定を実行したことにはならない。

## persistent field

| field | type / invariant | initial | conceptual scope |
| --- | --- | --- | --- |
| `digital_life_id` | trimで空でないstring | injected life ID | identity |
| `k_anchor` | finite `[0,1]`の4要素 | `[0.5,0.5,0.5,0.5]` | Digital Life Core |
| `q` | finite `[0,1]` | `0.5` | Digital Life Core |
| `e` | finite `[0,1]` | `0.0` | user_garden |
| `trial_count` | boolでない非負integer | `0` | Digital Life Core |
| `session_count` | boolでない非負integer | `0` | Digital Life Core |
| `profile_version` | exact version | `symbiotic_signal_loop_reference_v1_0` | compatibility |
| `algorithm_version` | exact version | `adaptive_random_search_confirmed_v1` | compatibility |
| `state_schema_version` | exact version | `relation_memory_state_v2` | compatibility |

Eは格納上同じimmutable recordへまとめるが、Digital Life Core所有のk/q/counterと、`user_garden` scopeのEを概念上同一視しない。

## strict validation

入力は次をすべて満たす。silent coercionまたはclipで不正値を修正しない。

- 3生命 `life-red`、`life-green`、`life-blue` がすべてあり、map keyとrecord内IDが完全一致する。
- required fieldの欠落とunknown fieldを拒否する。
- kは4要素のfinite numberで、各軸が0以上1以下である。A/Dも保持値であり、ロード時に再生成しない。
- q/Eはfiniteな0以上1以下である。NaNと正負infinityを拒否する。
- counterは非負integerである。Pythonのboolをintegerとして受け入れない。
- profile/algorithm/state schema versionは必須tupleとexactに一致する。version migration、fallback、旧schema探索は行わない。
- JSON decode後のstateとcanonical encode/decode後のstateは等価である。

## session-local stateとの分離

`RelationMemorySessionState` はsession開始ごとにpersistent stateから新規生成する。record schemaは `relation_memory_session_state_record_v1` である。代表fieldは次のとおり。

```text
session_count_used = persistent.session_count
initial_k_anchor   = persistent.k_anchor
W_anchor_session  = null
anchor_evaluated  = false
k_trial           = null
W_trial_1         = null
W_trial_2         = null
adaptation_phase  = anchor_evaluation
exploration_decision = null
candidate_generated = false
adoption_result   = pending
session_finalized = false
```

その他、`u_explore`、`p_explore`、sigma、direction、`epsilon_accept`、candidate generation trial/effective signal index、rollback reason、`anchor_return_W`、valid trial evaluation countを監査する。これらは出力logとして保存できるが、next persistent inputとして使わない。

特に、baselineの `W=0.5`、`W_anchor_session`、`W_trial_1/2`、`k_trial`、探索判定、phaseは次session開始時に引き継がない。`W_anchor_session` はBundle 0の資格生命の有効評価で初めて設定する。

## session lifecycle

### reset/start

1. 入力3stateをstrict validationする。
2. immutable initial persistent snapshotを保存する。
3. 生命ごとに新しいsession-local stateを作る。
4. `session_count_used` は入力 `session_count` に固定する。
5. `k_current=k_anchor`、`q/e` は入力値で開始する。

resetは注入されたinitial persistent stateへ戻し、前runのsession-local W/candidate/phase/recordを消去する。resetごとに `k_anchor`、q、E、counterをfresh defaultへ勝手に戻さない。

### normal closing

240秒closingのfeedback第2周でBundle 2を処理し、accept/rejectを確定する。unresolved candidateはold anchorへrollbackし、active `k_trial` を破棄する。その後で次をimmutable final stateへ反映する。

```text
k_anchor     = accepted trial or old anchor
q            = final committed q
e            = final committed E
trial_count  = candidate generation回数を反映
session_count = initial session_count + 1
```

non-holderもclosing完了で `session_count` を1増加する。`trial_count` はcandidateを実際に生成したG=1生命だけが増加する。session final state record保存後に既存priority 90でholderをreleaseする。

### abnormal termination

runtime error、同期不整合、closing第2周未完了では `session_count` 増加済みのfinal stateを正式commit済みとして公開・exportしない。部分的なmutable stateをStage 8用stateとして返さない。

## JSON I/O

fresh stateはinitial JSONを指定しない場合に明示的に作る。外部stateは次で注入・保存する。

```bash
python -m symbiotic_sim_v2 \
  --headless-relation-memory-demo \
  --initial-relation-state-json input.json \
  --export-final-relation-state-json output.json
```

state handoff fileのtop-levelは3生命IDをkeyとするexact mappingであり、各valueがpersistent recordである。map keyの欠落/unknown、duplicate JSON key、map keyとrecord IDの不一致を拒否する。project/documentの実行metadataをstate handoff fileの外側へ付加せず、profile/algorithm/state-schema versionは各persistent recordの必須fieldとしてcross-checkする。

書き出しはUTF-8で、NaN/Infinityを許可しない。digest用canonical JSONは `sort_keys=true`、`allow_nan=false`、compact separatorを使う。headless実行summaryはstate handoff fileと別に、project/document/profile/algorithm/state-schema versionとinitial/final stateを表示する。

headless summaryはinitial/final stateとdigestに加え、次を常に明示する。

```text
single_session_only = true
multi_session_not_implemented = true
convergence_evaluated = false
```

## Stage 8へのinterfaceと非目標

Stage 8が利用できる境界は「1 sessionのvalidated initial stateを注入し、正常終了後のvalidated final stateを取得する」ことだけである。Stage 5Cは次を行わない。

- output stateを次sessionへ自動投入する
- baselineを再取得し、複数sessionをschedulerで連結する
- session-local Wを次sessionの候補比較値として引き継ぐ
- adoption回数、k距離、W履歴からconvergenceを宣言する
- sustained convergence、Monte Carlo、係数調整を行う

これらはStage 8で明示的なsession runner、baseline lifecycle、収束判定contractを追加した後に実装する。
