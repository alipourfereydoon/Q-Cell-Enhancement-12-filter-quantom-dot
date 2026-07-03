# run_gate_report_2input.py
from __future__ import annotations

import argparse
import math
import multiprocessing as mp
import os
import random
import time
from typing import Dict, Any, List, Tuple, Optional

import numpy as np

from src.data_structures import Layout
from src.physics import PhysicalParameters, get_potential
from src.gates_2input import (
    get_2input_gate,
    get_all_2input_gate_names,
    normalize_gate_name,
    gate_category,
)
from src.paper_benchmarks_2input import (
    paper_like_skeleton_2in_1out,
    paper_like_skeleton_2in_2out,
    paper_like_skeleton_1in_1out,
    paper_like_canvas_2in_1out,
    paper_like_canvas_2in_2out,
    paper_like_canvas_1in_1out,
)
from src.filters import (
    F1_min_distance, F2_symmetry, F3_wire_interference,
    F4_positive_charge, F5_charge_count_bound,
    F6_input_pin_disturbance, F7_path_connectivity,
    F8_output_potential_bound, F9_electrostatic_pressure,
    F10_energy_lower_bound, F11_physical_infeasibility,
)
from src.reporting import (
    write_csv, write_json, write_markdown, markdown_table,
)

QC12_FILTERS = [
    F1_min_distance, F2_symmetry, F3_wire_interference,
    F4_positive_charge, F5_charge_count_bound,
    F6_input_pin_disturbance, F7_path_connectivity,
    F8_output_potential_bound, F9_electrostatic_pressure,
    F10_energy_lower_bound,
]

_G: Dict[str, Any] = {}


def _override(default_value, override_value):
    return default_value if override_value is None else override_value


def get_skeleton_and_canvas(gate_name: str):
    cat = gate_category(gate_name)
    if cat == "2in_1out":
        return paper_like_skeleton_2in_1out(), paper_like_canvas_2in_1out()
    elif cat == "2in_2out":
        return paper_like_skeleton_2in_2out(), paper_like_canvas_2in_2out()
    elif cat == "1in_1out":
        return paper_like_skeleton_1in_1out(), paper_like_canvas_1in_1out()
    raise ValueError(f"Unknown category for '{gate_name}'.")


def make_params(
    profile, io_margin_override, pressure_margin_override,
    wire_radius_override, input_disturbance_override,
    connectivity_radius_override=None,
):
    profile = str(profile).strip().lower()
    if profile == "safe":
        return PhysicalParameters(
            mu_minus=-0.32, mu_plus=-0.80, lambda_tf=5.0, epsilon_r=5.6,
            check_fixed_io_population=False,
            check_configuration_stability=False,
            relaxed_enumeration=True, instability_check_inputs=False,
            f10_check_input_inversions=False,
            charge_min_fraction=0.0, charge_max_fraction=1.0,
            bit0_requires_positive_pressure=False,
            wire_forbidden_radius=_override(0.35, wire_radius_override),
            connectivity_radius=connectivity_radius_override,
            pressure_margin=_override(0.0, pressure_margin_override),
            energy_bound_margin=None,
            io_instability_margin=_override(0.02, io_margin_override),
            input_disturbance_limit=input_disturbance_override,
        )
    if profile == "balanced":
        return PhysicalParameters(
            mu_minus=-0.32, mu_plus=-0.80, lambda_tf=5.0, epsilon_r=5.6,
            check_fixed_io_population=False,
            check_configuration_stability=False,
            relaxed_enumeration=True, instability_check_inputs=False,
            f10_check_input_inversions=False,
            charge_min_fraction=0.0, charge_max_fraction=1.0,
            bit0_requires_positive_pressure=False,
            wire_forbidden_radius=_override(0.40, wire_radius_override),
            connectivity_radius=connectivity_radius_override,
            pressure_margin=_override(0.0, pressure_margin_override),
            energy_bound_margin=None,
            io_instability_margin=_override(0.02, io_margin_override),
            input_disturbance_limit=input_disturbance_override,
        )
    if profile == "strict":
        return PhysicalParameters(
            mu_minus=-0.32, mu_plus=-0.80, lambda_tf=5.0, epsilon_r=5.6,
            check_fixed_io_population=False,
            check_configuration_stability=False,
            relaxed_enumeration=True, instability_check_inputs=False,
            f10_check_input_inversions=False,
            charge_min_fraction=0.0, charge_max_fraction=1.0,
            bit0_requires_positive_pressure=False,
            wire_forbidden_radius=_override(0.45, wire_radius_override),
            connectivity_radius=_override(2.5 * 5.0, connectivity_radius_override),
            pressure_margin=_override(0.0, pressure_margin_override),
            energy_bound_margin=None,
            io_instability_margin=_override(0.02, io_margin_override),
            input_disturbance_limit=_override(0.45, input_disturbance_override),
        )
    raise ValueError("Unknown profile. Use: safe, balanced, strict")


