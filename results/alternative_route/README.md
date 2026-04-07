# Alternative-route Results

這一層是目前 repo 的主線成果。

題目定義已經從單一路徑改成：

- 固定 source / target
- 求 `k=2` 條路
- 路徑之間要限制 overlap

也就是與 kSPwLO 方向對齊的 pedestrian alternative routing。

目前包含兩套核心成果：

- [`hard_theta_formal_02`](hard_theta_formal_02): 固定 hard-theta / overlap budget 的正式 benchmark
- [`mode_compare_formal_01`](mode_compare_formal_01): 不同 warm-start / overlap constraint 模式比較
