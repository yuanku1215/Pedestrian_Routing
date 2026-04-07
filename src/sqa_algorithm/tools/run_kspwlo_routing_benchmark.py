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
DEFAULT_OUTPUT_ROOT = ROOT / "outputs" / "kspwlo_routing" / "benchmarks"
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


def _run_job(
    job: Dict,
    run_py: Path,
    data_dir: Path,
    steps: int,
    replicas: int,
    slices: int,
    beta_init: float,
    beta_final: float,
    gamma_init: float,
    gamma_final: float,
) -> Dict:
    cmd = [
        sys.executable,
        str(run_py),
        "--rule",
        "kspwlo_routing",
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


def _build_summary_rows(run_jobs: List[Dict], k_paths: int) -> List[Dict]:
    rows = []
    for job in run_jobs:
        result_path = job["output_dir"] / "result.json"
        with result_path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        baseline = data.get("baseline_penalty_heuristic", {})
        comparison = data.get("comparison_to_baseline_heuristic", {})
        constraint = data.get("constraint_diagnostics", {})
        pairwise = data.get("pairwise_similarity", [])

        baseline_paths = baseline.get("paths", [])
        baseline_total_cost = _safe_float(baseline.get("total_route_cost"))
        baseline_total_length = _safe_float(baseline.get("total_route_length"))
        baseline_k_found = int(baseline.get("k_paths_found", 0))
        baseline_max_similarity = max((float(item.get("similarity", 0.0)) for item in baseline.get("pairwise_similarity", [])), default=0.0)
        baseline_within_theta = all(bool(item.get("within_threshold", False)) for item in baseline.get("pairwise_similarity", []))

        sqa_all_paths_found = bool(data.get("route_found"))
        sqa_total_cost = _safe_float(data.get("decoded_route_cost")) if sqa_all_paths_found else None
        sqa_total_length = _safe_float(data.get("decoded_route_length")) if sqa_all_paths_found else None
        sqa_cost_gap = None if sqa_total_cost is None or baseline_total_cost is None else float(sqa_total_cost) - float(baseline_total_cost)
        sqa_max_similarity = max((float(item.get("similarity", 0.0)) for item in pairwise), default=0.0)
        sqa_max_shared_weight = max((float(item.get("shared_weight", 0.0)) for item in pairwise), default=0.0)
        sqa_within_theta = bool(constraint.get("pairwise_similarity_within_threshold", False))
        sqa_within_hard_budget = bool(constraint.get("pairwise_hard_budget_within_cap", False))
        sqa_within_pathwise_ratio = bool(constraint.get("pairwise_pathwise_ratio_within_cap", False))
        feasible = bool(sqa_all_paths_found and sqa_within_theta and sqa_within_hard_budget and sqa_within_pathwise_ratio)

        if not sqa_all_paths_found:
            primary_outcome = "no_route"
        elif not sqa_within_theta or not sqa_within_hard_budget or not sqa_within_pathwise_ratio:
            primary_outcome = "infeasible"
        elif sqa_cost_gap is not None and sqa_cost_gap < -1e-9:
            primary_outcome = "win"
        elif bool(comparison.get("matches_exact_set")) or (sqa_cost_gap is not None and abs(sqa_cost_gap) <= 1e-9):
            primary_outcome = "tie"
        else:
            primary_outcome = "loss"

        rows.append(
            {
                "scenario_name": job["scenario_name"],
                "distance_label": job["distance_label"],
                "target_distance_m": job["target_distance_m"],
                "straight_line_distance_m": job["straight_line_distance_m"],
                "source_node": job["source_node"],
                "target_node": job["target_node"],
                "walkability_field": job["walkability_field"],
                "day_type": job["day_type"],
                "hour": job["hour"],
                "warm_start_enabled": job["warm_start_enabled"],
                "hard_overlap_mode": job["hard_overlap_mode"],
                "seed_index": job["seed_index"],
                "seed": job["seed"],
                "steps": job["steps"],
                "replicas": job["replicas"],
                "slices": job["slices"],
                "duration_sec": job["duration_sec"],
                "baseline_k_paths_found": baseline_k_found,
                "baseline_total_cost": baseline_total_cost,
                "baseline_total_length": baseline_total_length,
                "baseline_max_similarity": baseline_max_similarity,
                "baseline_within_theta": baseline_within_theta,
                "sqa_all_paths_found": sqa_all_paths_found,
                "sqa_total_cost": sqa_total_cost,
                "sqa_total_length": sqa_total_length,
                "sqa_selected_edge_count": data.get("selected_edge_count"),
                "sqa_max_similarity": sqa_max_similarity,
                "sqa_max_shared_weight": sqa_max_shared_weight,
                "sqa_within_theta": sqa_within_theta,
                "sqa_within_hard_budget": sqa_within_hard_budget,
                "sqa_within_pathwise_ratio": sqa_within_pathwise_ratio,
                "sqa_feasible": feasible,
                "sqa_matches_baseline_set": comparison.get("matches_exact_set"),
                "sqa_total_cost_gap_vs_baseline": sqa_cost_gap,
                "k_paths_requested": k_paths,
                "run_dir": str(job["output_dir"]),
                "log_file": str(job["log_file"]),
                "primary_outcome": primary_outcome,
            }
        )
    return rows


def _aggregate_counts(rows: List[Dict], group_keys: Sequence[str]) -> List[Dict]:
    groups = defaultdict(Counter)
    for row in rows:
        key = tuple(row[group_key] for group_key in group_keys)
        groups[key][row["primary_outcome"]] += 1

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
                "infeasible": counter.get("infeasible", 0),
            }
        )
        results.append(row)
    return results