def fixed_charges_ordered(skeleton, x, y):
    charges = []
    for i, pin in enumerate(skeleton.input_pins):
        charges.extend([q for _, q in pin.charges_for_bit(x[i])])
    for i, pin in enumerate(skeleton.output_pins):
        charges.extend([q for _, q in pin.charges_for_bit(y[i])])
    for _ in skeleton.wire_sidbs:
        charges.append(0)
    return charges


def precompute_potential_matrix(skeleton, canvas, params):
    positions = skeleton.all_positions() + canvas.positions
    n = len(positions)
    P = np.zeros((n, n), dtype=float)
    for i in range(n):
        for j in range(i + 1, n):
            v = get_potential(positions[i], positions[j], params)
            P[i, j] = v
            P[j, i] = v
    return P


def build_fixed_data(skeleton, func, params, P):
    n_s = len(skeleton.all_sidbs)
    data = {}
    for x in func.all_inputs():
        for y in func.all_outputs():
            charges = fixed_charges_ordered(skeleton, x, y)
            e_fp = 0.0
            for i in range(n_s):
                for j in range(i + 1, n_s):
                    e_fp += charges[i] * charges[j] * P[i, j]
            n_neg = sum(1 for q in charges if q == -1)
            data[(tuple(x), tuple(y))] = {
                "charges": charges,
                "e_fixed": e_fp + n_neg * params.mu_minus * abs(params.qe),
            }
    return data


def _init_worker(skeleton, canvas, params, func):
    _G["skeleton"] = skeleton
    _G["canvas"] = canvas
    _G["params"] = params
    _G["func"] = func
    P = precompute_potential_matrix(skeleton, canvas, params)
    _G["P"] = P
    _G["fixed_data"] = build_fixed_data(skeleton, func, params, P)
    _G["n_skel"] = len(skeleton.all_sidbs)


def make_layout(combo):
    canvas = _G["canvas"]
    skeleton = _G["skeleton"]
    return Layout(
        skeleton=skeleton,
        canvas_positions=[canvas.positions[i] for i in combo],
        canvas_indices=combo,
    )


def min_relaxed_energy(combo, x, y):
    params = _G["params"]
    P = _G["P"]
    n_s = _G["n_skel"]
    fd = _G["fixed_data"][(tuple(x), tuple(y))]
    fc = fd["charges"]
    e_f = fd["e_fixed"]
    cg = [n_s + i for i in combo]
    d = len(cg)
    linear = []
    for cidx in cg:
        c = params.mu_minus * abs(params.qe)
        for i, q in enumerate(fc):
            c += q * (-1) * P[i, cidx]
        linear.append(c)
    pcc = np.zeros((d, d), dtype=float)
    for i in range(d):
        for j in range(i + 1, d):
            pcc[i, j] = P[cg[i], cg[j]]
    best = float("inf")
    for mask in range(1 << d):
        e = e_f
        active = []
        for i in range(d):
            if mask & (1 << i):
                e += linear[i]
                active.append(i)
        for ai in range(len(active)):
            for bi in range(ai + 1, len(active)):
                e += pcc[active[ai], active[bi]]
        if e < best:
            best = e
    return best


