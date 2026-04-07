"""
sqa_numpy.py — Simulated Quantum Annealing (SQA) via Path-Integral Monte Carlo
================================================================================

物理基礎
--------
SQA 以 Suzuki-Trotter 展開將 d 維橫向場 Ising 模型映射為
(d+1) 維古典 Ising 模型：

    H_eff = (1/P) Σ_k  x_k^T Q x_k
            − J_⊥(β,Γ,P) Σ_{k,i}  σ_i^k · σ_i^{k+1}    (環狀邊界)

其中
    σ = 2x − 1 ∈ {−1, +1}   (Ising spin，由 binary {0,1} 轉換)

橫向場耦合強度（永遠 ≥ 0，強鐵磁）：
    J_⊥ = −(1/2β) · ln(tanh(βΓ/P))

退火時程：
    β : BETA_INITIAL  → BETA_FINAL      (逆溫度遞增，系統降溫)
    Γ : GAMMA_INITIAL → GAMMA_FINAL     (橫向場逐步關閉，量子 → 古典)

Metropolis 更新（對每個 spin i 在 slice s 中）：
    ΔE = ΔE_cl/P + ΔE_q
       = δ·h_i/P  +  2·J_⊥·σ_i·(σ_i^{s−1} + σ_i^{s+1})
    接受率 = min(1, exp(−β·ΔE))

效能設計
--------
棋盤格（Checkerboard）Trotter 更新（需 P 為偶數且 ≥ 4）：

    Pass 0 → 更新所有偶數切片 [0, 2, 4, ...]
    Pass 1 → 更新所有奇數切片 [1, 3, 5, ...]

    同一 pass 內的切片彼此不相鄰（偶數切片的鄰居皆為奇數切片），
    可視為 R × (P/2) 個完全獨立的量子鏈一次批次計算。

    Python 迴圈： O(2 × N)   （vs 舊版 O(P × N)）
    NumPy 批次： R × P/2     （vs 舊版 R）

局部場增量更新（O(N) per flip，vs 重算 O(N²)）：
    Qx_flat 在每次翻轉後增量更新，避免重複矩陣乘法。

最佳解追蹤：每步用 _all_energies() 掃一次 (R, P)，永不漏接。
"""

import os
import csv
import numpy as np
import matplotlib
matplotlib.use("Agg")           # 非互動後端，適合腳本執行
import matplotlib.pyplot as plt
from tqdm import tqdm
from collections import defaultdict

