# SQA Algorithm Package

## English

This folder is the curated version of the original `SQA_Algorithm/` workspace.  
It keeps the parts that are actually used by the current pedestrian-routing study.

### Core structure

- [`engine`](engine): the SQA core solver
- [`rules/path_routing`](rules/path_routing): single-route formulation, mainly kept as a baseline and historical phase
- [`rules/kspwlo_routing`](rules/kspwlo_routing): current main formulation aligned with kSPwLO-style alternative routing
- [`tools`](tools): graph packaging, benchmark, and comparison tools
- [`run.py`](run.py): generic runtime entrypoint

### Main entrypoints

#### Single kSPwLO run

```bash
python3 src/sqa_algorithm/run.py \
  --rule kspwlo_routing \
  --data data/processed/algorithm_ready \
  --steps 60 \
  --replicas 12 \
  --slices 20
```

#### kSPwLO benchmark

```bash
python3 src/sqa_algorithm/tools/run_kspwlo_routing_benchmark.py \
  --data data/processed/algorithm_ready
```

#### kSPwLO mode comparison

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

### What is preserved here

- engine core
- single-route and two-route routing rules
- benchmark scripts
- literature-alignment notes

### What is not preserved here

- large local scratch outputs
- deprecated duplicate benchmark folders
- local environment artifacts

Formal results are stored under [`../../results`](../../results).

## 中文

這個資料夾是從原本的 `SQA_Algorithm/` 工作區整理出來的版本。  
它保留了目前 pedestrian-routing 研究真正有在使用的部分。

### 核心結構

- [`engine`](engine): SQA 核心求解器
- [`rules/path_routing`](rules/path_routing): 單一路徑 formulation，主要作為 baseline 與歷程保留
- [`rules/kspwlo_routing`](rules/kspwlo_routing): 目前主線 formulation，對齊 kSPwLO 類型的 alternative routing
- [`tools`](tools): graph packaging、benchmark 與 comparison 工具
- [`run.py`](run.py): 通用執行入口

### 主要入口

#### 單次 kSPwLO 執行

```bash
python3 src/sqa_algorithm/run.py \
  --rule kspwlo_routing \
  --data data/processed/algorithm_ready \
  --steps 60 \
  --replicas 12 \
  --slices 20
```

#### kSPwLO benchmark

```bash
python3 src/sqa_algorithm/tools/run_kspwlo_routing_benchmark.py \
  --data data/processed/algorithm_ready
```

#### kSPwLO mode comparison

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

### 這裡保留的內容

- engine 核心
- 單一路徑與雙路徑 routing rules
- benchmark scripts
- 文獻對齊說明

### 這裡沒有保留的內容

- 大量本地 scratch outputs
- 已淘汰且重複的 benchmark 資料夾
- 本地環境檔案

正式成果請看 [`../../results`](../../results)。
