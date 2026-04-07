import argparse
import csv
import json
import os
import subprocess
import sys
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

import geopandas as gpd
import matplotlib
import numpy as np
import yaml
from shapely.geometry import LineString, Point

matplotlib.use("Agg")
import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = ROOT.parent / "303_demo_data" / "sidewalks" / "algorithm_ready"
DEFAULT_OUTPUT_ROOT = ROOT / "outputs" / "path_routing" / "benchmarks"
TIME_SLICE_FIELDS = [
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
]
MODE_SETTINGS = {
    "pure_sqa": {
        "description": "Random initialized SQA only",
        "config_updates": {
            "use_dijkstra_warm_start": False,
            "enable_path_local_search": False,
        },
        "primary_stage": "sqa",
    },
    "baseline_warm_start": {
        "description": "SQA with Dijkstra warm start",
        "config_updates": {
            "use_dijkstra_warm_start": True,
            "enable_path_local_search": False,
        },
        "primary_stage": "sqa",
    },
    "baseline_plus_block_move": {
        "description": "Dijkstra warm start plus baseline seeded block-move local search",
        "config_updates": {
            "use_dijkstra_warm_start": True,
            "enable_path_local_search": True,
            "path_local_search_seed_mode": "baseline_only",
        },
        "primary_stage": "local_search",
    },
}


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


def _extract_node_coords(segments_gdf: gpd.GeoDataFrame) -> Dict[int, Tuple[float, float]]:
    node_coords: Dict[int, Tuple[float, float]] = {}
    for row in segments_gdf.itertuples(index=False):
        geom = row.geometry
        if geom is None or geom.is_empty:
            continue
        coords = list(geom.coords)
        if len(coords) < 2:
            continue
        node_coords[int(row.source_node)] = (float(coords[0][0]), float(coords[0][1]))
        node_coords[int(row.target_node)] = (float(coords[-1][0]), float(coords[-1][1]))
    return node_coords


def _select_od_pairs(
    node_coords: Dict[int, Tuple[float, float]],
    targets: Sequence[float],
    rng_seed: int,
) -> List[Dict]:
    node_items = sorted(node_coords.items())
    node_ids = np.array([item[0] for item in node_items], dtype=int)
    xy = np.array([item[1] for item in node_items], dtype=float)
    deltas = xy[:, None, :] - xy[None, :, :]
    distances = np.sqrt(np.sum(deltas * deltas, axis=2))
    triu_i, triu_j = np.triu_indices(len(node_ids), k=1)

    all_candidates = []
    for idx_i, idx_j, dist in zip(triu_i, triu_j, distances[triu_i, triu_j]):
        if dist < 1.0:
            continue
        all_candidates.append(
            {
                "source_node": int(node_ids[idx_i]),
                "target_node": int(node_ids[idx_j]),
                "source_xy": (float(xy[idx_i][0]), float(xy[idx_i][1])),
                "target_xy": (float(xy[idx_j][0]), float(xy[idx_j][1])),
                "straight_line_distance_m": float(dist),
            }
        )

    rng = np.random.default_rng(rng_seed)
    used_nodes = set()
    selected = []
    for target in targets:
        ranked = sorted(
            (
                {
                    **candidate,
                    "distance_gap_m": float(abs(candidate["straight_line_distance_m"] - target)),
                }
                for candidate in all_candidates
            ),
            key=lambda row: row["distance_gap_m"],
        )
        pool = [
            row
            for row in ranked[:200]
            if row["source_node"] not in used_nodes and row["target_node"] not in used_nodes
        ]
        if not pool:
            pool = ranked[:50]
        choice = dict(pool[int(rng.integers(0, len(pool)))])
        used_nodes.add(choice["source_node"])
        used_nodes.add(choice["target_node"])
        choice["target_distance_m"] = int(target)
        choice["distance_label"] = f"d{int(target):04d}"
        selected.append(choice)
    return selected


def _parse_time_slice(field: str) -> Tuple[str, str]:
    return ("weekday" if "wd" in field else "weekend", field[-2:])


def _load_base_config(path: Path) -> Dict:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _scenario_name(distance_label: str, walkability_field: str) -> str:
    return f"{distance_label}_{walkability_field}"


