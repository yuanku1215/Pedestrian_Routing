# Raw Data

這裡放的是研究過程中的原始空間資料與動態切片資料。

主要類型包含：

- `sidewalks`: 行人道與動態 walkability 線資料
- `traffic`: 平日 / 假日、不同时段的交通切片
- `road_network`: 道路網
- `boundary`: 研究範圍
- `population`, `accidents`, `airpollution`, `slope`, `obstacles`: 其他環境圖層

## How It Connects To The Current Pipeline

目前 repo 中真正直接餵給演算法使用的不是這層 raw data，而是：

- [`data/processed/algorithm_ready`](../processed/algorithm_ready)

也就是說：

`raw data -> preprocessing / graph packaging -> algorithm_ready -> SQA / baseline benchmarks`

若你之後要重建圖資料，請看：

- [`src/sqa_algorithm/tools/build_sidewalk_graph_package.py`](../../src/sqa_algorithm/tools/build_sidewalk_graph_package.py)
