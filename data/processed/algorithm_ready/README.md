# Algorithm-ready Graph Package

這份資料包是目前 pedestrian routing 實驗的正式輸入。

## Files

- `nodes_all.geojson`, `nodes_all.csv`: 全部節點
- `segments_all.geojson`, `segments_all.csv`: 全部線段
- `directed_edges_all.geojson`, `directed_edges_all.csv`: 全部有向邊
- `nodes_main_component.geojson`: 最大連通分量節點
- `segments_main_component.geojson`: 最大連通分量線段
- `directed_edges_main_component.geojson`: 最大連通分量有向邊
- `sidewalk_graph_ready.gpkg`: 給 QGIS 最方便直接開的整包格式
- `components_summary.csv`: 連通分量摘要
- `graph_validation_report.txt`, `graph_validation_report.json`: 圖資料驗證結果

## Why This Package Exists

原始 sidewalk 線資料雖然幾何乾淨，但還不是演算法就緒格式。  
這份 package 已經補齊：

- 顯式 node / edge graph 結構
- directed routing 所需欄位
- component 標記
- QGIS 友善輸出

## Recommended Input

對目前 routing 題目來說，最推薦使用的是：

- `directed_edges_main_component.geojson`
- `segments_main_component.geojson`

這樣可以避免落到非主網路的小連通分量。
