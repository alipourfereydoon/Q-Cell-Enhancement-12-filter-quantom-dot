# export_siqad_validation_2input.py
from __future__ import annotations

import argparse
import csv
import json
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
from src.siqad_export import write_candidate_export

QC12_FILTERS = [
    F1_min_distance, F2_symmetry, F3_wire_interference,
    F4_positive_charge, F5_charge_count_bound,
    F6_input_pin_disturbance, F7_path_connectivity,
    F8_output_potential_bound, F9_electrostatic_pressure,
    F10_energy_lower_bound,
]

_G: Dict[str, Any] = {}


def _override(d, o):
    return d if o is None else o


def get_skeleton_and_canvas(gate_name):
    cat = gate_category(gate_name)
    if cat == "2in_1out":
        return paper_like_skeleton_2in_1out(), paper_like_canvas_2in_1out()
    elif cat == "2in_2out":
        return paper_like_skeleton_2in_2out(), paper_like_canvas_2in_2out()
    elif cat == "1in_1out":
        return paper_like_skeleton_1in_1out(), paper_like_canvas_1in_1out()
    raise ValueError(f"Unknown category for '{gate_name}'.")


def make_params(profile, io_margin_override, pressure_margin_override,
                wire_radius_override, input_disturbance_override,
                connectivity_radius_override,
                charge_min_fraction_override, charge_max_fraction_override,
                energy_margin_override):
    profile = str(profile).strip().lower()
    kw = dict(
        mu_minus=-0.32, mu_plus=-0.80, lambda_tf=5.0, epsilon_r=5.6,
        check_fixed_io_population=False, check_configuration_stability=False,
        relaxed_enumeration=True, instability_check_inputs=False,
        f10_check_input_inversions=False,
        bit0_requires_positive_pressure=False,
        charge_min_fraction=_override(0.0, charge_min_fraction_override),
        charge_max_fraction=_override(1.0, charge_max_fraction_override),
        connectivity_radius=connectivity_radius_override,
        pressure_margin=_override(0.0, pressure_margin_override),
        energy_bound_margin=energy_margin_override,
        io_instability_margin=_override(0.02, io_margin_override),
        input_disturbance_limit=input_disturbance_override,
    )
    wr = {"safe": 0.35, "balanced": 0.40, "strict": 0.45}
    if profile not in wr:
        raise ValueError("Unknown profile")
    kw["wire_forbidden_radius"] = _override(wr[profile], wire_radius_override)
    if profile == "strict":
        kw["connectivity_radius"] = _override(12.5, connectivity_radius_override)
        kw["input_disturbance_limit"] = _override(0.45, input_disturbance_override)
    return PhysicalParameters(**kw)


def apply_runtime_overrides(params, d_min, positive_charge_margin,
                            charge_count_conflict_radius,
                            f11_mode, f11_min_support_states):
    if d_min is not None:
        params.d_min = float(d_min)
    params.positive_charge_margin = float(positive_charge_margin or 0.0)
    params.charge_count_conflict_radius = charge_count_conflict_radius
    params.f11_mode = str(f11_mode)
    params.f11_min_support_states = int(f11_min_support_states)
    if params.f11_mode == "counted":
        params.relaxed_enumeration = True
        params.check_configuration_stability = False
    elif params.f11_mode == "strict-pop":
        params.relaxed_enumeration = False
        params.check_configuration_stability = False
        params.check_fixed_io_population = False
    elif params.f11_mode == "strict-hop":
        params.relaxed_enumeration = False
        params.check_configuration_stability = True
        params.check_fixed_io_population = False
    return params


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
    c = _G["canvas"]
    s = _G["skeleton"]
    return Layout(skeleton=s,
                  canvas_positions=[c.positions[i] for i in combo],
                  canvas_indices=combo)


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
    for ci in cg:
        c = params.mu_minus * abs(params.qe)
        for i, q in enumerate(fc):
            c += q * (-1) * P[i, ci]
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


def worker_process_chunk(chunk):
    a = [0] * 12
    passed = []
    for combo in chunk:
        lay = make_layout(combo)
        af, ok = run_filter_sequence_for_qc12(lay)
        for i in range(12):
            a[i] += af[i]
        if ok:
            passed.append(combo)
    return {"processed": len(chunk), "qc12_after": a, "qc12_passed": passed}


def random_combinations(n, d, count, seed):
    rng = random.Random(seed)
    seen = set()
    count = min(count, math.comb(n, d))
    while len(seen) < count:
        c = tuple(sorted(rng.sample(range(n), d)))
        if c not in seen:
            seen.add(c)
            yield c


