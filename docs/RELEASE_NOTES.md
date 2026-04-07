# Release Notes

## English

### 2026-04-08 Repository Packaging Release

This release turns the current pedestrian-routing research workspace into a structured GitHub project.

The goal is not to introduce a new solver in this release.  
The goal is to make the existing work:

- readable
- runnable
- traceable
- handoff-friendly

### Included in this release

#### 1. Source-code reorganization

The SQA-related code has been consolidated under:

- [`src/sqa_algorithm`](../src/sqa_algorithm)

This includes:

- the SQA engine
- `path_routing`
- `kspwlo_routing`
- benchmark runners
- graph-packaging tools
- the generic `run.py` entrypoint

#### 2. Algorithm-ready graph package

The formal graph input now lives in:

- [`data/processed/algorithm_ready`](../data/processed/algorithm_ready)

It contains:

- nodes
- segments
- directed edges
- component summary
- graph-validation reports
- QGIS-friendly GeoJSON and GPKG outputs

#### 3. Results packaging

Instead of keeping every historical scratch output, this release keeps two curated result lines:

- [`results/single_route`](../results/single_route)
- [`results/alternative_route`](../results/alternative_route)

#### 4. Documentation

The repository now includes:

- [`README.md`](../README.md)
- [`docs/RESULTS_SUMMARY.md`](RESULTS_SUMMARY.md)
- [`docs/REPRODUCTION.md`](REPRODUCTION.md)
- [`docs/references`](references)

### Scientific position supported by this release

- Pure SQA still cannot reliably grow a valid single route from scratch.
- In the `kSPwLO` setting, SQA can generate feasible two-route solutions under some settings.
- Current SQA results mainly reproduce the baseline heuristic.
- Warm start is still a practical requirement for the current solver design.

### What was intentionally excluded

- obsolete local scratch outputs
- repeated intermediate benchmark folders
- local cache and environment artifacts

The purpose of the repository is to be a maintainable research project, not a full machine backup.

### Recommended next release directions

1. better initialization and move design
2. stricter overlap-ratio formulation
3. global-coupling objectives that move the problem beyond shortest-path replay

## 中文

### 2026-04-08 Repository Packaging Release

這一版的目的，是把目前的 pedestrian-routing 研究工作區整理成正式的 GitHub 專案。

這次釋出不是為了新增一個 solver。  
它的目標是讓既有成果變成：

- 可讀
- 可跑
- 可追溯
- 可交接

### 這次釋出包含

#### 1. 原始碼重整

所有 SQA 相關程式已統一整理到：

- [`src/sqa_algorithm`](../src/sqa_algorithm)

內容包括：

- SQA engine
- `path_routing`
- `kspwlo_routing`
- benchmark runners
- graph packaging 工具
- 通用的 `run.py` 入口

#### 2. Algorithm-ready graph package

正式使用的圖資料現在整理在：

- [`data/processed/algorithm_ready`](../data/processed/algorithm_ready)

它包含：

- nodes
- segments
- directed edges
- component summary
- graph-validation reports
- 可直接匯入 QGIS 的 GeoJSON 與 GPKG

#### 3. 成果整理

這次不是把所有歷史輸出都保留，而是收斂成兩條主要成果線：

- [`results/single_route`](../results/single_route)
- [`results/alternative_route`](../results/alternative_route)

#### 4. 說明文件

repo 現在補齊了：

- [`README.md`](../README.md)
- [`docs/RESULTS_SUMMARY.md`](RESULTS_SUMMARY.md)
- [`docs/REPRODUCTION.md`](REPRODUCTION.md)
- [`docs/references`](references)

### 這版能支持的研究說法

- 純 SQA 目前仍無法可靠地從零長出合法單一路徑
- 在 `kSPwLO` 題目中，SQA 在部分設定下已能輸出可行的雙路徑解
- 目前 SQA 結果仍主要是在重現 baseline heuristic
- warm start 目前仍是實務上必要的條件

### 刻意沒有收進來的內容

- 已淘汰的本地 scratch outputs
- 重複且中間性的 benchmark 資料夾
- 本地 cache 與環境檔

這樣做的原因是：這個 repo 要成為可維護的研究專案，而不是整台機器的完整備份。

### 下一版最值得做的方向

1. 更好的 initialization 與 move design
2. 更嚴格、更接近論文的 overlap-ratio formulation
3. 加入全域耦合目標，讓問題真正脫離 shortest-path replay
