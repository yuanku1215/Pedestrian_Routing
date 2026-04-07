# hard_theta_formal_02

## English

This is the most complete preserved formal benchmark bundle for the current kSPwLO routing study.

### Problem setting

- `k = 2`
- `theta = 0.5`
- hard overlap mode: `budget`
- processed graph package with 10 dynamic time slices
- 3 OD straight-line targets: `400m / 800m / 1200m`

### Main result

According to [`summary/overall_statistics.json`](summary/overall_statistics.json):

- `total_runs = 30`
- `feasible_runs = 30`
- `ties = 30`
- `wins = 0`
- `losses = 0`
- `mean_max_similarity = 0.0607`

### Interpretation

- SQA can stably output two valid routes in the alternative-routing setting.
- Route overlap is being controlled.
- Under the current formulation and settings, the route set still matches the baseline heuristic.

### Folder notes

- `summary/*`: overview statistics and figures
- `runs/*`: complete outputs for every scenario
- `logs/*`: run logs

If you only want the conclusion, start from `summary`.

## 中文

這是目前 kSPwLO routing 研究中保留最完整的一包正式 benchmark。

### 題目設定

- `k = 2`
- `theta = 0.5`
- hard overlap mode 採用 `budget`
- 使用 processed graph package 與 10 個動態時段
- 3 組 OD 直線距離目標：`400m / 800m / 1200m`

### 主要結果

根據 [`summary/overall_statistics.json`](summary/overall_statistics.json)：

- `total_runs = 30`
- `feasible_runs = 30`
- `ties = 30`
- `wins = 0`
- `losses = 0`
- `mean_max_similarity = 0.0607`

### 解讀

- 在 alternative-routing 題目中，SQA 已能穩定輸出兩條合法路徑
- 兩條路之間的 overlap 也有被控制住
- 但在目前 formulation 與設定下，結果仍與 baseline heuristic 相同

### 資料夾說明

- `summary/*`: 總覽統計與圖表
- `runs/*`: 每個 scenario 的完整輸出
- `logs/*`: 單 run log

如果你只想先看結論，直接從 `summary` 開始。
