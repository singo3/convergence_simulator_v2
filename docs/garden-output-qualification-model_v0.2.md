# Garden output qualification model v0.2

## Identity and scope

Model versionは`relax_with_light_garden_output_qualification_v0_2`である。GUI非依存のGarden output coreはactual touch arrivalからholderを管理し、qualified Bと生命別feedbackを発行する。光刺激へのI mappingはこのmodelの責務ではない。

## Input boundary: ID/B only

生命由来の正式入力は`digital_life_touch_event_v2`であり、`digital_life_id`、signal識別metadata、4軸Bだけを受け取る。Garden coreはrole、role別F範囲、P、V、tau、E、q、k、Gをimport・保存・検査しない。

expected IDはRuntime/session rosterから注入される。configは3つの非空・一意なIDをlexical orderへ正規化する。標準fixtureのIDはcoreの個体性ではなく、arbitraryな3 IDでも同じ資格処理を行う。

## Qualification state

- assignment: `first_touch_when_empty`
- hold: `while_s_is_1`
- release: `after_closing_second_round_when_s_is_0`
- equal-time tie-break: `lexicographic_digital_life_id_on_equal_arrival_us`

holderはRuntimeがtauを比較して選ぶのではなく、Gardenが受け取ったactual touchの順序で決まる。holder保持中も全3生命が各active signalでtouchする。

## Holder-touch emission

発行policyは`qualified_b_on_holder_touch_v0_1`である。最初のactive roundでは最初のtouchでholderを割り当て、同じtouchのBを同じarrival timeへ発行する。後続active roundではnon-holder touchを無視して出力を待ち、holder touchのcurrent Bをそのarrival timeへ発行する。active outputは1 signal 1件である。

`garden_qualified_b_event_v2`のpriorityは65で、payloadの`effective_time_us`はevent scheduled timeと常に一致する。

## Finalize responsibility

active round finalizeはsignal末尾のpriority 70で動く。qualified Bの生成契機ではない。責務は次のとおりである。

- expected rosterの3touchが揃ったことを検証する
- holder touchがあることを検証する
- active outputが既に1件だけ発行されたことを検証する
- output ID/B/effective timeがholder touchと一致することを検証する
- formal diagnostics recordを確定する
- recipient自身のBを3件のfeedbackへ入れる
- feedbackと各生命の第2周を同期する

不完全・未発行・重複・不一致はerrorであり、finalize時のfallback outputは禁止する。

## Inactive and closing behavior

S=0ではtouchしない。no-touch finalize priority 31から、signal timeへinactive qualified B priority 65と3 feedback priority 80を発行する。inactive outputのholder/Bはnullである。

240秒closingではinactive commandを発行する一方、feedbackはrelease前holderと各生命のlast active Bを維持する。全生命がBundle 2評価を含む第2周を終えた後にだけholderをreleaseする。

## Explicit exclusions

このmodelはBをHue、blink BPM、saturation、brightness、光波形Iへ変換しない。Stage 6 consumerはformal qualified B v2だけを入力とし、Gardenの内部holder stateやdiagnostic recordを参照しない。
