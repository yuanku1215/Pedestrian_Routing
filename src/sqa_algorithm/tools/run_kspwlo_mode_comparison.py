import argparse
import csv
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = ROOT.parent / "303_demo_data" / "sidewalks" / "algorithm_ready"
DEFAULT_OUTPUT_ROOT = ROOT / "outputs" / "kspwlo_routing" / "benchmarks"

DEFAULT_MODES = [
    {
        "mode_name": "budget_warm_on",
        "warm_start": "on",
        "hard_overlap_mode": "budget",
    },
    {
        "mode_name": "budget_warm_off",
        "warm_start": "off",
        "hard_overlap_mode": "budget",
    },
    {
        "mode_name": "budget_plus_ratio_warm_on",
        "warm_start": "on",
        "hard_overlap_mode": "budget_plus_ratio",
    },
    {
        "mode_name": "budget_plus_ratio_warm_off",
        "warm_start": "off",
        "hard_overlap_mode": "budget_plus_ratio",
    },
]


def _write_json(path: Path, payload) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=4, ensure_ascii=False)


def _write_rows(path: Path, rows: List[Dict]) -> None:
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _next_suite_dir(root: Path, suite_name: str) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    idx = 1
    while True:
        candidate = root / f"{suite_name}_{idx:02d}"
        if not candidate.exists():
            return candidate
        idx += 1


