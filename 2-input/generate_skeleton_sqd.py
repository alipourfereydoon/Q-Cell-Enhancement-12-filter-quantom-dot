# generate_skeleton_sqd.py
"""
Generate proper .sqd skeleton files with VALID SiQAD lattice coordinates.

Lattice: Si(100)-2x1
  a1 = 3.84 Å (x-direction)
  a2 = 7.68 Å (y-direction)
  Basis: l=0 → (0, 0), l=1 → (0, 2.25 Å)

Physical position (n, m, l):
  x = n × 3.84 Å
  y = m × 7.68 + l × 2.25 Å

BDL pair convention (vertical, same sublattice):
  pos_a = (n, m, l)
  pos_b = (n, m+1, l)
  Separation = 7.68 Å = 0.768 nm
  bit 0: pos_a = -1, pos_b = 0
  bit 1: pos_a = 0, pos_b = -1
"""
from __future__ import annotations
import os
from datetime import datetime
from html import escape


A1_X = 3.84   # Å
A2_Y = 7.68   # Å
B1_Y = 0.0    # Å (sublattice 0)
B2_Y = 2.25   # Å (sublattice 1)


def phys(n: int, m: int, l: int):
    """Return physical (x, y) in Å from lattice coords."""
    x = n * A1_X
    y = m * A2_Y + l * B2_Y
    return x, y


def fmt(v: float) -> str:
    s = f"{v:.9f}".rstrip("0").rstrip(".")
    return "0" if s == "-0" else s


# ═══════════════════════════════════════════════════════════════════
#  Skeleton Definitions  (all on sublattice l=1)
# ═══════════════════════════════════════════════════════════════════

def skeleton_2in_1out():
    """
    2-input, 1-output skeleton — 15 SiDBs
      4 input  + 2 output + 9 wire
    """
    sidbs = []

    # ── Input A (upper-left BDL pair) ──
    sidbs.append({"n": -38, "m": 8, "l": 1, "kind": "input", "role": "IN0_A"})
    sidbs.append({"n": -38, "m": 9, "l": 1, "kind": "input", "role": "IN0_B"})

    # ── Input B (lower-left BDL pair) ──
    sidbs.append({"n": -38, "m": -9, "l": 1, "kind": "input", "role": "IN1_A"})
    sidbs.append({"n": -38, "m": -8, "l": 1, "kind": "input", "role": "IN1_B"})

    # ── Upper wire (diagonal right-down) ──
    sidbs.append({"n": -30, "m": 6, "l": 1, "kind": "wire", "role": "W0"})
    sidbs.append({"n": -22, "m": 4, "l": 1, "kind": "wire", "role": "W1"})
    sidbs.append({"n": -14, "m": 2, "l": 1, "kind": "wire", "role": "W2"})

    # ── Lower wire (diagonal right-up) ──
    sidbs.append({"n": -30, "m": -7, "l": 1, "kind": "wire", "role": "W3"})
    sidbs.append({"n": -22, "m": -5, "l": 1, "kind": "wire", "role": "W4"})
    sidbs.append({"n": -14, "m": -3, "l": 1, "kind": "wire", "role": "W5"})

    # ── Convergence + output wire ──
    sidbs.append({"n": -6, "m": 0, "l": 1, "kind": "wire", "role": "W6"})
    sidbs.append({"n":  2, "m": 0, "l": 1, "kind": "wire", "role": "W7"})
    sidbs.append({"n": 10, "m": 0, "l": 1, "kind": "wire", "role": "W8"})

    # ── Output (right BDL pair) ──
    sidbs.append({"n": 18, "m": 0, "l": 1, "kind": "output", "role": "OUT0_A"})
    sidbs.append({"n": 18, "m": 1, "l": 1, "kind": "output", "role": "OUT0_B"})

    return sidbs


