# === utils.py ===

import os
import numpy as np
import geopandas as gpd
import pandas as pd
import csv

def ensure_dir(path):
    
    os.makedirs(path, exist_ok=True)


def load_matrix(path, binary=False):
    mat = pd.read_csv(path, header=None).values
    if binary:
        return (mat > 0).astype(int)
    return mat


def load_shapefile_ids(shapefile_path):
    gdf = gpd.read_file(shapefile_path)
    if 'id' not in gdf.columns:
        raise ValueError("Shapefile must contain 'id' column.")
    return gdf['id'].tolist()


def build_penalty_matrix(d_matrix, lam):
    n = d_matrix.shape[0]
    penalty = np.zeros((n, n))
    for i in range(n):
        for j in range(n):
            if i != j:
                penalty[i, j] = 1 - np.exp(-lam * d_matrix[i, j])
    return penalty


def write_qubo_equation_summary(qubo, weight_list, save_path):
    w1s, w2s, w3s = 1.0, 1.0, 1.0
    with open(save_path, "w") as f:
        f.write("=== QUBO 目標函數 ===\n")
        f.write("Minimize: xᵀ Q x\n\n")

        f.write("=== 展開形式（symbolic）===\n")
        f.write("f(x) = ΣᵢΣⱼ Q[i,j] * xᵢ * xⱼ\n")
        f.write("      = f₁ + f₂ + f₃ + penalty\n\n")

        f.write("f₁ = -ΣᵢΣⱼ (pᵢ * pⱼ) * xᵢ * xⱼ\n")
        f.write("f₂ =  ΣᵢΣⱼ (sᵢ * sⱼ) * xᵢ * xⱼ\n")
        f.write("f₃ =  Σᵢ cᵢ * xᵢ\n")
        f.write("penalty = ΣᵢΣⱼ≠ᵢ (1 - exp(-λ * dᵢⱼ)) * xᵢ * xⱼ\n\n")

        f.write("=== 權重掃描組合（共 {} 組）===\n".format(len(weight_list)))
        for i, (w1, w2, w3) in enumerate(weight_list):
            # 標準化權重
            sw1, sw2, sw3 = w1 * w1s, w2 * w2s, w3 * w3s

            # 平均化 display 權重（最大值為 1）
            max_scaled = max(sw1, sw2, sw3) or 1e-12  # 防止除以 0
            dw1, dw2, dw3 = sw1 / max_scaled, sw2 / max_scaled, sw3 / max_scaled

            f.write(f"w{i:03d} = ({w1:.2f}, {w2:.2f}, {w3:.2f})")
            f.write(f" → scaled = ({sw1:.6e}, {sw2:.6e}, {sw3:.6e})")
            f.write(f" → display = ({dw1:.3f}, {dw2:.3f}, {dw3:.3f})\n")

        if len(weight_list) > 100:
            f.write("...略\n")

    # 額外輸出為 CSV 表格
    summary_csv = save_path.replace(".txt", ".csv")
    with open(summary_csv, "w", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["w1", "w2", "w3", "scaled_w1", "scaled_w2", "scaled_w3", "display_w1", "display_w2", "display_w3"])
        for w1, w2, w3 in weight_list:
            sw1, sw2, sw3 = w1 * w1s, w2 * w2s, w3 * w3s
            max_scaled = max(sw1, sw2, sw3) or 1e-12
            dw1, dw2, dw3 = sw1 / max_scaled, sw2 / max_scaled, sw3 / max_scaled
            writer.writerow([w1, w2, w3, sw1, sw2, sw3, dw1, dw2, dw3])