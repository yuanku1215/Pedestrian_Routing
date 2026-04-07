# mode_compare_formal_01

## English

This package answers one focused question:

- How much do warm start and stricter ratio-like overlap constraints affect SQA?

### Compared modes

- `budget_warm_on`
- `budget_warm_off`
- `budget_plus_ratio_warm_on`
- `budget_plus_ratio_warm_off`

### Main result

According to [`summary/mode_overall_summary.csv`](summary/mode_overall_summary.csv):

- `budget_warm_on`: `30/30 feasible`, `30/30 tie`
- `budget_warm_off`: `0/30 feasible`
- `budget_plus_ratio_warm_on`: `9/30 feasible`
- `budget_plus_ratio_warm_off`: `0/30 feasible`

### Interpretation

- Warm start is still a necessary condition.
- Moving closer to a hard-ratio overlap constraint raises the difficulty significantly.
- The current bottleneck is solver search power rather than problem definition.

### Included contents

- `comparison_manifest.json`: global settings for the four-mode comparison
- `summary/*`: aggregate comparison outputs
- `mode_suites/*/summary/*`: per-mode summary outputs

## 中文

這份資料夾專門回答一個聚焦問題：

- warm start 與更嚴格、類似 ratio 的 overlap constraint，對 SQA 影響到底有多大？

### 比較模式

- `budget_warm_on`
- `budget_warm_off`
- `budget_plus_ratio_warm_on`
- `budget_plus_ratio_warm_off`

### 主要結果

根據 [`summary/mode_overall_summary.csv`](summary/mode_overall_summary.csv)：

- `budget_warm_on`: `30/30 feasible`, `30/30 tie`
- `budget_warm_off`: `0/30 feasible`
- `budget_plus_ratio_warm_on`: `9/30 feasible`
- `budget_plus_ratio_warm_off`: `0/30 feasible`

### 解讀

- warm start 目前仍是必要條件
- 當 overlap constraint 更接近 hard ratio 時，問題難度會顯著上升
- 現階段真正的瓶頸是 solver 的搜尋能力，而不是題目定義本身

### 包含內容

- `comparison_manifest.json`: 四模式比較的整體設定
- `summary/*`: 四模式總覽輸出
- `mode_suites/*/summary/*`: 每個模式自己的摘要輸出
