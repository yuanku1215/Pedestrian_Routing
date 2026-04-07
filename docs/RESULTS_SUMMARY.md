# Results Summary

## English

This is the most important research summary in the repository.

### 1. Single-route path routing

Data location:

- [`results/single_route/formal_modes_suite_01`](../results/single_route/formal_modes_suite_01)

Main outcomes:

- `pure_sqa`: `150/150 no_route`
- `baseline_warm_start`: `150/150 tie`
- `baseline_plus_block_move`: `150/150 tie`

Interpretation:

- Pure SQA still cannot grow a valid single route from scratch.
- Once a baseline seed is provided, SQA can preserve the solution.
- It still does not beat the baseline.

### 2. kSPwLO hard-theta benchmark

Data location:

- [`results/alternative_route/hard_theta_formal_02`](../results/alternative_route/hard_theta_formal_02)

Main metrics:

- `total_runs = 30`
- `feasible_runs = 30`
- `ties = 30`
- `wins = 0`
- `mean_cost_gap_vs_baseline = 0.0`
- `mean_max_similarity = 0.0607`

Interpretation:

- The alternative-routing problem is now successfully implemented.
- SQA can stably produce two valid routes.
- The result set is still reproducing the baseline heuristic rather than outperforming it.

### 3. Mode comparison

Data location:

- [`results/alternative_route/mode_compare_formal_01`](../results/alternative_route/mode_compare_formal_01)

Comparison table:

| Mode | Feasible | Interpretation |
| --- | ---: | --- |
| `budget_warm_on` | 30/30 | Warm start allows stable baseline reproduction |
| `budget_warm_off` | 0/30 | Without warm start, the solver cannot grow a solution set |
| `budget_plus_ratio_warm_on` | 9/30 | A more ratio-like hard constraint makes the problem much harder |
| `budget_plus_ratio_warm_off` | 0/30 | No warm start plus harder constraints fully fails |

Interpretation:

- Warm start is still a necessary condition.
- The problem definition already has research value.
- The next bottleneck is solver search capability, not data cleaning.

### 4. Overall research position

The most honest claim supported by the current repository is:

- The task has been upgraded from plain shortest path to limited-overlap alternative routing.
- The benchmark pipeline, graph package, QGIS outputs, and reproduction path are already in place.
- SQA can reproduce baseline solutions under some settings.
- It has not yet been shown to reliably outperform classical heuristics on this task.

This makes the repository well suited as:

- a mid-project research archive
- a reproducible benchmark package
- a starting point for future solver improvements

## 中文

這份文件是目前 repo 中最重要的研究摘要。

### 1. 單一路徑 path routing

資料位置：

- [`results/single_route/formal_modes_suite_01`](../results/single_route/formal_modes_suite_01)

主要結果：

- `pure_sqa`: `150/150 no_route`
- `baseline_warm_start`: `150/150 tie`
- `baseline_plus_block_move`: `150/150 tie`

解讀：

- 純 SQA 目前仍無法從零長出合法單一路徑
- 一旦有 baseline seed，SQA 可以保住這個解
- 但仍然沒有超越 baseline

### 2. kSPwLO hard-theta benchmark

資料位置：

- [`results/alternative_route/hard_theta_formal_02`](../results/alternative_route/hard_theta_formal_02)

主要指標：

- `total_runs = 30`
- `feasible_runs = 30`
- `ties = 30`
- `wins = 0`
- `mean_cost_gap_vs_baseline = 0.0`
- `mean_max_similarity = 0.0607`

解讀：

- alternative routing 題目已經成功建立
- SQA 可以穩定輸出兩條合法路徑
- 但目前結果仍是在重現 baseline heuristic，而不是超越它

### 3. 模式比較

資料位置：

- [`results/alternative_route/mode_compare_formal_01`](../results/alternative_route/mode_compare_formal_01)

比較表：

| Mode | Feasible | Interpretation |
| --- | ---: | --- |
| `budget_warm_on` | 30/30 | 有 warm start 時，可穩定重現 baseline |
| `budget_warm_off` | 0/30 | 沒有 warm start 時，solver 無法自行長出解集合 |
| `budget_plus_ratio_warm_on` | 9/30 | 更接近 ratio-like hard constraint 後難度大幅上升 |
| `budget_plus_ratio_warm_off` | 0/30 | 沒有 warm start 且限制更硬時完全失敗 |

解讀：

- warm start 目前仍是必要條件
- 題目定義已經具備研究價值
- 下一個瓶頸是 solver 的搜尋能力，而不是資料清理

### 4. 目前研究定位

這份 repo 現在最誠實、也最穩的說法是：

- 題目已從普通 shortest path 升級成 limited-overlap alternative routing
- benchmark 流程、graph package、QGIS 輸出與重現管線都已建立
- 在部分設定下，SQA 可以穩定重現 baseline 解
- 但目前還沒有證明它能可靠地超越經典 heuristic

因此這份 repo 很適合當作：

- 中期研究整理版
- 可重現 benchmark archive
- 下一步 solver 改良的基底