class SQA_numpy:
    def __init__(self, qubo_matrix, steps=100, replicas=10, slices=20, beta_init=0.1, beta_final=5.0, gamma_init=5.0, gamma_final=0.1, seed=42, output_dir="outputs", verbose: bool = True, init_prob: float = 0.5, initial_state: np.ndarray = None, initial_flip_prob: float = 0.0, qubo_penalty: np.ndarray = None, lambda_init: float = 1.0, lambda_final: float = 1.0, diverse_frac: float = 0.0):
        self.Q       = qubo_matrix.astype(np.float64)
        self.n       = self.Q.shape[0]
        self.R       = replicas
        self.P       = slices
        self.verbose = verbose
        self.output_dir = output_dir
        self.init_prob = float(init_prob)

        if not 0.0 <= self.init_prob <= 1.0:
            raise ValueError(f"init_prob must be between 0 and 1, got {self.init_prob}")

        self.beta_schedule  = np.linspace(beta_init, beta_final, steps)
        self.gamma_schedule = np.linspace(gamma_init, gamma_final, steps)
        self.history        = []
        self.history_records = []
        self.state_evolution = []
        self.samples        = []
        self.initial_state_name = "random"

        np.random.seed(seed)

        if initial_state is None:
            self.state = (
                np.random.random(size=(self.R, self.P, self.n)) < self.init_prob
            ).astype(np.int8)
        else:
            base_state = np.asarray(initial_state, dtype=np.int8).reshape(self.n)
            if base_state.shape[0] != self.n:
                raise ValueError(
                    f"initial_state has wrong dimension {base_state.shape[0]}, expected {self.n}"
                )
            self.state = np.broadcast_to(base_state, (self.R, self.P, self.n)).copy()
            if initial_flip_prob > 0.0:
                noise = (
                    np.random.random(size=(self.R, self.P, self.n)) < float(initial_flip_prob)
                ).astype(np.int8)
                self.state = np.bitwise_xor(self.state, noise)
            
            if diverse_frac > 0.0:
                random_replicas = int(self.R * diverse_frac)
                if random_replicas > 0:
                    self.state[:random_replicas] = (
                        np.random.random(size=(random_replicas, self.P, self.n)) < self.init_prob
                    ).astype(np.int8)

            self.initial_state_name = "warm_start"

        self.qubo_penalty = qubo_penalty.astype(np.float64) if qubo_penalty is not None else None
        self.lambda_init = float(lambda_init)
        self.lambda_final = float(lambda_final)
        
        if self.qubo_penalty is not None:
            self.Q_obj = self.Q - self.qubo_penalty
        else:
            self.Q_obj = self.Q.copy()

        # ── Diverse Initialization（文獻 SQPT：異質 Replica 起點）────────
        # Nakano & Terada 2023 (IEEE Access): 不同 replica 從不同起點出發，
        # 讓系統能同時探索多個能量景觀盆地，避免全體困在同一局部最小值。
        if initial_state is not None and diverse_frac > 0.0:
            n_diverse = max(1, int(self.R * diverse_frac))
            self.state[:n_diverse] = (
                np.random.random(size=(n_diverse, self.P, self.n)) < self.init_prob
            ).astype(np.int8)
            self.initial_state_name = f"hybrid_{self.R - n_diverse}warm_{n_diverse}random"
            if self.verbose:
                print(
                    f"[SQA] Diverse init: {n_diverse}/{self.R} replicas randomized "
                    f"(p={self.init_prob:.3f}), {self.R - n_diverse} from warm start"
                )

        # ── Penalty Annealing 設定（文獻 ALIA：增廣拉格朗日迭代法）────────
        # Bernal et al. 2025 (arXiv:2509.08544): QUBO 約束項過大會「扭曲目標
        # 景觀，使低能譜區間失去資訊性」。ALIA 透過逐步增強懲罰 λ(t)，讓初期
        # Metropolis 可自由穿越約束障壁探索，後期收緊確保可行性。
        #
        # 實作：Q_eff(t) = Q_base + λ(t) · Q_penalty
        #   - _all_energies() 永遠使用完整 QUBO (self.Q) 追蹤真實能量
        #   - Metropolis 使用 Q_sym / Q_diag（反映當前 λ(t)）
        if qubo_penalty is not None:
            self.Q_penalty = qubo_penalty.astype(np.float64)
            self.Q_base    = self.Q - self.Q_penalty
            self.lambda_schedule = np.linspace(lambda_init, lambda_final, len(self.beta_schedule))
            Q_eff = self.Q_base + lambda_init * self.Q_penalty
            if self.verbose:
                print(
                    f"[SQA] Penalty Annealing enabled: λ = {lambda_init:.4f} → {lambda_final:.4f} "
                    f"(penalty ‖Q_pen‖_max={np.max(np.abs(self.Q_penalty)):.1f})"
                )
        else:
            self.Q_penalty = None
            self.Q_base    = None
            self.lambda_schedule = None
            Q_eff = self.Q

        # 預計算對稱化矩陣與對角線向量（Metropolis 用，隨 λ(t) 更新）
        # 局部場公式：h_i = Qx_sym[i] + Q_diag[i]·δ，  ΔE_cl = δ·h_i / P
        self.Q_sym  = Q_eff + Q_eff.T           # (n, n)  Metropolis 用
        self.Q_diag = np.diag(Q_eff).copy()     # (n,)

        # 棋盤格可用條件：P 為偶數且 ≥ 4
        self._use_checkerboard = (self.P % 2 == 0 and self.P >= 4)
        if not self._use_checkerboard and verbose:
            print(
                f"[SQA] 注意：P={self.P} 不符合棋盤格條件（需偶數 ≥ 4），"
                f"退回逐切片更新模式。建議設定 TROTTER_SLICES 為偶數且 ≥ 4。"
            )

    # ──────────────────────────────────────────────────────────────────
    # 能量計算
    # ──────────────────────────────────────────────────────────────────

    def local_energy(self, x: np.ndarray) -> float:
        """單一 binary 狀態向量的 QUBO 能量：E = x^T Q x"""
        x = np.asarray(x, dtype=np.float64)
        return float(x @ self.Q @ x)

    def _all_energies(self) -> np.ndarray:
        """
        向量化計算所有 (R, P) 組合的 QUBO 能量，回傳 shape (R, P)。
        同時服務：(1) total_energy 監控  (2) 每步最佳解追蹤
        """
        s  = self.state.astype(np.float64)                  # (R, P, n)
        Qx = np.tensordot(s, self.Q, axes=([2], [1]))       # (R, P, n)
        return np.einsum("rpn,rpn->rp", s, Qx)              # (R, P)

    def total_energy(self) -> float:
        """所有 replica × slice 的平均 QUBO 能量（僅供監控）"""
        return float(np.mean(self._all_energies()))

    # ──────────────────────────────────────────────────────────────────
    # 量子橫向場耦合
    # ──────────────────────────────────────────────────────────────────

    @staticmethod
    def compute_j_perp(beta: float, gamma: float, P: int) -> float:
        """
        Suzuki-Trotter 橫向場耦合強度：
            J_⊥ = −(1/2β) · ln(tanh(βΓ/P))

        J_⊥ ≥ 0（鐵磁耦合，鄰接切片傾向對齊）。
        大 Γ → 大 J_⊥ → 強量子隧穿；Γ→0 → J_⊥→0 → 古典極限。
        """
        arg = max(beta * gamma / P, 1e-12)
        t   = max(float(np.tanh(arg)), 1e-15)
        return -(1.0 / (2.0 * beta)) * np.log(t)

    # ──────────────────────────────────────────────────────────────────
    # 棋盤格核心更新
    # ──────────────────────────────────────────────────────────────────

    def _update_parity_batch(
        self,
        slice_indices: list[int],
        beta: float,
        j_perp: float,
    ) -> None:
        """
        同時更新一個奇偶 pass 內的所有 Trotter 切片。

        同一 pass 的切片（偶數 [0,2,...] 或奇數 [1,3,...]）彼此不相鄰：
        每個切片的 Trotter 鄰居都屬於另一奇偶組，本 pass 不會修改它們，
        因此這些切片可視為完全獨立 → 合法的平行 Metropolis 更新。

        將 R × M 個獨立鏈展平為 RM 個「虛擬 replica」，
        一次執行 N 個 spin 的 sequential Metropolis sweep。

        Parameters
        ----------
        slice_indices : 本 pass 要更新的切片索引（同奇偶）
        beta, j_perp  : 當前逆溫度與量子耦合強度
        """
        P       = self.P
        Q_sym   = self.Q_sym
        Q_diag  = self.Q_diag
        M       = len(slice_indices)        # ≈ P/2
        RM      = self.R * M                # 虛擬 replica 總數

        # 工作向量：float64 副本，(R, M, n) → 展平 (RM, n)
        x_flat  = (
            self.state[:, slice_indices, :]
            .astype(np.float64)
            .reshape(RM, self.n)
        )
        # 預計算 Q_sym @ x，後續增量更新：(RM, n)
        Qx_flat = x_flat @ Q_sym

        # 相鄰切片（另一奇偶組，本 pass 固定不動）的 Ising spin
        prev_s  = [(s - 1) % P for s in slice_indices]   # 均屬另一奇偶
        next_s  = [(s + 1) % P for s in slice_indices]
        # sigma_prev + sigma_next：(R, M, n) → (RM, n)
        nb_flat = (
            2.0 * self.state[:, prev_s, :].astype(np.float64) - 1.0
            + 2.0 * self.state[:, next_s, :].astype(np.float64) - 1.0
        ).reshape(RM, self.n)

        # Sequential spin sweep（同切片內 spin 有順序依賴，不可並行）
        for i in np.random.permutation(self.n):
            x_i    = x_flat[:, i]                                   # (RM,)
            delta  = 1.0 - 2.0 * x_i                               # (RM,)

            # ── 1. 古典 QUBO ΔE（除以 P）──────────────────────────
            h_i    = Qx_flat[:, i] + Q_diag[i] * delta             # (RM,)
            dE_cl  = delta * h_i / P                                # (RM,)

            # ── 2. 量子 Trotter 耦合 ΔE ────────────────────────────
            # ΔE_q = 2·J_⊥·σ_i·(σ_{i,s-1} + σ_{i,s+1})
            sigma_i = 2.0 * x_i - 1.0                              # (RM,)
            dE_q   = 2.0 * j_perp * sigma_i * nb_flat[:, i]        # (RM,)

            dE = dE_cl + dE_q                                       # (RM,)

            # ── Metropolis（向量化）──────────────────────────────────
            # dE ≤ 0 直接接受；dE > 0 才算 exp，避免不必要的指數運算
            accept   = dE <= 0.0
            need_exp = ~accept
            if need_exp.any():
                accept[need_exp] = (
                    np.random.rand(int(need_exp.sum()))
                    < np.exp(-beta * dE[need_exp])
                )

            if accept.any():
                x_flat[accept, i]  = 1.0 - x_i[accept]
                # 增量更新 Qx_flat（Q_sym 對稱，故 Q_sym[i] == Q_sym[:, i]）
                Qx_flat[accept]   += delta[accept, np.newaxis] * Q_sym[i]

        # 寫回 self.state：(RM, n) → (R, M, n) → int8
        self.state[:, slice_indices, :] = (
            x_flat.reshape(self.R, M, self.n).astype(np.int8)
        )

    def _update_slice_sequential(self, s: int, beta: float, j_perp: float) -> None:
        """
        退化路徑：逐一更新單一 Trotter 切片（僅 P 為奇數或 < 4 時使用）。
        所有 R 個 replica 仍然向量化同時計算。
        """
        P       = self.P
        Q_sym   = self.Q_sym
        Q_diag  = self.Q_diag

        x_all   = self.state[:, s].astype(np.float64)          # (R, n)
        Qx_all  = x_all @ Q_sym                                 # (R, n)

        s_prev  = (s - 1) % P
        s_next  = (s + 1) % P
        nb_all  = (
            2.0 * self.state[:, s_prev].astype(np.float64) - 1.0
            + 2.0 * self.state[:, s_next].astype(np.float64) - 1.0
        )                                                       # (R, n)

        for i in np.random.permutation(self.n):
            x_i    = x_all[:, i]
            delta  = 1.0 - 2.0 * x_i
            h_i    = Qx_all[:, i] + Q_diag[i] * delta
            dE_cl  = delta * h_i / P
            sigma_i = 2.0 * x_i - 1.0
            dE_q   = 2.0 * j_perp * sigma_i * nb_all[:, i]
            dE     = dE_cl + dE_q

            accept   = dE <= 0.0
            need_exp = ~accept
            if need_exp.any():
                accept[need_exp] = (
                    np.random.rand(int(need_exp.sum()))
                    < np.exp(-beta * dE[need_exp])
                )
            if accept.any():
                x_all[accept, i]  = 1.0 - x_i[accept]
                Qx_all[accept]   += delta[accept, np.newaxis] * Q_sym[i]

        self.state[:, s, :] = x_all.astype(np.int8)

    # ──────────────────────────────────────────────────────────────────
    # 對外介面：一次完整 sweep
    # ──────────────────────────────────────────────────────────────────

    def step(self, beta: float, gamma: float) -> None:
        """
        一次完整 SQA sweep（遍歷所有 Trotter slice）。

        棋盤格模式（P 偶數 ≥ 4）：
            Pass 0 更新偶數切片，Pass 1 更新奇數切片。
            每 pass 批次大小為 R × (P/2)，Python 迴圈從 P×N 降至 2×N。

        退化模式（P 奇數或 < 4）：
            逐切片更新，但每切片內 R 個 replica 仍向量化。
        """
        j_perp = self.compute_j_perp(beta, gamma, self.P)

        if self._use_checkerboard:
            for parity in (0, 1):
                slices = list(range(parity, self.P, 2))
                self._update_parity_batch(slices, beta, j_perp)
        else:
            for s in range(self.P):
                self._update_slice_sequential(s, beta, j_perp)

    # ──────────────────────────────────────────────────────────────────
    # 最佳解輔助
    # ──────────────────────────────────────────────────────────────────

    def _best_this_step(self, energies: np.ndarray) -> tuple:
        """給定 (R, P) 能量陣列，回傳 (最低能量, 對應狀態副本)。"""
        idx   = np.unravel_index(np.argmin(energies), energies.shape)
        return float(energies[idx]), self.state[idx].copy()

    # ──────────────────────────────────────────────────────────────────
    # 取樣 / Debug 輔助（僅對小 N 有意義）
    # ──────────────────────────────────────────────────────────────────

    def record_samples(self) -> None:
        """
        紀錄當前所有 (R, P) 切片的狀態與能量，供分布統計。
        對大 N（> 50）略過：狀態空間 2^N 中重複率幾乎為零，統計無意義。
        """
        if self.n > 50:
            return
        for r in range(self.R):
            for s in range(self.P):
                x_tup = tuple(int(v) for v in self.state[r, s])
                e     = self.local_energy(np.array(x_tup, dtype=np.float64))
                self.samples.append((x_tup, e))

    def debug_state_energies(self) -> None:
        """
        印出每個 (replica, slice) 的能量。
        僅對 N ≤ 20 執行：N 較大時輸出無法閱讀且佔滿終端機。
        """
        if self.n > 20:
            return
        print("  [Debug] Replica × Slice energies:")
        for r in range(self.R):
            for s in range(self.P):
                x = self.state[r, s].astype(np.float64)
                print(
                    f"    R{r:02d} S{s:02d}  "
                    f"{self.state[r, s].tolist()}  "
                    f"E={self.local_energy(x):.6f}"
                )

    def summarize_samples(
        self,
        best_state: np.ndarray,
        best_energy: float,
    ) -> np.ndarray:
        """分布統計摘要（小 N 用）並回傳全域最佳狀態。"""
        if self.samples and self.n <= 50:
            count: dict = defaultdict(int)
            for x, _ in self.samples:
                count[x] += 1
            print("\n=== 樣本分布（每 10 步採樣一次）===")
            for x in list(sorted(count.keys()))[:20]:
                e = self.local_energy(np.array(x, dtype=np.float64))
                print(f"  {list(x)}  count={count[x]}  E={e:.6f}")
            if len(count) > 20:
                print(f"  ... (共 {len(count)} 種不同狀態)")

        print("\n=== 全域最佳解（每步追蹤，不會漏接）===")
        print(f"  State  : {list(best_state)}")
        print(f"  Energy : {best_energy:.6f}")
        return best_state

    # ──────────────────────────────────────────────────────────────────
    # 視覺化
    # ──────────────────────────────────────────────────────────────────

    def plot_state_evolution(self) -> None:
        """
        儲存「最佳切片」狀態演化圖（每步使用最低能量 (r,s) 的狀態）。

        僅對 N ≤ 30 繪製：N 更大時 30+ 條線完全重疊，圖像無法閱讀。
        輸出路徑：RESULTS_DIR/figures/state_evolution.png
        """
        if self.n > 30:
            if self.verbose:
                print(
                    f"[SQA] 跳過狀態演化圖（N={self.n} > 30，"
                    f"多 spin 疊加後圖像不可讀）。"
                )
            return

        figures_dir = os.path.join(self.output_dir, "figures")
        os.makedirs(figures_dir, exist_ok=True)

        arr = np.array(self.state_evolution)   # (steps, n)
        plt.figure(figsize=(10, 4))
        for i in range(self.n):
            plt.plot(arr[:, i] + i * 1.5)
        plt.yticks([])
        plt.xlabel("Step")
        plt.title("State Evolution — best-energy (r,s) slice per step")
        plt.tight_layout()
        save_path = os.path.join(figures_dir, "state_evolution.png")
        plt.savefig(save_path, dpi=120)
        plt.close()
        if self.verbose:
            print(f"[SQA] State evolution → {save_path}")

    def plot_energy_history(self) -> None:
        """儲存能量收斂曲線（對任意 N 皆有意義）。"""
        figures_dir = os.path.join(self.output_dir, "figures")
        os.makedirs(figures_dir, exist_ok=True)

        plt.figure(figsize=(8, 4))
        plt.plot(self.history, lw=1.2, color="steelblue", label="E_avg")
        plt.xlabel("Step")
        plt.ylabel("Average QUBO Energy")
        plt.title("SQA Energy Convergence")
        plt.legend()
        plt.tight_layout()
        save_path = os.path.join(figures_dir, "energy_history.png")
        plt.savefig(save_path, dpi=120)
        plt.close()
        if self.verbose:
            print(f"[SQA] Energy history → {save_path}")

    def write_iteration_csv(self) -> None:
        csv_path = os.path.join(self.output_dir, "iteration_history.csv")
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "step",
                    "beta",
                    "gamma",
                    "j_perp",
                    "lambda_penalty",
                    "avg_energy",
                    "step_best_energy",
                    "best_energy_so_far",
                    "step_best_ones",
                ],
            )
            writer.writeheader()
            writer.writerows(self.history_records)
        if self.verbose:
            print(f"[SQA] Iteration CSV → {csv_path}")

    def plot_annealing_overview(self) -> None:
        figures_dir = os.path.join(self.output_dir, "figures")
        os.makedirs(figures_dir, exist_ok=True)

        if not self.history_records:
            return

        steps = [row["step"] for row in self.history_records]
        avg_energy = [row["avg_energy"] for row in self.history_records]
        step_best = [row["step_best_energy"] for row in self.history_records]
        best_so_far = [row["best_energy_so_far"] for row in self.history_records]
        beta_vals = [row["beta"] for row in self.history_records]
        gamma_vals = [row["gamma"] for row in self.history_records]
        j_perp_vals = [row["j_perp"] for row in self.history_records]
        ones_vals = [row["step_best_ones"] for row in self.history_records]

        fig, axes = plt.subplots(2, 2, figsize=(12, 8))

        axes[0, 0].plot(steps, avg_energy, label="E_avg", color="steelblue")
        axes[0, 0].plot(steps, step_best, label="E_best_step", color="darkorange", alpha=0.8)
        axes[0, 0].plot(steps, best_so_far, label="E_best_so_far", color="seagreen", lw=1.4)
        axes[0, 0].set_title("Energy")
        axes[0, 0].set_xlabel("Step")
        axes[0, 0].legend()

        axes[0, 1].plot(steps, beta_vals, label="beta", color="firebrick")
        axes[0, 1].plot(steps, gamma_vals, label="gamma", color="purple")
        lambda_vals = [row.get("lambda_penalty", 1.0) for row in self.history_records]
        if any(v != 1.0 for v in lambda_vals):
            ax_lambda = axes[0, 1].twinx()
            ax_lambda.plot(steps, lambda_vals, label="λ_penalty", color="darkorange", ls="--")
            ax_lambda.set_ylabel("λ_penalty")
            ax_lambda.legend(loc="center right")
        axes[0, 1].set_title("Annealing Schedule")
        axes[0, 1].set_xlabel("Step")
        axes[0, 1].legend()

        axes[1, 0].plot(steps, j_perp_vals, color="teal")
        axes[1, 0].set_title("Quantum Coupling J_perp")
        axes[1, 0].set_xlabel("Step")

        axes[1, 1].plot(steps, ones_vals, color="slategray")
        axes[1, 1].set_title("Selected Edges in Step Best State")
        axes[1, 1].set_xlabel("Step")

        fig.suptitle("SQA Annealing Overview")
        fig.tight_layout()
        save_path = os.path.join(figures_dir, "annealing_overview.png")
        fig.savefig(save_path, dpi=140)
        plt.close(fig)
        if self.verbose:
            print(f"[SQA] Overview figure → {save_path}")

    # ──────────────────────────────────────────────────────────────────
    # 主執行迴圈
    # ──────────────────────────────────────────────────────────────────

    def run(self) -> tuple:
        """
        執行完整退火過程，回傳 (best_binary_state, energy_history)。

        最佳解追蹤
        ----------
        每步呼叫 _all_energies() 掃描所有 (R, P) 的能量，
        立即更新 best_energy_ever / best_state_ever。
        無論最佳解在第幾步出現，絕不漏接。

        state_evolution 記錄
        --------------------
        使用當步最低能量 (r, s) 切片的狀態（非跨 replica/slice 平均）。
        多個 replica 可能收斂到不同極小值，平均值無物理意義。
        """
        initial_energies = self._all_energies()
        best_energy_ever, best_state_ever = self._best_this_step(initial_energies)

        steps = len(self.beta_schedule)
        pbar = tqdm(range(steps), desc="SQA")
        for t in pbar:
            beta  = self.beta_schedule[t]
            gamma = self.gamma_schedule[t]
            j_perp = self.compute_j_perp(beta, gamma, self.P)

            if self.qubo_penalty is not None:
                lam = self.lambda_init + (self.lambda_final - self.lambda_init) * (t / max(1, steps - 1))
                self.Q = self.Q_obj + lam * self.qubo_penalty
                self.Q_sym = self.Q + self.Q.T
                self.Q_diag = np.diag(self.Q).copy()

            self.step(beta, gamma)

            # ── 一次計算所有能量，同時服務監控 + 最佳解追蹤 ──────────
            energies = self._all_energies()             # (R, P)
            e_mean   = float(np.mean(energies))
            self.history.append(e_mean)

            step_best_e, step_best_s = self._best_this_step(energies)
            if step_best_e < best_energy_ever:
                best_energy_ever = step_best_e
                best_state_ever  = step_best_s

            self.history_records.append(
                {
                    "step": int(t),
                    "beta": float(beta),
                    "gamma": float(gamma),
                    "j_perp": float(j_perp),
                    "lambda_penalty": float(lam) if self.qubo_penalty is not None else 1.0,
                    "avg_energy": float(e_mean),
                    "step_best_energy": float(step_best_e),
                    "best_energy_so_far": float(best_energy_ever),
                    "step_best_ones": int(np.sum(step_best_s)),
                }
            )

            postfix_data = {
                "β":      f"{beta:.2f}",
                "Γ":      f"{gamma:.4f}",
                "E_best": f"{best_energy_ever:.4f}",
            }
            if self.qubo_penalty is not None:
                postfix_data["λ_pen"] = f"{lam:.2f}"
            pbar.set_postfix(postfix_data)

            # ── 狀態追蹤：使用最低能量切片（非平均）────────────────────
            # 【修正 Gemini Point 3】跨 replica/slice 平均在多峰問題中無意義：
            # 若 replica A 收斂至 [0,1]，replica B 收斂至 [1,0]，
            # 平均得到 [0.5, 0.5]，是無效解。改用當步最優切片的實際狀態。
            self.state_evolution.append(step_best_s.tolist())

            # ── 定期 log（每 10 步）─────────────────────────────────────
            if t % 10 == 0 and self.verbose:
                print(
                    f"\nStep {t:4d} | β={beta:.3f}  Γ={gamma:.4f}  "
                    f"J_⊥={j_perp:.4f} | "
                    f"E_avg={e_mean:.4f}  E_best={best_energy_ever:.4f}"
                )
                self.debug_state_energies()   # N > 20 時自動略過
                self.record_samples()         # N > 50 時自動略過

        self.write_iteration_csv()
        self.plot_state_evolution()
        self.plot_energy_history()
        self.plot_annealing_overview()
        best_state = self.summarize_samples(best_state_ever, best_energy_ever)
        return best_state, best_energy_ever, self.history, self.history_records