def chunked(it, sz):
    b = []
    for x in it:
        b.append(x)
        if len(b) >= sz:
            yield b
            b = []
    if b:
        yield b


def expected_truth_table(func):
    t = {}
    for x in func.all_inputs():
        t["".join(str(i) for i in x)] = "".join(str(i) for i in func.eval(x))
    return t


def select_ranked_candidates(combos, target, min_margin):
    scored = [(fast_energy_margin(c), c) for c in combos]
    scored.sort(key=lambda t: (-t[0], t[1]))
    sel = []
    rows = []
    for m, c in scored:
        if min_margin is not None and m < min_margin:
            continue
        if target is not None and target > 0 and len(sel) >= target:
            break
        sel.append(c)
        rows.append({"rank": len(sel), "energy_margin": m,
                      "canvas_indices": " ".join(str(i) for i in c)})
    return sel, rows


def write_csv_simple(path, rows):
    if not rows:
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def write_validation_sheet(root_dir, gate, candidate_ids, func, cmap):
    path = os.path.join(root_dir, "validation_sheet.csv")
    fn = ["gate", "candidate_id", "input_bits", "expected_output",
          "observed_output", "io_integrity_ok", "siqad_file", "notes"]
    rows = []
    for cid in candidate_ids:
        for x in func.all_inputs():
            ib = "".join(str(i) for i in x)
            eo = "".join(str(i) for i in func.eval(x))
            rows.append({"gate": gate, "candidate_id": cid,
                         "input_bits": ib, "expected_output": eo,
                         "observed_output": "", "io_integrity_ok": "",
                         "siqad_file": cmap[cid], "notes": ""})
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fn)
        w.writeheader()
        w.writerows(rows)
    return path


def write_readme(root_dir, gate):
    path = os.path.join(root_dir, "README_validation.md")
    lines = [
        f"# SiQAD Validation for {gate} (2-input)", "",
        "Open `candidate.sqd` in each candidate folder.", "",
        "BDL encoding: bit 0 → (pos_a=-1, pos_b=0), bit 1 → (pos_a=0, pos_b=-1)", "",
    ]
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return path


def parse_gate_argument(gate_arg):
    gate_arg = gate_arg.strip()
    if gate_arg.upper() == "ALL":
        return get_all_2input_gate_names()
    return [normalize_gate_name(g) for g in gate_arg.split(",") if g.strip()]