def skeleton_2in_2out():
    """
    2-input, 2-output skeleton — 19 SiDBs
      4 input + 4 output + 11 wire
    """
    sidbs = []

    # ── Input A (upper-left) ──
    sidbs.append({"n": -38, "m": 8, "l": 1, "kind": "input", "role": "IN0_A"})
    sidbs.append({"n": -38, "m": 9, "l": 1, "kind": "input", "role": "IN0_B"})

    # ── Input B (lower-left) ──
    sidbs.append({"n": -38, "m": -9, "l": 1, "kind": "input", "role": "IN1_A"})
    sidbs.append({"n": -38, "m": -8, "l": 1, "kind": "input", "role": "IN1_B"})

    # ── Upper wire ──
    sidbs.append({"n": -30, "m": 6, "l": 1, "kind": "wire", "role": "W0"})
    sidbs.append({"n": -22, "m": 4, "l": 1, "kind": "wire", "role": "W1"})
    sidbs.append({"n": -14, "m": 2, "l": 1, "kind": "wire", "role": "W2"})

    # ── Lower wire ──
    sidbs.append({"n": -30, "m": -7, "l": 1, "kind": "wire", "role": "W3"})
    sidbs.append({"n": -22, "m": -5, "l": 1, "kind": "wire", "role": "W4"})
    sidbs.append({"n": -14, "m": -3, "l": 1, "kind": "wire", "role": "W5"})

    # ── Convergence ──
    sidbs.append({"n": -6, "m": 0, "l": 1, "kind": "wire", "role": "W6"})

    # ── Fork upper ──
    sidbs.append({"n": 2, "m": 2, "l": 1, "kind": "wire", "role": "W7_UP"})
    sidbs.append({"n": 10, "m": 2, "l": 1, "kind": "wire", "role": "W8_UP"})

    # ── Fork lower ──
    sidbs.append({"n": 2, "m": -2, "l": 1, "kind": "wire", "role": "W7_DN"})
    sidbs.append({"n": 10, "m": -2, "l": 1, "kind": "wire", "role": "W8_DN"})

    # ── Output 0 (upper-right) ──
    sidbs.append({"n": 18, "m": 2, "l": 1, "kind": "output", "role": "OUT0_A"})
    sidbs.append({"n": 18, "m": 3, "l": 1, "kind": "output", "role": "OUT0_B"})

    # ── Output 1 (lower-right) ──
    sidbs.append({"n": 18, "m": -2, "l": 1, "kind": "output", "role": "OUT1_A"})
    sidbs.append({"n": 18, "m": -1, "l": 1, "kind": "output", "role": "OUT1_B"})

    return sidbs


def skeleton_1in_1out():
    """
    1-input, 1-output skeleton — 10 SiDBs
      2 input + 2 output + 6 wire
    """
    sidbs = []

    # ── Input (left) ──
    sidbs.append({"n": -38, "m": 0, "l": 1, "kind": "input", "role": "IN0_A"})
    sidbs.append({"n": -38, "m": 1, "l": 1, "kind": "input", "role": "IN0_B"})

    # ── Wire (straight horizontal) ──
    sidbs.append({"n": -30, "m": 0, "l": 1, "kind": "wire", "role": "W0"})
    sidbs.append({"n": -22, "m": 0, "l": 1, "kind": "wire", "role": "W1"})
    sidbs.append({"n": -14, "m": 0, "l": 1, "kind": "wire", "role": "W2"})
    sidbs.append({"n":  -6, "m": 0, "l": 1, "kind": "wire", "role": "W3"})
    sidbs.append({"n":   2, "m": 0, "l": 1, "kind": "wire", "role": "W4"})
    sidbs.append({"n":  10, "m": 0, "l": 1, "kind": "wire", "role": "W5"})

    # ── Output (right) ──
    sidbs.append({"n": 18, "m": 0, "l": 1, "kind": "output", "role": "OUT0_A"})
    sidbs.append({"n": 18, "m": 1, "l": 1, "kind": "output", "role": "OUT0_B"})

    return sidbs


