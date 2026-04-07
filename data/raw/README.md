# Raw Data

## English

This folder stores the raw spatial layers and dynamic time-slice data used during the research process.

Main categories include:

- `sidewalks`: sidewalk and dynamic walkability line layers
- `traffic`: weekday/weekend traffic slices across different hours
- `road_network`: road-network layers
- `boundary`: study-area boundaries
- `population`, `accidents`, `airpollution`, `slope`, `obstacles`: supporting environmental layers

### How it connects to the pipeline

The routing engine does not read this raw-data layer directly.  
The actual algorithm input is:

- [`data/processed/algorithm_ready`](../processed/algorithm_ready)

Pipeline:

`raw data -> preprocessing / graph packaging -> algorithm_ready -> SQA / baseline benchmarks`

If you want to rebuild the graph package, start with:

- [`src/sqa_algorithm/tools/build_sidewalk_graph_package.py`](../../src/sqa_algorithm/tools/build_sidewalk_graph_package.py)

## 中文

這個資料夾存放研究過程中的原始空間圖層與動態時段資料。

主要類型包含：

- `sidewalks`: 行人道與動態 walkability 線資料
- `traffic`: 平日／假日、不同時段的交通切片
- `road_network`: 道路網圖層
- `boundary`: 研究範圍邊界
- `population`, `accidents`, `airpollution`, `slope`, `obstacles`: 其他輔助環境圖層

### 它和目前流程的關係

routing engine 並不是直接讀這層 raw data。  
真正直接餵給演算法的是：

- [`data/processed/algorithm_ready`](../processed/algorithm_ready)

流程可理解為：

`raw data -> preprocessing / graph packaging -> algorithm_ready -> SQA / baseline benchmarks`

如果之後要重建 graph package，請從這支工具開始：

- [`src/sqa_algorithm/tools/build_sidewalk_graph_package.py`](../../src/sqa_algorithm/tools/build_sidewalk_graph_package.py)
