import numpy as np
from typing import Tuple, Callable, Dict, Any

def build_qubo(processed_data: Dict[str, Any], config: Dict[str, Any]) -> Tuple[np.ndarray, float, Callable[[np.ndarray], Dict[str, Any]]]:
    p_mat = processed_data["p_matrix"]
    s_mat = processed_data["s_matrix"]
    d_mat = processed_data["d_matrix"]
    cost_vec = processed_data["c_vector"]
    
    lam = config.get("lambda_penalty", 0.002)
    k_size = config.get("k", 10) # Not deeply enforced in legacy, but configurable

    N = p_mat.shape[0]
    print(f"\n[Facility Selection Builder] 構建 QUBO, N={N}")

    Q = np.zeros((N, N))
    offset = 0.0

    # === f1: maximize p_i —> negative term ===
    Q += -np.dot(p_mat, p_mat.T)

    # === f2: sidewalk retrofit cost ===
    Q += np.dot(s_mat, s_mat.T)

    # === f3: construction cost (linear on diagonal) ===
    Q += np.diag(cost_vec)

    # === penalty term: 1 - exp(-λ d_ij) for i ≠ j ===
    mask = ~np.eye(N, dtype=bool)
    Q[mask] += 1 - np.exp(-lam * d_mat[mask])

    print("QUBO matrix built. Shape:", Q.shape)

    def decoder(best_state_binary: np.ndarray) -> Dict[str, Any]:
        selected_indices = np.where(best_state_binary == 1)[0].tolist()
        return {
            "selected_facilities_indices": selected_indices,
            "total_selected": len(selected_indices)
        }

    return Q, offset, decoder