def fast_f12_relaxed(combo):
    params = _G["params"]
    func = _G["func"]
    tol = max(params.energy_tolerance, params.io_instability_margin)
    for x in func.all_inputs():
        yc = func.eval(x)
        ec = min_relaxed_energy(combo, tuple(x), tuple(yc))
        for ya in func.all_outputs():
            ya = tuple(ya)
            if ya == tuple(yc):
                continue
            if min_relaxed_energy(combo, tuple(x), ya) < ec - tol:
                return True
    return False


def fast_energy_margin(combo):
    func = _G["func"]
    mm = float("inf")
    for x in func.all_inputs():
        yc = tuple(func.eval(x))
        ec = min_relaxed_energy(combo, tuple(x), yc)
        ba = float("inf")
        for ya in func.all_outputs():
            ya = tuple(ya)
            if ya == yc:
                continue
            ea = min_relaxed_energy(combo, tuple(x), ya)
            if ea < ba:
                ba = ea
        m = ba - ec
        if m < mm:
            mm = m
    return float(mm)


def run_filter_sequence_for_qc12(layout):
    params = _G["params"]
    func = _G["func"]
    skeleton = _G["skeleton"]
    canvas = _G["canvas"]
    after = [0] * 12
    for i, f in enumerate(QC12_FILTERS):
        if f(layout=layout, params=params, func=func,
             skeleton=skeleton, canvas=canvas):
            return after, False
        after[i] = 1
    f11m = getattr(params, "f11_mode", "counted")
    if f11m == "counted":
        after[10] = 1
    else:
        if F11_physical_infeasibility(
            layout=layout, params=params, func=func,
            skeleton=skeleton, canvas=canvas):
            return after, False
        after[10] = 1
    if fast_f12_relaxed(tuple(layout.canvas_indices)):
        return after, False
    after[11] = 1
    return after, True


def run_filter_sequence_for_qc3(layout):
    params = _G["params"]
    func = _G["func"]
    skeleton = _G["skeleton"]
    canvas = _G["canvas"]
    out = {"after_f4": 0, "after_f11": 0, "after_f12": 0}
    if F4_positive_charge(layout=layout, params=params, func=func,
                          skeleton=skeleton, canvas=canvas):
        return out
    out["after_f4"] = 1
    out["after_f11"] = 1
    if fast_f12_relaxed(tuple(layout.canvas_indices)):
        return out
    out["after_f12"] = 1
    return out


def worker_process_chunk(chunk):
    qc12_after = [0] * 12
    qc12_passed = []
    qc3_f4 = 0
    qc3_f11 = 0
    qc3_f12 = 0
    for combo in chunk:
        layout = make_layout(combo)
        after, passed = run_filter_sequence_for_qc12(layout)
        for i in range(12):
            qc12_after[i] += after[i]
        if passed:
            qc12_passed.append(combo)
        qc3 = run_filter_sequence_for_qc3(layout)
        qc3_f4 += qc3["after_f4"]
        qc3_f11 += qc3["after_f11"]
        qc3_f12 += qc3["after_f12"]
    return {
        "processed": len(chunk),
        "qc12_after": qc12_after,
        "qc12_passed": qc12_passed,
        "qc3_after_f4": qc3_f4,
        "qc3_after_f11": qc3_f11,
        "qc3_after_f12": qc3_f12,
    }


def random_combinations(n, d, count, seed):
    rng = random.Random(seed)
    seen = set()
    count = min(count, math.comb(n, d))
    while len(seen) < count:
        c = tuple(sorted(rng.sample(range(n), d)))
        if c not in seen:
            seen.add(c)
            yield c