def _plot_mode_comparison(rows: List[Dict], output_path: Path) -> None:
    mode_names = [row["mode_name"] for row in rows]
    feasible_rates = [
        (float(row["feasible_runs"]) / float(row["total_runs"])) if row["total_runs"] else 0.0
        for row in rows
    ]
    tie_rates = [
        (float(row["ties"]) / float(row["total_runs"])) if row["total_runs"] else 0.0
        for row in rows
    ]
    no_route_rates = [
        (float(row["no_route_runs"]) / float(row["total_runs"])) if row["total_runs"] else 0.0
        for row in rows
    ]
    mean_gaps = [
        np.nan if row["mean_cost_gap_vs_baseline"] is None else float(row["mean_cost_gap_vs_baseline"])
        for row in rows
    ]

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))

    x = np.arange(len(mode_names))
    axes[0, 0].bar(x, feasible_rates, color="#2a9d8f")
    axes[0, 0].set_xticks(x)
    axes[0, 0].set_xticklabels(mode_names, rotation=20, ha="right")
    axes[0, 0].set_ylim(0.0, 1.05)
    axes[0, 0].set_ylabel("Rate")
    axes[0, 0].set_title("Feasible Rate")

    axes[0, 1].bar(x, tie_rates, color="#457b9d")
    axes[0, 1].set_xticks(x)
    axes[0, 1].set_xticklabels(mode_names, rotation=20, ha="right")
    axes[0, 1].set_ylim(0.0, 1.05)
    axes[0, 1].set_ylabel("Rate")
    axes[0, 1].set_title("Tie Rate vs Baseline")

    axes[1, 0].bar(x, no_route_rates, color="#6c757d")
    axes[1, 0].set_xticks(x)
    axes[1, 0].set_xticklabels(mode_names, rotation=20, ha="right")
    axes[1, 0].set_ylim(0.0, 1.05)
    axes[1, 0].set_ylabel("Rate")
    axes[1, 0].set_title("No-Route Rate")

    axes[1, 1].bar(x, mean_gaps, color="#e76f51")
    axes[1, 1].axhline(0.0, color="black", linewidth=1.0)
    axes[1, 1].set_xticks(x)
    axes[1, 1].set_xticklabels(mode_names, rotation=20, ha="right")
    axes[1, 1].set_ylabel("Cost Gap")
    axes[1, 1].set_title("Mean Cost Gap vs Baseline")

    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare warm-start and overlap-constraint modes for kSPwLO routing")
    parser.add_argument("--data", type=str, default=str(DEFAULT_DATA_DIR))
    parser.add_argument("--suite-name", type=str, default="mode_compare")
    parser.add_argument("--output-root", type=str, default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--steps", type=int, default=60)
    parser.add_argument("--replicas", type=int, default=12)
    parser.add_argument("--slices", type=int, default=20)
    parser.add_argument("--beta-init", type=float, default=0.2)
    parser.add_argument("--beta-final", type=float, default=4.0)
    parser.add_argument("--gamma-init", type=float, default=3.0)
    parser.add_argument("--gamma-final", type=float, default=0.2)
    parser.add_argument("--seed-base", type=int, default=42)
    parser.add_argument("--num-seeds", type=int, default=1)
    parser.add_argument("--jobs", type=int, default=8)
    parser.add_argument("--distances", type=float, nargs="+", default=[400.0, 800.0, 1200.0])
    parser.add_argument(
        "--time-slice-fields",
        nargs="+",
        default=[
            "dynwd05",
            "dynwd08",
            "dynwd12",
            "dynwd17",
            "dynwd21",
            "dynwe05",
            "dynwe08",
            "dynwe12",
            "dynwe17",
            "dynwe21",
        ],
    )
    args = parser.parse_args()

    comparison_dir = _next_suite_dir(Path(args.output_root).resolve(), args.suite_name)
    suites_dir = comparison_dir / "mode_suites"
    summary_dir = comparison_dir / "summary"
    logs_dir = comparison_dir / "driver_logs"
    for path in (comparison_dir, suites_dir, summary_dir, logs_dir):
        path.mkdir(parents=True, exist_ok=True)

    runner = ROOT / "tools" / "run_kspwlo_routing_benchmark.py"
    manifest = {
        "created_at": datetime.now().isoformat(),
        "comparison_dir": str(comparison_dir),
        "data_dir": str(Path(args.data).resolve()),
        "runner": str(runner),
        "steps": args.steps,
        "replicas": args.replicas,
        "slices": args.slices,
        "beta_init": args.beta_init,
        "beta_final": args.beta_final,
        "gamma_init": args.gamma_init,
        "gamma_final": args.gamma_final,
        "seed_base": args.seed_base,
        "num_seeds": args.num_seeds,
        "jobs": args.jobs,
        "distances": list(args.distances),
        "time_slice_fields": list(args.time_slice_fields),
        "modes": DEFAULT_MODES,
    }
    _write_json(comparison_dir / "comparison_manifest.json", manifest)

    overall_rows = []
    distance_rows = []

    for mode in DEFAULT_MODES:
        mode_name = mode["mode_name"]
        suite_dir = suites_dir / mode_name
        log_file = logs_dir / f"{mode_name}.log"
        cmd = [
            sys.executable,
            str(runner),
            "--data",
            str(Path(args.data).resolve()),
            "--suite-dir",
            str(suite_dir),
            "--suite-name",
            mode_name,
            "--steps",
            str(args.steps),
            "--replicas",
            str(args.replicas),
            "--slices",
            str(args.slices),
            "--beta-init",
            str(args.beta_init),
            "--beta-final",
            str(args.beta_final),
            "--gamma-init",
            str(args.gamma_init),
            "--gamma-final",
            str(args.gamma_final),
            "--seed-base",
            str(args.seed_base),
            "--num-seeds",
            str(args.num_seeds),
            "--jobs",
            str(args.jobs),
            "--warm-start",
            mode["warm_start"],
            "--hard-overlap-mode",
            mode["hard_overlap_mode"],
            "--distances",
            *[str(value) for value in args.distances],
            "--time-slice-fields",
            *list(args.time_slice_fields),
        ]
        with log_file.open("w", encoding="utf-8") as log_f:
            proc = subprocess.run(cmd, cwd=str(ROOT), stdout=log_f, stderr=subprocess.STDOUT)
        if proc.returncode != 0:
            raise RuntimeError(f"Mode {mode_name} failed. See {log_file}")

        overall_path = suite_dir / "summary" / "overall_statistics.json"
        distance_path = suite_dir / "summary" / "distance_statistics.csv"
        with overall_path.open("r", encoding="utf-8") as f:
            overall = json.load(f)
        overall_rows.append(
            {
                "mode_name": mode_name,
                "warm_start_enabled": mode["warm_start"] == "on",
                "hard_overlap_mode": mode["hard_overlap_mode"],
                "suite_dir": str(suite_dir),
                "total_runs": overall.get("total_runs"),
                "feasible_runs": overall.get("feasible_runs"),
                "wins": overall.get("wins"),
                "ties": overall.get("ties"),
                "losses": overall.get("losses"),
                "no_route_runs": overall.get("no_route_runs"),
                "infeasible_runs": overall.get("infeasible_runs"),
                "mean_duration_sec": overall.get("mean_duration_sec"),
                "mean_cost_gap_vs_baseline": overall.get("mean_cost_gap_vs_baseline"),
                "mean_max_similarity": overall.get("mean_max_similarity"),
            }
        )

        with distance_path.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                distance_rows.append(
                    {
                        "mode_name": mode_name,
                        "warm_start_enabled": mode["warm_start"] == "on",
                        "hard_overlap_mode": mode["hard_overlap_mode"],
                        **row,
                    }
                )

    _write_rows(summary_dir / "mode_overall_summary.csv", overall_rows)
    _write_rows(summary_dir / "mode_distance_summary.csv", distance_rows)
    _plot_mode_comparison(overall_rows, summary_dir / "mode_comparison.png")

    print(f"Mode comparison completed. Summary written to {summary_dir}")


if __name__ == "__main__":
    main()
