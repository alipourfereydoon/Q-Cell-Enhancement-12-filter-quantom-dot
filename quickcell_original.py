# quickcell_original.py
# Original QuickCell-style 3-filter flow:
#   F4, F11, F12

from __future__ import annotations

import time
from typing import Dict

from core_sidb import (
    PARAMS,
    Params,
    FUNCTIONS,
    generate_candidate_layouts,
    exact_verify_layout,
    F4_positive_charge_pruning,
    F11_physical_infeasibility_pruning,
    F12_io_signal_instability_pruning,
)


def run_quickcell_original(
    function_name: str,
    d: int = 3,
    params: Params = PARAMS,
) -> Dict:
    func = FUNCTIONS[function_name]
    layouts = generate_candidate_layouts(d)

    stats = {
        "F4": 0,
        "F11": 0,
        "F12": 0,
    }

    valid = 0
    survivors = 0

    t0 = time.perf_counter()

    for layout in layouts:
        if F4_positive_charge_pruning(layout, params):
            stats["F4"] += 1
            continue

        if F11_physical_infeasibility_pruning(layout, func, params):
            stats["F11"] += 1
            continue

        if F12_io_signal_instability_pruning(layout, func, params):
            stats["F12"] += 1
            continue

        survivors += 1

        if exact_verify_layout(layout, func, params):
            valid += 1

    elapsed = time.perf_counter() - t0

    return {
        "name": function_name,
        "initial": len(layouts),
        "survivors": survivors,
        "valid": valid,
        "time": elapsed,
        "stats": stats,
    }


if __name__ == "__main__":
    for fn in FUNCTIONS:
        print(fn, run_quickcell_original(fn))