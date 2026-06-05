# core_sidb.py
# QuickCell-8 CLEAN core
# Shared toy SiDB/BDL model for:
#   - original QuickCell 3-filter flow
#   - QuickCell-8 flow
#

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations, product
from math import exp, hypot, comb, isfinite
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple


CORE_VERSION = "QuickCell-8 CLEAN core v1"

Point = Tuple[float, float]

NEG = -1
NEU = 0


@dataclass
class Params:
    v_scale: float = 2.3

    eps_r: float = 5.6
    lambda_tf_nm: float = 5.0

    lattice_nm: float = 3.84

    mu_minus: float = -0.31
    mu_plus: float = -0.80

    energy_tol: float = 1e-9

    min_canvas_distance_lattice: float = 0.1
    connectivity_radius_lattice: float = 4.5


PARAMS = Params()


# ----------------------
# Geometry and electrostatics

def distance_lattice(a: Point, b: Point) -> float:
    return hypot(a[0] - b[0], a[1] - b[1])


def distance_nm(a: Point, b: Point, p: Params = PARAMS) -> float:
    return distance_lattice(a, b) * p.lattice_nm


def potential_eV_from_distance_nm(d_nm: float, p: Params = PARAMS) -> float:
    if d_nm <= 0:
        return float("inf")
    return (p.v_scale / p.eps_r) * exp(-d_nm / p.lambda_tf_nm) / d_nm


def potential_eV(a: Point, b: Point, p: Params = PARAMS) -> float:
    return potential_eV_from_distance_nm(distance_nm(a, b, p), p)


def print_physics_diagnostics(p: Params = PARAMS) -> None:
    print(f"CORE_VERSION = {CORE_VERSION}")
    print(f"V_scale = {p.v_scale} eV·nm")
    for d in [3.84, 5.43, 7.68, 11.5]:
        print(f"  V({d}nm) = {potential_eV_from_distance_nm(d, p):.4f} eV")
    six = 6.0 * potential_eV_from_distance_nm(3.84, p)
    print(f"  V at 3.84nm from 6 neighbors = {six:.4f} eV")


# ---------------------------------------
# Strict BDL encoding

def encode_bdl_pair(bit: int) -> Tuple[int, int]:
    """
    Strict BDL encoding:
        bit 0 -> (-1, 0)
        bit 1 -> (0, -1)
    """
    bit = int(bit)

    if bit == 0:
        return NEG, NEU

    if bit == 1:
        return NEU, NEG

    raise ValueError("BDL bit must be 0 or 1.")


def set_bdl_pair(charges: List[int], pair: Tuple[int, int], bit: int) -> None:
    i, j = pair
    qi, qj = encode_bdl_pair(bit)
    charges[i] = qi
    charges[j] = qj


def read_bdl_pair(charges: Sequence[int], pair: Tuple[int, int]) -> Optional[int]:
    """
    Strict BDL readout:
        (-1, 0) -> 0
        (0, -1) -> 1

    Invalid states:
        (-1, -1) -> None
        (0, 0)   -> None
    """
    i, j = pair

    if charges[i] == NEG and charges[j] == NEU:
        return 0

    if charges[i] == NEU and charges[j] == NEG:
        return 1

    return None


def format_charges(charges: Sequence[int]) -> str:
    return "[" + " ".join(f"{q:2d}" for q in charges) + "]"


# ------------------------------------------------------------------
# Boolean functions

def bool_AND(a: int, b: int) -> int:
    return a & b


def bool_OR(a: int, b: int) -> int:
    return a | b


def bool_XOR(a: int, b: int) -> int:
    return a ^ b


def bool_NAND(a: int, b: int) -> int:
    return 1 - (a & b)


def bool_NOR(a: int, b: int) -> int:
    return 1 - (a | b)


def bool_WIRE(a: int, b: int) -> int:
    return a


def bool_INV(a: int, b: int) -> int:
    return 1 - a


FUNCTIONS: Dict[str, Callable[[int, int], int]] = {
    "AND": bool_AND,
    "OR": bool_OR,
    "XOR": bool_XOR,
    "NAND": bool_NAND,
    "NOR": bool_NOR,
    "WIRE": bool_WIRE,
    "INV": bool_INV,
}


def all_input_patterns() -> List[Tuple[int, int]]:
    return [(0, 0), (0, 1), (1, 0), (1, 1)]


# ---------------------------------------
# Toy standard-cell template


SKELETON_POSITIONS: List[Point] = [
    (0, 0), (0, 2),      
    (0, 5), (0, 7),     
    (4, 0), (4, 2),      
]

INPUT_A_PAIR = (0, 1)
INPUT_B_PAIR = (2, 3)
OUTPUT_PAIR = (4, 5)

INPUT_PAIRS = [INPUT_A_PAIR, INPUT_B_PAIR]


CANVAS_POOL: List[Point] = [
    (1, 1),
    (2, 0),
    (2, 2),
    (3, 1),
    (1, 6),
    (2, 5),
    (2, 7),
]


@dataclass(frozen=True)
class Layout:
    combo: Tuple[int, ...]

    def canvas_positions(self) -> List[Point]:
        return [CANVAS_POOL[i] for i in self.combo]

    def points(self) -> List[Point]:
        return list(SKELETON_POSITIONS) + self.canvas_positions()

    def d(self) -> int:
        return len(self.combo)