def chunked(iterable, sz):
    b = []
    for x in iterable:
        b.append(x)
        if len(b) >= sz:
            yield b
            b = []
    if b:
        yield b


def merge(total, part):
    total["processed"] += part["processed"]
    for i in range(12):
        total["qc12_after"][i] += part["qc12_after"][i]
    total["qc12_passed"].extend(part["qc12_passed"])
    total["qc3_after_f4"] += part["qc3_after_f4"]
    total["qc3_after_f11"] += part["qc3_after_f11"]
    total["qc3_after_f12"] += part["qc3_after_f12"]


def select_ranked_candidates(combos, target, min_margin):
    scored = [(fast_energy_margin(c), c) for c in combos]
    scored.sort(key=lambda t: (-t[0], t[1]))
    selected = []
    rows = []
    for margin, combo in scored:
        if min_margin is not None and margin < min_margin:
            continue
        if target is not None and target > 0 and len(selected) >= target:
            break
        selected.append(combo)
        rows.append({
            "rank": len(selected),
            "energy_margin": margin,
            "canvas_indices": " ".join(str(i) for i in combo),
        })
    return selected, rows


def compute_phase_rows(total, elapsed, selection_enabled):
    processed = total["processed"]
    a = total["qc12_after"]
    rows = []

    def row(name, filters, inp, out, runtime=""):
        retention = out / inp if inp else 0.0
        pruning = 1.0 - retention
        reduction = inp / out if out else float("inf")
        return {
            "Phase": name, "Filters": filters,
            "Input Layouts": inp, "Output Layouts": out,
            "Retention Ratio [%]": round(retention * 100.0, 4),
            "Pruning Ratio [%]": round(pruning * 100.0, 4),
            "Reduction Factor": "inf" if reduction == float("inf") else round(reduction, 4),
            "Runtime [s]": runtime,
        }

    rows.append(row("Phase 1", "F1-F4", processed, a[3]))
    rows.append(row("Phase 2", "F5-F10", a[3], a[9]))
    rows.append(row("Phase 3", "F11-F12", a[9], a[11]))
    if selection_enabled:
        rows.append(row("Post-F12 Selection", "Energy-margin ranking",
                        a[11], total["selected_candidates"]))
        final_out = total["selected_candidates"]
        total_label = "F1-F12 + selection"
    else:
        final_out = a[11]
        total_label = "F1-F12"
    rows.append(row("Total", total_label, processed, final_out, round(elapsed, 4)))
    return rows


def compute_comparison_rows(total, selection_enabled):
    processed = total["processed"]
    a = total["qc12_after"]
    qc3_before = total["qc3_after_f12"]
    qc12_before = total["selected_candidates"] if selection_enabled else a[11]
    qc3_after_early = total["qc3_after_f4"]
    qc12_after_phase1 = a[3]
    qc12_before_enum = a[9]
    qc3_before_enum = qc3_after_early

    def imp(old, new):
        return "inf" if new == 0 else f"{old / new:.2f}x fewer"

    return [
        {"Metric": "Number of pruning filters",
         "Original QC-3": 3, "QuickCell-12": 12, "Improvement": "4.0x more"},
        {"Metric": "Processed layouts",
         "Original QC-3": processed, "QuickCell-12": processed, "Improvement": "same"},
        {"Metric": "After early pruning / Phase 1",
         "Original QC-3": qc3_after_early, "QuickCell-12": qc12_after_phase1,
         "Improvement": imp(qc3_after_early, qc12_after_phase1)},
        {"Metric": "Before expensive enumerative pruning",
         "Original QC-3": qc3_before_enum, "QuickCell-12": qc12_before_enum,
         "Improvement": imp(qc3_before_enum, qc12_before_enum)},
        {"Metric": "Before final verification",
         "Original QC-3": qc3_before, "QuickCell-12": qc12_before,
         "Improvement": imp(qc3_before, qc12_before)},
        {"Metric": "Candidate implementations",
         "Original QC-3": qc3_before, "QuickCell-12": qc12_before,
         "Improvement": imp(qc3_before, qc12_before)},
        {"Metric": "Search-space reduction",
         "Original QC-3": round(processed / qc3_before, 4) if qc3_before else "inf",
         "QuickCell-12": round(processed / qc12_before, 4) if qc12_before else "inf",
         "Improvement": imp(qc3_before, qc12_before)},
    ]