# ── 外部呼叫介面 ─────────────────────────────────────────────────────────────
def run_sqa(qubo_matrix, steps=100, replicas=10, slices=20, beta_init=0.1, beta_final=5.0, gamma_init=5.0, gamma_final=0.1, seed=42, output_dir="outputs", verbose: bool = False, init_prob: float = 0.5, initial_state: np.ndarray = None, initial_flip_prob: float = 0.0, qubo_penalty: np.ndarray = None, lambda_init: float = 1.0, lambda_final: float = 1.0, diverse_frac: float = 0.0) -> tuple:
    """
    對 QUBO 矩陣執行 SQA，回傳 (best_binary_state, energy_history)。

    Parameters
    ----------
    qubo_matrix : np.ndarray, shape (N, N)
        QUBO 矩陣，最小化 x^T Q x。
    verbose : bool
        True = 印出每 10 步的 log 與 debug 資訊（預設 False，適合批次掃描）。

    Returns
    -------
    best_state : np.ndarray[int8], shape (N,)
        找到的最低能量 binary 狀態。
    best_energy : float
        全域掃描到的最低 QUBO 能量。
    history : list[float]
        每步的平均 QUBO 能量。
    """
    sqa = SQA_numpy(
        qubo_matrix,
        steps=steps,
        replicas=replicas,
        slices=slices,
        beta_init=beta_init,
        beta_final=beta_final,
        gamma_init=gamma_init,
        gamma_final=gamma_final,
        seed=seed,
        output_dir=output_dir,
        verbose=verbose,
        init_prob=init_prob,
        initial_state=initial_state,
        initial_flip_prob=initial_flip_prob,
        qubo_penalty=qubo_penalty,
        lambda_init=lambda_init,
        lambda_final=lambda_final,
        diverse_frac=diverse_frac,
    )
    return sqa.run()