# ═══════════════════════════════════════════════════════════════════
#  Color map
# ═══════════════════════════════════════════════════════════════════
COLOR = {
    "input":  "#ff66ccff",
    "output": "#ffffcc66",
    "wire":   "#ffc8c8c8",
}


# ═══════════════════════════════════════════════════════════════════
#  SQD file writer
# ═══════════════════════════════════════════════════════════════════
def write_sqd(path: str, sidbs: list, title: str = "skeleton"):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)

    # Compute display region
    xs = [phys(s["n"], s["m"], s["l"])[0] for s in sidbs]
    ys = [phys(s["n"], s["m"], s["l"])[1] for s in sidbs]
    margin = 30.0
    x1, x2 = min(xs) - margin, max(xs) + margin
    y1, y2 = min(ys) - margin, max(ys) + margin

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with open(path, "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write("<siqad>\n")
        f.write("  <program>\n")
        f.write("    <file_purpose>save</file_purpose>\n")
        f.write("    <version>0.3.3</version>\n")
        f.write(f"    <date>{escape(now)}</date>\n")
        f.write("  </program>\n")

        f.write("  <gui>\n")
        f.write("    <zoom>0.05</zoom>\n")
        f.write(f'    <displayed_region x1="{fmt(x1)}" y1="{fmt(y1)}" '
                f'x2="{fmt(x2)}" y2="{fmt(y2)}"/>\n')
        f.write('    <scroll x="0" y="0"/>\n')
        f.write("  </gui>\n")

        f.write("  <layers>\n")
        # Layer 0: Lattice
        f.write("    <layer_prop>\n")
        f.write("      <name>Lattice</name>\n")
        f.write("      <type>Lattice</type>\n")
        f.write("      <role>Design</role>\n")
        f.write("      <zoffset>0</zoffset>\n")
        f.write("      <zheight>0</zheight>\n")
        f.write("      <visible>1</visible>\n")
        f.write("      <active>0</active>\n")
        f.write("      <lat_vec>\n")
        f.write('        <a1 x="3.84" y="0"/>\n')
        f.write('        <a2 x="0" y="7.68"/>\n')
        f.write("        <N>2</N>\n")
        f.write('        <b1 x="0" y="0"/>\n')
        f.write('        <b2 x="0" y="2.25"/>\n')
        f.write("      </lat_vec>\n")
        f.write("    </layer_prop>\n")
        # Layer 1: Misc
        f.write("    <layer_prop>\n")
        f.write("      <name>Screenshot Overlay</name>\n")
        f.write("      <type>Misc</type>\n")
        f.write("      <role>Overlay</role>\n")
        f.write("      <zoffset>0</zoffset>\n")
        f.write("      <zheight>0</zheight>\n")
        f.write("      <visible>1</visible>\n")
        f.write("      <active>0</active>\n")
        f.write("    </layer_prop>\n")
        # Layer 2: DB (Surface)
        f.write("    <layer_prop>\n")
        f.write("      <name>Surface</name>\n")
        f.write("      <type>DB</type>\n")
        f.write("      <role>Design</role>\n")
        f.write("      <zoffset>0</zoffset>\n")
        f.write("      <zheight>0</zheight>\n")
        f.write("      <visible>1</visible>\n")
        f.write("      <active>0</active>\n")
        f.write("    </layer_prop>\n")
        # Layer 3: Metal
        f.write("    <layer_prop>\n")
        f.write("      <name>Metal</name>\n")
        f.write("      <type>Electrode</type>\n")
        f.write("      <role>Design</role>\n")
        f.write("      <zoffset>1000</zoffset>\n")
        f.write("      <zheight>100</zheight>\n")
        f.write("      <visible>1</visible>\n")
        f.write("      <active>0</active>\n")
        f.write("    </layer_prop>\n")
        f.write("  </layers>\n")

        f.write("  <design>\n")
        f.write('    <layer type="Lattice"/>\n')
        f.write('    <layer type="Misc"/>\n')
        f.write('    <layer type="DB">\n')

        for s in sidbs:
            n, m, l = s["n"], s["m"], s["l"]
            px, py = phys(n, m, l)
            color = COLOR.get(s["kind"], "#ffc8c8c8")

            f.write(f"      <!-- {escape(s['kind'])} {escape(s['role'])} -->\n")
            f.write("      <dbdot>\n")
            f.write("        <layer_id>2</layer_id>\n")
            f.write(f'        <latcoord n="{n}" m="{m}" l="{l}"/>\n')
            f.write(f'        <physloc x="{fmt(px)}" y="{fmt(py)}"/>\n')
            f.write(f"        <color>{color}</color>\n")
            f.write("      </dbdot>\n")

        f.write("    </layer>\n")
        f.write('    <layer type="Electrode"/>\n')
        f.write("  </design>\n")
        f.write("</siqad>\n")

    print(f"  Created: {path}  ({len(sidbs)} SiDBs)")


# ═══════════════════════════════════════════════════════════════════
#  Print distance report
# ═══════════════════════════════════════════════════════════════════
def print_distances(sidbs, label):
    import math
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}")
    print(f"  Total SiDBs: {len(sidbs)}")
    print(f"  {'Role':<10} {'(n,m,l)':<15} {'x [nm]':>10} {'y [nm]':>10}")
    print(f"  {'-'*50}")
    for s in sidbs:
        px, py = phys(s["n"], s["m"], s["l"])
        print(f"  {s['role']:<10} ({s['n']:>3},{s['m']:>3},{s['l']})  "
              f"{px/10:>10.3f} {py/10:>10.3f}")

    # Nearest-neighbor distances
    print(f"\n  Wire inter-SiDB distances:")
    for i in range(len(sidbs)):
        for j in range(i+1, len(sidbs)):
            if sidbs[i]["kind"] == "wire" or sidbs[j]["kind"] == "wire":
                x1, y1 = phys(sidbs[i]["n"], sidbs[i]["m"], sidbs[i]["l"])
                x2, y2 = phys(sidbs[j]["n"], sidbs[j]["m"], sidbs[j]["l"])
                d = math.sqrt((x2-x1)**2 + (y2-y1)**2) / 10.0  # nm
                if d < 5.0:  # Only show close ones
                    print(f"    {sidbs[i]['role']:>8} ↔ {sidbs[j]['role']:<8} "
                          f": {d:.3f} nm")