def compute_speedup_rows(total, full_ld, elapsed, sim_time,
                         selection_enabled, num_input_patterns):
    processed = total["processed"]
    qc3_candidates = total["qc3_after_f12"]
    qc_candidates = (total["selected_candidates"]
                     if selection_enabled else total["qc12_after"][11])
    nip = num_input_patterns
    return [
        {"Quantity": "Processed layouts", "Value": processed},
        {"Quantity": "Full search space |Ld|", "Value": full_ld},
        {"Quantity": f"Input patterns ({nip})", "Value": nip},
        {"Quantity": "Assumed sim time per layout/input [s]", "Value": sim_time},
        {"Quantity": "Estimated brute-force (sample) [s]",
         "Value": round(processed * nip * sim_time, 4)},
        {"Quantity": "Estimated brute-force (full) [s]",
         "Value": round(full_ld * nip * sim_time, 4)},
        {"Quantity": "QC-3 candidates", "Value": qc3_candidates},
        {"Quantity": "QuickCell-12 candidates", "Value": qc_candidates},
        {"Quantity": "Candidate reduction over QC-3",
         "Value": f"{qc3_candidates / qc_candidates:.4f}x" if qc_candidates else "inf"},
        {"Quantity": "Wall time [s]", "Value": round(elapsed, 4)},
    ]


def write_reports(gate, full_ld, total, elapsed, output_dir,
                  sim_time, selection_enabled, selected_rows, nip):
    os.makedirs(output_dir, exist_ok=True)
    a = total["qc12_after"]
    table_i = [{
        "Benchmark": gate, "|Ld|": full_ld, "Processed": total["processed"],
        "After F1": a[0], "After F2": a[1], "After F3": a[2],
        "After F4": a[3], "After F5": a[4], "After F6": a[5],
        "After F7": a[6], "After F8": a[7], "After F9": a[8],
        "After F10": a[9], "After F11": a[10], "After F12": a[11],
        "Selected": total["selected_candidates"] if selection_enabled else "",
        "Candidates": total["selected_candidates"] if selection_enabled else a[11],
        "Time [s]": round(elapsed, 4),
    }]
    table_ii = compute_phase_rows(total, elapsed, selection_enabled)
    table_iii = compute_comparison_rows(total, selection_enabled)
    speedup = compute_speedup_rows(total, full_ld, elapsed, sim_time,
                                   selection_enabled, nip)
    write_csv(os.path.join(output_dir, "table_I_ablation.csv"),
              table_i, list(table_i[0].keys()))
    write_csv(os.path.join(output_dir, "table_II_phase_summary.csv"),
              table_ii, list(table_ii[0].keys()))
    write_csv(os.path.join(output_dir, "table_III_comparison.csv"),
              table_iii, list(table_iii[0].keys()))
    write_csv(os.path.join(output_dir, "speedup_calculation.csv"),
              speedup, list(speedup[0].keys()))
    if selected_rows:
        write_csv(os.path.join(output_dir, "selected_candidates.csv"),
                  selected_rows, list(selected_rows[0].keys()))
    write_json(os.path.join(output_dir, "report.json"), {
        "gate": gate, "full_ld": full_ld, "total": total,
        "elapsed": elapsed, "selection_enabled": selection_enabled,
        "table_I": table_i, "table_II": table_ii,
        "table_III": table_iii, "speedup": speedup,
        "selected_candidates": selected_rows,
    })
    md = []
    md.append(f"# QuickCell-12 Report (2-input): {gate}\n")
    md.append("## Table I\n")
    md.append(markdown_table(list(table_i[0].keys()), [list(table_i[0].values())]))
    md.append("\n\n## Table II\n")
    md.append(markdown_table(list(table_ii[0].keys()), [list(r.values()) for r in table_ii]))
    md.append("\n\n## Table III\n")
    md.append(markdown_table(list(table_iii[0].keys()), [list(r.values()) for r in table_iii]))
    md.append("\n\n## Speedup\n")
    md.append(markdown_table(list(speedup[0].keys()), [list(r.values()) for r in speedup]))
    write_markdown(os.path.join(output_dir, "report.md"), "\n".join(md))


