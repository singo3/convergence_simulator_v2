# coarse-refine-confirm search v0.1

`coarse_refine_confirm_search_v0_1`は決定論的な3段階探索である。条件値は小数点以下6桁へcanonical化し、範囲外値をclipせず除外し、重複を除く。

## Preset budget

| preset | Phase 1 | Phase 2上限 | Phase 3上限 | experimental session上限 |
|---|---:|---:|---:|---:|
| smoke | 4条件・2型・1 replicate・4 sessions | なし | なし | 32 |
| quick | 9条件・6型・2 replicates・12 sessions | なし | なし | 1,296 |
| standard | 30条件・6型・3 replicates・24 sessions | 12条件・5 replicates・24 sessions | 3条件・10 replicates・60 sessions | 40,000（最大計画32,400） |
| robust | 30条件・6型・5 replicates・24 sessions | 18条件・10 replicates・60 sessions | 5条件・20 replicates・60 sessions | 130,000（最大計画122,400） |

上限はreference cache runを別表示する。experimental session budgetを超える計画は一部条件へclipせず計画エラーにする。

## Phase 1 → 2

coarse gate通過、Pareto rank 1、robust順、specialist順から最大4 seedを決定論的に重複除去する。各seedにfatigue `-0.015/0/+0.015`、sigma `-0.125/0/+0.125`を適用する。許可範囲外は除外し、standard最大12、robust最大18条件へcanonical順で制限する。

## Phase 2 → 3

final gate、robust ranking、Pareto、specialist重複、flat safety、W ceilingを保持してstandard最大3、robust最大5条件を選ぶ。同じ条件をカテゴリ別に重複実行しない。Phase 3は60 sessionsで長期確認する。

各phaseは独立jobを持つ。condition ID/hashはpaired seedへ入れず、同じreplicate indexは条件横断で同じmaster seed系列を使う。出力順はjob ID順で実行順に依存しない。
