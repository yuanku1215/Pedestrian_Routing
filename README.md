# Pedestrian Routing

## English

This repository is a curated delivery package for the current pedestrian-routing research project.  
It is not only a code dump. It combines:

- data
- graph-ready inputs
- the SQA engine
- routing rules
- benchmark tools
- organized outputs
- research interpretation

The current study has two main phases:

1. single-route pedestrian routing
2. literature-aligned `kSPwLO` alternative routing

The second phase upgrades the task from “find one shortest path” to:

- fixed source and target
- `k = 2` routes
- limited overlap between routes
- baseline-vs-SQA comparison under the same graph and cost definitions

### What this repository is trying to answer

1. Can raw sidewalk and dynamic time-slice data be turned into a reliable graph package?
2. Can the SQA engine be connected to a pedestrian-routing problem?
3. Can pure SQA grow a valid route in the single-route setting?
4. Can SQA produce two valid routes in a limited-overlap alternative-routing setting?
5. Under the current formulation, does SQA show behavior beyond baseline heuristic replay?

### Current bottom line

The most honest one-sentence conclusion is:

**The project already provides a reproducible SQA benchmark framework for pedestrian routing, but current SQA results mainly reproduce the baseline heuristic rather than reliably outperforming it.**

### Research evolution

#### Phase 1: single-route routing

This phase was used to verify:

- graph correctness
- Dijkstra baseline correctness
- pure SQA behavior
- warm-start behavior
- block-move behavior

Observed outcome:

- `pure_sqa` almost always fails to form a valid route
- with baseline warm start, SQA can preserve the solution
- it still does not beat the baseline

#### Phase 2: kSPwLO alternative routing

Because the single-route task is still too close to standard shortest path, the main research line shifted to a `kSPwLO`-style problem:

- directed weighted graph
- two routes
- overlap control
- route-set comparison instead of only single-route comparison

This phase includes:

- classical penalty-heuristic baseline
- SQA solver
- warm-start on/off comparisons
- budget vs budget-plus-ratio overlap comparisons

### Key findings

#### A. Single-route benchmark

Location:

- [`results/single_route/formal_modes_suite_01`](results/single_route/formal_modes_suite_01)

Main results:

| Mode | Runs | Result |
| --- | ---: | --- |
| `pure_sqa` | 150 | `150/150 no_route` |
| `baseline_warm_start` | 150 | `150/150 tie` |
| `baseline_plus_block_move` | 150 | `150/150 tie` |

Interpretation:

- Pure SQA still cannot form a valid route from scratch.
- Warm start and block moves preserve the baseline.
- They still do not produce a better route.

#### B. kSPwLO hard-theta benchmark

Location:

- [`results/alternative_route/hard_theta_formal_02`](results/alternative_route/hard_theta_formal_02)

Main metrics:

| Metric | Value |
| --- | ---: |
| total runs | 30 |
| feasible runs | 30 |
| ties | 30 |
| wins | 0 |
| losses | 0 |
| mean cost gap vs baseline | 0.0 |
| mean max similarity | 0.0607 |

Interpretation:

- SQA can stably output two valid routes in the alternative-routing setting.
- Overlap is being controlled.
- The route set still matches the baseline heuristic.

#### C. Warm-start / ratio comparison

Location:

- [`results/alternative_route/mode_compare_formal_01`](results/alternative_route/mode_compare_formal_01)

Main results:

| Mode | Feasible | Main meaning |
| --- | ---: | --- |
| `budget_warm_on` | 30/30 | warm start allows stable baseline reproduction |
| `budget_warm_off` | 0/30 | without warm start, the solver cannot grow a route set |
| `budget_plus_ratio_warm_on` | 9/30 | ratio-like constraints make the task much harder |
| `budget_plus_ratio_warm_off` | 0/30 | no warm start plus harder constraints fully fails |

Interpretation:

- Warm start is still a practical requirement.
- The problem definition already has research value.
- The main bottleneck is now solver search capability.

### Repository structure

- [`data/raw`](data/raw): raw spatial and dynamic datasets
- [`data/processed/algorithm_ready`](data/processed/algorithm_ready): graph-ready input package for routing
- [`src/sqa_algorithm`](src/sqa_algorithm): SQA engine, routing rules, and benchmark tools
- [`results`](results): curated benchmark outputs
- [`docs`](docs): summaries, reproduction guide, release notes, and references

### Suggested reading order

1. [`docs/RELEASE_NOTES.md`](docs/RELEASE_NOTES.md)
2. [`docs/RESULTS_SUMMARY.md`](docs/RESULTS_SUMMARY.md)
3. [`data/processed/algorithm_ready/README.md`](data/processed/algorithm_ready/README.md)
4. [`src/sqa_algorithm/README.md`](src/sqa_algorithm/README.md)
5. [`results`](results)

### Quick start

#### Environment

