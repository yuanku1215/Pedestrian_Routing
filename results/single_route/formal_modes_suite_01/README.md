# formal_modes_suite_01

這是單一路徑版本的正式 benchmark 摘要包。

## What It Tests

- `pure_sqa`
- `baseline_warm_start`
- `baseline_plus_block_move`

## Key Outcome

根據 [`summary/overall_statistics.json`](summary/overall_statistics.json)：

- `total_runs = 450`
- `pure_sqa`: `150/150 no_route`
- `baseline_warm_start`: `150/150 tie`
- `baseline_plus_block_move`: `150/150 tie`

## Reading Tips

- `benchmark_manifest.json`: 這批 benchmark 的設定
- `od_pairs.*`: OD pair 定義
- `summary/*`: 最重要的統計與總覽圖

這份摘要已經足夠判讀單一路徑版本的研究結論，因此沒有把原本龐大的全部 run 明細一起塞進 repo。
