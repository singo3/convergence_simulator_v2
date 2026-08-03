# Rolling majority convergence definition v0.1

versionは`rolling_majority_pattern_convergence_v0_1`、config schemaは`rolling_pattern_convergence_config_v1`、record schemaは`rolling_convergence_record_v1`である。この定義はsimulation diagnostic assumptionであり、v2.0の探索係数ではない。

## 入力単位

一次判定の入力は有効な`SessionOutcome`である。Bundleは票ではない。各票はholder IDと、closing後に正式保存されたholderのanchorから得たHue/BPMを持つ。invalid outcomeはhistoryへ残すが、`use_valid_sessions_only=true`のrolling windowへ入れない。

## 距離

異なるholder IDは無条件に別patternとする。同じholderだけについて、Hue円環距離`d_hue=min(|h1-h2|, 360-|h1-h2|)`を使い、次を計算する。

```text
d_pattern = sqrt(
  (d_hue / hue_tolerance_degree)^2
  + ((bpm_1-bpm_2) / blink_bpm_tolerance)^2
)
```

`d_pattern <= 1`を近傍とする。境界はinclusiveである。

## cluster

直近M件の有効outcomeから全subsetを決定論的に評価する。候補はsize K以上、holder ID同一、全pairの距離が1以下でなければならない。MはGUIで12以下に制限し、探索をboundedにする。

選択順は、size最大、最大pairwise距離最小、平均pairwise距離最小、新しいsessionを多く含む、holder ID lexical、member index tuple lexicalである。medoidは全memberへの距離和が最小のsessionとし、同値なら新しいsessionを選ぶ。Hueは円環平均、BPMはmedianも併記する。

## state

既定はM=4、K=3、Hue tolerance=2°、BPM tolerance=20である。M件未満なら`insufficient_valid_sessions`。cluster成立後は`converged_monitoring`、最新有効sessionだけがoutlierなら`converged_monitoring_latest_outlier`。過去に収束していてrolling windowからclusterが消えた場合だけ`convergence_lost`、それ以前は`searching`とする。

`first_convergence_session_index`を保持し、loss、reconvergence、dominant switch、post-convergence exploration/adoption、outlierと1/2session以内のreturnを監査する。いずれの値もDigital Life、Runtime、Garden、session停止条件へ入力しない。
