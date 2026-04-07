import argparse
import importlib
import json
import os
import shutil
from datetime import datetime

import geopandas as gpd
import yaml
from shapely.geometry import Point

from engine import SQA_numpy


BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _write_json(path: str, payload) -> None:
    class NumpyEncoder(json.JSONEncoder):
        def default(self, obj):
            if hasattr(obj, "item"):
                return obj.item()
            return super().default(obj)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=4, ensure_ascii=False, cls=NumpyEncoder)


def _write_csv_rows(path: str, rows: list[dict]) -> None:
    import csv

    if not rows:
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _write_geojson_text(path: str, geojson_text: str) -> None:
    if not geojson_text:
        return
    with open(path, "w", encoding="utf-8") as f:
        f.write(geojson_text)


def _build_source_target_gdf(processed_data):
    rows = []
    graph_crs = processed_data.get("graph_crs")
    for role, node_key, coord_key in (
        ("source", "source_node", "source_xy"),
        ("target", "target_node", "target_xy"),
    ):
        coord = processed_data.get(coord_key)
        if coord is None:
            continue
        rows.append(
            {
                "role": role,
                "node_id": int(processed_data[node_key]),
                "x": float(coord[0]),
                "y": float(coord[1]),
                "geometry": Point(coord[0], coord[1]),
            }
        )
    if not rows:
        return None
    return gpd.GeoDataFrame(rows, geometry="geometry", crs=graph_crs)


