import heapq
from typing import Tuple, Callable, Dict, Any, Optional

import geopandas as gpd
import numpy as np


def _add_square_penalty(
    Q: np.ndarray,
    coeffs: Dict[int, float],
    rhs: float,
    weight: float,
) -> float:
    offset = weight * (rhs ** 2)
    items = list(coeffs.items())

    for idx, coeff in items:
        Q[idx, idx] += weight * ((coeff * coeff) - (2.0 * rhs * coeff))

    for pos, (idx_i, coeff_i) in enumerate(items):
        for idx_j, coeff_j in items[pos + 1:]:
            cross = 2.0 * weight * coeff_i * coeff_j
            Q[idx_i, idx_j] += cross / 2.0
            Q[idx_j, idx_i] += cross / 2.0

    return offset


def _edge_payload(edge: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "segment_id": edge["segment_id"],
        "orig_feature_id": edge["orig_feature_id"],
        "direction": edge["direction"],
        "length": float(edge["length"]),
        "dynwd": float(edge["dynwd"]),
        "cost": float(edge["cost"]),
        "source_node": int(edge["source"]),
        "target_node": int(edge["target"]),
    }


def _add_at_most_one_penalty(
    Q: np.ndarray,
    variable_indices: list[int],
    weight: float,
) -> None:
    for pos, idx_i in enumerate(variable_indices):
        for idx_j in variable_indices[pos + 1:]:
            Q[idx_i, idx_j] += weight
            Q[idx_j, idx_i] += weight


def _shortest_path(
    edges: list[Dict[str, Any]],
    source_node: int,
    target_node: int,
) -> list[Dict[str, Any]]:
    outgoing: Dict[int, list[Dict[str, Any]]] = {}
    for edge in edges:
        outgoing.setdefault(edge["source_node"], []).append(edge)

    pq: list[tuple[float, int]] = [(0.0, source_node)]
    best_cost = {source_node: 0.0}
    prev_edge: Dict[int, Dict[str, Any]] = {}

    while pq:
        cost, node = heapq.heappop(pq)
        if cost > best_cost.get(node, float("inf")):
            continue
        if node == target_node:
            break

        for edge in outgoing.get(node, []):
            next_node = edge["target_node"]
            new_cost = cost + edge["cost"]
            if new_cost >= best_cost.get(next_node, float("inf")):
                continue
            best_cost[next_node] = new_cost
            prev_edge[next_node] = edge
            heapq.heappush(pq, (new_cost, next_node))

    if target_node not in best_cost:
        return []

    route: list[Dict[str, Any]] = []
    node = target_node
    while node != source_node:
        edge = prev_edge[node]
        route.append(edge)
        node = edge["source_node"]
    route.reverse()
    return route


def _edges_geojson(edges: list[Dict[str, Any]], graph_crs: Optional[str]) -> str:
    if not edges:
        return ""
    return gpd.GeoDataFrame(edges, geometry="geometry", crs=graph_crs).to_json(drop_id=True)


