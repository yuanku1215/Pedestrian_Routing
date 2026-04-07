import os
import numpy as np
import pandas as pd
import geopandas as gpd
from typing import Dict, Any

def load_data(data_dir: str, config: Dict[str, Any]) -> Dict[str, Any]:
    print(f"=== [Facility Selection Adapter] Loading data from {data_dir} ===")
    
    p_path = os.path.join(data_dir, "p_normalized.csv")
    s_path = os.path.join(data_dir, "s_normalized.csv")
    d_path = os.path.join(data_dir, "d_matrix.csv")
    c_path = os.path.join(data_dir, "facility_cost.csv")
    id_path = os.path.join(data_dir, "points_KDE.shp")

    p_matrix = pd.read_csv(p_path, header=None).values
    s_matrix = pd.read_csv(s_path, header=None).values
    d_matrix = pd.read_csv(d_path, header=None).values

    if os.path.exists(c_path):
        c_vector = pd.read_csv(c_path, header=None).values.flatten()
        print("Loaded facility_cost.csv")
    else:
        fixed_cost = config.get("fixed_cost", 300000)
        candidate_ids = gpd.read_file(id_path)["id"].tolist()
        c_vector = np.full(len(candidate_ids), fixed_cost)
        print(f"Generated uniform cost vector of length {len(candidate_ids)} with cost {fixed_cost}")

    return {
        "p_matrix": p_matrix,
        "s_matrix": s_matrix,
        "d_matrix": d_matrix,
        "c_vector": c_vector
    }