def main():
    parser = argparse.ArgumentParser(
        description="Universal SQA Framework",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--rule", required=True, help="例如: facility_selection, path_routing")
    parser.add_argument("--data", required=True, help="Data 目錄路徑")
    parser.add_argument("--steps", type=int, default=100, help="退火步數")
    parser.add_argument("--replicas", type=int, default=10, help="Replica 數量")
    parser.add_argument("--slices", type=int, default=20, help="Trotter 切片數量")
    parser.add_argument("--beta-init", type=float, default=0.1, help="起始逆溫度")
    parser.add_argument("--beta-final", type=float, default=5.0, help="最終逆溫度")
    parser.add_argument("--gamma-init", type=float, default=5.0, help="起始橫向場")
    parser.add_argument("--gamma-final", type=float, default=0.1, help="最終橫向場")
    parser.add_argument("--seed", type=int, default=42, help="亂數種子")
    parser.add_argument("--init-prob", type=float, default=None, help="隨機初始化 bit=1 機率")
    parser.add_argument("--output", type=str, default="outputs", help="輸出根目錄")
    parser.add_argument("--output-dir", type=str, default="", help="若指定則直接輸出到此資料夾，不再建立 timestamp 目錄")
    parser.add_argument("--config", type=str, default="", help="自訂 YAML 設定檔路徑")
    parser.add_argument("--verbose", action="store_true", help="印出詳細除錯資訊")
    args = parser.parse_args()

    try:
        adapter_module = importlib.import_module(f"rules.{args.rule}.adapter")
        builder_module = importlib.import_module(f"rules.{args.rule}.builder")
    except ImportError as e:
        print(f"Error loading rule '{args.rule}': {e}")
        return
    try:
        local_search_module = importlib.import_module(f"rules.{args.rule}.local_search")
    except ImportError:
        local_search_module = None

    config_path = args.config if args.config else os.path.join(BASE_DIR, "rules", args.rule, "config.yaml")
    config = {}
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}
    else:
        print(f"Warning: Config file not found at {config_path}. Using empty config.")
    enable_path_local_search = bool(config.get("enable_path_local_search", True))

    processed_data = adapter_module.load_data(args.data, config)

    built = builder_module.build_qubo(processed_data, config)
    if len(built) == 3:
        Q, offset, decoder = built
        solver_context = {}
    else:
        Q, offset, decoder, solver_context = built

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = args.output_dir if args.output_dir else os.path.join(args.output, args.rule, timestamp)
    os.makedirs(out_dir, exist_ok=True)

    step01_dir = os.path.join(out_dir, "01_graph_input")
    step02_dir = os.path.join(out_dir, "02_baseline_dijkstra")
    step03_dir = os.path.join(out_dir, "03_sqa_run")
    step04_dir = os.path.join(out_dir, "04_path_local_search")
    for path in (step01_dir, step02_dir, step03_dir):
        os.makedirs(path, exist_ok=True)

    graph_summary = dict(processed_data.get("graph_summary", {}))
    graph_summary["data_argument"] = args.data
    graph_summary["config_path"] = config_path
    _write_json(os.path.join(step01_dir, "graph_summary.json"), graph_summary)

    manifest = {
        "step_01_graph_input": step01_dir,
        "step_02_baseline_dijkstra": step02_dir,
        "step_03_sqa_run": step03_dir,
    }
    if enable_path_local_search and local_search_module is not None:
        os.makedirs(step04_dir, exist_ok=True)
        manifest["step_04_path_local_search"] = step04_dir
    _write_json(os.path.join(out_dir, "run_manifest.json"), manifest)

    source_target_gdf = _build_source_target_gdf(processed_data)
    if source_target_gdf is not None:
        source_target_gdf.to_file(
            os.path.join(step01_dir, "source_target_points.geojson"),
            driver="GeoJSON",
        )

    if "segments_gdf" in processed_data:
        processed_data["segments_gdf"].to_file(
            os.path.join(step01_dir, "segments_snapshot.geojson"),
            driver="GeoJSON",
        )

    init_prob = args.init_prob if args.init_prob is not None else config.get("init_prob", 0.5)
    initial_state = solver_context.get("initial_state")
    initial_flip_prob = float(solver_context.get("warm_start_flip_prob", 0.0))
    initialization_mode = solver_context.get("initial_state_name", "random")

    # ── Penalty Annealing + Diverse Init 參數 ──────────────────────────
    qubo_penalty = solver_context.get("qubo_penalty")
    lambda_init  = float(config.get("lambda_init", 1.0))
    lambda_final = float(config.get("lambda_final", 1.0))
    diverse_frac = float(config.get("diverse_frac", 0.0))

    print(f"\n🚀 啟動 SQA, 矩陣大小: {Q.shape}")
    if qubo_penalty is not None and lambda_init < 1.0:
        print(f"   Penalty Annealing: λ = {lambda_init:.4f} → {lambda_final:.4f}")
    if diverse_frac > 0.0:
        print(f"   Diverse Init: {diverse_frac:.0%} replicas randomized")
    sqa = SQA_numpy(
        qubo_matrix=Q,
        steps=args.steps,
        replicas=args.replicas,
        slices=args.slices,
        beta_init=args.beta_init,
        beta_final=args.beta_final,
        gamma_init=args.gamma_init,
        gamma_final=args.gamma_final,
        seed=args.seed,
        output_dir=step03_dir,
        verbose=args.verbose,
        init_prob=init_prob,
        initial_state=initial_state,
        initial_flip_prob=initial_flip_prob,
        qubo_penalty=qubo_penalty,
        lambda_init=lambda_init,
        lambda_final=lambda_final,
        diverse_frac=diverse_frac,
    )
    if initial_state is not None:
        sqa.initial_state_name = initialization_mode

    best_state_binary, best_energy, history, history_records = sqa.run()

    try:
        readable_result = decoder(best_state_binary, out_dir=out_dir)
    except TypeError:
        readable_result = decoder(best_state_binary)
    qgis_export = readable_result.pop("qgis_export", {})

    baseline_payload = readable_result.get("baseline_dijkstra", {})
    _write_json(os.path.join(step02_dir, "baseline_summary.json"), baseline_payload)
    _write_csv_rows(
        os.path.join(step02_dir, "baseline_route_edges.csv"),
        baseline_payload.get("route_edges", []),
    )
    _write_geojson_text(
        os.path.join(step02_dir, "baseline_path.geojson"),
        qgis_export.get("baseline_path_geojson", ""),
    )

    for filename, geojson_text in qgis_export.items():
        if filename == "baseline_path_geojson":
            continue
        export_path = os.path.join(step03_dir, filename.replace("_geojson", "") + ".geojson")
        _write_geojson_text(export_path, geojson_text)

    comparison_payload = {
        "selected_edge_count": readable_result.get("selected_edge_count"),
        "route_found": readable_result.get("route_found"),
        "decoded_route_length": readable_result.get("decoded_route_length"),
        "decoded_route_cost": readable_result.get("decoded_route_cost"),
        "decoded_route_average_walkability": readable_result.get("decoded_route_average_walkability"),
        "comparison_to_dijkstra": readable_result.get("comparison_to_dijkstra", {}),
        "constraint_diagnostics": readable_result.get("constraint_diagnostics", {}),
    }
    _write_json(os.path.join(step03_dir, "comparison_summary.json"), comparison_payload)
    _write_csv_rows(
        os.path.join(step03_dir, "selected_edges.csv"),
        readable_result.get("path_edges", []),
    )
    _write_csv_rows(
        os.path.join(step03_dir, "decoded_route_edges.csv"),
        readable_result.get("decoded_route_edges", []),
    )

    figures_dir = os.path.join(step03_dir, "figures")
    figure_manifest = {}
    if os.path.isdir(figures_dir):
        for name in sorted(os.listdir(figures_dir)):
            src = os.path.join(figures_dir, name)
            dst = os.path.join(step03_dir, name)
            if os.path.isfile(src):
                shutil.copy2(src, dst)
                figure_manifest[name] = dst
    if figure_manifest:
        _write_json(os.path.join(step03_dir, "figure_manifest.json"), figure_manifest)

    readable_result["metadata"] = {
        "rule": args.rule,
        "data_dir": args.data,
        "best_energy": float(best_energy),
        "offset": float(offset),
        "steps": int(args.steps),
        "replicas": int(args.replicas),
        "slices": int(args.slices),
        "qubo_dimension": int(Q.shape[0]),
        "init_prob": float(init_prob),
        "initialization_mode": initialization_mode,
        "initial_flip_prob": float(initial_flip_prob),
        "lambda_init": float(lambda_init),
        "lambda_final": float(lambda_final),
        "diverse_frac": float(diverse_frac),
        "penalty_annealing_enabled": qubo_penalty is not None and lambda_init < 1.0,
        "iteration_history_csv": os.path.join(step03_dir, "iteration_history.csv"),
        "iteration_records": len(history_records),
    }

    result_path = os.path.join(out_dir, "result.json")
    _write_json(result_path, readable_result)

    _write_json(
        os.path.join(step03_dir, "solver_summary.json"),
        {
            "best_energy": float(best_energy),
            "history_length": len(history),
            "initialization_mode": initialization_mode,
            "initial_flip_prob": float(initial_flip_prob),
            "best_state_ones": int(sum(best_state_binary)),
            "history_preview": history_records[:5],
        },
    )

    if enable_path_local_search and local_search_module is not None and hasattr(local_search_module, "run_local_search"):
        local_search_result = local_search_module.run_local_search(
            processed_data=processed_data,
            config=config,
            initial_result=readable_result,
            qubo_matrix=Q,
            output_dir=step04_dir,
        )
        readable_result["path_local_search"] = local_search_result["summary"]
        _write_json(os.path.join(step04_dir, "local_search_manifest.json"), local_search_result)
        _write_json(result_path, readable_result)

    print(f"\n✅ 求解完成！結果已存於 {result_path}")


if __name__ == "__main__":
    main()
