# Single-route Results

這一層保留的是在轉向 kSPwLO 之前的單一路徑 benchmark。

它的價值不在於最終模型，而在於回答一個很重要的問題：

- 純 SQA 能不能自己長出合法路徑？
- warm start 與 block move 在單一路徑問題上有沒有幫助？

答案在目前這批 benchmark 中很明確：

- `pure_sqa`: 不行
- `baseline_warm_start`: 可以重現 baseline
- `baseline_plus_block_move`: 仍然只是重現 baseline

也因此，後續研究才會正式轉向 alternative routing。
