import csv
import json
import os
import random
from typing import Any, Dict, List, Optional, Sequence, Tuple

import geopandas as gpd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


EdgeRecord = Dict[str, Any]


def _edge_signature(edge: EdgeRecord) -> Tuple[str, str, int, int]:
    return (
        str(edge["segment_id"]),
        str(edge["direction"]),
        int(edge["source_node"]),
        int(edge["target_node"]),
    )


def _route_nodes(route_edges: Sequence[EdgeRecord]) -> List[int]:
    if not route_edges:
        return []
    nodes = [int(route_edges[0]["source_node"])]
    nodes.extend(int(edge["target_node"]) for edge in route_edges)
    return nodes


def _route_cost(route_edges: Sequence[EdgeRecord]) -> float:
    return float(sum(float(edge["cost"]) for edge in route_edges))


def _route_length(route_edges: Sequence[EdgeRecord]) -> float:
    return float(sum(float(edge["length"]) for edge in route_edges))


def _route_average_walkability(route_edges: Sequence[EdgeRecord]) -> float:
    if not route_edges:
        return 0.0
    return float(sum(float(edge["dynwd"]) for edge in route_edges) / len(route_edges))


def _is_simple_route(route_edges: Sequence[EdgeRecord]) -> bool:
    nodes = _route_nodes(route_edges)
    return len(nodes) == len(set(nodes))


def _validate_route(route_edges: Sequence[EdgeRecord], source_node: int, target_node: int) -> bool:
    if not route_edges:
        return False
    if int(route_edges[0]["source_node"]) != int(source_node):
        return False
    if int(route_edges[-1]["target_node"]) != int(target_node):
        return False
    for prev_edge, next_edge in zip(route_edges, route_edges[1:]):
        if int(prev_edge["target_node"]) != int(next_edge["source_node"]):
            return False
    return _is_simple_route(route_edges)


def _route_to_state(
    route_edges: Sequence[EdgeRecord],
    num_edges: int,
) -> np.ndarray:
    state = np.zeros(num_edges, dtype=np.float64)
    for edge in route_edges:
        state[int(edge["edge_idx"])] = 1.0
    return state


def _route_summary(
    route_edges: Sequence[EdgeRecord],
    qubo_matrix: np.ndarray,
    num_edges: int,
    label: str,
) -> Dict[str, Any]:
    state = _route_to_state(route_edges, num_edges)
    return {
        "label": label,
        "route_found": bool(route_edges),
        "edge_count": int(len(route_edges)),
        "node_count": int(len(_route_nodes(route_edges))),
        "route_length": _route_length(route_edges),
        "route_cost": _route_cost(route_edges),
        "route_average_walkability": _route_average_walkability(route_edges),
        "qubo_energy": float(state @ qubo_matrix @ state) if len(route_edges) else None,
        "is_simple_path": _is_simple_route(route_edges),
        "signatures": [
            list(_edge_signature(edge))
            for edge in route_edges
        ],
    }


def _signature_list_from_rows(route_rows: Sequence[Dict[str, Any]]) -> List[List[Any]]:
    return [
        [
            str(edge["segment_id"]),
            str(edge["direction"]),
            int(edge["source_node"]),
            int(edge["target_node"]),
        ]
        for edge in route_rows
    ]


def _edges_to_geojson(
    route_edges: Sequence[EdgeRecord],
    graph_crs: Optional[str],
) -> str:
    if not route_edges:
        return ""
    gdf = gpd.GeoDataFrame(list(route_edges), geometry="geometry", crs=graph_crs)
    return gdf.to_json(drop_id=True)


def _write_json(path: str, payload: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=4, ensure_ascii=False)