# ═══════════════════════════════════════════════════════════════════
#  Main
# ═══════════════════════════════════════════════════════════════════
def main():
    out_dir = "skeleton_sqd_files"
    os.makedirs(out_dir, exist_ok=True)

    print("Generating SiQAD skeleton files with valid lattice coordinates...\n")

    # ── 2-input, 1-output ──
    s1 = skeleton_2in_1out()
    write_sqd(os.path.join(out_dir, "skeleton_2in_1out.sqd"), s1,
              "2-Input, 1-Output Skeleton")
    print_distances(s1, "2-Input, 1-Output (AND, NAND, OR, NOR, XOR, XNOR, LT, GT, LE, GE)")

    # ── 2-input, 2-output ──
    s2 = skeleton_2in_2out()
    write_sqd(os.path.join(out_dir, "skeleton_2in_2out.sqd"), s2,
              "2-Input, 2-Output Skeleton")
    print_distances(s2, "2-Input, 2-Output (DOUBLE_WIRE, CX, HA)")

    # ── 1-input, 1-output ──
    s3 = skeleton_1in_1out()
    write_sqd(os.path.join(out_dir, "skeleton_1in_1out.sqd"), s3,
              "1-Input, 1-Output Skeleton")
    print_distances(s3, "1-Input, 1-Output (WIRE, INV)")

    print(f"\n{'='*60}")
    print(f"All .sqd files saved in: {out_dir}/")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()