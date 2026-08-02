# RRI window membership policy v0.1

## Status

- policy name: `measurement_end_time`
- policy version: v0.1
- implementation: Stage 4 Garden入力層
- classification: **simulation implementation assumption**

このpolicyは規範仕様v2.0の補足規範ではない。Stage 4の決定性と検証可能性のために採用した、交換可能なsimulation実装方針である。

## v2.0に明示されていない点

1件のRRIは、前heartbeatから現在heartbeatまでの時間差である。その区間がdiscard/evaluationまたは2つのbundleの境界をまたぐ場合、RRI全体を次のどの時刻でwindowへ所属させるかについて、v2.0には明示がない。

- interval start time
- interval midpoint
- measurement end time
- 境界で分割または重み付け

したがってStage 4は、この未規定点を規範値として解釈せず、明示的なversion付きpolicyとして分離する。

## 採用する規則

`RriMeasurementEvent.scheduled_time_us` をmeasurement end timeとして使用し、その一点をphaseの半開区間へ当てはめる。H10 contract上、この値はpayloadの `current_heartbeat_time_us` と一致する。

```text
membership_time_us = RriMeasurementEvent.scheduled_time_us
                   = current_heartbeat_time_us
```

RRIのstart timeやmidpointは所属判定に使わず、1件を分割しない。たとえば59.5秒のheartbeatから60.4秒のheartbeatまでの900 ms RRIは、終了時刻60.4秒によりBundle 0 discardへ全体を所属させる。

## measurement end timeを採用した理由

- `RriMeasurementEvent` が実際にGardenへ到着し、測定値として確定する時刻と一致する。
- Stage 3のformal event contractだけで判定でき、仮想ユーザー内部stateやH10内部recordを参照しない。
- integer microsecondsの単一点分類になるため、scheduler ordering、headless、GUI、CSVで同じ結果を再現できる。
- 境界をまたぐRRIの分割や按分という、v2.0にない生理学的仮定を追加しない。

この理由はsimulation実装としての選択理由であり、他の所属方式より生理学的に正しいと主張するものではない。

## 半開区間

すべてのphaseとevaluation windowを `[start_us, end_us)` として扱う。開始時刻は含み、終了時刻は次のphaseへ所属する。

| measurement end time | membership | evaluationへ含む |
| ---: | --- | --- |
| 29.999秒 | `baseline_discard` | いいえ |
| 30秒 | `baseline_evaluation` | はい |
| 59.999秒 | `baseline_evaluation` | はい |
| 60秒 | `bundle_0_discard` | いいえ |
| 90秒 | `bundle_0_evaluation` | はい |
| 120秒 | `bundle_1_discard` | いいえ |
| 150秒 | `bundle_1_evaluation` | はい |
| 180秒 | `bundle_2_discard` | いいえ |
| 210秒 | `bundle_2_evaluation` | はい |
| 239.999秒 | `bundle_2_evaluation` | はい |
| 240秒 | `outside` | いいえ |

評価windowは `[30, 60)`、`[90, 120)`、`[150, 180)`、`[210, 240)` だけである。discard/outsideに所属したRRIもartifact分類とvalid median history更新の対象にはなるが、evaluation件数とRMSSDには含めない。

## 同時刻eventとの関係

boundaryではphase eventとevaluation finalizeがRRI eventより先に処理される。例として60秒では、phase変更、baseline評価確定、evaluation result、1秒signal、heartbeat、RRIの順となる。60秒ちょうどのRRIはbaseline確定後に到着し、純粋な時刻分類でもBundle 0 discardとなる。eventの登録順やGUI描画タイミングで所属を変えない。

## 記録と単一実装

全RRI診断recordへ `membership_policy = measurement_end_time` を記録する。phase表示、S、evaluation buffer、CSV、境界testは同じpure time classifierを使用し、consumerごとに境界式を複製しない。

## 将来のpolicy変更

将来、実機入力や研究要件によりstart time、midpoint、overlap方式が必要になった場合は、既存policyの意味を変更しない。新しいpolicy名・version、config、文書、境界fixture、digest baselineを追加し、単一のmembership classifierを差し替える。

新policyは少なくとも次を明示する必要がある。

- canonical membership timeまたは分割式
- 半開区間の扱い
- 境界をまたぐRRIの例
- discard/outsideとartifact historyの関係
- event orderingへの影響
- model/schema/digest互換性

Stage 4 v0.1の結果を再現する場合は、必ず `measurement_end_time` を指定する。
