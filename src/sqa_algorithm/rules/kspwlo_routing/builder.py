import csv
import heapq
import json
import math
import os
from itertools import combinations
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import geopandas as gpd
import numpy as np


EdgeRecord = Dict[str, Any]


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


def _add_at_most_one_penalty(
    Q: np.ndarray,
    variable_indices: Sequence[int],
    weight: float,
) -> None:
    indices = list(variable_indices)
    for pos, idx_i in enumerate(indices):
        for idx_j in indices[pos + 1:]:
            Q[idx_i, idx_j] += weight
            Q[idx_j, idx_i] += weight


def _add_binary_and_penalty(
    Q: np.ndarray,
    lhs_indices: Sequence[int],
    rhs_indices: Sequence[int],
    and_index: int,
    weight: float,
) -> None:
    Q[and_index, and_index] += 3.0 * weight
    for idx_l in lhs_indices:
        Q[idx_l, and_index] += -weight
        Q[and_index, idx_l] += -weight
    for idx_r in rhs_indices:
        Q[idx_r, and_index] += -weight
        Q[and_index, idx_r] += -weight
    for idx_l in lhs_indices:
        for idx_r in rhs_indices:
            Q[idx_l, idx_r] += weight / 2.0
            Q[idx_r, idx_l] += weight / 2.0


def _edge_payload(edge: EdgeRecord) -> Dict[str, Any]:
    return {
        "segment_id": str(edge["segment_id"]),
        "orig_feature_id": edge["orig_feature_id"],
        "direction": str(edge["direction"]),
        "length": float(edge["length"]),
        "dynwd": float(edge["dynwd"]),
        "cost": float(edge["cost"]),
        "source_node": int(edge["source_node"]),
        "target_node": int(edge["target_node"]),
        "edge_idx": int(edge["edge_idx"]),
    }


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


def _write_geojson(path: str, geojson_text: str) -> None:
    if not geojson_text:
        return
    with open(path, "w", encoding="utf-8") as f:
        f.write(geojson_text)


def _route_signatures(route_edges: Sequence[EdgeRecord]) -> List[Tuple[str, str, int, int]]:
    return [
        (
            str(edge["segment_id"]),
            str(edge["direction"]),
            int(edge["source_node"]),
            int(edge["target_node"]),
        )
        for edge in route_edges
    ]


def _route_segment_ids(route_edges: Sequence[EdgeRecord]) -> List[str]:
    return [str(edge["segment_id"]) for edge in route_edges]


def _route_nodes(route_edges: Sequence[EdgeRecord]) -> List[int]:
    if not route_edges:
        return []
    nodes = [int(route_edges[0]["source_node"])]
    nodes.extend(int(edge["target_node"]) for edge in route_edges)
    return nodes


def _route_weight(route_edges: Sequence[EdgeRecord], weight_field: str) -> float:
    return float(sum(float(edge[weight_field]) for edge in route_edges))


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


def _build_outgoing(edges: Sequence[EdgeRecord]) -> Dict[int, List[EdgeRecord]]:
    outgoing: Dict[int, List[EdgeRecord]] = {}
    for edge in edges:
        outgoing.setdefault(int(edge["source_node"]), []).append(edge)
    return outgoing


def _shortest_path(
    edges: Sequence[EdgeRecord],
    source_node: int,
    target_node: int,
    weight_field: str = "cost",
    max_original_cost: Optional[float] = None,
    banned_segment_ids: Optional[set] = None,
) -> List[EdgeRecord]:
    outgoing = _build_outgoing(edges)
    banned_segment_ids = banned_segment_ids or set()

    pq: List[Tuple[float, float, int]] = [(0.0, 0.0, source_node)]
    best_penalized = {source_node: 0.0}
    best_original = {source_node: 0.0}
    prev_edge: Dict[int, EdgeRecord] = {}

    while pq:
        penalized_cost, original_cost, node = heapq.heappop(pq)
        if penalized_cost > best_penalized.get(node, float("inf")) + 1e-9:
            continue
        if node == target_node:
            break

        for edge in outgoing.get(node, []):
            if str(edge["segment_id"]) in banned_segment_ids:
                continue
            next_node = int(edge["target_node"])
            next_original = original_cost + float(edge["cost"])
            if max_original_cost is not None and next_original > max_original_cost + 1e-9:
                continue

            next_penalized = penalized_cost + float(edge[weight_field])
            current_penalized = best_penalized.get(next_node, float("inf"))
            current_original = best_original.get(next_node, float("inf"))
            if (
                next_penalized > current_penalized + 1e-9
                or (
                    abs(next_penalized - current_penalized) <= 1e-9
                    and next_original >= current_original - 1e-9
                )
            ):
                continue

            best_penalized[next_node] = next_penalized
            best_original[next_node] = next_original
            prev_edge[next_node] = edge
            heapq.heappush(pq, (next_penalized, next_original, next_node))

    if target_node not in prev_edge and target_node != source_node:
        return []

    route: List[EdgeRecord] = []
    node = target_node
    while node != source_node:
        edge = prev_edge.get(node)
        if edge is None:
            return []
        route.append(edge)
        node = int(edge["source_node"])
    route.reverse()
    return route