def _make_od_geojson(suite_dir: Path, od_pairs: List[Dict], crs: str) -> None:
    point_rows = []
    line_rows = []
    for row in od_pairs:
        pair_id = row["distance_label"]
        sx, sy = row["source_xy"]
        tx, ty = row["target_xy"]
        point_rows.append(
            {
                "pair_id": pair_id,
                "role": "source",
                "node_id": row["source_node"],
                "target_distance_m": row["target_distance_m"],
                "straight_line_distance_m": row["straight_line_distance_m"],
                "geometry": Point(sx, sy),
            }
        )
        point_rows.append(
            {
                "pair_id": pair_id,
                "role": "target",
                "node_id": row["target_node"],
                "target_distance_m": row["target_distance_m"],
                "straight_line_distance_m": row["straight_line_distance_m"],
                "geometry": Point(tx, ty),
            }
        )
        line_rows.append(
            {
                "pair_id": pair_id,
                "target_distance_m": row["target_distance_m"],
                "straight_line_distance_m": row["straight_line_distance_m"],
                "geometry": LineString([(sx, sy), (tx, ty)]),
            }
        )

    gpd.GeoDataFrame(point_rows, geometry="geometry", crs=crs).to_file(
        suite_dir / "od_points.geojson",
        driver="GeoJSON",
    )
    gpd.GeoDataFrame(line_rows, geometry="geometry", crs=crs).to_file(
        suite_dir / "od_pairs.geojson",
        driver="GeoJSON",
    )


def _safe_float(value):
    return None if value in ("", None) else float(value)


def _run_job(job: Dict, run_py: Path, data_dir: Path, steps: int, replicas: int, slices: int, beta_init: float, beta_final: float, gamma_init: float, gamma_final: float) -> Dict:
    cmd = [
        sys.executable,
        str(run_py),
        "--rule",
        "path_routing",
        "--data",
        str(data_dir),
        "--config",
        str(job["config_file"]),
        "--steps",
        str(steps),
        "--replicas",
        str(replicas),
        "--slices",
        str(slices),
        "--beta-init",
        str(beta_init),
        "--beta-final",
        str(beta_final),
        "--gamma-init",
        str(gamma_init),
        "--gamma-final",
        str(gamma_final),
        "--seed",
        str(job["seed"]),
        "--output-dir",
        str(job["output_dir"]),
    ]
    job["log_file"].parent.mkdir(parents=True, exist_ok=True)
    start = time.perf_counter()
    with job["log_file"].open("w", encoding="utf-8") as log_f:
        proc = subprocess.run(
            cmd,
            cwd=str(ROOT),
            stdout=log_f,
            stderr=subprocess.STDOUT,
        )
    duration = time.perf_counter() - start
    result = dict(job)
    result["duration_sec"] = round(duration, 3)
    result["return_code"] = int(proc.returncode)
    return result


def _primary_metrics(row: Dict) -> Tuple[bool, float, bool, str]:
    primary_stage = row["mode_primary_stage"]
    if primary_stage == "local_search":
        route_found = row["local_search_status"] == "completed" and row["local_search_route_cost"] is not None
        cost_gap = row["local_search_cost_gap_vs_baseline"]
        matches_baseline = bool(row["local_search_matches_baseline_route"])
    else:
        route_found = bool(row["sqa_route_found"])
        cost_gap = row["sqa_cost_gap_vs_baseline"]
        matches_baseline = bool(row["sqa_matches_baseline_route"])
    return route_found, cost_gap, matches_baseline, primary_stage


