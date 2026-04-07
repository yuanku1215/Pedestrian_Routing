# Reproduction Guide

## English

### Environment

```bash
cd /path/to/Pedestrian_Routing
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip setuptools wheel
python3 -m pip install -r requirements.txt
```

### Quick smoke test

```bash
python3 src/sqa_algorithm/run.py \
  --rule kspwlo_routing \
  --data data/processed/algorithm_ready \
  --steps 10 \
  --replicas 2 \
  --slices 6 \
  --seed 42 \
  --output-dir tmp/portable_smoke
```

### Single kSPwLO run

```bash
python3 src/sqa_algorithm/run.py \
  --rule kspwlo_routing \
  --data data/processed/algorithm_ready \
  --steps 60 \
  --replicas 12 \
  --slices 20 \
  --beta-init 0.2 \
  --beta-final 4.0 \
  --gamma-init 3.0 \
  --gamma-final 0.2 \
  --seed 42
```

### Mode-comparison benchmark

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

### Helpful shell wrappers

- [`scripts/run_kspwlo_single.sh`](../scripts/run_kspwlo_single.sh)
- [`scripts/run_kspwlo_mode_compare.sh`](../scripts/run_kspwlo_mode_compare.sh)

### Expected data input

All current routing tasks expect:

- [`data/processed/algorithm_ready`](../data/processed/algorithm_ready)

If you replace it with another dataset, make sure it contains:

- graph-ready nodes
- segments
- directed edges
- fields compatible with the current configs

## 中文

### 環境建立

```bash
cd /path/to/Pedestrian_Routing
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip setuptools wheel
python3 -m pip install -r requirements.txt
```

### 快速 smoke test

```bash
python3 src/sqa_algorithm/run.py \
  --rule kspwlo_routing \
  --data data/processed/algorithm_ready \
  --steps 10 \
  --replicas 2 \
  --slices 6 \
  --seed 42 \
  --output-dir tmp/portable_smoke
```

### 單次 kSPwLO 執行

```bash
python3 src/sqa_algorithm/run.py \
  --rule kspwlo_routing \
  --data data/processed/algorithm_ready \
  --steps 60 \
  --replicas 12 \
  --slices 20 \
  --beta-init 0.2 \
  --beta-final 4.0 \
  --gamma-init 3.0 \
  --gamma-final 0.2 \
  --seed 42
```

### 模式比較 benchmark

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

### 好用的 shell wrapper

- [`scripts/run_kspwlo_single.sh`](../scripts/run_kspwlo_single.sh)
- [`scripts/run_kspwlo_mode_compare.sh`](../scripts/run_kspwlo_mode_compare.sh)

### 預期資料輸入

目前所有 routing 題目都預期使用：

- [`data/processed/algorithm_ready`](../data/processed/algorithm_ready)

如果你要換別的資料集，至少要確保它包含：

- graph-ready nodes
- segments
- directed edges
- 與目前 config 相容的主要欄位