def _weighted_overlap_ratio(
    route_a: Sequence[EdgeRecord],
    route_b: Sequence[EdgeRecord],
    weight_field: str,
) -> float:
    if not route_a or not route_b:
        return 0.0

    weight_a = {str(edge["segment_id"]): float(edge[weight_field]) for edge in route_a}
    weight_b = {str(edge["segment_id"]): float(edge[weight_field]) for edge in route_b}
    shared_ids = set(weight_a) & set(weight_b)
    if not shared_ids:
        return 0.0

    overlap_weight = sum(min(weight_a[segment_id], weight_b[segment_id]) for segment_id in shared_ids)
    denom = min(_route_weight(route_a, weight_field), _route_weight(route_b, weight_field))
    if denom <= 0.0:
        return 0.0
    return float(overlap_weight / denom)


def _route_summary(
    route_edges: Sequence[EdgeRecord],
    path_label: str,
    weight_field: str,
) -> Dict[str, Any]:
    return {
        "path_label": path_label,
        "route_found": bool(route_edges),
        "edge_count": int(len(route_edges)),
        "node_count": int(len(_route_nodes(route_edges))),
        "route_length": _route_weight(route_edges, "length"),
        "route_cost": _route_weight(route_edges, "cost"),
        "route_average_walkability": _route_average_walkability(route_edges),
        "is_simple_path": _is_simple_route(route_edges) if route_edges else False,
        "overlap_weight_field": weight_field,
        "route_weight_for_overlap": _route_weight(route_edges, weight_field),
        "segment_ids": _route_segment_ids(route_edges),
        "signatures": [list(sig) for sig in _route_signatures(route_edges)],
        "route_edges": [{key: value for key, value in edge.items() if key != "geometry"} for edge in route_edges],
    }


def _paths_set_signature(path_summaries: Sequence[Dict[str, Any]]) -> Tuple[Tuple[Tuple[Any, ...], ...], ...]:
    normalized = []
    for summary in path_summaries:
        signatures = tuple(tuple(sig) for sig in summary.get("signatures", []))
        normalized.append(signatures)
    return tuple(sorted(normalized))


def _edges_geojson(edges: Sequence[EdgeRecord], graph_crs: Optional[str]) -> str:
    if not edges:
        return ""
    return gpd.GeoDataFrame(list(edges), geometry="geometry", crs=graph_crs).to_json(drop_id=True)


def _binary_slack_size(max_units: int) -> int:
    if max_units <= 0:
        return 0
    return int(math.ceil(math.log2(max_units + 1)))


def _fill_slack_bits(remaining_units: int, num_bits: int) -> List[int]:
    values = [0] * num_bits
    units = max(int(remaining_units), 0)
    for bit in reversed(range(num_bits)):
        bit_value = 2 ** bit
        if units >= bit_value:
            values[bit] = 1
            units -= bit_value
    return values


