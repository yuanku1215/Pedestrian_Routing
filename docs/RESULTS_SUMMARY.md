# Results Summary

這份文件是目前 repo 中最重要的研究摘要。

## 1. Single-route Path Routing

資料位置：

- [`results/single_route/formal_modes_suite_01`](../results/single_route/formal_modes_suite_01)

結論：

- `pure_sqa`: `150/150 no_route`
- `baseline_warm_start`: `150/150 tie`
- `baseline_plus_block_move`: `150/150 tie`

解讀：

- 單一路徑問題中，純 SQA 無法從零自行拼出合法路徑
- 一旦有 baseline seed，SQA 可以保住解，但仍沒有超越 baseline

## 2. kSPwLO Hard-theta Benchmark

資料位置：

- [`results/alternative_route/hard_theta_formal_02`](../results/alternative_route/hard_theta_formal_02)

統計：

- `total_runs = 30`
- `feasible_runs = 30`
- `ties = 30`
- `wins = 0`
- `mean_cost_gap_vs_baseline = 0.0`
- `mean_max_similarity = 0.0607`

解讀：

- alternative routing 題目已經建立成功
- SQA 能穩定解出兩條合法路
- 但現在仍是在重現 baseline heuristic，而不是超越它

## 3. Mode Comparison

資料位置：

- [`results/alternative_route/mode_compare_formal_01`](../results/alternative_route/mode_compare_formal_01)

模式對照：

| Mode | Feasible | Interpretation |
| --- | ---: | --- |
| `budget_warm_on` | 30/30 | 有 warm start 時，可穩定重現 baseline |
| `budget_warm_off` | 0/30 | 拿掉 warm start 後，solver 無法自行長出解 |
| `budget_plus_ratio_warm_on` | 9/30 | 更接近文獻 hard ratio 後，難度顯著提高 |
| `budget_plus_ratio_warm_off` | 0/30 | 無 warm start 且高難度 constraint 時完全失敗 |

解讀：

- `warm start` 目前仍然是必要條件
- 題目定義已具有研究價值
- 下一步研究重點應放在 solver 搜尋能力，而不是再去懷疑 baseline 是否太強

## 4. Overall Research Position

目前這份 repo 能支持的最誠實說法是：

- 題目已從普通 shortest path 升級成 limited-overlap alternative routing
- benchmark、資料包、QGIS 輸出、重現管線都已經建立
- SQA 已能在部分設定下穩定重現 baseline
- 但還沒有證明它能在這個題目上超越經典 heuristic

這也是為什麼目前成果非常適合當作：

- 中期研究整理版
- 可重現 benchmark archive
- 下一步 solver 改良的基底