def parse_gate_argument(gate_arg):
    gate_arg = gate_arg.strip()
    if gate_arg.upper() == "ALL":
        return get_all_2input_gate_names()
    return [normalize_gate_name(g) for g in gate_arg.split(",") if g.strip()]


def run_gate(gate, samples, workers, chunksize, seed, sim_time,
             strict_profile, io_margin, pressure_margin,
             connectivity_radius, d_min, positive_charge_margin,
             charge_min_fraction, charge_max_fraction,
             charge_count_conflict_radius, input_disturbance,
             energy_margin, f11_mode, f11_min_support_states,
             selection_target, selection_min_margin, canvas_d):
    gate = normalize_gate_name(gate)
    func = get_2input_gate(gate)
    skeleton, canvas = get_skeleton_and_canvas(gate)
    nip = 2 ** func.num_inputs
    params = make_params(
        profile=strict_profile,
        io_margin_override=io_margin,
        pressure_margin_override=pressure_margin,
        wire_radius_override=None,
        input_disturbance_override=input_disturbance,
        connectivity_radius_override=connectivity_radius,
    )
    params.f11_mode = f11_mode
    if f11_mode == "counted":
        params.relaxed_enumeration = True
        params.check_configuration_stability = False
    elif f11_mode == "strict-pop":
        params.relaxed_enumeration = False
        params.check_configuration_stability = False
        params.check_fixed_io_population = False
    elif f11_mode == "strict-hop":
        params.relaxed_enumeration = False
        params.check_configuration_stability = True
        params.check_fixed_io_population = False
    if d_min is not None:
        params.d_min = float(d_min)
    params.positive_charge_margin = float(positive_charge_margin or 0.0)
    if charge_min_fraction is not None:
        params.charge_min_fraction = float(charge_min_fraction)
    if charge_max_fraction is not None:
        params.charge_max_fraction = float(charge_max_fraction)
    params.charge_count_conflict_radius = charge_count_conflict_radius
    params.energy_bound_margin = energy_margin
    params.f11_min_support_states = int(f11_min_support_states)
    d = canvas_d
    full_ld = math.comb(canvas.n_pos, d)
    selection_enabled = ((selection_target is not None and selection_target > 0)
                         or (selection_min_margin is not None))
    print("=" * 80)
    print(f"Gate: {gate}  ({gate_category(gate)})")
    print(f"|C|={canvas.n_pos}, d={d}, |Ld|={full_ld:,}, inputs={func.num_inputs}")
    print(f"samples={samples:,}, workers={workers}, profile={strict_profile}")
    print(f"mu_minus={params.mu_minus}, io_margin={params.io_instability_margin}")
    print("=" * 80)
    total = {
        "processed": 0, "qc12_after": [0] * 12, "qc12_passed": [],
        "qc3_after_f4": 0, "qc3_after_f11": 0, "qc3_after_f12": 0,
        "selected_candidates": 0,
    }
    combos = random_combinations(canvas.n_pos, d, samples, seed)
    chunks = list(chunked(combos, chunksize))
    start = time.time()
    if workers <= 1:
        _init_worker(skeleton, canvas, params, func)
        for chunk in chunks:
            merge(total, worker_process_chunk(chunk))
    else:
        ctx = mp.get_context("spawn")
        with ctx.Pool(processes=workers, initializer=_init_worker,
                       initargs=(skeleton, canvas, params, func)) as pool:
            for idx, part in enumerate(
                    pool.imap_unordered(worker_process_chunk, chunks), 1):
                merge(total, part)
                if idx % 5 == 0 or idx == len(chunks):
                    print(f"  {total['processed']:,}/{samples:,} "
                          f"({100*total['processed']/samples:.1f}%)")
        _init_worker(skeleton, canvas, params, func)
    selected_rows = []
    if selection_enabled:
        sc, selected_rows = select_ranked_candidates(
            total["qc12_passed"], target=selection_target,
            min_margin=selection_min_margin)
        total["selected_candidates"] = len(sc)
    else:
        total["selected_candidates"] = total["qc12_after"][11]
    elapsed = time.time() - start
    output_dir = os.path.join("results_2input", gate)
    write_reports(gate, full_ld, total, elapsed, output_dir,
                  sim_time, selection_enabled, selected_rows, nip)
    print(f"\nProcessed: {total['processed']:,}")
    print(f"After F12: {total['qc12_after'][11]:,}")
    print(f"Candidates: {total['selected_candidates']:,}")
    print(f"Wall time: {elapsed:.2f}s  →  {output_dir}")


