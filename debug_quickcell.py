# debug_quickcell.py
# Debug QuickCell-8 CLEAN setup

import core_sidb

from core_sidb import (
    PARAMS,
    CORE_VERSION,
    FUNCTIONS,
    generate_candidate_layouts,
    print_physics_diagnostics,
    debug_F4_positive_charge,
    all_input_patterns,
    ground_state_fixed_io,
    predict_output,
    exact_verify_layout,
    read_bdl_pair,
    OUTPUT_PAIR,
    format_charges,
)


def debug_one_layout():
    print("Imported core_sidb from:", core_sidb.__file__)
    print("CORE_VERSION:", CORE_VERSION)

    print_physics_diagnostics(PARAMS)

    layouts = generate_candidate_layouts(d=3)
    layout = layouts[0]

    print("\nLayout")
    print("------")
    print(f"Total SiDBs = {len(layout.points())}")
    print(f"Skeleton + canvas points = {layout.points()}")
    print(f"Canvas combo = {layout.combo}")
    print(f"Canvas positions = {layout.canvas_positions()}")

    if len(layout.points()) != 9:
        print("\nERROR: This is not the CLEAN QuickCell-8 setup.")
        print("Expected 9 SiDBs = 6 skeleton + 3 canvas.")
        print("You are probably running old files.")
        return

    print("\nNote: F4 is removed in QuickCell-8, but shown here for diagnosis only.")
    debug_F4_positive_charge(layout, PARAMS)

    func = FUNCTIONS["AND"]

    print("\nAND debug")
    print("---------")

    for bits in all_input_patterns():
        expected = func(*bits)

        e0, n0, c0 = ground_state_fixed_io(layout, bits, 0, PARAMS)
        e1, n1, c1 = ground_state_fixed_io(layout, bits, 1, PARAMS)

        pred = predict_output(layout, bits, PARAMS)

        print(f"\n=== Input {bits}, expected AND = {expected} ===")

        print(f"  output=0 feasible configs: {c0}, E0={e0:.4f}")
        if n0 is not None:
            print(f"    n0={format_charges(n0)}, read={read_bdl_pair(n0, OUTPUT_PAIR)}")

        print(f"  output=1 feasible configs: {c1}, E1={e1:.4f}")
        if n1 is not None:
            print(f"    n1={format_charges(n1)}, read={read_bdl_pair(n1, OUTPUT_PAIR)}")

        print(f"  predicted output = {pred}")
        print(f"  match? {pred == expected}")

    print("\nExact verify this layout as AND:")
    print("  valid?", exact_verify_layout(layout, func, PARAMS))


if __name__ == "__main__":
    debug_one_layout()