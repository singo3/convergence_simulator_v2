# Stage 8A.1 experiment output schemas

Stage 8A.1のJSON/CSVはsimulationと診断の監査artifactであり、formal eventではない。再開入力となるcondition/state JSONはunknown/missing field、duplicate key、boolの数値化、非有限値、schema/policy version不一致を拒否する。headless result JSONは読み取り専用の監査投影である。digest入力はUTF-8、`sort_keys=true`、`allow_nan=false`、compact separatorsのcanonical JSONである。

## JSON schemas

| schema | 主な責務 |
|---|---|
| `fatigue_sigma_condition_v1` | condition ID、user type v2、fatigue/sigma policyと値、sessions、seed、normative/experiment metadata |
| `fatigue_sigma_replicate_result_v1` | paired replicate seed、completion/error、trajectory/structured/truth/rotation/W-ceilingの集約、result digest |
| `fatigue_sigma_session_outcome_v1` | 1回の240秒sessionのholder、候補、疲労・sigma監査、initial/final persistent state |
| `fatigue_sigma_condition_summary_v1` | completed/failed replicate数、構造収束率、truth率、時刻・outlier/return・rotation・W天井・E・sigmaの個別指標 |
| `fatigue_sigma_grid_summary_v1` | user type、axes、sessions、replicates、planned runs、paired seeds、決定論的条件summary列、grid digests |
| `fatigue_sigma_experiment_manifest_v1` | `formal_spec_adoption=false`、base/experiment profile、modified/unchanged fields、stationary/moving/Monte Carlo flags |
| `fatigue_sigma_multi_session_state_v1` | authoritative condition、次session index、生命別persistent state、完了outcome、paired reference history、error stop state |

single-condition headless JSONはproject/normative/lab/policy/schema versions、user type profile、condition、reference arm metadata、sessions completed、persistent state、fatigue/sigma summary、structured flags/classification、truth、rotation、W ceiling、session outcomes、digestsを持つ。grid JSONはmanifest、user type、axis values、sessions/replicates/planned runs、completed/failed conditions、condition summaries、paired seeds、grid digestsを持つ。

## CSV schemas

| file | rowの単位と必須column family |
|---|---|
| `stage_08a1_conditions.csv` | condition; ID、user type、fatigue target/recovery、sigma multiplier、sessions/seed、policy/schema |
| `stage_08a1_fatigue_trajectory.csv` | condition/replicate/session/life; start/baseline/active/pre-policy/post-policy E、selected count、full-recovery |
| `stage_08a1_sigma_trajectory.csv` | candidate; W anchor、reference min/max/sigma、multiplier/effective sigma、delta F/T/Hue/BPM、acceptance |
| `stage_08a1_session_pattern_trajectory.csv` | committed/trial presentation; session/life/Hue/BPM、E、explore/adoption、trial result |
| `stage_08a1_structured_convergence_history.csv` | evaluated session; life/BPM/multi flags/scores、summary、outlier/return、rotation、truth、W ceiling |
| `stage_08a1_replicate_results.csv` | condition/replicate; completion、classification/rates/counts、final state/digest references |
| `stage_08a1_condition_summaries.csv` | condition; replicate completion/failure、個別のtrade-off aggregate、単一best scoreなし |
| `stage_08a1_grid_heatmap.csv` | fatigue × sigma cell; metric name/value、replicate/completion/failure、E/sigma summary |

`stage_08a1_experiment_manifest.json`はCSV directoryにも保存する。CSV exportの有無はsimulation、state、digestを変えない。reference armとexperimental full-recovery conditionを同一cell/rowとして混同せず、arm/policy metadataで分離する。