def _build_penalty_baseline(
    full_edges: Sequence[EdgeRecord],
    source_node: int,
    target_node: int,
    k_paths: int,
    theta: float,
    epsilon: float,
    overlap_weight_field: str,
    complete_result: bool,
    relax_theta_step: float,
    max_candidates: int,
) -> Dict[str, Any]:
    shortest_path = _shortest_path(full_edges, source_node, target_node, weight_field="cost")
    shortest_cost = _route_weight(shortest_path, "cost")
    l_max = (1.0 + epsilon) * shortest_cost

    selected_paths = [shortest_path] if shortest_path else []
    candidate_pool = [shortest_path] if shortest_path else []
    candidate_seen = {tuple(_route_signatures(shortest_path))} if shortest_path else set()
    theta_current = float(theta)
    failure_rounds = 0
    rounds: List[Dict[str, Any]] = []

    def penalty_factor(magnitude: int) -> float:
        return 2.0 - (magnitude * max(1.0 - epsilon, 0.0) / 2.0)

    while shortest_path and len(selected_paths) < k_paths:
        found_in_round = False
        magnitude = 0
        while True:
            factor = penalty_factor(magnitude)
            if factor <= 1.0 + 1e-9:
                break

            penalized_edges: List[EdgeRecord] = []
            penalized_segment_ids = {
                str(edge["segment_id"])
                for route in selected_paths
                for edge in route
            }
            for edge in full_edges:
                penalized_edge = dict(edge)
                penalized_edge["penalized_cost"] = (
                    float(edge["cost"]) * factor
                    if str(edge["segment_id"]) in penalized_segment_ids
                    else float(edge["cost"])
                )
                penalized_edges.append(penalized_edge)

            candidate = _shortest_path(
                penalized_edges,
                source_node,
                target_node,
                weight_field="penalized_cost",
                max_original_cost=l_max,
            )
            candidate_signature = tuple(_route_signatures(candidate))
            if candidate and candidate_signature not in candidate_seen:
                candidate_seen.add(candidate_signature)
                candidate_pool.append(candidate)

                similarities = [
                    _weighted_overlap_ratio(existing, candidate, overlap_weight_field)
                    for existing in selected_paths
                ]
                max_similarity = max(similarities) if similarities else 0.0
                rounds.append(
                    {
                        "penalty_factor": factor,
                        "magnitude": magnitude,
                        "candidate_cost": _route_weight(candidate, "cost"),
                        "candidate_length": _route_weight(candidate, "length"),
                        "candidate_max_similarity": max_similarity,
                        "accepted": bool(max_similarity <= theta_current + 1e-9),
                    }
                )
                if max_similarity <= theta_current + 1e-9:
                    selected_paths.append(candidate)
                    found_in_round = True
                    break

            magnitude += 1

        if found_in_round:
            failure_rounds = 0
            continue

        failure_rounds += 1
        if not complete_result:
            break
        theta_current = min(1.0, theta_current + relax_theta_step)
        if theta_current >= 1.0 - 1e-9 or failure_rounds > max_candidates:
            break

    selected_summaries = [
        _route_summary(route, f"baseline_path_{idx + 1}", overlap_weight_field)
        for idx, route in enumerate(selected_paths)
    ]
    pairwise = []
    for idx_a, idx_b in combinations(range(len(selected_paths)), 2):
        similarity = _weighted_overlap_ratio(
            selected_paths[idx_a],
            selected_paths[idx_b],
            overlap_weight_field,
        )
        pairwise.append(
            {
                "path_i": idx_a + 1,
                "path_j": idx_b + 1,
                "similarity": similarity,
                "theta_used": theta_current,
                "within_threshold": bool(similarity <= theta_current + 1e-9),
            }
        )

    return {
        "method": "kMDNSP-inspired penalty shortest-path heuristic",
        "k_paths_requested": int(k_paths),
        "k_paths_found": int(len(selected_paths)),
        "theta_initial": float(theta),
        "theta_used": float(theta_current),
        "epsilon_near_shortest": float(epsilon),
        "complete_result": bool(complete_result),
        "near_shortest_cost_limit": float(l_max),
        "paths": selected_summaries,
        "pairwise_similarity": pairwise,
        "round_log": rounds[:max_candidates],
        "candidate_pool_size": int(len(candidate_pool)),
        "route_found": bool(selected_paths),
        "route_edges": selected_summaries[0]["route_edges"] if selected_summaries else [],
        "route_cost": selected_summaries[0]["route_cost"] if selected_summaries else None,
        "route_length": selected_summaries[0]["route_length"] if selected_summaries else None,
        "route_average_walkability": selected_summaries[0]["route_average_walkability"] if selected_summaries else None,
    }


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
    source_xy = processed_data.get("source_xy")
    target_xy = processed_data.get("target_xy")

    alpha = float(config.get("alpha_distance", 1.0))
    beta = float(config.get("beta_walkability", 2.0))
    base_penalty = float(config.get("penalty_factor", 10000.0))
    endpoint_penalty = float(config.get("endpoint_penalty", base_penalty))
    intermediate_penalty = float(config.get("intermediate_penalty", base_penalty))
    direction_penalty = float(config.get("direction_conflict_penalty", base_penalty))
    overlap_penalty = float(config.get("soft_overlap_penalty", 3.0))
    overlap_link_penalty = float(config.get("overlap_link_penalty", intermediate_penalty))
    hard_overlap_penalty = float(config.get("hard_overlap_penalty", intermediate_penalty))
    pathwise_ratio_penalty = float(config.get("pathwise_ratio_penalty", hard_overlap_penalty))
    overlap_weight_field = str(config.get("overlap_weight_field", "cost"))
    theta = float(config.get("theta_overlap", 0.5))
    epsilon = float(config.get("epsilon_near_shortest", 0.2))
    k_paths = int(config.get("k_paths", 2))
    hard_overlap_mode = str(config.get("hard_overlap_mode", "budget")).strip().lower()
    if hard_overlap_mode not in {"budget", "pathwise_ratio", "budget_plus_ratio", "soft"}:
        raise ValueError("hard_overlap_mode must be one of: budget, pathwise_ratio, budget_plus_ratio, soft")
    use_hard_overlap_budget = bool(config.get("use_hard_overlap_budget", True)) and hard_overlap_mode in {"budget", "budget_plus_ratio"}
    use_pathwise_ratio_constraint = hard_overlap_mode in {"pathwise_ratio", "budget_plus_ratio"}
    overlap_budget_resolution = float(config.get("hard_overlap_budget_resolution", 5.0))
    pathwise_ratio_resolution = float(config.get("pathwise_ratio_resolution", overlap_budget_resolution))
    pathwise_ratio_route_cap_factor = float(config.get("pathwise_ratio_route_cap_factor", 1.25))

    if k_paths < 2:
        raise ValueError("kSPwLO routing requires k_paths >= 2.")
    if overlap_weight_field not in {"cost", "length"}:
        raise ValueError("overlap_weight_field must be 'cost' or 'length'.")

    full_edge_records: List[EdgeRecord] = []
    outgoing_edges: Dict[int, List[EdgeRecord]] = {node_id: [] for node_id in range(num_nodes)}
    incoming_edges: Dict[int, List[EdgeRecord]] = {node_id: [] for node_id in range(num_nodes)}

    for edge in edges_info:
        walk_cost = max(5.0 - float(edge["dynwd"]), 0.0)
        edge["cost"] = alpha * float(edge["length"]) + beta * walk_cost
        record = {
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
        full_edge_records.append(record)
        outgoing_edges[int(edge["source"])].append(record)
        incoming_edges[int(edge["target"])].append(record)

    by_segment: Dict[str, List[EdgeRecord]] = {}
    for edge in full_edge_records:
        by_segment.setdefault(str(edge["segment_id"]), []).append(edge)

    overlap_pair_keys = list(combinations(range(k_paths), 2))
    pair_to_pos = {pair: idx for idx, pair in enumerate(overlap_pair_keys)}
    overlap_segment_ids = sorted(by_segment.keys())
    overlap_segment_pos = {segment_id: idx for idx, segment_id in enumerate(overlap_segment_ids)}

    overlap_lower_bound_route = _shortest_path(
        full_edge_records,
        source_node,
        target_node,
        weight_field=overlap_weight_field,
    )
    overlap_lower_bound = _route_weight(overlap_lower_bound_route, overlap_weight_field)
    overlap_budget_cap = float(theta * overlap_lower_bound)
    slack_max_units = max(int(math.floor(overlap_budget_cap / overlap_budget_resolution + 1e-9)), 0)

    baseline_payload = _build_penalty_baseline(
        full_edges=full_edge_records,
        source_node=source_node,
        target_node=target_node,
        k_paths=k_paths,
        theta=theta,
        epsilon=epsilon,
        overlap_weight_field=overlap_weight_field,
        complete_result=bool(config.get("baseline_complete_result", False)),
        relax_theta_step=float(config.get("baseline_relax_theta_step", 0.02)),
        max_candidates=int(config.get("baseline_max_candidates", 64)),
    )
    baseline_paths = baseline_payload.get("paths", [])
    baseline_overlap_weights = [
        float(path.get("route_weight_for_overlap", 0.0))
        for path in baseline_paths
        if path.get("route_found")
    ]
    ratio_route_weight_cap = max(
        [overlap_lower_bound, overlap_lower_bound * (1.0 + max(epsilon, 0.0)), *baseline_overlap_weights]
    ) * max(pathwise_ratio_route_cap_factor, 1.0)
    ratio_slack_max_units = max(
        int(math.ceil((theta * ratio_route_weight_cap) / pathwise_ratio_resolution - 1e-9)),
        0,
    )

    slack_bits_per_pair = _binary_slack_size(slack_max_units) if use_hard_overlap_budget else 0
    ratio_constraints_per_pair = 2 if use_pathwise_ratio_constraint else 0
    ratio_slack_bits_per_constraint = _binary_slack_size(ratio_slack_max_units) if use_pathwise_ratio_constraint else 0

    base_path_var_count = k_paths * num_edges
    overlap_var_count = len(overlap_pair_keys) * len(overlap_segment_ids) if (use_hard_overlap_budget or use_pathwise_ratio_constraint) else 0
    slack_var_count = len(overlap_pair_keys) * slack_bits_per_pair if use_hard_overlap_budget else 0
    overlap_var_base = base_path_var_count
    slack_var_base = overlap_var_base + overlap_var_count
    ratio_slack_var_base = slack_var_base + slack_var_count
    ratio_slack_var_count = len(overlap_pair_keys) * ratio_constraints_per_pair * ratio_slack_bits_per_constraint if use_pathwise_ratio_constraint else 0
    total_variables = base_path_var_count + overlap_var_count + slack_var_count + ratio_slack_var_count

    Q = np.zeros((total_variables, total_variables), dtype=np.float64)
    offset = 0.0

    def var_idx(path_idx: int, edge_idx: int) -> int:
        return path_idx * num_edges + edge_idx

    def overlap_idx(path_a: int, path_b: int, segment_id: str) -> int:
        pair = tuple(sorted((path_a, path_b)))
        return overlap_var_base + pair_to_pos[pair] * len(overlap_segment_ids) + overlap_segment_pos[str(segment_id)]

    def slack_idx(pair_pos: int, bit: int) -> int:
        return slack_var_base + pair_pos * slack_bits_per_pair + bit

    def ratio_slack_idx(pair_pos: int, route_pos: int, bit: int) -> int:
        per_pair = ratio_constraints_per_pair * ratio_slack_bits_per_constraint
        return ratio_slack_var_base + pair_pos * per_pair + route_pos * ratio_slack_bits_per_constraint + bit

    intermediate_nodes = [
        node_id for node_id in range(num_nodes)
        if node_id not in (source_node, target_node)
    ]

    for path_idx in range(k_paths):
        for edge in full_edge_records:
            idx = var_idx(path_idx, int(edge["edge_idx"]))
            Q[idx, idx] += float(edge["cost"])

        offset += _add_square_penalty(
            Q,
            {var_idx(path_idx, int(edge["edge_idx"])): 1.0 for edge in outgoing_edges[source_node]},
            1.0,
            endpoint_penalty,
        )
        offset += _add_square_penalty(
            Q,
            {var_idx(path_idx, int(edge["edge_idx"])): 1.0 for edge in incoming_edges[source_node]},
            0.0,
            endpoint_penalty,
        )
        offset += _add_square_penalty(
            Q,
            {var_idx(path_idx, int(edge["edge_idx"])): 1.0 for edge in incoming_edges[target_node]},
            1.0,
            endpoint_penalty,
        )
        offset += _add_square_penalty(
            Q,
            {var_idx(path_idx, int(edge["edge_idx"])): 1.0 for edge in outgoing_edges[target_node]},
            0.0,
            endpoint_penalty,
        )

        for node_id in intermediate_nodes:
            incoming_indices = [var_idx(path_idx, int(edge["edge_idx"])) for edge in incoming_edges[node_id]]
            outgoing_indices = [var_idx(path_idx, int(edge["edge_idx"])) for edge in outgoing_edges[node_id]]

            balance_coeffs = {idx: 1.0 for idx in incoming_indices}
            for idx in outgoing_indices:
                balance_coeffs[idx] = balance_coeffs.get(idx, 0.0) - 1.0
            offset += _add_square_penalty(Q, balance_coeffs, 0.0, intermediate_penalty)
            _add_at_most_one_penalty(Q, incoming_indices, intermediate_penalty)
            _add_at_most_one_penalty(Q, outgoing_indices, intermediate_penalty)

    for path_idx in range(k_paths):
        for segment_edges in by_segment.values():
            edge_indices = [var_idx(path_idx, int(edge["edge_idx"])) for edge in segment_edges]
            _add_at_most_one_penalty(Q, edge_indices, direction_penalty)

    for path_a, path_b in overlap_pair_keys:
        for segment_id, segment_edges in by_segment.items():
            overlap_weight = float(segment_edges[0][overlap_weight_field]) * overlap_penalty
            if overlap_weight != 0.0:
                indices_a = [var_idx(path_a, int(edge["edge_idx"])) for edge in segment_edges]
                indices_b = [var_idx(path_b, int(edge["edge_idx"])) for edge in segment_edges]
                for idx_a in indices_a:
                    for idx_b in indices_b:
                        Q[idx_a, idx_b] += overlap_weight / 2.0
                        Q[idx_b, idx_a] += overlap_weight / 2.0

            if use_hard_overlap_budget or use_pathwise_ratio_constraint:
                z_idx = overlap_idx(path_a, path_b, segment_id)
                lhs_indices = [var_idx(path_a, int(edge["edge_idx"])) for edge in segment_edges]
                rhs_indices = [var_idx(path_b, int(edge["edge_idx"])) for edge in segment_edges]
                _add_binary_and_penalty(Q, lhs_indices, rhs_indices, z_idx, overlap_link_penalty)

    if use_hard_overlap_budget and overlap_pair_keys and overlap_budget_cap > 0.0:
        for pair, pair_pos in pair_to_pos.items():
            coeffs: Dict[int, float] = {}
            for segment_id in overlap_segment_ids:
                segment_edges = by_segment[segment_id]
                coeffs[overlap_idx(pair[0], pair[1], segment_id)] = float(segment_edges[0][overlap_weight_field]) / overlap_budget_cap
            for bit in range(slack_bits_per_pair):
                coeffs[slack_idx(pair_pos, bit)] = (overlap_budget_resolution * (2 ** bit)) / overlap_budget_cap
            offset += _add_square_penalty(Q, coeffs, 1.0, hard_overlap_penalty)
    elif use_hard_overlap_budget and overlap_pair_keys and overlap_budget_cap <= 0.0:
        for pair in overlap_pair_keys:
            for segment_id in overlap_segment_ids:
                idx = overlap_idx(pair[0], pair[1], segment_id)
                Q[idx, idx] += hard_overlap_penalty
    if use_pathwise_ratio_constraint and overlap_pair_keys:
        for pair, pair_pos in pair_to_pos.items():
            for route_pos, path_idx in enumerate(pair):
                coeffs = {}
                for segment_id in overlap_segment_ids:
                    segment_edges = by_segment[segment_id]
                    coeffs[overlap_idx(pair[0], pair[1], segment_id)] = float(segment_edges[0][overlap_weight_field])
                for edge in full_edge_records:
                    coeffs[var_idx(path_idx, int(edge["edge_idx"]))] = coeffs.get(
                        var_idx(path_idx, int(edge["edge_idx"])),
                        0.0,
                    ) - (theta * float(edge[overlap_weight_field]))
                for bit in range(ratio_slack_bits_per_constraint):
                    coeffs[ratio_slack_idx(pair_pos, route_pos, bit)] = pathwise_ratio_resolution * (2 ** bit)
                offset += _add_square_penalty(Q, coeffs, 0.0, pathwise_ratio_penalty)

    initial_state = np.zeros(total_variables, dtype=np.int8)
    for path_idx, baseline_path in enumerate(baseline_paths):
        if path_idx >= k_paths:
            break
        for edge in baseline_path.get("route_edges", []):
            initial_state[var_idx(path_idx, int(edge["edge_idx"]))] = 1

    if use_hard_overlap_budget or use_pathwise_ratio_constraint:
        baseline_path_segment_sets = [
            set(path.get("segment_ids", []))
            for path in baseline_paths[:k_paths]
        ]
        for pair, pair_pos in pair_to_pos.items():
            if max(pair) >= len(baseline_path_segment_sets):
                continue
            shared_segments = baseline_path_segment_sets[pair[0]] & baseline_path_segment_sets[pair[1]]
            used_budget = 0.0
            for segment_id in shared_segments:
                initial_state[overlap_idx(pair[0], pair[1], segment_id)] = 1
                used_budget += float(by_segment[segment_id][0][overlap_weight_field])
            if use_hard_overlap_budget:
                remaining_units = max(
                    int(math.floor((overlap_budget_cap - used_budget) / overlap_budget_resolution + 1e-9)),
                    0,
                )
                for bit, bit_value in enumerate(_fill_slack_bits(remaining_units, slack_bits_per_pair)):
                    if bit_value:
                        initial_state[slack_idx(pair_pos, bit)] = 1
            if use_pathwise_ratio_constraint:
                for route_pos, pair_path_idx in enumerate(pair):
                    if pair_path_idx >= len(baseline_paths):
                        continue
                    route_overlap_weight = float(baseline_paths[pair_path_idx].get("route_weight_for_overlap", 0.0))
                    remaining_units = max(
                        int(math.floor(((theta * route_overlap_weight) - used_budget) / pathwise_ratio_resolution + 1e-9)),
                        0,
                    )
                    for bit, bit_value in enumerate(_fill_slack_bits(remaining_units, ratio_slack_bits_per_constraint)):
                        if bit_value:
                            initial_state[ratio_slack_idx(pair_pos, route_pos, bit)] = 1

    warm_start_enabled = bool(config.get("use_penalty_baseline_warm_start", True))
    solver_context = {
        "initial_state": initial_state if warm_start_enabled else None,
        "initial_state_name": f"penalty_baseline_{hard_overlap_mode}" if warm_start_enabled else "random",
        "warm_start_flip_prob": float(config.get("warm_start_flip_prob", 0.02)) if warm_start_enabled else 0.0,
        "baseline_route_count": int(baseline_payload.get("k_paths_found", 0)),
        "problem_type": (
            "kSPwLO_style_budget_plus_ratio"
            if use_hard_overlap_budget and use_pathwise_ratio_constraint
            else "kSPwLO_style_pathwise_ratio"
            if use_pathwise_ratio_constraint
            else "kSPwLO_style_hard_overlap_budget"
            if use_hard_overlap_budget
            else "kSPwLO_style_soft_overlap"
        ),
    }

    baseline_total_cost = float(sum(path["route_cost"] for path in baseline_paths))
    baseline_total_length = float(sum(path["route_length"] for path in baseline_paths))

    def decoder(best_state_binary: np.ndarray, out_dir: Optional[str] = None) -> Dict[str, Any]:
        state_vector = np.asarray(best_state_binary, dtype=np.float64)
        path_results: List[Dict[str, Any]] = []
        qgis_export: Dict[str, str] = {}
        artifact_dir = None
        if out_dir:
            artifact_dir = os.path.join(out_dir, "05_kspwlo_problem")
            os.makedirs(artifact_dir, exist_ok=True)

        edge_lookup = {int(edge["edge_idx"]): edge for edge in full_edge_records}

        for path_idx in range(k_paths):
            selected_features = [
                dict(edge)
                for edge in full_edge_records
                if int(best_state_binary[var_idx(path_idx, int(edge["edge_idx"]))]) == 1
            ]
            decoded_route = _shortest_path(
                selected_features,
                source_node,
                target_node,
                weight_field="cost",
            )
            invalid_signatures = set(_route_signatures(selected_features)) - set(_route_signatures(decoded_route))
            summary = _route_summary(decoded_route, f"sqa_path_{path_idx + 1}", overlap_weight_field)
            summary["path_index"] = int(path_idx + 1)
            summary["selected_edge_count"] = int(len(selected_features))
            summary["invalid_selected_edges_count"] = int(len(invalid_signatures))
            path_results.append(summary)

            qgis_export[f"sqa_path_{path_idx + 1}_geojson"] = _edges_geojson(decoded_route, graph_crs)
            qgis_export[f"sqa_selected_edges_path_{path_idx + 1}_geojson"] = _edges_geojson(selected_features, graph_crs)

        ordered_paths = sorted(path_results, key=lambda item: (not item["route_found"], item["route_cost"] or float("inf")))
        pairwise_similarity = []
        for path_a, path_b in combinations(path_results, 2):
            route_a = [dict(edge_lookup[int(edge["edge_idx"])]) for edge in path_a["route_edges"]]
            route_b = [dict(edge_lookup[int(edge["edge_idx"])]) for edge in path_b["route_edges"]]
            similarity = _weighted_overlap_ratio(route_a, route_b, overlap_weight_field)
            shared_ids = set(path_a["segment_ids"]) & set(path_b["segment_ids"])
            shared_weight = float(sum(float(by_segment[segment_id][0][overlap_weight_field]) for segment_id in shared_ids))
            pairwise_similarity.append(
                {
                    "path_i": int(path_a["path_index"]),
                    "path_j": int(path_b["path_index"]),
                    "similarity": float(similarity),
                    "theta_threshold": float(theta),
                    "within_threshold": bool(similarity <= theta + 1e-9),
                    "shared_weight": shared_weight,
                    "hard_budget_cap": float(overlap_budget_cap),
                    "within_hard_budget": bool(
                        (not use_hard_overlap_budget)
                        or (shared_weight <= overlap_budget_cap + overlap_budget_resolution + 1e-9)
                    ),
                    "within_pathwise_ratio_i": bool(
                        (not use_pathwise_ratio_constraint)
                        or (shared_weight <= theta * float(path_a["route_weight_for_overlap"]) + pathwise_ratio_resolution + 1e-9)
                    ),
                    "within_pathwise_ratio_j": bool(
                        (not use_pathwise_ratio_constraint)
                        or (shared_weight <= theta * float(path_b["route_weight_for_overlap"]) + pathwise_ratio_resolution + 1e-9)
                    ),
                }
            )

        for idx, baseline_path in enumerate(baseline_paths, start=1):
            baseline_edges = [dict(edge_lookup[int(edge["edge_idx"])]) for edge in baseline_path.get("route_edges", [])]
            qgis_export[f"baseline_path_{idx}_geojson"] = _edges_geojson(baseline_edges, graph_crs)

        total_selected_edge_count = sum(path["selected_edge_count"] for path in path_results)
        all_paths_found = all(path["route_found"] for path in path_results)
        total_route_cost = float(sum(path["route_cost"] for path in path_results if path["route_found"]))
        total_route_length = float(sum(path["route_length"] for path in path_results if path["route_found"]))
        avg_walkability = (
            float(np.mean([path["route_average_walkability"] for path in path_results if path["route_found"]]))
            if any(path["route_found"] for path in path_results)
            else 0.0
        )

        sqa_set_signature = _paths_set_signature(path_results)
        baseline_set_signature = _paths_set_signature(baseline_paths)

        max_similarity = max((item["similarity"] for item in pairwise_similarity), default=0.0)
        max_shared_weight = max((item["shared_weight"] for item in pairwise_similarity), default=0.0)
        pairwise_within_theta = all(item["within_threshold"] for item in pairwise_similarity)
        pairwise_within_hard_budget = all(item["within_hard_budget"] for item in pairwise_similarity)
        pairwise_within_pathwise_ratio = all(
            item["within_pathwise_ratio_i"] and item["within_pathwise_ratio_j"]
            for item in pairwise_similarity
        )

        problem_summary = {
            "problem_name": "kSPwLO-style alternative routing with SQA",
            "k_paths": int(k_paths),
            "theta_overlap": float(theta),
            "epsilon_near_shortest": float(epsilon),
            "overlap_weight_field": overlap_weight_field,
            "soft_overlap_penalty": float(overlap_penalty),
            "hard_overlap_mode": hard_overlap_mode,
            "use_hard_overlap_budget": bool(use_hard_overlap_budget),
            "use_pathwise_ratio_constraint": bool(use_pathwise_ratio_constraint),
            "hard_overlap_penalty": float(hard_overlap_penalty),
            "overlap_link_penalty": float(overlap_link_penalty),
            "hard_overlap_budget_cap": float(overlap_budget_cap),
            "hard_overlap_budget_resolution": float(overlap_budget_resolution),
            "hard_overlap_slack_bits_per_pair": int(slack_bits_per_pair),
            "pathwise_ratio_penalty": float(pathwise_ratio_penalty),
            "pathwise_ratio_resolution": float(pathwise_ratio_resolution),
            "pathwise_ratio_route_cap": float(ratio_route_weight_cap),
            "pathwise_ratio_slack_bits_per_constraint": int(ratio_slack_bits_per_constraint),
            "source_node": int(source_node),
            "target_node": int(target_node),
        }

        if artifact_dir:
            _write_json(os.path.join(artifact_dir, "problem_definition.json"), problem_summary)
            _write_json(os.path.join(artifact_dir, "baseline_penalty_heuristic.json"), baseline_payload)
            _write_json(os.path.join(artifact_dir, "sqa_path_summaries.json"), path_results)
            _write_json(os.path.join(artifact_dir, "pairwise_similarity.json"), pairwise_similarity)
            _write_rows(
                os.path.join(artifact_dir, "sqa_paths.csv"),
                [
                    {
                        "path_index": path["path_index"],
                        "route_found": path["route_found"],
                        "selected_edge_count": path["selected_edge_count"],
                        "route_cost": path["route_cost"],
                        "route_length": path["route_length"],
                        "route_average_walkability": path["route_average_walkability"],
                        "invalid_selected_edges_count": path["invalid_selected_edges_count"],
                    }
                    for path in path_results
                ],
            )
            _write_rows(
                os.path.join(artifact_dir, "baseline_paths.csv"),
                [
                    {
                        "path_label": path["path_label"],
                        "route_found": path["route_found"],
                        "route_cost": path["route_cost"],
                        "route_length": path["route_length"],
                        "route_average_walkability": path["route_average_walkability"],
                    }
                    for path in baseline_paths
                ],
            )
            _write_rows(os.path.join(artifact_dir, "pairwise_similarity.csv"), pairwise_similarity)
            for name, geojson_text in qgis_export.items():
                _write_geojson(os.path.join(artifact_dir, f"{name.replace('_geojson', '')}.geojson"), geojson_text)

        return {
            "source_node": int(source_node),
            "target_node": int(target_node),
            "source_coord_projected": source_xy,
            "target_coord_projected": target_xy,
            "selected_edge_count": int(total_selected_edge_count),
            "route_found": bool(all_paths_found),
            "decoded_route_length": float(total_route_length),
            "decoded_route_cost": float(total_route_cost),
            "decoded_route_average_walkability": float(avg_walkability),
            "selected_state_qubo_energy": float(state_vector @ Q @ state_vector),
            "problem_definition": problem_summary,
            "sqa_paths": path_results,
            "baseline_penalty_heuristic": {
                **baseline_payload,
                "total_route_cost": baseline_total_cost,
                "total_route_length": baseline_total_length,
            },
            "baseline_dijkstra": {
                "route_edges": baseline_payload.get("route_edges", []),
                "route_found": baseline_payload.get("route_found", False),
                "route_length": baseline_payload.get("route_length"),
                "route_cost": baseline_payload.get("route_cost"),
                "route_average_walkability": baseline_payload.get("route_average_walkability"),
            },
            "pairwise_similarity": pairwise_similarity,
            "comparison_to_dijkstra": {
                "matches_exact_route": bool(sqa_set_signature == baseline_set_signature),
                "baseline_k_paths_found": int(baseline_payload.get("k_paths_found", 0)),
                "sqa_all_paths_found": bool(all_paths_found),
                "sqa_total_cost_minus_baseline": (
                    float(total_route_cost) - float(baseline_total_cost)
                    if all_paths_found and len(baseline_paths) == k_paths
                    else None
                ),
            },
            "comparison_to_baseline_heuristic": {
                "matches_exact_set": bool(sqa_set_signature == baseline_set_signature),
                "baseline_k_paths_found": int(baseline_payload.get("k_paths_found", 0)),
                "sqa_all_paths_found": bool(all_paths_found),
                "sqa_total_cost_minus_baseline": (
                    float(total_route_cost) - float(baseline_total_cost)
                    if all_paths_found and len(baseline_paths) == k_paths
                    else None
                ),
                "sqa_max_similarity_minus_theta": float(max_similarity - theta),
                "sqa_max_shared_weight_minus_cap": float(max_shared_weight - overlap_budget_cap),
            },
            "constraint_diagnostics": {
                "k_paths_requested": int(k_paths),
                "all_paths_found": bool(all_paths_found),
                "pairwise_similarity_within_threshold": bool(pairwise_within_theta),
                "pairwise_hard_budget_within_cap": bool(pairwise_within_hard_budget),
                "pairwise_pathwise_ratio_within_cap": bool(pairwise_within_pathwise_ratio),
                "max_pairwise_similarity": float(max_similarity),
                "max_pairwise_shared_weight": float(max_shared_weight),
            },
            "decoded_route_edges": ordered_paths[0]["route_edges"] if ordered_paths else [],
            "qgis_export": qgis_export,
            "kspwlo_artifacts": {
                "artifact_dir": artifact_dir,
                "problem_definition_json": os.path.join(artifact_dir, "problem_definition.json") if artifact_dir else None,
                "baseline_penalty_heuristic_json": os.path.join(artifact_dir, "baseline_penalty_heuristic.json") if artifact_dir else None,
                "sqa_path_summaries_json": os.path.join(artifact_dir, "sqa_path_summaries.json") if artifact_dir else None,
                "pairwise_similarity_json": os.path.join(artifact_dir, "pairwise_similarity.json") if artifact_dir else None,
            },
        }

    return Q, offset, decoder, solver_context
