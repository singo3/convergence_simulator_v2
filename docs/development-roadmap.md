# Development roadmap

- 1. 時間シミュレーター: 完了
- 2. 外部刺激なし仮想ユーザー: 完了
- 3. 仮想Polar H10: 完了
- 4. Garden入力層とセッションシグナル: 完了
- 5A. 1体のデジタル生命・第1周: 完了
- 5B. 3生命・資格競争・第2周: 完了
- 5B.1. Garden出力境界・qualified B実効時刻補正: 完了
- 6. 光点滅シミュレーター: 完了
- 7. 固定反応特性の光応答仮想ユーザー: 完了
- 7.1. 物理光監査segment・response dynamics epoch分離: 完了
- 5C. 3Bundle関係記憶探索・確認型候補採否: 完了
- 8A. 固定好み・複数セッション収束ラボ: 完了
- 8A.1. 固定好み・疲労／探索幅・収束条件ラボ: 完了
- 8A.2. 自動条件探索・堅牢候補抽出: 完了
- 8A.3. 自律・プラセボRMSSD適応検証: 完了
- ローカルstandard validationの実行と結果レビュー: 次工程
- 必要に応じたローカルrobust validation: standardレビュー後
- 8B. 変化する好み・追従性: 上記実験レビュー後
- 8C. 追加係数比較: 後続
- 9. Webアプリ: 後続

Stage 7はStage 6の `LightStimulusStateEvent` だけをformal inputとし、固定Hue/BPM嗜好、一次遅れresponse、平均RRI・呼吸性RRI変動幅を介して既存 `HeartbeatEvent` へ閉ループ接続した。Stage 7.1は物理parameterの監査segmentとtarget変更のresponse dynamics epochを分離したが、生理式とformal event streamは変更しない。GUI preview、segment、20ms waveform sample、holder/source Bを生理入力にしない。

Stage 5Cはこの閉ループに、各Digital Life内部の `adaptive_random_search_confirmed_v1` を追加した。Bundle 0でanchorを評価し、決定論的にhold/exploreを選び、最大1つのF/T candidateをBundle 1/2で仮評価・確認する。Stage 8Aはこのstrict state seamを使い、固定user landscapeの下で正常終了stateを次sessionへ渡し、毎session baselineと`W_anchor_session`を取り直す。一次収束は完了sessionを独立票とする観測専用の3-of-4 rolling診断であり、探索を停止しない。

Stage 8A.1は参照armを不変のまま保存し、experimental armで選出時1session疲労target、非選出生命の正常closing後全回復、参照sigmaへの共通倍率を比較する。生命優勢、cross-life BPM共通帯、生命別多峰、機械的rotation、W天井を観測専用に診断する。`formal_spec_adoption=false`であり、moving preferenceはStage 8B、sigma以外の追加係数比較はStage 8Cへ残す。

Stage 8A.2はStage 8A.1 runnerを変更・コピーせず再利用し、ローカルCPUでcoarse→refine→confirmを決定論的に実行する。paired seed、reference cache、atomic checkpoint/resume、不確実性表示、Pareto/trade-off、robust/specialist候補、自己完結HTML reportを保存するが、Coreへ結果を返さず正式Profileを採用しない。次は利用者がpush後にstandard探索をローカル実行し、結果をレビューし、必要な場合だけrobust探索を行う。その後にStage 8Bへ進む。

Stage 8A.3はStage 8A.1の固定仮想ユーザーと閉ループrunner、Stage 8A.2のローカルcheckpoint/report基盤を再利用する。autonomous、別participantのautonomous光系列を再生するyoked placebo、RMSSD非依存randomをpaired比較し、同時点反応と過去ΔRMSSD→将来選択のlagged adaptationを分ける。historyは過去sessionだけ、集計はparticipant単位、跨sessionの主尺度はΔRMSSDとする。次は利用者によるローカルstandard validationと結果レビュー、必要時だけrobust validationである。その後までStage 8B moving preferenceへ進まない。
