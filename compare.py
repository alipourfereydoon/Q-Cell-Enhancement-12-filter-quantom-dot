"""
compare.py — Compare QuickCell vs QuickCell-12 on small benchmark.
"""

import time
from itertools import product, combinations
from quickcell_original import quickcell_3filter
from quickcell_12       import quickcell_12
from core_sidb          import SiDBParams, SiDBLayout


# ----------------------------------------------------------------------
# Correct layout 

def generate_candidate_layouts(d_cell: int = 3,
                               n_inputs: int = 2) -> list:
   
    # canvas positions (input pins, fixed)
    canvas = [(0, 0), (0, 1)]
    # cell-candidate positions (cannot overlap with canvas)
    cell_pool = [(x, y) for x in range(3) for y in range(3)
                 if (x, y) not in canvas]

    layouts = []
    for combo in combinations(cell_pool, d_cell):
    
        layouts.append(SiDBLayout(canvas, list(combo)))
    return layouts


FUNCTIONS = {
    'AND' : lambda x: x[0] & x[1],
    'OR'  :  lambda x: x[0] | x[1],
    'XOR' : lambda x: x[0] ^ x[1],
    'NAND':  lambda x: 1 - (x[0] & x[1]),
    'NOR' : lambda x: 1 - (x[0] | x[1]),
    'XNOR':  lambda x: 1 - (x[0] ^ x[1]),
    'WIRE':  lambda x: x[0],
    'INV' : lambda x: 1 - x[0],
}


def run_comparison():
    params = SiDBParams()
    cands  = generate_candidate_layouts(d_cell=3, n_inputs=2)
    print(f"Candidates: {len(cands)}\n")

    hdr = (f"{'Fn':<6}{'|Ld|':>6}{'P1':>5}{'P2':>5}"
           f"{'|L*|3':>7}{'t3[s]':>8}"
           f"{'|L*|12':>7}{'t12[s]':>9}{'Spdup':>8}")
    print(hdr); print("-"*len(hdr))

    for name, f in FUNCTIONS.items():
        t0 = time.perf_counter()
        v3 = quickcell_3filter(f, cands, params)
        t3 = time.perf_counter() - t0

        t0 = time.perf_counter()
        v12, st = quickcell_12(f, cands, params)
        t12 = time.perf_counter() - t0

        sp = (t3/t12) if t12>0 else float('inf')
        print(f"{name:<6}{len(cands):>6}{st['P1']:>5}{st['P2']:>5}"
              f"{len(v3):>7}{t3:>8.2f}"
              f"{len(v12):>7}{t12:>9.2f}{sp:>7.1f}×")


if __name__ == "__main__":
    run_comparison()