def _write_rows(path: str, rows: List[Dict[str, Any]]) -> None:
    if not rows:
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _write_geojson_text(path: str, text: str) -> None:
    if not text:
        return
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def _shortest_path(
    outgoing: Dict[int, List[EdgeRecord]],
    source_node: int,
    target_node: int,
    banned_nodes: Optional[set] = None,
    banned_segment_ids: Optional[set] = None,
    banned_edge_signatures: Optional[set] = None,
) -> List[EdgeRecord]:
    import heapq

    banned_nodes = banned_nodes or set()
    banned_segment_ids = banned_segment_ids or set()
    banned_edge_signatures = banned_edge_signatures or set()

    pq: List[Tuple[float, int]] = [(0.0, source_node)]
    best_cost = {source_node: 0.0}
    prev_edge: Dict[int, EdgeRecord] = {}

    while pq:
        cost, node = heapq.heappop(pq)
        if cost > best_cost.get(node, float("inf")):
            continue
        if node == target_node:
            break

        for edge in outgoing.get(node, []):
            next_node = int(edge["target_node"])
            if next_node != target_node and next_node in banned_nodes:
                continue
            if str(edge["segment_id"]) in banned_segment_ids:
                continue
            if _edge_signature(edge) in banned_edge_signatures:
                continue

            new_cost = cost + float(edge["cost"])
            if new_cost >= best_cost.get(next_node, float("inf")):
                continue
            best_cost[next_node] = new_cost
            prev_edge[next_node] = edge
            heapq.heappush(pq, (new_cost, next_node))

    if target_node not in best_cost:
        return []

    route: List[EdgeRecord] = []
    node = target_node
    while node != source_node:
        edge = prev_edge[node]
        route.append(edge)
        node = int(edge["source_node"])
    route.reverse()
    return route


def _candidate_segment_reroute(
    current_route: Sequence[EdgeRecord],
    outgoing: Dict[int, List[EdgeRecord]],
    anchor_start: int,
    anchor_end: int,
) -> Optional[Tuple[List[EdgeRecord], Dict[str, Any]]]:
    route_nodes = _route_nodes(current_route)
    prefix = list(current_route[:anchor_start])
    removed_block = list(current_route[anchor_start:anchor_end])
    suffix = list(current_route[anchor_end:])

    start_node = route_nodes[anchor_start]
    end_node = route_nodes[anchor_end]
    banned_nodes = set(route_nodes[:anchor_start] + route_nodes[anchor_end + 1 :])
    banned_segment_ids = {str(edge["segment_id"]) for edge in removed_block}

    replacement = _shortest_path(
        outgoing=outgoing,
        source_node=start_node,
        target_node=end_node,
        banned_nodes=banned_nodes,
        banned_segment_ids=banned_segment_ids,
    )
    if not replacement:
        return None

    candidate = prefix + replacement + suffix
    info = {
        "move_type": "segment_reroute",
        "anchor_start_edge": int(anchor_start),
        "anchor_end_edge": int(anchor_end),
        "removed_edge_count": int(len(removed_block)),
        "replacement_edge_count": int(len(replacement)),
    }
    return candidate, info


def _candidate_block_move(
    current_route: Sequence[EdgeRecord],
    outgoing: Dict[int, List[EdgeRecord]],
    source_node: int,
    target_node: int,
    block_start: int,
    block_end: int,
) -> Optional[Tuple[List[EdgeRecord], Dict[str, Any]]]:
    removed_block = list(current_route[block_start:block_end])
    banned_segment_ids = {str(edge["segment_id"]) for edge in removed_block}
    candidate = _shortest_path(
        outgoing=outgoing,
        source_node=source_node,
        target_node=target_node,
        banned_segment_ids=banned_segment_ids,
    )
    if not candidate:
        return None

    info = {
        "move_type": "block_move",
        "anchor_start_edge": int(block_start),
        "anchor_end_edge": int(block_end),
        "removed_edge_count": int(len(removed_block)),
        "replacement_edge_count": int(len(candidate)),
    }
    return candidate, info


