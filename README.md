# Pedestrian Routing

這個 repo 整理了目前行人路徑研究的三個核心部分：

1. 原始資料與可直接餵演算法的圖資料。
2. SQA 求解引擎與 pedestrian routing 規則。
3. 已完成的 benchmark 成果、圖表與研究筆記。

目前主線題目是：

- `single-route path routing`
- `kSPwLO alternative routing (k=2, limited overlap)`

其中 `kSPwLO` 版本已經對齊文獻問題定義，並且保留了：

- 經典 baseline heuristic
- SQA solver
- 不同 warm-start / overlap constraint 模式比較

## Repository Map

- [`data/raw`](data/raw): 原始空間資料與動態時段資料。
- [`data/processed/algorithm_ready`](data/processed/algorithm_ready): 已清理完成、可直接給 routing 演算法使用的 graph package。
- [`src/sqa_algorithm`](src/sqa_algorithm): SQA 引擎、routing rules、benchmark 工具與執行入口。
- [`results`](results): 已完成 benchmark 的整理版成果。
- [`docs`](docs): 研究摘要、重現流程與文獻對齊說明。

## Current Highlights

### 1. Single-route benchmark

來自 [`results/single_route/formal_modes_suite_01`](results/single_route/formal_modes_suite_01)：

- 共 `450` runs
- `pure_sqa`: `150/150 no_route`
- `baseline_warm_start`: `150/150 tie`
- `baseline_plus_block_move`: `150/150 tie`

這代表單一路徑題目中，純 SQA 仍然難以自行長出合法路徑；一旦使用 baseline 引導，SQA 可以穩定重現 baseline，但尚未超越。

### 2. kSPwLO hard-theta benchmark

來自 [`results/alternative_route/hard_theta_formal_02`](results/alternative_route/hard_theta_formal_02)：

- 共 `30` runs
- `30/30 feasible`
- `30/30 ties`
- `mean_max_similarity = 0.0607`

這表示在 hard-theta / overlap budget 條件下，SQA 可以穩定重現 baseline heuristic 的雙路徑集合，但目前仍未出現比 baseline 更好的案例。

### 3. Warm-start / ratio comparison

來自 [`results/alternative_route/mode_compare_formal_01`](results/alternative_route/mode_compare_formal_01)：

- `budget_warm_on`: `30/30 feasible`, `30/30 tie`
- `budget_warm_off`: `0/30 feasible`
- `budget_plus_ratio_warm_on`: `9/30 feasible`
- `budget_plus_ratio_warm_off`: `0/30 feasible`

這組結果非常清楚地指出：

- `warm start` 目前仍是必要條件
- ratio constraint 更接近文獻定義，但同時顯著提高求解難度

更完整的判讀請看 [`docs/RESULTS_SUMMARY.md`](docs/RESULTS_SUMMARY.md)。

## Quick Start

### 1. 建立環境

```bash
cd /path/to/Pedestrian_Routing
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip setuptools wheel
python3 -m pip install -r requirements.txt
```

### 2. 跑單次 kSPwLO routing

```bash
python3 src/sqa_algorithm/run.py \
  --rule kspwlo_routing \
  --data data/processed/algorithm_ready \
  --steps 60 \
  --replicas 12 \
  --slices 20
```

### 3. 跑正式 mode comparison

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

也可以直接用：

- [`scripts/run_kspwlo_single.sh`](scripts/run_kspwlo_single.sh)
- [`scripts/run_kspwlo_mode_compare.sh`](scripts/run_kspwlo_mode_compare.sh)

## Reading Order

如果你是第一次看這個 repo，建議順序是：

1. 看 [`docs/RESULTS_SUMMARY.md`](docs/RESULTS_SUMMARY.md)
2. 看 [`data/processed/algorithm_ready/README.md`](data/processed/algorithm_ready/README.md)
3. 看 [`src/sqa_algorithm/README.md`](src/sqa_algorithm/README.md)
4. 最後進入 [`results`](results) 看各 benchmark 資料夾
