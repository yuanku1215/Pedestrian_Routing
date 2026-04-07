# hard_theta_formal_02

這是目前最完整保留的 kSPwLO 正式 benchmark bundle。

## Problem Setting

- `k = 2`
- `theta = 0.5`
- hard overlap 採用 `budget` 模式
- 使用 processed graph package 與 10 個動態時段
- 3 組 OD 距離：`400m / 800m / 1200m`

## Main Result

根據 [`summary/overall_statistics.json`](summary/overall_statistics.json)：

- `total_runs = 30`
- `feasible_runs = 30`
- `ties = 30`
- `wins = 0`
- `losses = 0`
- `mean_max_similarity = 0.0607`

## Interpretation

這批結果表示：

- SQA 已能在 alternative routing 題目上穩定輸出兩條合法路徑
- 兩條路之間的 overlap 也受到控制
- 但在目前 formulation 與設定下，SQA 的結果仍與 baseline heuristic 一致

## Folder Notes

- `summary/*`: 總覽與統計
- `runs/*`: 每一個 scenario 的完整輸出
- `logs/*`: 單 run 執行 log

如果你只想快速看結論，先從 `summary` 開始。
