# mode_compare_formal_01

這份資料夾專門回答一件事：

- `warm start` 和更嚴格的 `ratio-like overlap constraint` 對 SQA 影響多大？

## Compared Modes

- `budget_warm_on`
- `budget_warm_off`
- `budget_plus_ratio_warm_on`
- `budget_plus_ratio_warm_off`

## Main Result

根據 [`summary/mode_overall_summary.csv`](summary/mode_overall_summary.csv)：

- `budget_warm_on`: `30/30 feasible`, `30/30 tie`
- `budget_warm_off`: `0/30 feasible`
- `budget_plus_ratio_warm_on`: `9/30 feasible`
- `budget_plus_ratio_warm_off`: `0/30 feasible`

## Interpretation

這表示：

- 目前 `warm start` 還是必要條件
- 一旦把 overlap constraint 推得更接近 hard ratio，問題難度明顯上升
- 現階段的瓶頸已經不是題目定義，而是 solver 搜尋能力

## What Is Included

- `comparison_manifest.json`: 四模式比較的整體設定
- `summary/*`: 四模式整體比較
- `mode_suites/*/summary/*`: 各模式自己的統計摘要
