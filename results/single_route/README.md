# Single-route Results

## English

This folder preserves the single-route benchmark phase that came before the move to kSPwLO.

Its value is not the final model itself.  
Its value is that it answers two important questions:

- Can pure SQA grow a valid route by itself?
- Do warm start and block moves help in the single-route setting?

The answer from the benchmark is clear:

- `pure_sqa`: no
- `baseline_warm_start`: it can reproduce the baseline
- `baseline_plus_block_move`: it still reproduces the baseline

That is why the research later shifted to alternative routing.

## 中文

這一層保留的是在轉向 kSPwLO 之前的單一路徑 benchmark。

它的價值不在最終模型本身，而在於它回答了兩個很重要的問題：

- 純 SQA 能不能自己長出合法路徑？
- 在單一路徑題目裡，warm start 與 block move 有沒有幫助？

從 benchmark 得到的答案很清楚：

- `pure_sqa`: 不行
- `baseline_warm_start`: 可以重現 baseline
- `baseline_plus_block_move`: 仍然只是重現 baseline

也因此，後續研究才會正式轉向 alternative routing。