def _build_summary_rows(run_jobs: List[Dict]) -> List[Dict]:
    rows = []
    for job in run_jobs:
        result_path = job["output_dir"] / "result.json"
        with result_path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        baseline = data.get("baseline_dijkstra", {})
        comparison = data.get("comparison_to_dijkstra", {})
        local_search = data.get("path_local_search", {})

        baseline_cost = _safe_float(baseline.get("route_cost"))
        sqa_route_found = bool(data.get("route_found"))
        sqa_cost = _safe_float(data.get("decoded_route_cost")) if sqa_route_found else None
        sqa_length = _safe_float(data.get("decoded_route_length")) if sqa_route_found else None
        sqa_cost_gap = None if sqa_cost is None or baseline_cost is None else float(sqa_cost) - float(baseline_cost)

        local_search_status = local_search.get("status")
        if local_search_status == "completed":
            local_best = local_search.get("best_route", {})
            local_search_cost = _safe_float(local_best.get("route_cost"))
            local_search_length = _safe_float(local_best.get("route_length"))
            local_search_cost_gap = None if local_search_cost is None or baseline_cost is None else float(local_search_cost) - float(baseline_cost)
            local_search_matches = local_search.get("comparison", {}).get("best_matches_baseline_route")
        else:
            local_search_cost = None
            local_search_length = None
            local_search_cost_gap = None
            local_search_matches = None

        row = {
            "mode": job["mode"],
            "mode_description": MODE_SETTINGS[job["mode"]]["description"],
            "mode_primary_stage": MODE_SETTINGS[job["mode"]]["primary_stage"],
            "scenario_name": job["scenario_name"],
            "distance_label": job["distance_label"],
            "target_distance_m": job["target_distance_m"],
            "straight_line_distance_m": job["straight_line_distance_m"],
            "source_node": job["source_node"],
            "target_node": job["target_node"],
            "walkability_field": job["walkability_field"],
            "day_type": job["day_type"],
            "hour": job["hour"],
            "seed_index": job["seed_index"],
            "seed": job["seed"],
            "steps": job["steps"],
            "replicas": job["replicas"],
            "slices": job["slices"],
            "duration_sec": job["duration_sec"],
            "baseline_route_found": baseline.get("route_found"),
            "baseline_route_cost": baseline_cost,
            "baseline_route_length": _safe_float(baseline.get("route_length")),
            "sqa_route_found": sqa_route_found,
            "sqa_route_cost": sqa_cost,
            "sqa_route_length": sqa_length,
            "sqa_selected_edge_count": data.get("selected_edge_count"),
            "sqa_matches_baseline_route": comparison.get("matches_exact_route"),
            "sqa_cost_gap_vs_baseline": sqa_cost_gap,
            "local_search_status": local_search_status,
            "local_search_route_cost": local_search_cost,
            "local_search_route_length": local_search_length,
            "local_search_cost_gap_vs_baseline": local_search_cost_gap,
            "local_search_matches_baseline_route": local_search_matches,
            "run_dir": str(job["output_dir"]),
            "log_file": str(job["log_file"]),
        }
        route_found, primary_cost_gap, matches_baseline, primary_stage = _primary_metrics(row)
        row["primary_route_found"] = route_found
        row["primary_cost_gap_vs_baseline"] = primary_cost_gap
        row["primary_matches_baseline_route"] = matches_baseline
        row["primary_stage"] = primary_stage
        rows.append(row)
    return rows


def _categorize_summary(rows: List[Dict]) -> None:
    for row in rows:
        sqa_gap = row["sqa_cost_gap_vs_baseline"]
        if row["sqa_route_found"] is not True:
            row["sqa_outcome"] = "no_route"
        elif sqa_gap is not None and sqa_gap < -1e-9:
            row["sqa_outcome"] = "win"
        elif bool(row["sqa_matches_baseline_route"]) or (sqa_gap is not None and abs(sqa_gap) <= 1e-9):
            row["sqa_outcome"] = "tie"
        else:
            row["sqa_outcome"] = "loss"

        ls_status = row["local_search_status"]
        ls_gap = row["local_search_cost_gap_vs_baseline"]
        if ls_status != "completed":
            row["local_search_outcome"] = "skipped"
        elif ls_gap is not None and ls_gap < -1e-9:
            row["local_search_outcome"] = "win"
        elif bool(row["local_search_matches_baseline_route"]) or (ls_gap is not None and abs(ls_gap) <= 1e-9):
            row["local_search_outcome"] = "tie"
        else:
            row["local_search_outcome"] = "loss"

        primary_gap = row["primary_cost_gap_vs_baseline"]
        if row["primary_route_found"] is not True:
            row["primary_outcome"] = "no_route" if row["primary_stage"] == "sqa" else "skipped"
        elif primary_gap is not None and primary_gap < -1e-9:
            row["primary_outcome"] = "win"
        elif bool(row["primary_matches_baseline_route"]) or (primary_gap is not None and abs(primary_gap) <= 1e-9):
            row["primary_outcome"] = "tie"
        else:
            row["primary_outcome"] = "loss"


