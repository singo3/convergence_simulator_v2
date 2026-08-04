# Paired replicate seed policy v0.1

`paired_replicate_seed_policy_v0_1`は条件比較の偶然差を抑えるpaired replicate用policyである。replicate数は1〜20、既定5である。これは条件間のpaired comparisonであり、大規模一括検証のMonte Carlo機能ではない。

replicate master seedは次のUTF-8 keyのSHA-256先頭32 bitをunsigned big-endian integerとして読む。

```text
key = "{base_master_seed}:stage8a1:replicate:{replicate_index}"
```

各sessionのroot seedは既存Stage 8Aの`deterministic_per_session_physiology_seed_v0_1`を使い、replicate master seed、user type ID、session indexだけから生成する。同じuser typeとreplicate indexの条件は同じ生理seed列を共有する。

fatigue target、sigma multiplier、condition ID/hash、convergence結果をseed keyに入れない。condition間で共有するのはseed列だけであり、persistent state、E/q/k、trial/session counter、runner/component、収束履歴はすべて分離する。条件反復順とCSV exportの有無はseedと結果を変えない。
