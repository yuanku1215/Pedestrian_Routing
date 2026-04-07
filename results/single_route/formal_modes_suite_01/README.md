# formal_modes_suite_01

## English

This is the formal summary package for the single-route benchmark stage.

### What it tests

- `pure_sqa`
- `baseline_warm_start`
- `baseline_plus_block_move`

### Key outcome

According to [`summary/overall_statistics.json`](summary/overall_statistics.json):

- `total_runs = 450`
- `pure_sqa`: `150/150 no_route`
- `baseline_warm_start`: `150/150 tie`
- `baseline_plus_block_move`: `150/150 tie`

### Reading tips

- `benchmark_manifest.json`: benchmark settings
- `od_pairs.*`: OD definitions
- `summary/*`: the most important tables and overview figures

This summary package is intentionally much lighter than the original full run tree.

## 中文

這是單一路徑 benchmark 階段的正式摘要包。

### 測試內容

- `pure_sqa`
- `baseline_warm_start`
- `baseline_plus_block_move`

### 主要結果

根據 [`summary/overall_statistics.json`](summary/overall_statistics.json)：

- `total_runs = 450`
- `pure_sqa`: `150/150 no_route`
- `baseline_warm_start`: `150/150 tie`
- `baseline_plus_block_move`: `150/150 tie`

### 閱讀建議

- `benchmark_manifest.json`: benchmark 設定
- `od_pairs.*`: OD 定義
- `summary/*`: 最重要的表格與總覽圖

這份摘要包刻意比原始完整 run tree 輕很多，方便快速判讀結論。
