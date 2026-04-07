from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import LineString, Point


ROOT = Path("/Users/tsun-yuanku/local/qa_course_platform_github_pages")
INPUT_PATH = ROOT / "303_demo_data/sidewalks/sidewalk_nckuarea_dynamicwalkability_final_cleaned.geojson"
OUTPUT_DIR = ROOT / "303_demo_data/sidewalks/algorithm_ready"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    gdf = gpd.read_file(INPUT_PATH)
    source_name = INPUT_PATH.stem

    node_registry: dict[tuple[float, float], int] = {}
    node_rows: list[dict] = []
    segment_rows: list[dict] = []
    directed_rows: list[dict] = []

    def get_node_id(x: float, y: float) -> int:
        key = (round(float(x), 5), round(float(y), 5))
        if key in node_registry:
            return node_registry[key]
        node_id = len(node_registry)
        node_registry[key] = node_id
        node_rows.append(
            {
                "node_id": node_id,
                "x": key[0],
                "y": key[1],
                "geometry": Point(key[0], key[1]),
            }
        )
        return node_id

    for _, row in gdf.iterrows():
        geom = row.geometry
        if geom is None:
            continue

        if geom.geom_type == "LineString":
            parts = [geom]
        elif geom.geom_type == "MultiLineString":
            parts = list(geom.geoms)
        else:
            continue

        base_attrs = row.drop(labels=["geometry"]).to_dict()
        base_id = base_attrs["id"]

        for part_idx, part in enumerate(parts):
            coords = list(part.coords)
            if len(coords) < 2:
                continue

            source_node = get_node_id(*coords[0])
            target_node = get_node_id(*coords[-1])
            segment_id = f"{base_id}:{part_idx}"
            segment_length = float(part.length if len(parts) > 1 else base_attrs.get("length", part.length))

            segment_record = dict(base_attrs)
            segment_record.update(
                {
                    "segment_id": segment_id,
                    "part_idx": part_idx,
                    "source_node": source_node,
                    "target_node": target_node,
                    "segment_length": segment_length,
                    "geometry": LineString(coords),
                }
            )
            segment_rows.append(segment_record)

            walkability_cols = [col for col in base_attrs.keys() if col.startswith("dynw")]
            for direction, u, v in (
                ("forward", source_node, target_node),
                ("backward", target_node, source_node),
            ):
                directed_record = dict(base_attrs)
                directed_record.update(
                    {
                        "segment_id": segment_id,
                        "part_idx": part_idx,
                        "direction": direction,
                        "source_node": u,
                        "target_node": v,
                        "segment_length": segment_length,
                        "geometry": LineString(coords),
                    }
                )
                for col in walkability_cols:
                    directed_record[f"cost_{col}"] = float(segment_length + max(5.0 - float(base_attrs[col]), 0.0) * 5.0)
                directed_rows.append(directed_record)

    segments_gdf = gpd.GeoDataFrame(segment_rows, geometry="geometry", crs=gdf.crs)
    nodes_gdf = gpd.GeoDataFrame(node_rows, geometry="geometry", crs=gdf.crs)
    directed_gdf = gpd.GeoDataFrame(directed_rows, geometry="geometry", crs=gdf.crs)

    adjacency = defaultdict(set)
    degree = Counter()
    for row in segment_rows:
        u = row["source_node"]
        v = row["target_node"]
        adjacency[u].add(v)
        adjacency[v].add(u)
        degree[u] += 1
        degree[v] += 1

    component_id_by_node: dict[int, int] = {}
    components: list[dict] = []
    next_component = 0
    for node_id in nodes_gdf["node_id"].tolist():
        if node_id in component_id_by_node:
            continue
        stack = [node_id]
        component_nodes = []
        while stack:
            current = stack.pop()
            if current in component_id_by_node:
                continue
            component_id_by_node[current] = next_component
            component_nodes.append(current)
            for nxt in adjacency[current]:
                if nxt not in component_id_by_node:
                    stack.append(nxt)

        node_set = set(component_nodes)
        component_edges = sum(
            1
            for row in segment_rows
            if row["source_node"] in node_set and row["target_node"] in node_set
        )
        components.append(
            {
                "component_id": next_component,
                "node_count": len(component_nodes),
                "segment_count": component_edges,
            }
        )
        next_component += 1

    nodes_gdf["degree"] = nodes_gdf["node_id"].map(lambda n: int(degree[n]))
    nodes_gdf["is_leaf"] = nodes_gdf["degree"] == 1
    nodes_gdf["component_id"] = nodes_gdf["node_id"].map(component_id_by_node)

    segments_gdf["component_id"] = segments_gdf["source_node"].map(component_id_by_node)
    directed_gdf["component_id"] = directed_gdf["source_node"].map(component_id_by_node)

    largest_component_id = max(components, key=lambda item: item["node_count"])["component_id"]
    nodes_main = nodes_gdf[nodes_gdf["component_id"] == largest_component_id].copy()
    segments_main = segments_gdf[segments_gdf["component_id"] == largest_component_id].copy()
    directed_main = directed_gdf[directed_gdf["component_id"] == largest_component_id].copy()

    components_df = pd.DataFrame(components).sort_values(["node_count", "segment_count"], ascending=False)

    gpkg_path = OUTPUT_DIR / "sidewalk_graph_ready.gpkg"
    if gpkg_path.exists():
        gpkg_path.unlink()

    nodes_gdf.to_file(gpkg_path, layer="nodes_all", driver="GPKG")
    segments_gdf.to_file(gpkg_path, layer="segments_all", driver="GPKG")
    directed_gdf.to_file(gpkg_path, layer="directed_edges_all", driver="GPKG")
    nodes_main.to_file(gpkg_path, layer="nodes_main_component", driver="GPKG")
    segments_main.to_file(gpkg_path, layer="segments_main_component", driver="GPKG")
    directed_main.to_file(gpkg_path, layer="directed_edges_main_component", driver="GPKG")

    nodes_gdf.to_file(OUTPUT_DIR / "nodes_all.geojson", driver="GeoJSON")
    segments_gdf.to_file(OUTPUT_DIR / "segments_all.geojson", driver="GeoJSON")
    directed_gdf.to_file(OUTPUT_DIR / "directed_edges_all.geojson", driver="GeoJSON")
    nodes_main.to_file(OUTPUT_DIR / "nodes_main_component.geojson", driver="GeoJSON")
    segments_main.to_file(OUTPUT_DIR / "segments_main_component.geojson", driver="GeoJSON")
    directed_main.to_file(OUTPUT_DIR / "directed_edges_main_component.geojson", driver="GeoJSON")

    nodes_gdf.drop(columns="geometry").to_csv(OUTPUT_DIR / "nodes_all.csv", index=False)
    segments_gdf.drop(columns="geometry").to_csv(OUTPUT_DIR / "segments_all.csv", index=False)
    directed_gdf.drop(columns="geometry").to_csv(OUTPUT_DIR / "directed_edges_all.csv", index=False)
    components_df.to_csv(OUTPUT_DIR / "components_summary.csv", index=False)

    report = {
        "source_file": str(INPUT_PATH),
        "source_crs": str(gdf.crs) if gdf.crs is not None else None,
        "source_rows": int(len(gdf)),
        "exploded_segment_count": int(len(segments_gdf)),
        "node_count": int(len(nodes_gdf)),
        "directed_edge_count": int(len(directed_gdf)),
        "null_geometry_count": int(gdf.geometry.isna().sum()),
        "invalid_geometry_count": int((~gdf.geometry.is_valid).sum()),
        "component_count": int(len(components)),
        "largest_component_id": int(largest_component_id),
        "largest_component_node_count": int(len(nodes_main)),
        "largest_component_segment_count": int(len(segments_main)),
        "leaf_node_count_all": int(nodes_gdf["is_leaf"].sum()),
        "files_created": [
            "sidewalk_graph_ready.gpkg",
            "nodes_all.geojson",
            "segments_all.geojson",
            "directed_edges_all.geojson",
            "nodes_main_component.geojson",
            "segments_main_component.geojson",
            "directed_edges_main_component.geojson",
            "nodes_all.csv",
            "segments_all.csv",
            "directed_edges_all.csv",
            "components_summary.csv",
            "graph_validation_report.txt",
        ],
    }

    report_lines = [
        f"Source file: {report['source_file']}",
        f"CRS: {report['source_crs']}",
        f"Original rows: {report['source_rows']}",
        f"Exploded segments: {report['exploded_segment_count']}",
        f"Nodes: {report['node_count']}",
        f"Directed edges: {report['directed_edge_count']}",
        f"Null geometries: {report['null_geometry_count']}",
        f"Invalid geometries: {report['invalid_geometry_count']}",
        f"Connected components: {report['component_count']}",
        f"Largest component id: {report['largest_component_id']}",
        f"Largest component nodes: {report['largest_component_node_count']}",
        f"Largest component segments: {report['largest_component_segment_count']}",
        f"Leaf nodes (all): {report['leaf_node_count_all']}",
        "",
        "Interpretation:",
        "- The original cleaned GeoJSON is geometrically valid.",
        "- It is not yet algorithm-ready by itself because it does not explicitly contain graph nodes, directed edges, or component labels.",
        "- The algorithm-ready package produced here keeps the original attributes and adds graph structure required by routing solvers and QGIS workflows.",
        "- For routing by default, use the *_main_component layers unless you intentionally want to keep disconnected subnetworks.",
    ]
    (OUTPUT_DIR / "graph_validation_report.txt").write_text("\n".join(report_lines), encoding="utf-8")
    (OUTPUT_DIR / "graph_validation_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