```bash
cd /path/to/Pedestrian_Routing
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip setuptools wheel
python3 -m pip install -r requirements.txt
```

#### Single kSPwLO run

```bash
python3 src/sqa_algorithm/run.py \
  --rule kspwlo_routing \
  --data data/processed/algorithm_ready \
  --steps 60 \
  --replicas 12 \
  --slices 20
```

#### Mode comparison benchmark

```bash
python3 src/sqa_algorithm/tools/run_kspwlo_mode_comparison.py \
  --data data/processed/algorithm_ready \
  --suite-name mode_compare_formal \
  --steps 60 \
  --replicas 12 \
  --slices 20 \
  --num-seeds 1 \
  --jobs 8
```

Shell wrappers:

- [`scripts/run_kspwlo_single.sh`](scripts/run_kspwlo_single.sh)
- [`scripts/run_kspwlo_mode_compare.sh`](scripts/run_kspwlo_mode_compare.sh)

### QGIS-friendly outputs

The repository preserves GIS-friendly outputs such as:

- `.geojson` and `.gpkg` files in `algorithm_ready`
- `baseline_path_*.geojson`
- `sqa_path_*.geojson`
- `sqa_selected_edges_path_*.geojson`

If you want to inspect a concrete two-route output, start with:

- [`results/alternative_route/hard_theta_formal_02/runs`](results/alternative_route/hard_theta_formal_02/runs)

### What this repository can honestly claim

- it provides a graph-ready pedestrian-routing pipeline
- it provides an SQA-based routing benchmark framework
- it aligns the main formulation with kSPwLO-style alternative routing
- it supports reproducible baseline-vs-SQA comparisons
- it preserves QGIS-friendly outputs

### What it should not overclaim

- it should not claim that SQA already outperforms the classical heuristic
- it should not claim that warm start is no longer needed
- it should not claim that the stricter hard-ratio version is already solved robustly

### Next steps

The most natural future directions are:

1. better initialization and path-aware move design
2. stricter and more exact overlap-ratio constraints
3. stronger global-coupling objectives that move the task beyond shortest-path replay

## 中文

這個 repository 是目前 pedestrian-routing 研究的整理版交付包。  
它不只是把程式碼丟上來而已，而是把以下內容整合成一份可重現、可閱讀、也可持續研究的專案：

- data
- graph-ready inputs
- SQA engine
- routing rules
- benchmark tools
- 整理過的成果
- 研究判讀

目前研究分成兩個主要階段：

1. 單一路徑 pedestrian routing
2. 對齊文獻的 `kSPwLO` alternative routing

第二階段已經把題目從「找一條最短路」提升成：

- 固定 source 與 target
- 求 `k = 2` 條路
- 限制兩條路之間的 overlap
- 在同一套 graph 與 cost 定義下比較 baseline 與 SQA

### 這個 repository 想回答什麼

1. 能不能把原始 sidewalk 與動態時段資料整理成可靠的 graph package？
2. 能不能把 SQA engine 接上 pedestrian-routing 題目？
3. 在單一路徑設定下，pure SQA 能不能自己長出合法路？
4. 在 limited-overlap alternative-routing 設定下，SQA 能不能輸出兩條合法路？
5. 在目前 formulation 下，SQA 是否已展現出超越 baseline heuristic replay 的能力？

### 目前最精簡的結論

最誠實的一句話是：

**這個專案已經建立了可重現的 pedestrian-routing SQA benchmark framework，但目前 SQA 的結果仍主要是在重現 baseline heuristic，尚未證明能可靠地超越它。**

### 研究演進

#### Phase 1: 單一路徑 routing

這個階段主要用來驗證：

- graph 是否正確
- Dijkstra baseline 是否正確
- pure SQA 的行為
- warm-start 的行為
- block-move 的行為

觀察到的結果是：

- `pure_sqa` 幾乎總是無法形成合法路徑
- 有 baseline warm start 時，SQA 可以保住這條解
- 但仍然沒有超越 baseline

#### Phase 2: kSPwLO alternative routing

因為單一路徑題目本質上仍太接近標準 shortest path，研究主線後來轉向 `kSPwLO` 類型的題目：

- directed weighted graph
- 兩條路
- overlap control
- 由單一路徑比較改成 route-set 比較

這個階段包含：

- classical penalty-heuristic baseline
- SQA solver
- warm-start on/off 對照
- budget 與 budget-plus-ratio 的 overlap 對照

### 主要發現

#### A. 單一路徑 benchmark

位置：

- [`results/single_route/formal_modes_suite_01`](results/single_route/formal_modes_suite_01)

主要結果：

| Mode | Runs | Result |
| --- | ---: | --- |
| `pure_sqa` | 150 | `150/150 no_route` |
| `baseline_warm_start` | 150 | `150/150 tie` |
| `baseline_plus_block_move` | 150 | `150/150 tie` |

