import math
import os
from typing import Any, Dict, Tuple

import geopandas as gpd
from shapely.geometry import Point


def _resolve_graph_paths(data_path: str, config: Dict[str, Any]) -> Tuple[str, str]:
    directed_name = config.get("directed_edges_file", "directed_edges_main_component.geojson")
    segments_name = config.get("segments_file", "segments_main_component.geojson")

    if os.path.isfile(data_path):
        if os.path.basename(data_path) == directed_name:
            base_dir = os.path.dirname(data_path)
            directed_path = data_path
            segments_path = os.path.join(base_dir, segments_name)
            return directed_path, segments_path
        raise FileNotFoundError(
            "Path routing expects a directory or the directed edges file itself. "
            f"Received unsupported file path: {data_path}"
        )

    candidate_pairs = [
        (
            os.path.join(data_path, directed_name),
            os.path.join(data_path, segments_name),
        ),
        (
            os.path.join(data_path, "algorithm_ready", directed_name),
            os.path.join(data_path, "algorithm_ready", segments_name),
        ),
    ]

    for directed_path, segments_path in candidate_pairs:
        if os.path.exists(directed_path) and os.path.exists(segments_path):
            return directed_path, segments_path

    raise FileNotFoundError(
        "Could not locate path routing graph package. Checked:\n"
        + "\n".join(
            f"- directed={directed_path} | segments={segments_path}"
            for directed_path, segments_path in candidate_pairs
        )
    )


def _normalize_coord(coord_like: Any) -> Tuple[float, float]:
    if not isinstance(coord_like, (list, tuple)) or len(coord_like) != 2:
        raise ValueError(f"Invalid coordinate: {coord_like!r}")
    return float(coord_like[0]), float(coord_like[1])


def _project_coord(
    coord_like: Any,
    source_crs: str,
    target_crs: Any,
) -> Tuple[float, float]:
    x, y = _normalize_coord(coord_like)
    if target_crs is None or str(target_crs) == source_crs:
        return x, y
    series = gpd.GeoSeries([Point(x, y)], crs=source_crs).to_crs(target_crs)
    pt = series.iloc[0]
    return float(pt.x), float(pt.y)


def load_data(data_dir: str, config: Dict[str, Any]) -> Dict[str, Any]:
    directed_path, segments_path = _resolve_graph_paths(data_dir, config)
    print(f"=== [Path Routing Adapter] Loading graph package ===")
    print(f"Directed edges: {directed_path}")
    print(f"Segments      : {segments_path}")

    directed_gdf = gpd.read_file(directed_path)
    segments_gdf = gpd.read_file(segments_path)

    if directed_gdf.empty:
        raise ValueError("Directed edge layer is empty.")
    if segments_gdf.empty:
        raise ValueError("Segment layer is empty.")

    required_cols = {
        "segment_id",
        "direction",
        "source_node",
        "target_node",
        "segment_length",
    }
    missing = required_cols - set(directed_gdf.columns)
    if missing:
        raise ValueError(f"Directed edge layer is missing required columns: {sorted(missing)}")

    walkability_field = config.get("walkability_field", "dynwd12")
    if walkability_field not in directed_gdf.columns:
        raise ValueError(
            f"walkability_field={walkability_field!r} not found in directed edge layer."
        )

    raw_node_coords: Dict[int, Tuple[float, float]] = {}
    edges_info = []

    for edge_idx, row in enumerate(directed_gdf.itertuples(index=False)):
        geom = row.geometry
        if geom is None or geom.is_empty:
            continue

        coords = list(geom.coords)
        if len(coords) < 2:
            continue

        source_node = int(row.source_node)
        target_node = int(row.target_node)
        direction = str(row.direction)

        if direction == "forward":
            source_xy = coords[0]
            target_xy = coords[-1]
        else:
            source_xy = coords[-1]
            target_xy = coords[0]

        raw_node_coords[source_node] = (float(source_xy[0]), float(source_xy[1]))
        raw_node_coords[target_node] = (float(target_xy[0]), float(target_xy[1]))

        length = float(getattr(row, "segment_length", getattr(row, "length")))
        walkability = float(getattr(row, walkability_field))
        orig_feature_id = getattr(row, "id", edge_idx)

        edges_info.append(
            {
                "edge_idx": edge_idx,
                "segment_id": str(row.segment_id),
                "source": source_node,
                "target": target_node,
                "length": length,
                "dynwd": walkability,
                "orig_feature_id": orig_feature_id,
                "direction": direction,
                "geometry": geom,
                "component_id": int(getattr(row, "component_id", 0)),
                "urbantype": getattr(row, "urbantype", None),
            }
        )

    raw_node_ids = sorted(raw_node_coords.keys())
    node_id_map = {raw_id: idx for idx, raw_id in enumerate(raw_node_ids)}
    node_coords = {
        node_id_map[raw_id]: coord
        for raw_id, coord in raw_node_coords.items()
    }
    for edge in edges_info:
        edge["source_raw"] = edge["source"]
        edge["target_raw"] = edge["target"]
        edge["source"] = node_id_map[edge["source"]]
        edge["target"] = node_id_map[edge["target"]]

    coord_crs = config.get("coord_crs", "EPSG:4326")
    source_xy = _project_coord(config.get("source_coord"), coord_crs, directed_gdf.crs)
    target_xy = _project_coord(config.get("target_coord"), coord_crs, directed_gdf.crs)

    def find_nearest_node(target_xy: Tuple[float, float]) -> Tuple[int, float]:
        best_node = 0
        min_dist = float("inf")
        for node_id, coord in node_coords.items():
            dist = math.dist(coord, target_xy)
            if dist < min_dist:
                min_dist = dist
                best_node = node_id
        return best_node, min_dist

    source_node, source_dist = find_nearest_node(source_xy)
    target_node, target_dist = find_nearest_node(target_xy)
    print(
        f"Selected Routing Source Node: {source_node} (distance={source_dist:.3f})  "
        f"Target Node: {target_node} (distance={target_dist:.3f})"
    )

    if source_node == target_node:
        raise ValueError(
            "Source node and target node resolved to the same graph node. "
            "Please verify source/target coordinates and CRS."
        )

    component_ids = sorted(int(value) for value in segments_gdf["component_id"].dropna().unique())
    graph_summary = {
        "directed_edges_path": directed_path,
        "segments_path": segments_path,
        "graph_crs": str(directed_gdf.crs) if directed_gdf.crs is not None else None,
        "num_nodes": len(node_coords),
        "num_directed_edges": len(edges_info),
        "num_segments": int(len(segments_gdf)),
        "component_ids": component_ids,
        "walkability_field": walkability_field,
        "raw_node_id_min": min(raw_node_ids) if raw_node_ids else None,
        "raw_node_id_max": max(raw_node_ids) if raw_node_ids else None,
        "source_node": source_node,
        "target_node": target_node,
        "source_coord_projected": source_xy,
        "target_coord_projected": target_xy,
        "source_snap_distance": source_dist,
        "target_snap_distance": target_dist,
    }

    return {
        "edges_info": edges_info,
        "num_nodes": len(node_coords),
        "num_edges": len(edges_info),
        "source_node": source_node,
        "target_node": target_node,
        "graph_crs": graph_summary["graph_crs"],
        "node_coords": node_coords,
        "source_xy": source_xy,
        "target_xy": target_xy,
        "directed_gdf": directed_gdf,
        "segments_gdf": segments_gdf,
        "graph_summary": graph_summary,
    }
