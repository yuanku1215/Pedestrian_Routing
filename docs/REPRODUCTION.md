# Reproduction Guide

## Environment

```bash
cd /path/to/Pedestrian_Routing
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip setuptools wheel
python3 -m pip install -r requirements.txt
```

## Quick Smoke Test

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

## Single kSPwLO Run

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

## Mode Comparison Benchmark

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

## Helpful Shell Wrappers

- [`scripts/run_kspwlo_single.sh`](../scripts/run_kspwlo_single.sh)
- [`scripts/run_kspwlo_mode_compare.sh`](../scripts/run_kspwlo_mode_compare.sh)

## Expected Data Input

所有 routing 題目都預期 `--data` 指向：

- [`data/processed/algorithm_ready`](../data/processed/algorithm_ready)

如果你改用別的資料夾，至少要保證其中包含：

- graph-ready nodes
- segments
- directed edges
- 主要欄位與目前 config 相容
