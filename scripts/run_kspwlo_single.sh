#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

python3 "$ROOT/src/sqa_algorithm/run.py" \
  --rule kspwlo_routing \
  --data "$ROOT/data/processed/algorithm_ready" \
  --steps 60 \
  --replicas 12 \
  --slices 20 \
  --beta-init 0.2 \
  --beta-final 4.0 \
  --gamma-init 3.0 \
  --gamma-final 0.2 \
  --seed 42
