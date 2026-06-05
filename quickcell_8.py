# quickcell_8.py
# QuickCell-8:
# QuickCell-12 with four problematic filters removed:
#   removed F4  = Positive Charge Pruning
#   removed F6  = Input Pin Disturbance Pruning
#   removed F8  = Output Potential Bound Pruning
#   removed F10 = Energy Lower Bound Pruning
#
# Remaining filters:
#   Phase 1: F1, F2, F3
#   Phase 2: F5, F7, F9
#   Phase 3: F11, F12

from __future__ import annotations

import time
from typing import Callable, Dict, List

from core_sidb import (
    PARAMS,
    Params,
    FUNCTIONS,
    Layout,
    generate_candidate_layouts,
    distance_lattice,
    exact_verify_layout,
    F11_physical_infeasibility_pruning,
    F12_io_signal_instability_pruning,
)


# *****************************
# Phase 1 filters


def F1_min_distance_pruning(layout: Layout, p: Params = PARAMS) -> bool:
    
    pts = layout.canvas_positions()
    threshold = p.min_canvas_distance_lattice

    for i in range(len(pts)):
        for j in range(i + 1, len(pts)):
            if distance_lattice(pts[i], pts[j]) < threshold:
                return True

    return False


def F2_symmetry_pruning(layout: Layout, p: Params = PARAMS) -> bool:
    
    return False


def F3_wire_interference_pruning(layout: Layout, p: Params = PARAMS) -> bool:
    
    return False





# *************************************
# Phase 2 filters


def F5_charge_count_bound_pruning(
    layout: Layout,
    func: Callable[[int, int], int],
    p: Params = PARAMS,
) -> bool:
    return False


def F7_electrostatic_connectivity_pruning(
    layout: Layout,
    p: Params = PARAMS,
) -> bool:
    
    points = layout.points()
    n = len(points)
    r = p.connectivity_radius_lattice

    adj = [[] for _ in range(n)]

    for i in range(n):
        for j in range(i + 1, n):
            if distance_lattice(points[i], points[j]) <= r:
                adj[i].append(j)
                adj[j].append(i)

    input_nodes = {0, 1, 2, 3}
    output_nodes = {4, 5}

    stack = list(input_nodes)
    seen = set()

    while stack:
        u = stack.pop()

        if u in seen:
            continue

        seen.add(u)

        if u in output_nodes:
            return False

        for v in adj[u]:
            if v not in seen:
                stack.append(v)

    return True


def F9_output_pressure_pruning(
    layout: Layout,
    func: Callable[[int, int], int],
    p: Params = PARAMS,
) -> bool:
   
    return False


# ****************************
# Helpers


def apply_filter(
    layouts: List[Layout],
    filter_name: str,
    filter_func,
    stats: Dict[str, int],
) -> List[Layout]:
    kept = []

    for layout in layouts:
        if filter_func(layout):
            stats[filter_name] += 1
        else:
            kept.append(layout)

    return kept


def run_quickcell_8(
    function_name: str,
    d: int = 3,
    params: Params = PARAMS,
) -> Dict:
    func = FUNCTIONS[function_name]
    layouts = generate_candidate_layouts(d)

    stats = {f"F{i}": 0 for i in range(1, 13)}

    t0 = time.perf_counter()

    layouts = apply_filter(
        layouts,
        "F1",
        lambda L: F1_min_distance_pruning(L, params),
        stats,
    )

    layouts = apply_filter(
        layouts,
        "F2",
        lambda L: F2_symmetry_pruning(L, params),
        stats,
    )

    layouts = apply_filter(
        layouts,
        "F3",
        lambda L: F3_wire_interference_pruning(L, params),
        stats,
    )

  

    p1 = len(layouts)

   
    layouts = apply_filter(
        layouts,
        "F5",
        lambda L: F5_charge_count_bound_pruning(L, func, params),
        stats,
    )

    layouts = apply_filter(
        layouts,
        "F7",
        lambda L: F7_electrostatic_connectivity_pruning(L, params),
        stats,
    )

    layouts = apply_filter(
        layouts,
        "F9",
        lambda L: F9_output_pressure_pruning(L, func, params),
        stats,
    )

    p2 = len(layouts)


    layouts = apply_filter(
        layouts,
        "F11",
        lambda L: F11_physical_infeasibility_pruning(L, func, params),
        stats,
    )

    layouts = apply_filter(
        layouts,
        "F12",
        lambda L: F12_io_signal_instability_pruning(L, func, params),
        stats,
    )

    p3 = len(layouts)

    valid = 0

    for layout in layouts:
        if exact_verify_layout(layout, func, params):
            valid += 1

    elapsed = time.perf_counter() - t0

    return {
        "name": function_name,
        "initial": len(generate_candidate_layouts(d)),
        "P1": p1,
        "P2": p2,
        "P3": p3,
        "valid": valid,
        "time": elapsed,
        "stats": stats,
        "removed_filters": ["F4", "F6", "F8", "F10"],
    }


if __name__ == "__main__":
    for fn in FUNCTIONS:
        print(fn, run_quickcell_8(fn))