from __future__ import annotations
import csv, json, os
from datetime import datetime
from html import escape
from typing import Dict, Any, List
from .data_structures import Layout

LATTICE_A1_X = 0.384    
LATTICE_A2_Y = 0.768    
LATTICE_BASIS = {0: (0.0, 0.0), 1: (0.0, 0.225)}  

SIQAD_A1_X = 3.84      
SIQAD_A2_Y = 7.68       
SIQAD_BASIS_Y = {0: 0.0, 1: 2.25}                    


def _fmt(v):
    s = f"{float(v):.9f}".rstrip("0").rstrip(".")
    return "0" if s == "-0" else s


def _arr_to_list(p):
    return [float(p[0]), float(p[1]), float(p[2]) if len(p) > 2 else 0.0]


def _nearest_lattice_coord(x_nm, y_nm, used, max_radius=50):
    for radius in range(max_radius + 1):
        candidates = []
        for l_val, (_, by) in LATTICE_BASIS.items():
            n0 = round(x_nm / LATTICE_A1_X)
            m0 = round((y_nm - by) / LATTICE_A2_Y)
            for dn in range(-radius, radius + 1):
                for dm in range(-radius, radius + 1):
                    n, m = n0 + dn, m0 + dm
                    key = (int(n), int(m), int(l_val))
                    if key in used:
                        continue
                    sx = n * LATTICE_A1_X
                    sy = m * LATTICE_A2_Y + by
                    dist2 = (sx - x_nm)**2 + (sy - y_nm)**2
                    candidates.append((dist2, int(n), int(m), int(l_val)))
        if candidates:
            candidates.sort(key=lambda t: t[0])
            dist2, n, m, l_val = candidates[0]
            used.add((n, m, l_val))
            return {
                "n": n, "m": m, "l": l_val,
                "siqad_x": float(n * SIQAD_A1_X),
                "siqad_y": float(m * SIQAD_A2_Y + SIQAD_BASIS_Y[l_val]),
                "snap_error": float(dist2**0.5),
            }
    raise RuntimeError("No unused lattice site found.")


def collect_layout_rows(layout):
    rows = []
    sk = layout.skeleton
    sid = 0
    for pi, pin in enumerate(sk.input_pins):
        for sfx, pos in [("A", pin.pos_a), ("B", pin.pos_b)]:
            rows.append({"site_id": sid, "kind": "skeleton_input",
                         "role": f"IN{pi}_{sfx}", "pin_index": pi,
                         "x": float(pos[0]), "y": float(pos[1]),
                         "z": float(pos[2]) if len(pos) > 2 else 0.0})
            sid += 1
    for pi, pin in enumerate(sk.output_pins):
        for sfx, pos in [("A", pin.pos_a), ("B", pin.pos_b)]:
            rows.append({"site_id": sid, "kind": "skeleton_output",
                         "role": f"OUT{pi}_{sfx}", "pin_index": pi,
                         "x": float(pos[0]), "y": float(pos[1]),
                         "z": float(pos[2]) if len(pos) > 2 else 0.0})
            sid += 1
    for wi, w in enumerate(sk.wire_sidbs):
        rows.append({"site_id": sid, "kind": "skeleton_wire",
                     "role": f"WIRE{wi}", "pin_index": "",
                     "x": float(w.coords[0]), "y": float(w.coords[1]),
                     "z": float(w.coords[2])})
        sid += 1
    for ci, p in enumerate(layout.canvas_positions):
        rows.append({"site_id": sid, "kind": "canvas",
                     "role": f"CANVAS{ci}", "pin_index": "",
                     "x": float(p[0]), "y": float(p[1]),
                     "z": float(p[2]) if len(p) > 2 else 0.0})
        sid += 1
    return rows


def prepare_siqad_rows(rows, snap_to_lattice=True):
    out = []
    used = set()
    for row in rows:
        r = dict(row)
        nearest = _nearest_lattice_coord(float(row["x"]), float(row["y"]), used)
        r.update(nearest)
        if snap_to_lattice:
            r["export_x"] = nearest["siqad_x"]
            r["export_y"] = nearest["siqad_y"]
        else:
            r["export_x"] = float(row["x"]) * 10.0
            r["export_y"] = float(row["y"]) * 10.0
        out.append(r)
    return out


def color_for_kind(kind):
    return {"skeleton_input": "#ff66ccff", "skeleton_output": "#ffffcc66",
            "skeleton_wire": "#ffc8c8c8", "canvas": "#ff66dd66"
            }.get(kind, "#ffc8c8c8")


def write_rows_csv(path, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fn = ["site_id", "kind", "role", "pin_index", "x", "y", "z",
          "n", "m", "l", "siqad_x", "siqad_y",
          "export_x", "export_y", "snap_error"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fn)
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k, "") for k in fn})


