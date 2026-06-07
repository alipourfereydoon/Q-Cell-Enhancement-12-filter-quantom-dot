"""
quickcell_12.py — 12-filter QuickCell.
"""

import numpy as np
from itertools import product
from typing import List, Tuple
from core_sidb import (SiDBParams, SiDBLayout, electrostatic_potential,
                       ground_state_energy, decode_output)
from quickcell_original import (positive_charge_pruning,
                                physical_infeasibility_pruning,
                                io_signal_instability_pruning)



def F1_min_distance(L: SiDBLayout, P: SiDBParams) -> bool:
    D = L.distances(); n = L.n
    for i in range(n):
        for j in range(i+1, n):
            if D[i,j] < P.d_min: return True
    return False

def F2_symmetry(L: SiDBLayout, P: SiDBParams) -> bool:
    if L.n < 2: return False
    pos = sorted(L.all)
    if pos == sorted([(-x,-y) for x,y in pos]):
        return tuple(L.all) > tuple(pos)
    return False

def F3_wire_interference(L: SiDBLayout, P: SiDBParams) -> bool:
    n_canvas = len(L.canvas_inputs)
    D = L.distances()
    for i in range(n_canvas, L.n):
        s = 0.0
        for j in range(n_canvas):
            if D[i,j] > 0: s += 1.0 / D[i,j]**2
        if s > 0.45: return True
    return False

def F4_positive_charge(L: SiDBLayout, P: SiDBParams) -> bool:
    return positive_charge_pruning(L, P)

def F5_charge_count_bound(L: SiDBLayout, P: SiDBParams) -> bool:
    return len(L.cell_sidbs) < (L.n // 3) + 2   # +2 for BDL pair

def F6_input_pin_disturbance(L, f, P) -> bool:
    for ip in product([0,1], repeat=len(L.canvas_inputs)):
        E,_ = ground_state_energy(L, P, max_iter=20000)
        if E < P.E_valid_min: return True
    return False

def F7_path_connectivity(L, P) -> bool:
    n_io = len(L.canvas_inputs)
    D = L.distances(); d_max = 3*3.84
    for src in range(n_io):
        vis = {src}; stk = [src]
        while stk:
            u = stk.pop()
            for v in range(n_io):
                if v not in vis and D[u,v] < d_max:
                    vis.add(v); stk.append(v)
        if len(vis) < n_io: return True
    return False

def F8_output_potential_bound(L, f, P) -> bool:
    n_canvas = len(L.canvas_inputs)
    for ip in product([0,1], repeat=n_canvas):
        ch = np.array([-1 if v==0 else 0 for v in ip] + [0]*len(L.cell_sidbs))
        V= electrostatic_potential(L, ch, P)
        out_v = np.sum(V[n_canvas:][-2:])
        if out_v < P.E_valid_min or out_v > 5.0: return True
    return False

def F9_energy_lower_bound(L, f, P) -> bool:
    D = L.distances(); b = 0.0
    for i in range(L.n):
        for j in range(i+1, L.n):
            if D[i,j] > 0: b += 1.0/D[i,j]
    if b * P.d_min < 8.0: return True
    return False

def F10_physical_instability(L, f, P) -> bool:
    return physical_infeasibility_pruning(L, f, P)

def F11_existence_proof(L, f, P) -> bool:
    n_canvas = len(L.canvas_inputs)
    for ip in product([0,1], repeat=n_canvas):
        E_gs,_ = ground_state_energy(L, P, max_iter=20000)
        for k in range(len(L.cell_sidbs)):
            ch = np.array([-1 if v==0 else 0 for v in ip] + [0]*len(L.cell_sidbs))
            ch[n_canvas+k] = 1 - (ch[n_canvas+k]+1)
            V = electrostatic_potential(L, ch, P)
            Ea = 0.0
            for i in range(L.n):
                for j in range(i+1, L.n):
                    if ch[i]!=0 and ch[j]!=0: Ea += 0.5*V[i]*ch[j]
            if Ea < E_gs - 0.1: return True
    return False

def F12_io_signal_instability(L, f, P) -> bool:
    return io_signal_instability_pruning(L, f, P)


def quickcell_12(boolean_func, all_layouts: List[SiDBLayout],
                 params: SiDBParams = SiDBParams(),
                 verbose: bool = False):
    stats = {}
    
    s1 = [L for L in all_layouts
          if not (F1_min_distance(L,params) or F2_symmetry(L,params) or
                  F3_wire_interference(L,params) or
                  F4_positive_charge(L,params) or
                  F5_charge_count_bound(L,params))]
    stats['P1'] = len(s1)
    if verbose: print(f"Phase 1: {len(s1)}")
   
    s2 = [L for L in s1
          if not (F6_input_pin_disturbance(L,boolean_func,params) or
                  F7_path_connectivity(L,params) or
                  F8_output_potential_bound(L,boolean_func,params) or
                  F9_energy_lower_bound(L,boolean_func,params))]
    stats['P2'] = len(s2)
    if verbose: print(f"Phase 2: {len(s2)}")
    
    valid = []
    for L in s2:
        if F10_physical_instability(L,boolean_func,params):  continue
        if F11_existence_proof(L,boolean_func,params):       continue
        if F12_io_signal_instability(L,boolean_func,params): continue
        n_canvas = len(L.canvas_inputs)
        ok = True
        for ip in product([0,1], repeat=n_canvas):
            E,n_gs = ground_state_energy(L,params,max_iter=20000)
            if decode_output(n_gs, n_canvas) != boolean_func(ip):
                ok = False; break
        if ok: valid.append(L)
    stats['P3'] = len(s2); stats['valid'] = len(valid)
    if verbose: print(f"Phase 3: {len(valid)} valid")
    return valid, stats