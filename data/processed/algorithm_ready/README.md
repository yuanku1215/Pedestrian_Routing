# Algorithm-ready Graph Package

## English

This package is the formal routing input used by the current pedestrian-routing experiments.

### Included files

- `nodes_all.geojson`, `nodes_all.csv`: all graph nodes
- `segments_all.geojson`, `segments_all.csv`: all undirected segments
- `directed_edges_all.geojson`, `directed_edges_all.csv`: all directed routing edges
- `nodes_main_component.geojson`: nodes in the largest connected component
- `segments_main_component.geojson`: segments in the largest connected component
- `directed_edges_main_component.geojson`: directed edges in the largest connected component
- `sidewalk_graph_ready.gpkg`: easiest package to open directly in QGIS
- `components_summary.csv`: connected-component summary
- `graph_validation_report.txt`, `graph_validation_report.json`: graph validation outputs

### Why it exists

The original sidewalk line data is geometrically clean, but it is not yet algorithm-ready.  
This package adds:

- explicit node/edge graph structure
- directed-routing fields
- component labeling
- QGIS-friendly exports

### Recommended inputs

For current routing tasks, the recommended files are:

- `directed_edges_main_component.geojson`
- `segments_main_component.geojson`

This avoids accidentally selecting OD points from small disconnected components.

## 中文

這份資料包是目前 pedestrian routing 實驗正式使用的輸入。

### 內容包含

- `nodes_all.geojson`, `nodes_all.csv`: 全部 graph nodes
- `segments_all.geojson`, `segments_all.csv`: 全部無向線段
- `directed_edges_all.geojson`, `directed_edges_all.csv`: 全部有向 routing edges
- `nodes_main_component.geojson`: 最大連通分量的 nodes
- `segments_main_component.geojson`: 最大連通分量的線段
- `directed_edges_main_component.geojson`: 最大連通分量的有向邊
- `sidewalk_graph_ready.gpkg`: 最適合直接用 QGIS 開啟的整包格式
- `components_summary.csv`: 連通分量摘要
- `graph_validation_report.txt`, `graph_validation_report.json`: 圖資料驗證結果

### 為什麼需要它

原始 sidewalk 線資料雖然幾何乾淨，但還不是演算法可直接使用的格式。  
這份 package 補上了：

- 明確的 node/edge graph 結構
- directed routing 所需欄位
- component 標記
- QGIS 友善輸出

### 建議輸入

對目前的 routing 題目來說，最建議直接使用：

- `directed_edges_main_component.geojson`
- `segments_main_component.geojson`

這樣可以避免 OD 點落到小型非主網路連通分量。