def generate_candidate_layouts(d: int = 3) -> List[Layout]:
    return [Layout(tuple(c)) for c in combinations(range(len(CANVAS_POOL)), d)]


def number_of_candidates(d: int = 3) -> int:
    return comb(len(CANVAS_POOL), d)


# ----------------------------------------------------
# Charge construction -toy energy


def skeleton_charges_for(input_bits: Tuple[int, int], output_bit: int) -> List[int]:

    a, b = input_bits

    charges = [NEU] * len(SKELETON_POSITIONS)

    set_bdl_pair(charges, INPUT_A_PAIR, a)
    set_bdl_pair(charges, INPUT_B_PAIR, b)
    set_bdl_pair(charges, OUTPUT_PAIR, output_bit)

    return charges


def canvas_charge_states(d: int) -> Iterable[Tuple[int, ...]]:
    return product([NEG, NEU], repeat=d)


def total_energy(points: Sequence[Point], charges: Sequence[int], p: Params = PARAMS) -> float:
    
    e = 0.0
    n = len(charges)

    for i in range(n):
        if charges[i] != NEG:
            continue

        for j in range(i + 1, n):
            if charges[j] != NEG:
                continue
            e += potential_eV(points[i], points[j], p)

    e += p.mu_minus * sum(1 for q in charges if q == NEG)

    return e


def ground_state_fixed_io(
    layout: Layout,
    input_bits: Tuple[int, int],
    output_bit: int,
    p: Params = PARAMS,
) -> Tuple[float, Optional[Tuple[int, ...]], int]:
   
    points = layout.points()
    skel = skeleton_charges_for(input_bits, output_bit)

    best_e = float("inf")
    best_n: Optional[Tuple[int, ...]] = None
    count = 0

    for cstate in canvas_charge_states(layout.d()):
        charges = tuple(skel + list(cstate))

      
        if read_bdl_pair(charges, OUTPUT_PAIR) != output_bit:
            continue

        count += 1

        e = total_energy(points, charges, p)

        if e < best_e:
            best_e = e
            best_n = charges

    return best_e, best_n, count


def predict_output(
    layout: Layout,
    input_bits: Tuple[int, int],
    p: Params = PARAMS,
) -> Optional[int]:
    
    e0, _, c0 = ground_state_fixed_io(layout, input_bits, 0, p)
    e1, _, c1 = ground_state_fixed_io(layout, input_bits, 1, p)

    if c0 == 0 and c1 == 0:
        return None

    if not isfinite(e0) and not isfinite(e1):
        return None

    if abs(e0 - e1) <= p.energy_tol:
        return None

    return 0 if e0 < e1 else 1


def exact_verify_layout(
    layout: Layout,
    func: Callable[[int, int], int],
    p: Params = PARAMS,
) -> bool:
   
    for bits in all_input_patterns():
        expected = func(*bits)
        pred = predict_output(layout, bits, p)

        if pred is None:
            return False

        if pred != expected:
            return False

    return True


# -------------------------------------------
# Original QuickCell-like filters


def F4_positive_charge_pruning(layout: Layout, p: Params = PARAMS) -> bool:
   
    points = layout.points()

    for i, pi in enumerate(points):
        vmax = 0.0

        for j, pj in enumerate(points):
            if i == j:
                continue
            vmax += potential_eV(pi, pj, p)

        if p.mu_plus + vmax > 0:
            return True

    return False


def F11_physical_infeasibility_pruning(
    layout: Layout,
    func: Callable[[int, int], int],
    p: Params = PARAMS,
) -> bool:
   
    for bits in all_input_patterns():
        y = func(*bits)
        e, _, count = ground_state_fixed_io(layout, bits, y, p)

        if count == 0 or not isfinite(e):
            return True

    return False


def F12_io_signal_instability_pruning(
    layout: Layout,
    func: Callable[[int, int], int],
    p: Params = PARAMS,
) -> bool:
   
    for bits in all_input_patterns():
        y = func(*bits)
        wrong = 1 - y

        e_correct, _, c_correct = ground_state_fixed_io(layout, bits, y, p)
        e_wrong, _, c_wrong = ground_state_fixed_io(layout, bits, wrong, p)

        if c_correct == 0 or not isfinite(e_correct):
            return True

        if c_wrong > 0 and isfinite(e_wrong):
            if e_wrong <= e_correct + p.energy_tol:
                return True

    return False


def debug_F4_positive_charge(layout: Layout, p: Params = PARAMS) -> None:
    points = layout.points()

    print("\nF4 Positive Charge Debug")
    print("------------------------")

    for i, pi in enumerate(points):
        contributions = []

        for j, pj in enumerate(points):
            if i == j:
                continue
            contributions.append((j, potential_eV(pi, pj, p)))

        vmax = sum(v for _, v in contributions)
        condition = p.mu_plus + vmax
        status = "PRUNE" if condition > 0 else "OK"

        print(
            f"SiDB {i:2d} at {pi}: "
            f"Vmax={vmax:.4f} eV, "
            f"mu_plus+Vmax={condition:.4f} -> {status}"
        )

        strongest = sorted(contributions, key=lambda x: x[1], reverse=True)[:5]
        print("   strongest:", [(j, round(v, 4)) for j, v in strongest])