def _plot_local_search(log_rows: List[Dict[str, Any]], output_dir: str) -> None:
    if not log_rows:
        return

    steps = [row["iteration"] for row in log_rows]
    current_cost = [row["current_cost"] for row in log_rows]
    best_cost = [row["best_cost"] for row in log_rows]
    candidate_cost = [
        row["candidate_cost"] if row["candidate_cost"] is not None else np.nan
        for row in log_rows
    ]
    accepted = [1 if row["accepted"] else 0 for row in log_rows]

    fig, axes = plt.subplots(2, 1, figsize=(11, 7), sharex=True)
    axes[0].plot(steps, current_cost, label="current_cost", color="steelblue")
    axes[0].plot(steps, best_cost, label="best_cost", color="seagreen")
    axes[0].scatter(steps, candidate_cost, s=18, color="darkorange", label="candidate_cost")
    axes[0].set_ylabel("Route Cost")
    axes[0].set_title("Path Local Search Progress")
    axes[0].legend()

    axes[1].step(steps, accepted, where="mid", color="firebrick", label="accepted move")
    axes[1].set_xlabel("Iteration")
    axes[1].set_ylabel("Accepted")
    axes[1].set_yticks([0, 1])
    axes[1].legend()

    fig.tight_layout()
    save_path = os.path.join(output_dir, "local_search_overview.png")
    fig.savefig(save_path, dpi=140)
    plt.close(fig)