def _aggregate_counts(rows: List[Dict], group_keys: Sequence[str], outcome_key: str) -> List[Dict]:
    groups = defaultdict(Counter)
    for row in rows:
        key = tuple(row[group_key] for group_key in group_keys)
        groups[key][row[outcome_key]] += 1

    results = []
    for key in sorted(groups.keys()):
        counter = groups[key]
        total = sum(counter.values())
        row = {group_keys[idx]: key[idx] for idx in range(len(group_keys))}
        row.update(
            {
                "total_runs": total,
                "win": counter.get("win", 0),
                "tie": counter.get("tie", 0),
                "loss": counter.get("loss", 0),
                "no_route": counter.get("no_route", 0),
                "skipped": counter.get("skipped", 0),
            }
        )
        results.append(row)
    return results


def _plot_suite_overview(rows: List[Dict], output_path: Path) -> None:
    mode_order = list(MODE_SETTINGS.keys())
    outcome_order = ["win", "tie", "loss", "no_route", "skipped"]
    colors = {
        "win": "#2a9d8f",
        "tie": "#457b9d",
        "loss": "#e76f51",
        "no_route": "#6c757d",
        "skipped": "#adb5bd",
    }

    counts = {mode: Counter() for mode in mode_order}
    for row in rows:
        counts[row["mode"]][row["primary_outcome"]] += 1

    fig, axes = plt.subplots(2, 1, figsize=(14, 10))

    bottom = np.zeros(len(mode_order))
    x = np.arange(len(mode_order))
    for outcome in outcome_order:
        values = np.array([counts[mode].get(outcome, 0) for mode in mode_order], dtype=float)
        axes[0].bar(x, values, bottom=bottom, label=outcome, color=colors[outcome])
        bottom += values
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(mode_order)
    axes[0].set_ylabel("Run Count")
    axes[0].set_title("Primary Outcomes by Mode")
    axes[0].legend()

    gap_data = []
    labels = []
    for mode in mode_order:
        values = [
            row["primary_cost_gap_vs_baseline"]
            for row in rows
            if row["mode"] == mode and row["primary_cost_gap_vs_baseline"] is not None
        ]
        gap_data.append(values if values else [np.nan])
        labels.append(mode)
    axes[1].boxplot(gap_data, labels=labels, showfliers=False)
    axes[1].axhline(0.0, color="black", lw=1)
    axes[1].set_ylabel("Primary Cost Gap vs Baseline")
    axes[1].set_title("Primary Cost Gap Distribution")

    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description="Formal benchmark for path routing modes, time slices, and OD distances")
    parser.add_argument("--data", type=str, default=str(DEFAULT_DATA_DIR))
    parser.add_argument("--suite-name", type=str, default="formal_modes_suite")
    parser.add_argument("--steps", type=int, default=200)
    parser.add_argument("--replicas", type=int, default=32)
    parser.add_argument("--slices", type=int, default=20)
    parser.add_argument("--beta-init", type=float, default=0.2)
    parser.add_argument("--beta-final", type=float, default=4.0)
    parser.add_argument("--gamma-init", type=float, default=3.0)
    parser.add_argument("--gamma-final", type=float, default=0.2)
    parser.add_argument("--seed-base", type=int, default=42)
    parser.add_argument("--num-seeds", type=int, default=5)
    parser.add_argument("--jobs", type=int, default=max(1, min(4, os.cpu_count() or 1)))
    parser.add_argument("--distances", type=float, nargs="+", default=[400.0, 800.0, 1200.0])
    parser.add_argument("--time-slice-fields", nargs="+", default=TIME_SLICE_FIELDS)
    parser.add_argument("--modes", nargs="+", default=list(MODE_SETTINGS.keys()))
    args = parser.parse_args()

    if not (5 <= args.num_seeds <= 10):
        raise ValueError(f"num-seeds should be between 5 and 10 for this benchmark, got {args.num_seeds}")

    invalid_modes = [mode for mode in args.modes if mode not in MODE_SETTINGS]
    if invalid_modes:
        raise ValueError(f"Unknown modes requested: {invalid_modes}")

    data_dir = Path(args.data).resolve()
    directed_path = data_dir / "directed_edges_main_component.geojson"
    segments_path = data_dir / "segments_main_component.geojson"
    config_path = ROOT / "rules" / "path_routing" / "config.yaml"
    run_py = ROOT / "run.py"

    segments_gdf = gpd.read_file(segments_path)
    directed_gdf = gpd.read_file(directed_path)
    node_coords = _extract_node_coords(segments_gdf)
    od_pairs = _select_od_pairs(node_coords=node_coords, targets=args.distances, rng_seed=args.seed_base)

    suite_dir = _next_suite_dir(DEFAULT_OUTPUT_ROOT, args.suite_name)
    runs_dir = suite_dir / "runs"
    configs_dir = suite_dir / "configs"
    summary_dir = suite_dir / "summary"
    logs_dir = suite_dir / "logs"
    for path in (suite_dir, runs_dir, configs_dir, summary_dir, logs_dir):
        path.mkdir(parents=True, exist_ok=True)

    _write_rows(suite_dir / "od_pairs.csv", od_pairs)
    _make_od_geojson(suite_dir, od_pairs, str(segments_gdf.crs))

    base_config = _load_base_config(config_path)
    for field in args.time_slice_fields:
        if field not in directed_gdf.columns:
            raise ValueError(f"Missing walkability field in directed edges: {field}")

    manifest = {
        "suite_dir": str(suite_dir),
        "created_at": datetime.now().isoformat(),
        "data_dir": str(data_dir),
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
        "modes": {
            mode: {
                "description": MODE_SETTINGS[mode]["description"],
                "config_updates": MODE_SETTINGS[mode]["config_updates"],
                "primary_stage": MODE_SETTINGS[mode]["primary_stage"],
            }
            for mode in args.modes
        },
        "notes": "Formal benchmark with three mode variants and multiple random seeds.",
    }
    _write_json(suite_dir / "benchmark_manifest.json", manifest)

    scenarios = []
    run_jobs = []
    for mode in args.modes:
        mode_config_dir = configs_dir / mode
        mode_config_dir.mkdir(parents=True, exist_ok=True)
        for od in od_pairs:
            for field in args.time_slice_fields:
                day_type, hour = _parse_time_slice(field)
                scenario_name = _scenario_name(od["distance_label"], field)
                scenario_dir = runs_dir / mode / scenario_name
                scenario_config = dict(base_config)
                scenario_config.update(
                    {
                        "source_coord": [od["source_xy"][0], od["source_xy"][1]],
                        "target_coord": [od["target_xy"][0], od["target_xy"][1]],
                        "coord_crs": str(segments_gdf.crs),
                        "walkability_field": field,
                        **MODE_SETTINGS[mode]["config_updates"],
                    }
                )
                config_file = mode_config_dir / f"{scenario_name}.yaml"
                with config_file.open("w", encoding="utf-8") as f:
                    yaml.safe_dump(scenario_config, f, allow_unicode=True, sort_keys=False)

                scenario_row = {
                    "mode": mode,
                    "scenario_name": scenario_name,
                    "distance_label": od["distance_label"],
                    "target_distance_m": od["target_distance_m"],
                    "straight_line_distance_m": od["straight_line_distance_m"],
                    "source_node": od["source_node"],
                    "target_node": od["target_node"],
                    "walkability_field": field,
                    "day_type": day_type,
                    "hour": hour,
                    "config_file": str(config_file),
                    "scenario_dir": str(scenario_dir),
                }
                scenarios.append(scenario_row)

                for seed_index in range(args.num_seeds):
                    seed_value = args.seed_base + seed_index
                    run_name = f"seed_{seed_value:03d}"
                    output_dir = scenario_dir / run_name
                    log_file = logs_dir / mode / f"{scenario_name}__{run_name}.log"
                    run_jobs.append(
                        {
                            "mode": mode,
                            "scenario_name": scenario_name,
                            "distance_label": od["distance_label"],
                            "target_distance_m": od["target_distance_m"],
                            "straight_line_distance_m": od["straight_line_distance_m"],
                            "source_node": od["source_node"],
                            "target_node": od["target_node"],
                            "walkability_field": field,
                            "day_type": day_type,
                            "hour": hour,
                            "seed_index": seed_index,
                            "seed": seed_value,
                            "steps": args.steps,
                            "replicas": args.replicas,
                            "slices": args.slices,
                            "config_file": config_file,
                            "output_dir": output_dir,
                            "log_file": log_file,
                        }
                    )

    _write_rows(suite_dir / "scenario_index.csv", scenarios)
    _write_rows(
        suite_dir / "run_index.csv",
        [
            {
                key: (str(value) if isinstance(value, Path) else value)
                for key, value in job.items()
            }
            for job in run_jobs
        ],
    )

    completed_jobs = []
    failed_jobs = []
    total_jobs = len(run_jobs)
    print(f"Running {total_jobs} jobs with {args.jobs} workers")
    with ThreadPoolExecutor(max_workers=args.jobs) as executor:
        future_to_job = {
            executor.submit(
                _run_job,
                job,
                run_py,
                data_dir,
                args.steps,
                args.replicas,
                args.slices,
                args.beta_init,
                args.beta_final,
                args.gamma_init,
                args.gamma_final,
            ): job
            for job in run_jobs
        }
        for idx, future in enumerate(as_completed(future_to_job), start=1):
            result = future.result()
            completed_jobs.append(result)
            tag = f"{result['mode']} / {result['scenario_name']} / seed={result['seed']}"
            if result["return_code"] != 0:
                failed_jobs.append(result)
                print(f"[{idx:03d}/{total_jobs}] FAIL {tag} ({result['duration_sec']:.2f}s)")
            else:
                print(f"[{idx:03d}/{total_jobs}] OK   {tag} ({result['duration_sec']:.2f}s)")

    completed_jobs.sort(key=lambda job: (job["mode"], job["scenario_name"], job["seed_index"]))
    _write_rows(
        suite_dir / "run_index_completed.csv",
        [
            {
                key: (str(value) if isinstance(value, Path) else value)
                for key, value in job.items()
            }
            for job in completed_jobs
        ],
    )

    if failed_jobs:
        _write_rows(
            summary_dir / "failed_runs.csv",
            [
                {
                    key: (str(value) if isinstance(value, Path) else value)
                    for key, value in job.items()
                }
                for job in failed_jobs
            ],
        )
        raise RuntimeError(f"{len(failed_jobs)} benchmark jobs failed. See failed_runs.csv")

    rows = _build_summary_rows(completed_jobs)
    _categorize_summary(rows)
    _write_rows(summary_dir / "all_runs_summary.csv", rows)
    _write_rows(summary_dir / "mode_statistics.csv", _aggregate_counts(rows, ["mode"], "primary_outcome"))
    _write_rows(summary_dir / "mode_distance_statistics.csv", _aggregate_counts(rows, ["mode", "distance_label"], "primary_outcome"))
    _write_rows(summary_dir / "mode_timeslice_statistics.csv", _aggregate_counts(rows, ["mode", "walkability_field"], "primary_outcome"))
    _write_rows(summary_dir / "sqa_mode_statistics.csv", _aggregate_counts(rows, ["mode"], "sqa_outcome"))
    _write_rows(summary_dir / "local_search_mode_statistics.csv", _aggregate_counts(rows, ["mode"], "local_search_outcome"))

    overall_statistics = {
        "total_runs": len(rows),
        "mode_primary_outcomes": {
            mode: dict(Counter(row["primary_outcome"] for row in rows if row["mode"] == mode))
            for mode in args.modes
        },
        "mode_sqa_outcomes": {
            mode: dict(Counter(row["sqa_outcome"] for row in rows if row["mode"] == mode))
            for mode in args.modes
        },
        "mode_local_search_outcomes": {
            mode: dict(Counter(row["local_search_outcome"] for row in rows if row["mode"] == mode))
            for mode in args.modes
        },
        "mean_duration_sec_by_mode": {
            mode: float(np.mean([row["duration_sec"] for row in rows if row["mode"] == mode]))
            for mode in args.modes
        },
        "mean_primary_cost_gap_by_mode": {
            mode: (
                float(np.mean([row["primary_cost_gap_vs_baseline"] for row in rows if row["mode"] == mode and row["primary_cost_gap_vs_baseline"] is not None]))
                if any(row["mode"] == mode and row["primary_cost_gap_vs_baseline"] is not None for row in rows)
                else None
            )
            for mode in args.modes
        },
    }
    _write_json(summary_dir / "overall_statistics.json", overall_statistics)
    _plot_suite_overview(rows, summary_dir / "benchmark_overview.png")

    print(f"Benchmark complete: {suite_dir}")


if __name__ == "__main__":
    main()