def write_siqad_033_sqd(path, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if rows:
        xs = [float(r["export_x"]) for r in rows]
        ys = [float(r["export_y"]) for r in rows]
        mg = 100.0
        x1, x2, y1, y2 = min(xs)-mg, max(xs)+mg, min(ys)-mg, max(ys)+mg
    else:
        x1, x2, y1, y2 = -500, 500, -500, 500
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(path, "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write("<siqad>\n")
        f.write("  <program>\n")
        f.write(" <file_purpose>save</file_purpose>\n")
        f.write("   <version>0.3.3</version>\n")
        f.write(f"<date>{escape(now)}</date>\n")
        f.write("  </program>\n")
        f.write("  <gui>\n")
        f.write(" <zoom>0.05</zoom>\n")
        f.write(f'  <displayed_region x1="{_fmt(x1)}" y1="{_fmt(y1)}" '
                f'x2="{_fmt(x2)}" y2="{_fmt(y2)}"/>\n')
        f.write(' <scroll x="0" y="0"/>\n')
        f.write("  </gui>\n")
        f.write("<layers>\n")
        f.write(" <layer_prop>\n")
        f.write(" <name>Lattice</name><type>Lattice</type>\n")
        f.write("    <role>Design</role><zoffset>0</zoffset>\n")
        f.write(" <zheight>0</zheight><visible>1</visible><active>0</active>\n")
        f.write("   <lat_vec>\n")
        f.write(' <a1 x="3.84" y="0"/><a2 x="0" y="7.68"/>\n')
        f.write("   <N>2</N>\n")
        f.write(' <b1 x="0" y="0"/><b2 x="0" y="2.25"/>\n')
        f.write(" </lat_vec>\n")
        f.write("   </layer_prop>\n")
        f.write("<layer_prop>\n")
        f.write("  <name>Screenshot Overlay</name><type>Misc</type>\n")
        f.write(" <role>Overlay</role><zoffset>0</zoffset>\n")
        f.write("   <zheight>0</zheight><visible>1</visible><active>0</active>\n")
        f.write(" </layer_prop>\n")
        f.write("  <layer_prop>\n")
        f.write("  <name>Surface</name><type>DB</type>\n")
        f.write("    <role>Design</role><zoffset>0</zoffset>\n")
        f.write(" <zheight>0</zheight><visible>1</visible><active>0</active>\n")
        f.write(" </layer_prop>\n")
        f.write("   <layer_prop>\n")
        f.write(" <name>Metal</name><type>Electrode</type>\n")
        f.write(" <role>Design</role><zoffset>1000</zoffset>\n")
        f.write("   <zheight>100</zheight><visible>1</visible><active>0</active>\n")
        f.write(" </layer_prop>\n")
        f.write(" </layers>\n")
        f.write("  <design>\n")
        f.write(' <layer type="Lattice"/>\n')
        f.write('<layer type="Misc"/>\n')
        f.write(' <layer type="DB">\n')
        for row in rows:
            color = color_for_kind(row["kind"])
            f.write(f"      <!-- {escape(str(row['kind']))} "
                    f"{escape(str(row['role']))} -->\n")
            f.write(" <dbdot>\n")
            f.write("  <layer_id>2</layer_id>\n")
            f.write(f' <latcoord n="{int(row["n"])}" '
                    f'm="{int(row["m"])}" l="{int(row["l"])}"/>\n')
            f.write(f' <physloc x="{_fmt(row["export_x"])}" '
                    f'y="{_fmt(row["export_y"])}"/>\n')
            f.write(f" <color>{color}</color>\n")
            f.write(" </dbdot>\n")
        f.write(" </layer>\n")
        f.write(' <layer type="Electrode"/>\n')
        f.write("</design>\n")
        f.write("</siqad>\n")


def layout_to_json_dict(gate_name, candidate_id, layout, truth, siqad_rows):
    sk = layout.skeleton
    return {
        "gate": gate_name, "candidate_id": candidate_id,
        "canvas_indices": list(layout.canvas_indices),
        "input_pins": [
            {"pin_index": i, "pos_a": _arr_to_list(p.pos_a),
             "pos_b": _arr_to_list(p.pos_b),
             "encoding": {"0": {"pos_a": -1, "pos_b": 0},
                          "1": {"pos_a": 0, "pos_b": -1}}}
            for i, p in enumerate(sk.input_pins)],
        "output_pins": [
            {"pin_index": i, "pos_a": _arr_to_list(p.pos_a),
             "pos_b": _arr_to_list(p.pos_b),
             "encoding": {"0": {"pos_a": -1, "pos_b": 0},
                          "1": {"pos_a": 0, "pos_b": -1}}}
            for i, p in enumerate(sk.output_pins)],
        "wire_sidbs": [_arr_to_list(w.coords) for w in sk.wire_sidbs],
        "canvas_sidbs": [_arr_to_list(p) for p in layout.canvas_positions],
        "expected_truth_table": truth,
        "siqad_export_rows": siqad_rows,
    }


def write_candidate_export(root_dir, gate_name, candidate_id,
                           layout, expected_truth_table, snap_to_lattice=True):
    cdir = os.path.join(root_dir, "candidates", f"candidate_{candidate_id:06d}")
    os.makedirs(cdir, exist_ok=True)
    raw = collect_layout_rows(layout)
    srows = prepare_siqad_rows(raw, snap_to_lattice=snap_to_lattice)
    csv_p = os.path.join(cdir, "all_sidbs.csv")
    sqd_p = os.path.join(cdir, "candidate.sqd")
    json_p = os.path.join(cdir, "candidate.json")
    write_rows_csv(csv_p, srows)
    write_siqad_033_sqd(sqd_p, srows)
    data = layout_to_json_dict(gate_name, candidate_id, layout,
                               expected_truth_table, srows)
    with open(json_p, "w", encoding="utf-8") as fp:
        json.dump(data, fp, indent=2, ensure_ascii=False)
    return {"candidate_dir": cdir, "csv": csv_p, "sqd": sqd_p, "json": json_p}