def run_local_search(
    processed_data: Dict[str, Any],
    config: Dict[str, Any],
    initial_result: Dict[str, Any],
    qubo_matrix: np.ndarray,
    output_dir: str,
) -> Dict[str, Any]:
    os.makedirs(output_dir, exist_ok=True)

    iterations = int(config.get("path_local_search_iterations", 25))
    segment_trials = int(config.get("segment_reroute_trials_per_iteration", 4))
    block_trials = int(config.get("block_move_trials_per_iteration", 2))
    max_anchor_span = int(config.get("segment_reroute_max_anchor_span", 10))
    seed = int(config.get("path_local_search_seed", 42))
    rng = random.Random(seed)
    seed_mode = str(config.get("path_local_search_seed_mode", "sqa_or_baseline"))

    edges_info = processed_data["edges_info"]
    graph_crs = processed_data.get("graph_crs")
    source_node = int(initial_result["source_node"])
    target_node = int(initial_result["target_node"])
    num_edges = int(len(edges_info))

    edge_by_signature = {
        (
            str(edge["segment_id"]),
            str(edge["direction"]),
            int(edge["source"]),
            int(edge["target"]),
        ): {
            "segment_id": str(edge["segment_id"]),
            "orig_feature_id": edge["orig_feature_id"],
            "direction": str(edge["direction"]),
            "length": float(edge["length"]),
            "dynwd": float(edge["dynwd"]),
            "cost": float(edge["cost"]),
            "source_node": int(edge["source"]),
            "target_node": int(edge["target"]),
            "edge_idx": int(edge["edge_idx"]),
            "geometry": edge["geometry"],
        }
        for edge in edges_info
    }
    outgoing: Dict[int, List[EdgeRecord]] = {}
    for edge in edge_by_signature.values():
        outgoing.setdefault(int(edge["source_node"]), []).append(edge)

    if seed_mode == "sqa_only":
        route_seed_rows = initial_result.get("decoded_route_edges") if initial_result.get("route_found") else []
    elif seed_mode == "baseline_only":
        route_seed_rows = initial_result.get("baseline_dijkstra", {}).get("route_edges", [])
    else:
        route_seed_rows = (
            initial_result.get("decoded_route_edges")
            if initial_result.get("route_found")
            else initial_result.get("baseline_dijkstra", {}).get("route_edges", [])
        )

    if not route_seed_rows:
        summary = {
            "status": "skipped",
            "reason": f"No seed route available for seed_mode={seed_mode}",
            "seed_mode": seed_mode,
            "iterations": int(iterations),
            "accepted_moves": 0,
            "improved_moves": 0,
        }
        _write_json(os.path.join(output_dir, "local_search_summary.json"), summary)
        return {
            "summary": summary,
            "output_dir": output_dir,
            "iteration_csv": None,
            "overview_figure": None,
        }

    seed_route = [
        edge_by_signature[
            (
                str(edge["segment_id"]),
                str(edge["direction"]),
                int(edge["source_node"]),
                int(edge["target_node"]),
            )
        ]
        for edge in route_seed_rows
    ]
    if not _validate_route(seed_route, source_node, target_node):
        summary = {
            "status": "skipped",
            "reason": "Local search seed route is not a valid simple path.",
            "seed_mode": seed_mode,
            "iterations": int(iterations),
            "accepted_moves": 0,
            "improved_moves": 0,
        }
        _write_json(os.path.join(output_dir, "local_search_summary.json"), summary)
        return {
            "summary": summary,
            "output_dir": output_dir,
            "iteration_csv": None,
            "overview_figure": None,
        }

    seed_summary = _route_summary(seed_route, qubo_matrix, num_edges, "seed_route")
    current_route = list(seed_route)
    best_route = list(seed_route)
    current_cost = _route_cost(current_route)
    best_cost = current_cost
    accepted_moves = 0
    improved_moves = 0
    log_rows: List[Dict[str, Any]] = []
    candidate_rows: List[Dict[str, Any]] = []

    candidate_counter = 0
    for iteration in range(iterations):
        route_len = len(current_route)
        segment_pairs = [
            (start, end)
            for start in range(route_len)
            for end in range(start + 1, min(route_len, start + max_anchor_span) + 1)
        ]
        block_pairs = [
            (start, end)
            for start in range(route_len)
            for end in range(start + 1, route_len + 1)
        ]
        candidate_choices: List[Tuple[List[EdgeRecord], Dict[str, Any]]] = []

        if segment_pairs:
            sampled = rng.sample(segment_pairs, k=min(segment_trials, len(segment_pairs)))
            for start, end in sampled:
                candidate = _candidate_segment_reroute(current_route, outgoing, start, end)
                if candidate is not None:
                    candidate_choices.append(candidate)

        if block_pairs:
            sampled = rng.sample(block_pairs, k=min(block_trials, len(block_pairs)))
            for start, end in sampled:
                candidate = _candidate_block_move(
                    current_route=current_route,
                    outgoing=outgoing,
                    source_node=source_node,
                    target_node=target_node,
                    block_start=start,
                    block_end=end,
                )
                if candidate is not None:
                    candidate_choices.append(candidate)

        best_candidate = None
        best_candidate_cost = None
        best_candidate_info = None
        best_candidate_row_idx = None

        for candidate_route, move_info in candidate_choices:
            if not _validate_route(candidate_route, source_node, target_node):
                continue
            candidate_cost = _route_cost(candidate_route)
            candidate_counter += 1
            row = {
                "candidate_id": int(candidate_counter),
                "iteration": int(iteration),
                "move_type": move_info["move_type"],
                "anchor_start_edge": int(move_info["anchor_start_edge"]),
                "anchor_end_edge": int(move_info["anchor_end_edge"]),
                "removed_edge_count": int(move_info["removed_edge_count"]),
                "replacement_edge_count": int(move_info["replacement_edge_count"]),
                "candidate_cost": float(candidate_cost),
                "candidate_length": float(_route_length(candidate_route)),
                "candidate_average_walkability": float(_route_average_walkability(candidate_route)),
                "chosen_as_iteration_best": False,
                "accepted": False,
            }
            candidate_rows.append(row)
            if best_candidate_cost is None or candidate_cost < best_candidate_cost:
                best_candidate = candidate_route
                best_candidate_cost = candidate_cost
                best_candidate_info = move_info
                best_candidate_row_idx = len(candidate_rows) - 1

        accepted = False
        improved_best = False
        candidate_summary = None
        move_type = None

        if best_candidate is not None and best_candidate_info is not None:
            candidate_summary = _route_summary(
                best_candidate,
                qubo_matrix,
                num_edges,
                f"candidate_{candidate_rows[best_candidate_row_idx]['candidate_id']}",
            )
            move_type = best_candidate_info["move_type"]
            if best_candidate_row_idx is not None:
                candidate_rows[best_candidate_row_idx]["chosen_as_iteration_best"] = True
            if float(candidate_summary["route_cost"]) + 1e-9 < current_cost:
                current_route = list(best_candidate)
                current_cost = float(candidate_summary["route_cost"])
                accepted = True
                accepted_moves += 1
                if best_candidate_row_idx is not None:
                    candidate_rows[best_candidate_row_idx]["accepted"] = True
                if current_cost + 1e-9 < best_cost:
                    best_route = list(best_candidate)
                    best_cost = current_cost
                    improved_best = True
                    improved_moves += 1

        log_rows.append(
            {
                "iteration": int(iteration),
                "candidate_count": int(len(candidate_choices)),
                "move_type": move_type,
                "candidate_cost": (
                    None if candidate_summary is None else float(candidate_summary["route_cost"])
                ),
                "candidate_length": (
                    None if candidate_summary is None else float(candidate_summary["route_length"])
                ),
                "candidate_qubo_energy": (
                    None if candidate_summary is None else float(candidate_summary["qubo_energy"])
                ),
                "anchor_start_edge": (
                    None if best_candidate_info is None else int(best_candidate_info["anchor_start_edge"])
                ),
                "anchor_end_edge": (
                    None if best_candidate_info is None else int(best_candidate_info["anchor_end_edge"])
                ),
                "removed_edge_count": (
                    None if best_candidate_info is None else int(best_candidate_info["removed_edge_count"])
                ),
                "replacement_edge_count": (
                    None if best_candidate_info is None else int(best_candidate_info["replacement_edge_count"])
                ),
                "accepted": bool(accepted),
                "improved_best": bool(improved_best),
                "current_cost": float(current_cost),
                "best_cost": float(best_cost),
            }
        )

    best_summary = _route_summary(best_route, qubo_matrix, num_edges, "best_local_search_route")
    baseline_summary = initial_result.get("baseline_dijkstra", {})
    baseline_signatures = _signature_list_from_rows(baseline_summary.get("route_edges", []))
    comparison = {
        "seed_matches_baseline_route": seed_summary["signatures"] == baseline_signatures,
        "best_matches_baseline_route": best_summary["signatures"] == baseline_signatures,
        "best_cost_minus_baseline": (
            float(best_summary["route_cost"]) - float(baseline_summary.get("route_cost", 0.0))
        ),
        "best_cost_minus_seed": float(best_summary["route_cost"]) - float(seed_summary["route_cost"]),
    }

    _write_json(
        os.path.join(output_dir, "local_search_summary.json"),
        {
            "status": "completed",
            "seed_mode": seed_mode,
            "seed_route": seed_summary,
            "best_route": best_summary,
            "baseline_route_cost": baseline_summary.get("route_cost"),
            "iterations": iterations,
            "accepted_moves": accepted_moves,
            "improved_moves": improved_moves,
            "comparison": comparison,
        },
    )
    _write_rows(os.path.join(output_dir, "local_search_iterations.csv"), log_rows)
    _write_rows(os.path.join(output_dir, "local_search_candidates.csv"), candidate_rows)
    _write_rows(
        os.path.join(output_dir, "best_local_search_route_edges.csv"),
        [
            {key: value for key, value in edge.items() if key != "geometry"}
            for edge in best_route
        ],
    )
    _write_rows(
        os.path.join(output_dir, "seed_route_edges.csv"),
        [
            {key: value for key, value in edge.items() if key != "geometry"}
            for edge in seed_route
        ],
    )
    _write_geojson_text(
        os.path.join(output_dir, "best_local_search_path.geojson"),
        _edges_to_geojson(best_route, graph_crs),
    )
    _write_geojson_text(
        os.path.join(output_dir, "seed_route.geojson"),
        _edges_to_geojson(seed_route, graph_crs),
    )
    _plot_local_search(log_rows, output_dir)

    return {
        "summary": {
            "status": "completed",
            "seed_mode": seed_mode,
            "seed_route": seed_summary,
            "best_route": best_summary,
            "iterations": int(iterations),
            "accepted_moves": int(accepted_moves),
            "improved_moves": int(improved_moves),
            "comparison": comparison,
        },
        "output_dir": output_dir,
        "iteration_csv": os.path.join(output_dir, "local_search_iterations.csv"),
        "overview_figure": os.path.join(output_dir, "local_search_overview.png"),
    }
