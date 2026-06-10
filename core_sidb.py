import numpy as np
from itertools import product
from typing import List, Tuple
from dataclasses import dataclass


@dataclass
class SiDBParams:
    mu_minus: float = -0.31
    mu_plus:  float = -0.32
    epsilon_r: float = 5.6
    lambda_tf: float = 5.0
    d_min: float = 0.76
    a_cc: float = 3.84
    q_e: float = 1.0
    E_valid_min: float = 0.5947
    V_scale: float = 14.4


class SiDBLayout:
    def __init__(self, canvas_inputs, cell_sidbs):
        self.canvas_inputs = list(canvas_inputs)
        self.cell_sidbs = list(cell_sidbs)
        self.all = list(canvas_inputs) + list(cell_sidbs)
        self.n = len(self.all)

    def distances(self):
        d = np.zeros((self.n, self.n))
        for i in range(self.n):
            for j in range(i + 1, self.n):
                dij = np.hypot(self.all[i][0] - self.all[j][0],
                               self.all[i][1] - self.all[j][1]) * 3.84
                d[i, j] = d[j, i] = dij
        return d


def electrostatic_potential(layout, charges, params):
    n = layout.n
    V = np.zeros(n)
    d = layout.distances()
    coeff = params.V_scale / params.epsilon_r
    for i in range(n):
        for j in range(n):
            if i != j and d[i, j] > 0:
                V[i] += -coeff * np.exp(-d[i, j] / params.lambda_tf) \
                          / d[i, j] * charges[j] * params.q_e
    return V


def is_physically_valid(V, charges, params):
    mu_m = -params.mu_minus
    mu_p = -params.mu_plus
    for i in range(len(charges)):
        q, v = charges[i], V[i]
        if q == -1 and v <  mu_m:  return False
        elif q == +1 and v >  mu_p:return False
        elif q == 0 and (v < mu_m or v > mu_p): return False
    return True


def quickexact_ground_state(layout, params):
    n = layout.n
    n_vec = np.zeros(n, dtype=int)

    for iteration in range(n):
        V = electrostatic_potential(layout, n_vec, params)

        best_idx = -1
        best_V = -np.inf
        for i in range(n):
            if n_vec[i] != 0: continue
            # اگر V_i > 0.31، می‌تواند -1 شود
            if V[i] > 0.31 and V[i] > best_V:
                best_V = V[i]
                best_idx = i

        if best_idx == -1:
            break   

        n_vec[best_idx] = -1

    V_final = electrostatic_potential(layout, n_vec, params)
    E = 0.0
    for i in range(n):
        for j in range(i + 1, n):
            if n_vec[i] != 0 and n_vec[j] != 0:
                E += 0.5 * V_final[i] * n_vec[j] * params.q_e
    return E, n_vec


def decode_output(charge_vec, n_canvas):
    return int(np.sum(charge_vec[n_canvas:][-2:]) < 0)


def quick_test():
    p = SiDBParams()
    print(f"V_scale = {p.V_scale} eV·nm")
    for d in [3.84, 5.43, 7.68]:
        V = -p.V_scale/p.epsilon_r * np.exp(-d/p.lambda_tf)/d * (-1)
        print(f"  V at d={d}nm, q=-1 → V_i = {V:.4f} eV")


if __name__ == "__main__":
    quick_test()