def _group_statistics(rows: List[Dict], group_keys: Sequence[str]) -> List[Dict]:
    groups: Dict[Tuple, List[Dict]] = defaultdict(list)
    for row in rows:
        groups[tuple(row[key] for key in group_keys)].append(row)

    stats = []
    for key in sorted(groups.keys()):
        group_rows = groups[key]
        cost_gaps = [row["sqa_total_cost_gap_vs_baseline"] for row in group_rows if row["sqa_total_cost_gap_vs_baseline"] is not None]
        similarities = [row["sqa_max_similarity"] for row in group_rows if row["sqa_max_similarity"] is not None]
        entry = {group_keys[idx]: key[idx] for idx in range(len(group_keys))}
        entry.update(
            {
                "total_runs": len(group_rows),
                "feasible_runs": sum(1 for row in group_rows if row["sqa_feasible"]),
                "within_theta_runs": sum(1 for row in group_rows if row["sqa_within_theta"]),
                "within_hard_budget_runs": sum(1 for row in group_rows if row["sqa_within_hard_budget"]),
                "within_pathwise_ratio_runs": sum(1 for row in group_rows if row["sqa_within_pathwise_ratio"]),
                "wins": sum(1 for row in group_rows if row["primary_outcome"] == "win"),
                "ties": sum(1 for row in group_rows if row["primary_outcome"] == "tie"),
                "losses": sum(1 for row in group_rows if row["primary_outcome"] == "loss"),
                "no_route_runs": sum(1 for row in group_rows if row["primary_outcome"] == "no_route"),
                "infeasible_runs": sum(1 for row in group_rows if row["primary_outcome"] == "infeasible"),
                "mean_cost_gap_vs_baseline": float(np.mean(cost_gaps)) if cost_gaps else None,
                "mean_max_similarity": float(np.mean(similarities)) if similarities else None,
            }
        )
        stats.append(entry)
    return stats


