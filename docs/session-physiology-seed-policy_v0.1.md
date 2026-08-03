# Session physiology seed policy v0.1

Stage 8Aはpreference landscapeを固定したまま、生理noiseだけをsessionごとに決定論的に変えられる。

## deterministic policy

既定`deterministic_per_session_physiology_seed_v0_1`は次のUTF-8 keyをSHA-256へ入力する。

```text
"{master_seed}:stage8a:{stationary_user_type_id}:{session_index}"
```

digest先頭4 bytesをbig-endian unsigned 32-bit integerとして読み、その値をsessionの`VirtualUserConfig.root_seed`へそのまま設定する。既定master seedは`20260802`である。modulo、signed変換、maskによる値変更を行わない。

このpolicyはDigital Life ID、curiosity、Hash01 key、trial/session counter、preference peakを変更しない。Stage 2と同じnamed random stream、stream名、beat-index key、clamp、microsecond丸めを使う。

比較用`repeat_same_physiology_seed_v0_1`は全sessionでmaster seedそのものをroot seedとして使う。どちらのpolicyもmoving preferenceではなく、同一config・stateからの再実行、GUI/headless、pause/batch、CSV有無で同じseed列と結果を再現する。
