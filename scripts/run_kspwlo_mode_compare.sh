#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

python3 "$ROOT/src/sqa_algorithm/tools/run_kspwlo_mode_comparison.py" \
  --data "$ROOT/data/processed/algorithm_ready" \
  --suite-name mode_compare_formal \
  --steps 60 \
  --replicas 12 \
  --slices 20 \
  --num-seeds 1 \
  --jobs 8
