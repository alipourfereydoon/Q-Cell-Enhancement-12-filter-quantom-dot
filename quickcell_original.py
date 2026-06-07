"""
quickcell_original.py — 3-filter QuickCell  (paper-faithful).
"""

import numpy as np
from itertools import product
from typing import List
from core_sidb import (SiDBParams, SiDBLayout, electrostatic_potential,
     ground_state_energy, decode_output)


def positive_charge_pruning(layout: SiDBLayout, params: SiDBParams) -> bool:
   
    D = layout.distances()
    mu_plus = params.mu_plus
    coeff = 1.0 / (4 * np.pi * params.epsilon_r)
    n = layout.n
    for i in range(n):
        V_max = 0.0
        for j in range(n):
            if i != j and D[i, j] > 0:
                V_max += -coeff * np.exp(-D[i, j] / params.lambda_tf) \
                          / D[i, j] * (-1) * params.q_e
        if V_max > mu_plus:
            return True
    return False


def physical_infeasibility_pruning(layout: SiDBLayout,
                                   boolean_func,
                                   params: SiDBParams) -> bool:
    
    n_canvas = len(layout.canvas_inputs)
    n_in = n_canvas       
    k  = len(layout.cell_sidbs)
    if k < 2:                  
        return True

    for in_pattern in product([0, 1], repeat=n_in):
        feasible = False
        # encode inputs on canvas (one SiDB per input, -1 for "0")
        input_charges = [-1 if v == 0 else 0 for v in in_pattern]
        for cell_charges in product([-1, 0, 1], repeat=k):
            charges = np.array(input_charges + list(cell_charges))
            V = electrostatic_potential(layout, charges, params)
            ok = True
            for idx, q in enumerate(charges):
                if q == -1 and V[idx] >= 0:   ok = False; break
                if q ==  1 and V[idx] <= 0:   ok = False; break
                if q ==  0 and (V[idx] < params.mu_plus or
                                    V[idx] > params.mu_minus):
                    ok = False; break
            if not ok:
                continue
            out = decode_output(charges, n_canvas)
            if out == boolean_func(in_pattern):
                feasible = True
                break
        if not feasible:
            return True
    return False


def io_signal_instability_pruning(layout: SiDBLayout,
                                  boolean_func,
                                  params: SiDBParams) -> bool:
    
    n_canvas = len(layout.canvas_inputs)
    n_in = n_canvas
    k = len(layout.cell_sidbs)
    for in_pattern in product([0, 1], repeat=n_in):
        inverted = tuple(1 - x for x in in_pattern)
        out_wrong = 1 - boolean_func(in_pattern)
        wrong_bdl = [0, -1] if out_wrong == 1 else [-1, 0]
        charges = (np.array(list(inverted) +
                            wrong_bdl +
                            [0]*(k-2))).astype(int)
        E, _ = ground_state_energy(layout, params, max_iter=50000)
        if E < params.E_valid_min:
            return True
    return False


def quickcell_3filter(boolean_func, all_layouts: List[SiDBLayout],
                      params: SiDBParams = SiDBParams()) -> List[SiDBLayout]:
    valid = []
    for L in all_layouts:
        if positive_charge_pruning(L, params):              continue
        if physical_infeasibility_pruning(L, boolean_func, params): continue
        if io_signal_instability_pruning(L, boolean_func, params): continue
        n_canvas = len(L.canvas_inputs)
        n_in = n_canvas
        ok = True
        for in_pattern in product([0, 1], repeat=n_in):
            E, n_gs = ground_state_energy(L, params, max_iter=50000)
            if decode_output(n_gs, n_canvas) != boolean_func(in_pattern):
                ok = False
                break
        if ok:
            valid.append(L)
    return valid