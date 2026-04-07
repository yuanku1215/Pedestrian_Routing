# SQA Algorithm Package

這個資料夾是從原本的 `SQA_Algorithm/` 整理而來，保留了目前 pedestrian routing 研究真正需要的部分。

## Core Structure

- [`engine`](engine): SQA 核心求解器。
- [`rules/path_routing`](rules/path_routing): 單一路徑版本，主要作為基準與演進歷程。
- [`rules/kspwlo_routing`](rules/kspwlo_routing): 目前主線題目，對齊 kSPwLO alternative routing。
- [`tools`](tools): 資料封裝、benchmark、mode comparison 等操作工具。
- [`run.py`](run.py): 通用執行入口。

## Main Entry Points

### 單次 kSPwLO run

```bash
python3 src/sqa_algorithm/run.py \
  --rule kspwlo_routing \
  --data data/processed/algorithm_ready \
  --steps 60 \
  --replicas 12 \
  --slices 20
```

### kSPwLO benchmark

```bash
python3 src/sqa_algorithm/tools/run_kspwlo_routing_benchmark.py \
  --data data/processed/algorithm_ready
```

### kSPwLO mode comparison

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

## What Is Preserved Here

- 引擎核心
- 單一路徑與雙路徑 routing 規則
- benchmark scripts
- 文獻對齊說明

## What Is Not Stored Here

- 大量暫存輸出
- 已淘汰的重複 benchmark 資料夾
- 本地開發環境檔案

正式成果請到 [`../../results`](../../results) 看。