解讀：

- 純 SQA 目前仍無法從零形成合法路徑
- warm start 與 block move 能保住 baseline
- 但仍未產生更好的路徑

#### B. kSPwLO hard-theta benchmark

位置：

- [`results/alternative_route/hard_theta_formal_02`](results/alternative_route/hard_theta_formal_02)

主要指標：

| Metric | Value |
| --- | ---: |
| total runs | 30 |
| feasible runs | 30 |
| ties | 30 |
| wins | 0 |
| losses | 0 |
| mean cost gap vs baseline | 0.0 |
| mean max similarity | 0.0607 |

解讀：

- 在 alternative-routing 設定下，SQA 已能穩定輸出兩條合法路
- overlap 也有被控制住
- 但整體 route set 仍與 baseline heuristic 相同

#### C. Warm-start / ratio comparison

位置：

- [`results/alternative_route/mode_compare_formal_01`](results/alternative_route/mode_compare_formal_01)

主要結果：

| Mode | Feasible | Main meaning |
| --- | ---: | --- |
| `budget_warm_on` | 30/30 | 有 warm start 時，可穩定重現 baseline |
| `budget_warm_off` | 0/30 | 沒有 warm start 時，solver 無法長出 route set |
| `budget_plus_ratio_warm_on` | 9/30 | 類 ratio 的限制會讓問題更難 |
| `budget_plus_ratio_warm_off` | 0/30 | 沒有 warm start 且限制更硬時完全失敗 |

解讀：

- warm start 目前仍是實務上必要條件
- 題目定義本身已具備研究價值
- 現在真正的瓶頸是 solver 的搜尋能力

### Repository 結構

- [`data/raw`](data/raw): 原始空間與動態資料
- [`data/processed/algorithm_ready`](data/processed/algorithm_ready): routing 正式使用的 graph-ready input package
- [`src/sqa_algorithm`](src/sqa_algorithm): SQA engine、routing rules 與 benchmark tools
- [`results`](results): 整理過的 benchmark outputs
- [`docs`](docs): 摘要、重現方式、release notes 與 references

### 建議閱讀順序

1. [`docs/RELEASE_NOTES.md`](docs/RELEASE_NOTES.md)
2. [`docs/RESULTS_SUMMARY.md`](docs/RESULTS_SUMMARY.md)
3. [`data/processed/algorithm_ready/README.md`](data/processed/algorithm_ready/README.md)
4. [`src/sqa_algorithm/README.md`](src/sqa_algorithm/README.md)
5. [`results`](results)

### Quick start

#### 環境建立

```bash
cd /path/to/Pedestrian_Routing
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip setuptools wheel
python3 -m pip install -r requirements.txt
```

#### 單次 kSPwLO 執行

```bash
python3 src/sqa_algorithm/run.py \
  --rule kspwlo_routing \
  --data data/processed/algorithm_ready \
  --steps 60 \
  --replicas 12 \
  --slices 20
```

#### Mode comparison benchmark

```bash
python3 src/sqa_algorithm/tools/run_kspwlo_mode_comparison.py \
  --data data/processed/algorithm_ready \
  --suite-name mode_compare_formal \
  --steps 60 \
  --replicas 12 \
  --slices 20 \
  --num-seeds 1 \
  --jobs 8
```

Shell wrappers：

- [`scripts/run_kspwlo_single.sh`](scripts/run_kspwlo_single.sh)
- [`scripts/run_kspwlo_mode_compare.sh`](scripts/run_kspwlo_mode_compare.sh)

### QGIS 友善輸出

repo 內也保留了方便進 GIS 工具看的輸出，例如：

- `algorithm_ready` 裡的 `.geojson` 與 `.gpkg`
- `baseline_path_*.geojson`
- `sqa_path_*.geojson`
- `sqa_selected_edges_path_*.geojson`

如果你想看某一次具體的雙路徑結果，建議從這裡開始：

- [`results/alternative_route/hard_theta_formal_02/runs`](results/alternative_route/hard_theta_formal_02/runs)

### 這個 repository 可以誠實主張的事

- 已建立 graph-ready pedestrian-routing pipeline
- 已建立 SQA-based routing benchmark framework
- 已讓主 formulation 對齊 kSPwLO 類型的 alternative routing
- 已能做可重現的 baseline-vs-SQA 比較
- 已保留 QGIS 友善輸出

### 這個 repository 不應過度宣稱的事

- 目前還不能說 SQA 已穩定優於 classical heuristic
- 目前還不能說 warm start 已不再需要
- 目前也不能說更嚴格的 hard-ratio 版本已被穩定解開

### 下一步

最自然的後續方向是：

1. 更好的 initialization 與 path-aware move design
2. 更嚴格、更精確的 overlap-ratio constraints
3. 更強的 global-coupling objectives，讓問題真正脫離 shortest-path replay