def run_export_for_gate(args, gate):
    gate = normalize_gate_name(gate)
    func = get_2input_gate(gate)
    skeleton, canvas = get_skeleton_and_canvas(gate)
    d = args.canvas_d

    params = make_params(
        profile=args.strict_profile,
        io_margin_override=args.io_margin,
        pressure_margin_override=args.pressure_margin,
        wire_radius_override=args.wire_radius,
        input_disturbance_override=args.input_disturbance,
        connectivity_radius_override=args.connectivity_radius,
        charge_min_fraction_override=args.charge_min_fraction,
        charge_max_fraction_override=args.charge_max_fraction,
        energy_margin_override=args.energy_margin,
    )
    params = apply_runtime_overrides(
        params, args.d_min, args.positive_charge_margin,
        args.charge_count_conflict_radius,
        args.f11_mode, args.f11_min_support_states,
    )

    root_dir = os.path.join(args.output_dir, gate)
    os.makedirs(root_dir, exist_ok=True)

    combos = random_combinations(canvas.n_pos, d, args.samples, args.seed)
    chunks = list(chunked(combos, args.chunksize))

    print("=" * 80)
    print(f"Exporting: {gate} ({gate_category(gate)})")
    print(f"|C|={canvas.n_pos}, d={d}, |Ld|={math.comb(canvas.n_pos, d):,}")
    print(f"Samples: {args.samples}, Max candidates: {args.max_candidates}")
    print("=" * 80)

    total_processed = 0
    after_counts = [0] * 12
    passed_all = []
    start = time.time()

    if args.workers <= 1:
        _init_worker(skeleton, canvas, params, func)
        for chunk in chunks:
            r = worker_process_chunk(chunk)
            total_processed += r["processed"]
            for i in range(12):
                after_counts[i] += r["qc12_after"][i]
            passed_all.extend(r["qc12_passed"])
    else:
        ctx = mp.get_context("spawn")
        with ctx.Pool(processes=args.workers, initializer=_init_worker,
                       initargs=(skeleton, canvas, params, func)) as pool:
            for idx, r in enumerate(
                    pool.imap_unordered(worker_process_chunk, chunks), 1):
                total_processed += r["processed"]
                for i in range(12):
                    after_counts[i] += r["qc12_after"][i]
                passed_all.extend(r["qc12_passed"])
                if idx % 5 == 0 or idx == len(chunks):
                    print(f"  [{gate}] {total_processed}/{args.samples} "
                          f"raw_passed={len(passed_all)}")
        _init_worker(skeleton, canvas, params, func)

    sel_enabled = (args.selection_target > 0
                   or args.selection_min_margin is not None)
    if sel_enabled:
        selected_combos, _ = select_ranked_candidates(
            passed_all,
            target=args.selection_target if args.selection_target > 0 else None,
            min_margin=args.selection_min_margin)
    else:
        selected_combos = passed_all[:args.max_candidates]

    if len(selected_combos) > args.max_candidates:
        selected_combos = selected_combos[:args.max_candidates]

    truth = expected_truth_table(func)
    cids = []
    cmap = {}
    summary = []

    for combo in selected_combos:
        cid = len(cids) + 1
        lay = Layout(
            skeleton=skeleton,
            canvas_positions=[canvas.positions[i] for i in combo],
            canvas_indices=combo)
        files = write_candidate_export(
            root_dir=root_dir, gate_name=gate, candidate_id=cid,
            layout=lay, expected_truth_table=truth,
            snap_to_lattice=not args.no_snap)
        cids.append(cid)
        cmap[cid] = files["sqd"]
        summary.append({
            "gate": gate, "candidate_id": cid,
            "energy_margin": fast_energy_margin(combo),
            "canvas_indices": " ".join(str(i) for i in combo),
            "candidate_sqd": files["sqd"],
        })

    sheet = write_validation_sheet(root_dir, gate, cids, func, cmap)
    write_csv_simple(os.path.join(root_dir, "export_summary.csv"), summary)
    write_readme(root_dir, gate)
    elapsed = time.time() - start

    report = {
        "gate": gate, "category": gate_category(gate),
        "samples_processed": total_processed,
        "raw_post_f12": len(passed_all),
        "exported": len(cids),
        "elapsed": elapsed,
        "after_counts": {f"F{i+1}": after_counts[i] for i in range(12)},
    }
    with open(os.path.join(root_dir, "export_report.json"), "w",
              encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(f"\nFilter counts:")
    for i, v in enumerate(after_counts, 1):
        print(f"  F{i}: {v}")
    print(f"Raw post-F12: {len(passed_all)}")
    print(f"Exported: {len(cids)} in {elapsed:.2f}s → {root_dir}")
    return report


def write_global_summary(output_dir, reports):
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, "all_gates_export_summary.csv")
    rows = [{"gate": r["gate"], "category": r.get("category"),
             "exported": r["exported"], "elapsed": r["elapsed"]}
            for r in reports]
    write_csv_simple(path, rows)
    print(f"\nGlobal summary: {path}")


def main():
    p = argparse.ArgumentParser(
        description="Export QuickCell candidates for SiQAD (2-input gates).")
    p.add_argument("--gate", required=True)
    p.add_argument("--samples", type=int, default=100000)
    p.add_argument("--max-candidates", type=int, default=20)
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--chunksize", type=int, default=2000)
    p.add_argument("--seed", type=int, default=12345)
    p.add_argument("--canvas-d", type=int, default=3)
    p.add_argument("--output-dir", default="validation_exports_2input")
    p.add_argument("--strict-profile", default="balanced",
                   choices=["safe", "balanced", "strict"])
    p.add_argument("--io-margin", type=float, default=None)
    p.add_argument("--pressure-margin", type=float, default=None)
    p.add_argument("--d-min", type=float, default=None)
    p.add_argument("--wire-radius", type=float, default=None)
    p.add_argument("--positive-charge-margin", type=float, default=0.0)
    p.add_argument("--charge-min-fraction", type=float, default=None)
    p.add_argument("--charge-max-fraction", type=float, default=None)
    p.add_argument("--charge-count-conflict-radius", type=float, default=None)
    p.add_argument("--input-disturbance", type=float, default=None)
    p.add_argument("--connectivity-radius", type=float, default=None)
    p.add_argument("--energy-margin", type=float, default=None)
    p.add_argument("--f11-mode", default="counted",
                   choices=["counted", "strict-pop", "strict-hop"])
    p.add_argument("--f11-min-support-states", type=int, default=1)
    p.add_argument("--selection-target", type=int, default=0)
    p.add_argument("--selection-min-margin", type=float, default=None)
    p.add_argument("--no-snap", action="store_true")
    args = p.parse_args()

    gates = parse_gate_argument(args.gate)
    reports = [run_export_for_gate(args, g) for g in gates]
    write_global_summary(args.output_dir, reports)


if __name__ == "__main__":
    main()