def _plot_suite_overview(rows: List[Dict], output_path: Path) -> None:
    outcome_order = ["win", "tie", "loss", "no_route", "infeasible"]
    colors = {
        "win": "#2a9d8f",
        "tie": "#457b9d",
        "loss": "#e76f51",
        "no_route": "#6c757d",
        "infeasible": "#b56576",
    }

    distance_order = sorted({row["distance_label"] for row in rows})
    counts = {distance: Counter() for distance in distance_order}
    for row in rows:
        counts[row["distance_label"]][row["primary_outcome"]] += 1

    fig, axes = plt.subplots(2, 2, figsize=(15, 10))

    x = np.arange(len(distance_order))
    bottom = np.zeros(len(distance_order))
    for outcome in outcome_order:
        values = np.array([counts[distance].get(outcome, 0) for distance in distance_order], dtype=float)
        axes[0, 0].bar(x, values, bottom=bottom, label=outcome, color=colors[outcome])
        bottom += values
    axes[0, 0].set_xticks(x)
    axes[0, 0].set_xticklabels(distance_order)
    axes[0, 0].set_ylabel("Run Count")
    axes[0, 0].set_title("Outcomes by Distance")
    axes[0, 0].legend()

    gap_data = []
    labels = []
    for distance in distance_order:
        values = [
            row["sqa_total_cost_gap_vs_baseline"]
            for row in rows
            if row["distance_label"] == distance and row["sqa_total_cost_gap_vs_baseline"] is not None
        ]
        gap_data.append(values if values else [np.nan])
        labels.append(distance)
    axes[0, 1].boxplot(gap_data, tick_labels=labels, showfliers=False)
    axes[0, 1].axhline(0.0, color="black", lw=1)
    axes[0, 1].set_ylabel("Total Cost Gap vs Baseline")
    axes[0, 1].set_title("Cost Gap by Distance")

    time_fields = sorted({row["walkability_field"] for row in rows})
    feasible_rates = []
    for field in time_fields:
        field_rows = [row for row in rows if row["walkability_field"] == field]
        feasible_rates.append(sum(1 for row in field_rows if row["sqa_feasible"]) / max(len(field_rows), 1))
    axes[1, 0].bar(np.arange(len(time_fields)), feasible_rates, color="#577590")
    axes[1, 0].set_xticks(np.arange(len(time_fields)))
    axes[1, 0].set_xticklabels(time_fields, rotation=45, ha="right")
    axes[1, 0].set_ylim(0.0, 1.05)
    axes[1, 0].set_ylabel("Feasible Rate")
    axes[1, 0].set_title("Feasible Rate by Time Slice")

    similarity_data = []
    similarity_labels = []
    for distance in distance_order:
        values = [row["sqa_max_similarity"] for row in rows if row["distance_label"] == distance]
        similarity_data.append(values if values else [np.nan])
        similarity_labels.append(distance)
    axes[1, 1].boxplot(similarity_data, tick_labels=similarity_labels, showfliers=False)
    axes[1, 1].axhline(0.5, color="firebrick", lw=1, linestyle="--")
    axes[1, 1].set_ylabel("Max Pairwise Similarity")
    axes[1, 1].set_title("Similarity by Distance")

    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description="Formal benchmark for kSPwLO routing across time slices and OD distances")
    parser.add_argument("--data", type=str, default=str(DEFAULT_DATA_DIR))
    parser.add_argument("--suite-name", type=str, default="hard_theta_suite")
    parser.add_argument("--suite-dir", type=str, default="", help="If set, write benchmark directly into this directory.")
    parser.add_argument("--output-root", type=str, default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--steps", type=int, default=200)
    parser.add_argument("--replicas", type=int, default=32)
    parser.add_argument("--slices", type=int, default=20)
    parser.add_argument("--beta-init", type=float, default=0.2)
    parser.add_argument("--beta-final", type=float, default=4.0)
    parser.add_argument("--gamma-init", type=float, default=3.0)
    parser.add_argument("--gamma-final", type=float, default=0.2)
    parser.add_argument("--seed-base", type=int, default=42)
    parser.add_argument("--num-seeds", type=int, default=5)
    parser.add_argument("--jobs", type=int, default=max(1, min(6, os.cpu_count() or 1)))
    parser.add_argument("--distances", type=float, nargs="+", default=[400.0, 800.0, 1200.0])
    parser.add_argument("--time-slice-fields", nargs="+", default=TIME_SLICE_FIELDS)
    parser.add_argument("--warm-start", choices=["on", "off"], default="on")
    parser.add_argument(
        "--hard-overlap-mode",
        choices=["budget", "pathwise_ratio", "budget_plus_ratio", "soft"],
        default="budget_plus_ratio",
    )
    args = parser.parse_args()

    if not (1 <= args.num_seeds <= 10):
        raise ValueError(f"num-seeds should be between 1 and 10 for this benchmark, got {args.num_seeds}")

    data_dir = Path(args.data).resolve()
    directed_path = data_dir / "directed_edges_main_component.geojson"
    segments_path = data_dir / "segments_main_component.geojson"
    config_path = ROOT / "rules" / "kspwlo_routing" / "config.yaml"
    run_py = ROOT / "run.py"

    segments_gdf = gpd.read_file(segments_path)
    directed_gdf = gpd.read_file(directed_path)
    node_coords = _extract_node_coords(segments_gdf)
    od_pairs = _select_od_pairs(node_coords=node_coords, targets=args.distances, rng_seed=args.seed_base)

    output_root = Path(args.output_root).resolve()
    if args.suite_dir:
        suite_dir = Path(args.suite_dir).resolve()
        if suite_dir.exists():
            raise FileExistsError(f"suite-dir already exists: {suite_dir}")
    else:
        suite_dir = _next_suite_dir(output_root, args.suite_name)
    runs_dir = suite_dir / "runs"
    configs_dir = suite_dir / "configs"
    summary_dir = suite_dir / "summary"
    logs_dir = suite_dir / "logs"
    for path in (suite_dir, runs_dir, configs_dir, summary_dir, logs_dir):
        path.mkdir(parents=True, exist_ok=True)

    _write_rows(suite_dir / "od_pairs.csv", od_pairs)
    _make_od_geojson(suite_dir, od_pairs, str(segments_gdf.crs))

    base_config = _load_base_config(config_path)
    k_paths = int(base_config.get("k_paths", 2))
    for field in args.time_slice_fields:
        if field not in directed_gdf.columns:
            raise ValueError(f"Missing walkability field in directed edges: {field}")

    manifest = {
        "suite_dir": str(suite_dir),
        "created_at": datetime.now().isoformat(),
        "data_dir": str(data_dir),
        "rule": "kspwlo_routing",
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
        "k_paths": k_paths,
        "warm_start_enabled": bool(args.warm_start == "on"),
        "hard_overlap_mode": args.hard_overlap_mode,
        "theta_overlap": base_config.get("theta_overlap"),
        "epsilon_near_shortest": base_config.get("epsilon_near_shortest"),
        "use_hard_overlap_budget": base_config.get("use_hard_overlap_budget"),
        "hard_overlap_budget_resolution": base_config.get("hard_overlap_budget_resolution"),
        "notes": "Formal benchmark for kSPwLO-style SQA with warm-start control and configurable hard overlap mode.",
    }
    _write_json(suite_dir / "benchmark_manifest.json", manifest)

    scenarios = []
    run_jobs = []
    for od in od_pairs:
        for field in args.time_slice_fields:
            day_type, hour = _parse_time_slice(field)
            scenario_name = _scenario_name(od["distance_label"], field)
            scenario_dir = runs_dir / scenario_name
            scenario_config = dict(base_config)
            scenario_config.update(
                {
                    "source_coord": [od["source_xy"][0], od["source_xy"][1]],
                    "target_coord": [od["target_xy"][0], od["target_xy"][1]],
                    "coord_crs": str(segments_gdf.crs),
                    "walkability_field": field,
                    "use_penalty_baseline_warm_start": bool(args.warm_start == "on"),
                    "hard_overlap_mode": args.hard_overlap_mode,
                }
            )
            config_file = configs_dir / f"{scenario_name}.yaml"
            with config_file.open("w", encoding="utf-8") as f:
                yaml.safe_dump(scenario_config, f, allow_unicode=True, sort_keys=False)

            scenario_row = {
                "scenario_name": scenario_name,
                "distance_label": od["distance_label"],
                "target_distance_m": od["target_distance_m"],
                "straight_line_distance_m": od["straight_line_distance_m"],
                "source_node": od["source_node"],
                "target_node": od["target_node"],
                "walkability_field": field,
                "day_type": day_type,
                "hour": hour,
                "warm_start_enabled": bool(args.warm_start == "on"),
                "hard_overlap_mode": args.hard_overlap_mode,
                "config_file": str(config_file),
                "scenario_dir": str(scenario_dir),
            }
            scenarios.append(scenario_row)

            for seed_index in range(args.num_seeds):
                seed_value = args.seed_base + seed_index
                run_name = f"seed_{seed_value:03d}"
                output_dir = scenario_dir / run_name
                log_file = logs_dir / f"{scenario_name}__{run_name}.log"
                run_jobs.append(
                    {
                        "scenario_name": scenario_name,
                        "distance_label": od["distance_label"],
                        "target_distance_m": od["target_distance_m"],
                        "straight_line_distance_m": od["straight_line_distance_m"],
                        "source_node": od["source_node"],
                        "target_node": od["target_node"],
                        "walkability_field": field,
                        "day_type": day_type,
                        "hour": hour,
                        "warm_start_enabled": bool(args.warm_start == "on"),
                        "hard_overlap_mode": args.hard_overlap_mode,
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
    print(f"Running {total_jobs} kSPwLO jobs with {args.jobs} workers")
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
            tag = f"{result['scenario_name']} / seed={result['seed']}"
            if result["return_code"] != 0:
                failed_jobs.append(result)
                print(f"[{idx:03d}/{total_jobs}] FAIL {tag} ({result['duration_sec']:.2f}s)")
            else:
                print(f"[{idx:03d}/{total_jobs}] OK   {tag} ({result['duration_sec']:.2f}s)")

    completed_jobs.sort(key=lambda job: (job["scenario_name"], job["seed_index"]))
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

    summary_rows = _build_summary_rows([job for job in completed_jobs if job["return_code"] == 0], k_paths=k_paths)
    _write_rows(summary_dir / "all_runs_summary.csv", summary_rows)

    overall_counts = _aggregate_counts(summary_rows, group_keys=["distance_label"])
    time_counts = _aggregate_counts(summary_rows, group_keys=["walkability_field"])
    distance_stats = _group_statistics(summary_rows, group_keys=["distance_label"])
    timeslice_stats = _group_statistics(summary_rows, group_keys=["walkability_field"])
    mode_stats = _group_statistics(summary_rows, group_keys=["warm_start_enabled", "hard_overlap_mode"])

    _write_rows(summary_dir / "distance_outcomes.csv", overall_counts)
    _write_rows(summary_dir / "timeslice_outcomes.csv", time_counts)
    _write_rows(summary_dir / "distance_statistics.csv", distance_stats)
    _write_rows(summary_dir / "timeslice_statistics.csv", timeslice_stats)
    _write_rows(summary_dir / "mode_statistics.csv", mode_stats)

    overall_statistics = {
        "total_runs": len(summary_rows),
        "feasible_runs": sum(1 for row in summary_rows if row["sqa_feasible"]),
        "wins": sum(1 for row in summary_rows if row["primary_outcome"] == "win"),
        "ties": sum(1 for row in summary_rows if row["primary_outcome"] == "tie"),
        "losses": sum(1 for row in summary_rows if row["primary_outcome"] == "loss"),
        "no_route_runs": sum(1 for row in summary_rows if row["primary_outcome"] == "no_route"),
        "infeasible_runs": sum(1 for row in summary_rows if row["primary_outcome"] == "infeasible"),
        "mean_duration_sec": float(np.mean([row["duration_sec"] for row in summary_rows])) if summary_rows else None,
        "mean_cost_gap_vs_baseline": float(np.mean([row["sqa_total_cost_gap_vs_baseline"] for row in summary_rows if row["sqa_total_cost_gap_vs_baseline"] is not None])) if summary_rows else None,
        "mean_max_similarity": float(np.mean([row["sqa_max_similarity"] for row in summary_rows])) if summary_rows else None,
        "manifest": str(suite_dir / "benchmark_manifest.json"),
    }
    _write_json(summary_dir / "overall_statistics.json", overall_statistics)
    _plot_suite_overview(summary_rows, summary_dir / "benchmark_overview.png")

    print(f"Benchmark completed. Summary written to {summary_dir}")


if __name__ == "__main__":
    main()
