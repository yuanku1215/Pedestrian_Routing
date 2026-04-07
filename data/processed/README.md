# Processed Data

這裡放的是已經整理成研究可直接使用格式的資料。

目前最重要的是：

- [`algorithm_ready`](algorithm_ready)

這份資料包已經包含：

- node 資料
- segment 資料
- directed edge 資料
- connected component 資訊
- graph validation 報告
- 可直接匯入 QGIS 的 GeoJSON / GPKG

如果你是要重跑路徑演算法，直接把 `--data` 指到這個資料夾即可。
