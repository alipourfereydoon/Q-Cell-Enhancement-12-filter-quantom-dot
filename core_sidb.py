"""
core_sidb.py — Common SiDB physics, simulation, and utility functions.
"""

import numpy as np
from itertools import product
from typing import List, Tuple, Optional
from dataclasses import dataclass


@dataclass
class SiDBParams:
    mu_minus: float = -0.31
    mu_plus:    float = -0.32
    epsilon_r:  float = 5.6
    lambda_tf: float = 5.0
    d_min:  float = 0.76
    a_cc:  float = 3.84
    q_e: float = 1.0
    E_valid_min: float = 0.5947


class SiDBLayout:
   
    def __init__(self,
                 canvas_inputs: List[Tuple[int, int]],
                 cell_sidbs:    List[Tuple[int, int]]):
        self.canvas_inputs = list(canvas_inputs)
        self.cell_sidbs = list(cell_sidbs)
        self.all  = list(canvas_inputs) + list(cell_sidbs)
        self.n = len(self.all)

    @property
    def n_in(self) -> int:
        """Number of input pins on the canvas."""
        return len(self.canvas_inputs) - 2   
                                            

    @property
    def n_cell(self) -> int:
        return len(self.cell_sidbs)

    def distances(self) -> np.ndarray:
        d = np.zeros((self.n, self.n))
        for i in range(self.n):
            for j in range(i + 1, self.n):
                dij = np.hypot(self.all[i][0] - self.all[j][0],
                               self.all[i][1] - self.all[j][1]) * 3.84
                d[i, j] = d[j, i] = dij
        return d


def electrostatic_potential(layout: SiDBLayout, charges: np.ndarray,
                            params: SiDBParams) -> np.ndarray:
    n = layout.n
    V = np.zeros(n)
    d = layout.distances()
    coeff = 1.0 / (4 * np.pi * params.epsilon_r)
    for i in range(n):
        for j in range(n):
            if i != j and d[i, j] > 0:
                V[i] += -coeff * np.exp(-d[i, j] / params.lambda_tf) \
                          / d[i, j] * charges[j] * params.q_e
    return V


def ground_state_energy(layout: SiDBLayout, params: SiDBParams,
                        max_iter: int = 200000) -> Tuple[float, np.ndarray]:
    best_E =  np.inf
    best_n = np.zeros(layout.n, dtype=int)
    n = layout.n
    qe = params.q_e
    it = 0
    for signs in product([-1, 0, 1], repeat=n):
        it += 1
        if it > max_iter:
            break
        n_vec = np.array(signs)
        if np.sum(n_vec == 1) != np.sum(n_vec == -1):
            continue
        V = electrostatic_potential(layout, n_vec, params)
        ok = True
        for i in range(n):
            if n_vec[i] == -1 and V[i] >= 0:
                ok = False; break
            if n_vec[i] ==  1 and V[i] <= 0:
                ok = False; break
            if n_vec[i] ==  0 and (V[i] < params.mu_plus or
                                    V[i] > params.mu_minus):
                ok = False; break
        if not ok:
            continue
        E = 0.0
        for i in range(n):
            for j in range(i + 1, n):
                if n_vec[i] != 0 and n_vec[j] != 0:
                    E += 0.5 * V[i] * n_vec[j] * qe
        if E < best_E:
            best_E, best_n = E, n_vec
    return best_E, best_n


def decode_output(charge_vec: np.ndarray,
                  n_canvas: int) -> int:
   
    return int(np.sum(charge_vec[n_canvas:][-2:]) < 0)


def decode_all_outputs(charge_vec: np.ndarray,
                       n_canvas: int, n_outputs: int = 1) -> int:
    cell_vec = charge_vec[n_canvas:]
    if len(cell_vec) < 2 * n_outputs:
        return 0
    return int(np.sum(cell_vec[-2*n_outputs:]) < 0)