def main():
    p = argparse.ArgumentParser(description="QuickCell-12 for 2-input gates")
    p.add_argument("--gate", required=True)
    p.add_argument("--samples", type=int, default=100000)
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--chunksize", type=int, default=2000)
    p.add_argument("--seed", type=int, default=12345)
    p.add_argument("--sim-time", type=float, default=0.01)
    p.add_argument("--canvas-d", type=int, default=3)
    p.add_argument("--strict-profile", default="balanced",
                   choices=["safe", "balanced", "strict"])
    p.add_argument("--io-margin", type=float, default=None)
    p.add_argument("--pressure-margin", type=float, default=None)
    p.add_argument("--connectivity-radius", type=float, default=None)
    p.add_argument("--d-min", type=float, default=None)
    p.add_argument("--positive-charge-margin", type=float, default=0.0)
    p.add_argument("--charge-min-fraction", type=float, default=None)
    p.add_argument("--charge-max-fraction", type=float, default=None)
    p.add_argument("--charge-count-conflict-radius", type=float, default=None)
    p.add_argument("--input-disturbance", type=float, default=None)
    p.add_argument("--energy-margin", type=float, default=None)
    p.add_argument("--f11-mode", default="counted",
                   choices=["counted", "strict-pop", "strict-hop"])
    p.add_argument("--f11-min-support-states", type=int, default=1)
    p.add_argument("--selection-target", type=int, default=0)
    p.add_argument("--selection-min-margin", type=float, default=None)
    args = p.parse_args()
    gates = parse_gate_argument(args.gate)
    sel_t = args.selection_target if args.selection_target > 0 else None
    for gate in gates:
        run_gate(
            gate=gate, samples=args.samples, workers=args.workers,
            chunksize=args.chunksize, seed=args.seed, sim_time=args.sim_time,
            strict_profile=args.strict_profile, io_margin=args.io_margin,
            pressure_margin=args.pressure_margin,
            connectivity_radius=args.connectivity_radius,
            d_min=args.d_min,
            positive_charge_margin=args.positive_charge_margin,
            charge_min_fraction=args.charge_min_fraction,
            charge_max_fraction=args.charge_max_fraction,
            charge_count_conflict_radius=args.charge_count_conflict_radius,
            input_disturbance=args.input_disturbance,
            energy_margin=args.energy_margin,
            f11_mode=args.f11_mode,
            f11_min_support_states=args.f11_min_support_states,
            selection_target=sel_t,
            selection_min_margin=args.selection_min_margin,
            canvas_d=args.canvas_d,
        )


if __name__ == "__main__":
    main()