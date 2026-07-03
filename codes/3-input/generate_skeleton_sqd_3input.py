# generate_skeleton_sqd_3input.py.py.py.pei
import os, math
from datetime import datetime
from html import escape

A1_X = 3.84; A2_Y = 7.68; B2_Y = 2.25

def phys(n, m, l=1):
    return n * A1_X, m * A2_Y + l * B2_Y

def fmt(v):
    s = f"{float(v):.9f}".rstrip("0").rstrip(".")
    return "0" if s == "-0" else s

COLOR = {"input": "#ff66ccff", "output": "#ffffcc66", "wire": "#ffc8c8c8"}

def skeleton_3in_1out():
    s = []
    s.append({"n":-15,"m": 9,"l":1,"kind":"input","role":"IN0_A"})
    s.append({"n":-15,"m":10,"l":1,"kind":"input","role":"IN0_B"})
    s.append({"n":-15,"m": 0,"l":1,"kind":"input","role":"IN1_A"})
    s.append({"n":-15,"m": 1,"l":1,"kind":"input","role":"IN1_B"})
    s.append({"n":-15,"m":-10,"l":1,"kind":"input","role":"IN2_A"})
    s.append({"n":-15,"m": -9,"l":1,"kind":"input","role":"IN2_B"})
    for i,(n,m) in enumerate([(-10,9),(-5,6),(0,3)]):
        s.append({"n":n,"m":m,"l":1,"kind":"wire","role":f"W_UP{i}"})
    for i,n in enumerate([-10,-5,0]):
        s.append({"n":n,"m":0,"l":1,"kind":"wire","role":f"W_MID{i}"})
    for i,(n,m) in enumerate([(-10,-9),(-5,-6),(0,-3)]):
        s.append({"n":n,"m":m,"l":1,"kind":"wire","role":f"W_LO{i}"})
    s.append({"n":5,"m":0,"l":1,"kind":"wire","role":"W_OUT"})
    s.append({"n":10,"m":0,"l":1,"kind":"output","role":"OUT0_A"})
    s.append({"n":10,"m":1,"l":1,"kind":"output","role":"OUT0_B"})
    return s

def write_sqd(path, sidbs):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    xs = [phys(s["n"],s["m"],s["l"])[0] for s in sidbs]
    ys = [phys(s["n"],s["m"],s["l"])[1] for s in sidbs]
    mg = 50.0
    x1,x2 = min(xs)-mg, max(xs)+mg
    y1,y2 = min(ys)-mg, max(ys)+mg
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(path,"w",encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n<siqad>\n')
        f.write(f'  <program><file_purpose>save</file_purpose>'
                f'<version>0.3.3</version><date>{escape(now)}</date></program>\n')
        f.write(f'  <gui><zoom>0.05</zoom>'
                f'<displayed_region x1="{fmt(x1)}" y1="{fmt(y1)}" '
                f'x2="{fmt(x2)}" y2="{fmt(y2)}"/>'
                f'<scroll x="0" y="0"/></gui>\n')
        f.write('  <layers>\n')
        f.write('    <layer_prop><name>Lattice</name><type>Lattice</type>'
                '<role>Design</role><zoffset>0</zoffset><zheight>0</zheight>'
                '<visible>1</visible><active>0</active><lat_vec>'
                '<a1 x="3.84" y="0"/><a2 x="0" y="7.68"/><N>2</N>'
                '<b1 x="0" y="0"/><b2 x="0" y="2.25"/></lat_vec></layer_prop>\n')
        f.write('    <layer_prop><name>Screenshot Overlay</name><type>Misc</type>'
                '<role>Overlay</role><zoffset>0</zoffset><zheight>0</zheight>'
                '<visible>1</visible><active>0</active></layer_prop>\n')
        f.write('    <layer_prop><name>Surface</name><type>DB</type>'
                '<role>Design</role><zoffset>0</zoffset><zheight>0</zheight>'
                '<visible>1</visible><active>0</active></layer_prop>\n')
        f.write('    <layer_prop><name>Metal</name><type>Electrode</type>'
                '<role>Design</role><zoffset>1000</zoffset><zheight>100</zheight>'
                '<visible>1</visible><active>0</active></layer_prop>\n')
        f.write('  </layers>\n  <design>\n')
        f.write('    <layer type="Lattice"/>\n    <layer type="Misc"/>\n')
        f.write('    <layer type="DB">\n')
        for s in sidbs:
            px,py = phys(s["n"],s["m"],s["l"])
            color = COLOR.get(s["kind"],"#ffc8c8c8")
            f.write(f' <!-- {escape(s["kind"])} {escape(s["role"])} -->\n')
            f.write(f'<dbdot><layer_id>2</layer_id>'
                    f'<latcoord n="{s["n"]}" m="{s["m"]}" l="{s["l"]}"/>'
                    f'<physloc x="{fmt(px)}" y="{fmt(py)}"/>'
                    f'<color>{color}</color></dbdot>\n')
        f.write(' </layer>\n    <layer type="Electrode"/>\n')
        f.write('  </design>\n</siqad>\n')
    print(f"Created: {path} ({len(sidbs)} SiDBs)")

def print_info(sidbs):
    print(f"\n{'='*60}")
    print(f"  3-Input Compact Skeleton ({len(sidbs)} SiDBs)")
    print(f"{'='*60}")
    for s in sidbs:
        px,py = phys(s["n"],s["m"],s["l"])
        print(f"  {s['role']:<10} n={s['n']:>4} m={s['m']:>4}  "
              f"x={px/10:.3f}nm  y={py/10:.3f}nm")
    # F3 trigger analyses
    print(f"\n  Wire positions (for F3 analysis):")
    wires = [(s["n"],s["m"]) for s in sidbs if s["kind"]=="wire"]
    canvas_n = [-13,-11,-6,-3,-1,3,6,8,11,14,17]
    canvas_m = [-12,-9,-6,-4,-3,-1,0,1,3,4,6,9,12]
    triggers = 0
    for cn in canvas_n:
        for cm in canvas_m:
            for wn,wm in wires:
                d = math.sqrt(((cn-wn)*0.384)**2 + ((cm-wm)*0.768)**2)
                if d < 0.40:
                    print(f"    Canvas({cn},{cm}) ↔ Wire({wn},{wm}): {d:.3f} nm → F3 TRIGGER")
                    triggers += 1
    print(f"  Total F3 trigger positions: {triggers} / 143")

def main():
    out = "skeleton_sqd_files"
    os.makedirs(out, exist_ok=True)
    s = skeleton_3in_1out()
    write_sqd(os.path.join(out,"skeleton_3in_1out_compact.sqd"), s)
    print_info(s)

if __name__ == "__main__":
    main()