def build_qubo(
    processed_data: Dict[str, Any],
    config: Dict[str, Any],
) -> Tuple[np.ndarray, float, Callable[[np.ndarray], Dict[str, Any]], Dict[str, Any]]:
    edges_info = processed_data["edges_info"]
    num_nodes = processed_data["num_nodes"]
    num_edges = processed_data["num_edges"]
    source_node = processed_data["source_node"]
    target_node = processed_data["target_node"]
    graph_crs = processed_data.get("graph_crs")
    node_coords = processed_data.get("node_coords", {})
    source_xy = processed_data.get("source_xy")
    target_xy = processed_data.get("target_xy")

    print(f"\n[Path Routing Builder] 構建 QUBO, Edges={num_edges}, Nodes={num_nodes}")

    alpha = config.get("alpha_distance", 1.0)
    beta = config.get("beta_walkability", 2.0)
    base_penalty = config.get("penalty_factor", 10000.0)
    endpoint_penalty = config.get("endpoint_penalty", base_penalty)
    intermediate_penalty = config.get("intermediate_penalty", base_penalty)
    direction_penalty = config.get("direction_conflict_penalty", base_penalty)
    balance_penalty = config.get("balance_penalty", intermediate_penalty)
    degree_penalty = config.get("degree_penalty", intermediate_penalty)

    intermediate_nodes = [
        node_id for node_id in range(num_nodes)
        if node_id not in (source_node, target_node)
    ]

    # ── 分離 Q_obj（目標函數）與 Q_pen（約束懲罰），支援 Penalty Annealing ──
    # 文獻基礎：Bernal et al. 2025 (ALIA) — 懲罰項過大會「扭曲目標景觀，
    # 使低能譜區間失去資訊性」。將 Q 拆分後，solver 可以在退火初期使用
    # Q_eff = Q_obj + λ(t)·Q_pen（λ 從 0.01 漸增至 1.0），讓 Metropolis
    # 初期能穿越約束障壁自由探索，後期收緊確保可行性。
    Q_obj = np.zeros((num_edges, num_edges), dtype=np.float64)
    Q_pen = np.zeros((num_edges, num_edges), dtype=np.float64)
    offset = 0.0

    outgoing_edges: Dict[int, list[Dict[str, Any]]] = {node_id: [] for node_id in range(num_nodes)}
    incoming_edges: Dict[int, list[Dict[str, Any]]] = {node_id: [] for node_id in range(num_nodes)}

    for edge in edges_info:
        walk_cost = max(5.0 - edge["dynwd"], 0.0)
        edge["cost"] = alpha * edge["length"] + beta * walk_cost
        Q_obj[edge["edge_idx"], edge["edge_idx"]] += edge["cost"]
        outgoing_edges[edge["source"]].append(edge)
        incoming_edges[edge["target"]].append(edge)

    # Source/target endpoint constraints → Q_pen
    offset += _add_square_penalty(
        Q_pen,
        {edge["edge_idx"]: 1.0 for edge in outgoing_edges[source_node]},
        1.0,
        endpoint_penalty,
    )
    offset += _add_square_penalty(
        Q_pen,
        {edge["edge_idx"]: 1.0 for edge in incoming_edges[source_node]},
        0.0,
        endpoint_penalty,
    )
    offset += _add_square_penalty(
        Q_pen,
        {edge["edge_idx"]: 1.0 for edge in incoming_edges[target_node]},
        1.0,
        endpoint_penalty,
    )
    offset += _add_square_penalty(
        Q_pen,
        {edge["edge_idx"]: 1.0 for edge in outgoing_edges[target_node]},
        0.0,
        endpoint_penalty,
    )

    # Intermediate nodes: flow balance + degree constraints → Q_pen
    for node_id in intermediate_nodes:
        incoming_indices = [edge["edge_idx"] for edge in incoming_edges[node_id]]
        outgoing_indices = [edge["edge_idx"] for edge in outgoing_edges[node_id]]

        balance_coeffs = {idx: 1.0 for idx in incoming_indices}
        for idx in outgoing_indices:
            balance_coeffs[idx] = balance_coeffs.get(idx, 0.0) - 1.0
        offset += _add_square_penalty(Q_pen, balance_coeffs, 0.0, balance_penalty)

        _add_at_most_one_penalty(Q_pen, incoming_indices, degree_penalty)
        _add_at_most_one_penalty(Q_pen, outgoing_indices, degree_penalty)

    # Direction conflict → Q_pen
    by_segment: Dict[str, list[Dict[str, Any]]] = {}
    for edge in edges_info:
        by_segment.setdefault(edge["segment_id"], []).append(edge)
    for segment_edges in by_segment.values():
        if len(segment_edges) != 2:
            continue
        idx_i = segment_edges[0]["edge_idx"]
        idx_j = segment_edges[1]["edge_idx"]
        Q_pen[idx_i, idx_j] += direction_penalty / 2.0
        Q_pen[idx_j, idx_i] += direction_penalty / 2.0

    # ── 合併完整 QUBO（能量追蹤用） ──
    Q = Q_obj + Q_pen

    full_edge_records = [
        {**_edge_payload(edge), "geometry": edge["geometry"]}
        for edge in edges_info
    ]
    baseline_route_edges = _shortest_path(full_edge_records, source_node, target_node)
    baseline_state = np.zeros(num_edges, dtype=np.float64)
    edge_index_by_signature = {
        (edge["segment_id"], edge["direction"], edge["source"], edge["target"]): edge["edge_idx"]
        for edge in edges_info
    }
    for edge in baseline_route_edges:
        idx = edge_index_by_signature[(
            edge["segment_id"],
            edge["direction"],
            edge["source_node"],
            edge["target_node"],
        )]
        baseline_state[idx] = 1.0
    baseline_qubo_energy = float(baseline_state @ Q @ baseline_state)

    print("QUBO matrix built. Shape:", Q.shape)

    use_dijkstra_warm_start = bool(config.get("use_dijkstra_warm_start", True))
    solver_context = {
        "initial_state": baseline_state.astype(np.int8) if use_dijkstra_warm_start else None,
        "initial_state_name": "dijkstra_baseline" if use_dijkstra_warm_start else "random",
        "warm_start_flip_prob": float(config.get("warm_start_flip_prob", 0.01)) if use_dijkstra_warm_start else 0.0,
        "baseline_route_edge_count": len(baseline_route_edges),
        "baseline_qubo_energy": baseline_qubo_energy,
        "use_dijkstra_warm_start": use_dijkstra_warm_start,
        "qubo_penalty": Q_pen,
    }

    def decoder(best_state_binary: np.ndarray) -> Dict[str, Any]:
        selected_state = np.asarray(best_state_binary[:num_edges], dtype=np.float64)
        selected_features = [
            {**_edge_payload(edge), "geometry": edge["geometry"]}
            for edge in edges_info
            if int(best_state_binary[edge["edge_idx"]]) == 1
        ]
        selected_edges = [
            {key: value for key, value in edge.items() if key != "geometry"}
            for edge in selected_features
        ]

        route_edges = _shortest_path(selected_features, source_node, target_node)
        route_signatures = [
            (edge["segment_id"], edge["direction"])
            for edge in route_edges
        ]
        baseline_signatures = [
            (edge["segment_id"], edge["direction"])
            for edge in baseline_route_edges
        ]
        route_edge_keys = {
            (edge["segment_id"], edge["direction"], edge["source_node"], edge["target_node"])
            for edge in route_edges
        }
        invalid_selected_edges = [
            {key: value for key, value in edge.items() if key != "geometry"}
            for edge in selected_features
            if (
                edge["segment_id"],
                edge["direction"],
                edge["source_node"],
                edge["target_node"],
            ) not in route_edge_keys
        ]

        in_degree = {node_id: 0 for node_id in range(num_nodes)}
        out_degree = {node_id: 0 for node_id in range(num_nodes)}
        for edge in selected_features:
            out_degree[edge["source_node"]] += 1
            in_degree[edge["target_node"]] += 1

        branching_nodes = []
        dangling_nodes = []
        for node_id in intermediate_nodes:
            indeg = in_degree[node_id]
            outdeg = out_degree[node_id]
            if indeg > 1 or outdeg > 1:
                branching_nodes.append({
                    "node_id": node_id,
                    "in_degree": indeg,
                    "out_degree": outdeg,
                })
            if not ((indeg == 0 and outdeg == 0) or (indeg == 1 and outdeg == 1)):
                dangling_nodes.append({
                    "node_id": node_id,
                    "in_degree": indeg,
                    "out_degree": outdeg,
                })

        route_length = sum(edge["length"] for edge in route_edges)
        route_cost = sum(edge["cost"] for edge in route_edges)
        route_walkability = (
            sum(edge["dynwd"] for edge in route_edges) / len(route_edges)
            if route_edges else 0.0
        )
        baseline_length = sum(edge["length"] for edge in baseline_route_edges)
        baseline_cost = sum(edge["cost"] for edge in baseline_route_edges)
        baseline_walkability = (
            sum(edge["dynwd"] for edge in baseline_route_edges) / len(baseline_route_edges)
            if baseline_route_edges else 0.0
        )

        qgis_export = {
            "selected_edges_geojson": _edges_geojson(selected_features, graph_crs),
            "decoded_path_geojson": _edges_geojson(route_edges, graph_crs),
            "baseline_path_geojson": _edges_geojson(baseline_route_edges, graph_crs),
        }

        node_rows = []
        if source_node in node_coords:
            sx, sy = node_coords[source_node]
            node_rows.append({
                "node_id": source_node,
                "role": "source",
                "geometry": gpd.points_from_xy([sx], [sy])[0],
            })
        if target_node in node_coords:
            tx, ty = node_coords[target_node]
            node_rows.append({
                "node_id": target_node,
                "role": "target",
                "geometry": gpd.points_from_xy([tx], [ty])[0],
            })
        if node_rows:
            qgis_export["route_nodes_geojson"] = gpd.GeoDataFrame(
                node_rows,
                geometry="geometry",
                crs=graph_crs,
            ).to_json(drop_id=True)

        return {
            "source_node": source_node,
            "target_node": target_node,
            "source_coord_projected": source_xy,
            "target_coord_projected": target_xy,
            "path_edges": selected_edges,
            "selected_edge_count": len(selected_edges),
            "selected_state_qubo_energy": float(selected_state @ Q @ selected_state),
            "total_path_length": sum(edge["length"] for edge in selected_edges),
            "average_walkability": (
                sum(edge["dynwd"] for edge in selected_edges) / max(len(selected_edges), 1)
            ),
            "decoded_route_edges": [
                {key: value for key, value in edge.items() if key != "geometry"}
                for edge in route_edges
            ],
            "route_found": bool(route_edges),
            "decoded_route_length": route_length,
            "decoded_route_cost": route_cost,
            "decoded_route_average_walkability": route_walkability,
            "invalid_selected_edges_count": len(invalid_selected_edges),
            "invalid_selected_edges_preview": invalid_selected_edges[:20],
            "baseline_dijkstra": {
                "route_edges": [
                    {key: value for key, value in edge.items() if key != "geometry"}
                    for edge in baseline_route_edges
                ],
                "route_found": bool(baseline_route_edges),
                "route_length": baseline_length,
                "route_cost": baseline_cost,
                "route_average_walkability": baseline_walkability,
                "qubo_energy": baseline_qubo_energy,
            },
            "comparison_to_dijkstra": {
                "matches_exact_route": route_signatures == baseline_signatures,
                "decoded_route_cost_gap": (
                    route_cost - baseline_cost if route_edges else None
                ),
                "decoded_route_length_gap": (
                    route_length - baseline_length if route_edges else None
                ),
                "qubo_energy_gap": float((selected_state @ Q @ selected_state) - baseline_qubo_energy),
            },
            "constraint_diagnostics": {
                "source_in_degree": in_degree[source_node],
                "source_out_degree": out_degree[source_node],
                "target_in_degree": in_degree[target_node],
                "target_out_degree": out_degree[target_node],
                "branching_node_count": len(branching_nodes),
                "branching_nodes_preview": branching_nodes[:10],
                "dangling_node_count": len(dangling_nodes),
                "dangling_nodes_preview": dangling_nodes[:10],
            },
            "qgis_export": qgis_export,
        }

    return Q, offset, decoder, solver_context
