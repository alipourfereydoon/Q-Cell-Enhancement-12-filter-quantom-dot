# quickcell12.py
# Research prototype for:
#   1) Original QuickCell 3-filter pruning flow
#   2) QuickCell-12 three-phase twelve-filter pruning flow
#
# No external dependency required.

from __future__ import annotations

from dataclasses import dataclass, field
from typing import (
    Callable,
    Dict,
    Iterable,
    List,
    Optional,
    Sequence,
    Tuple,
)
import itertools
import math
import time
import csv


Point = Tuple[float, float]
ChargeTuple = Tuple[int, ...]


# Coulomb constant in eV*nm:
# e^2 / (4*pi*epsilon0) = 1.439964548 eV nm
K_E_EV_NM = 1.439964548


# ============================================================
# Basic utilities
# ============================================================

def bits_of_int(x: int, width: int) -> Tuple[int, ...]:
    return tuple((x >> i) & 1 for i in range(width))


def int_from_bits(bits: Sequence[int]) -> int:
    y = 0
    for i, b in enumerate(bits):
        y |= (int(b) & 1) << i
    return y


def euclidean(a: Point, b: Point) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def point_segment_distance(p: Point, a: Point, b: Point) -> float:
    ax, ay = a
    bx, by = b
    px, py = p

    vx, vy = bx - ax, by - ay
    wx, wy = px - ax, py - ay

    vv = vx * vx + vy * vy
    if vv == 0.0:
        return euclidean(p, a)

    t = max(0.0, min(1.0, (wx * vx + wy * vy) / vv))
    proj = (ax + t * vx, ay + t * vy)
    return euclidean(p, proj)


# ============================================================
# Physical parameters
# ============================================================

@dataclass
class PhysParams:
    # Energies in eV
    mu_minus: float = -0.31
    mu_plus: float = -0.80

    # Thomas-Fermi screening length in nm
    lambda_tf: float = 5.0

    # Relative permittivity
    eps_r: float = 5.6

    # Optional hard minimum distance in nm.
    # If None, it is computed from a conservative single-neighbor criterion.
    d_min: Optional[float] = None

    # F3 wire interference radius in nm.
    # If no protected wire geometry is specified in Skeleton, F3 does nothing.
    wire_forbidden_radius: float = 1.0

    # F7 effective interaction radius.
    # If None, r_eff = 3 * lambda_tf.
    r_eff: Optional[float] = None

    # F5 physically admissible total negative-charge interval:
    # [floor(charge_min_frac*N), ceil(charge_max_frac*N)]
    # Default [0, N] means F5 is disabled unless calibrated.
    charge_min_frac: float = 0.0
    charge_max_frac: float = 1.0

    # Numerical tolerances
    tol: float = 1e-12
    final_energy_tol: float = 1e-10

    # In F10/F12, if True, also consider flipped input-pin states
    # as competing incorrect I/O assignments.
    include_input_flips_in_instability: bool = True


def screened_coupling(distance_nm: float, p: PhysParams) -> float:
    """
    Positive pairwise coupling J_ij in eV:
        J_ij = e^2/(4*pi*eps0*eps_r) * exp(-r/lambda_tf) / r
    """
    if distance_nm <= 0:
        return float("inf")
    return (K_E_EV_NM / p.eps_r) * math.exp(-distance_nm / p.lambda_tf) / distance_nm


def compute_min_allowed_distance(p: PhysParams) -> float:
    """
    Conservative d_min based on:
        J(d_min) = |mu_plus|
    Solved numerically. If p.d_min is given, it is used directly.
    """
    if p.d_min is not None:
        return p.d_min

    target = abs(p.mu_plus)
    if target <= 0:
        return 0.0

    lo = 1e-9
    hi = max(1.0, p.lambda_tf)

    while screened_coupling(hi, p) > target:
        hi *= 2.0
        if hi > 1e9:
            break

    for _ in range(100):
        mid = 0.5 * (lo + hi)
        if screened_coupling(mid, p) > target:
            lo = mid
        else:
            hi = mid

    return hi


# ============================================================
# Boolean function
# ============================================================

@dataclass(frozen=True)
class BoolFunction:
    """
    truth_tables[k] stores the truth table of output bit k.
    Bit x of truth_tables[k] is f_k(x).
    Example:
        AND3 = BoolFunction.from_hex(3, 0x80)
        XOR3 = BoolFunction.from_hex(3, 0x96)
        multi-output: BoolFunction.from_hex(2, (0xC, 0xA))
    """
    n_inputs: int
    n_outputs: int
    truth_tables: Tuple[int, ...]

    @classmethod
    def from_hex(cls, n_inputs: int, hex_values) -> "BoolFunction":
        if isinstance(hex_values, str):
            vals = (int(hex_values, 16),)
        elif isinstance(hex_values, int):
            vals = (hex_values,)
        else:
            vals = tuple(int(v, 16) if isinstance(v, str) else int(v)
                         for v in hex_values)

        return cls(
            n_inputs=n_inputs,
            n_outputs=len(vals),
            truth_tables=vals,
        )

    def output_int(self, input_value: int) -> int:
        y = 0
        for k, tt in enumerate(self.truth_tables):
            bit = (tt >> input_value) & 1
            y |= bit << k
        return y

    def output_bits(self, input_value: int) -> Tuple[int, ...]:
        return bits_of_int(self.output_int(input_value), self.n_outputs)


# ============================================================
# Skeleton and BDL encoding
# ============================================================

@dataclass(frozen=True)
class BDLPair:
    """
    bit0_neg: skeleton index that is negative when logical bit = 0
    bit1_neg: skeleton index that is negative when logical bit = 1
    """
    bit0_neg: int
    bit1_neg: int

    def indices(self) -> Tuple[int, int]:
        return self.bit0_neg, self.bit1_neg

    def neg_for_bit(self, bit: int) -> int:
        return self.bit1_neg if bit else self.bit0_neg

    def other_for_bit(self, bit: int) -> int:
        return self.bit0_neg if bit else self.bit1_neg

    def apply_to_charge_list(self, charges: List[Optional[int]], bit: int) -> None:
        i0, i1 = self.indices()
        charges[i0] = 0
        charges[i1] = 0
        charges[self.neg_for_bit(bit)] = -1


@dataclass
class Skeleton:
    """
    positions:
        Coordinates of all skeleton SiDBs in nm.

    input_pins:
        input_pins[i] is a list of BDL pairs forming input wire i.

    output_pins:
        output_pins[k] is a list of BDL pairs forming output wire k.

    fixed_charges:
        Optional fixed skeleton charges, e.g., permanent perturbers.

    protected_points/protected_segments:
        Used by F3 wire interference pruning.

    symmetries:
        List of permutations over canvas indices, used by F2.
        If empty, F2 is disabled.
    """
    positions: List[Point]

    input_pins: List[List[BDLPair]] = field(default_factory=list)
    output_pins: List[List[BDLPair]] = field(default_factory=list)

    fixed_charges: Dict[int, int] = field(default_factory=dict)

    protected_points: List[Point] = field(default_factory=list)
    protected_segments: List[Tuple[Point, Point]] = field(default_factory=list)

    symmetries: List[Tuple[int, ...]] = field(default_factory=list)

    input_terminal_indices: Optional[List[int]] = None
    output_terminal_indices: Optional[List[int]] = None

    default_unassigned_charge: int = 0

    def skeleton_charges(
        self,
        input_value: int,
        output_value: int,
        n_inputs: int,
        n_outputs: int,
    ) -> ChargeTuple:
        charges: List[Optional[int]] = [None] * len(self.positions)

        for idx, q in self.fixed_charges.items():
            charges[idx] = int(q)

        in_bits = bits_of_int(input_value, n_inputs)
        out_bits = bits_of_int(output_value, n_outputs)

        if len(self.input_pins) < n_inputs:
            raise ValueError("Skeleton has fewer input pins than function inputs.")

        if len(self.output_pins) < n_outputs:
            raise ValueError("Skeleton has fewer output pins than function outputs.")

        for pin_idx in range(n_inputs):
            bit = in_bits[pin_idx]
            for pair in self.input_pins[pin_idx]:
                pair.apply_to_charge_list(charges, bit)

        for out_idx in range(n_outputs):
            bit = out_bits[out_idx]
            for pair in self.output_pins[out_idx]:
                pair.apply_to_charge_list(charges, bit)

        return tuple(
            self.default_unassigned_charge if q is None else int(q)
            for q in charges
        )

    def input_site_indices(self) -> List[int]:
        s = set()
        for pin in self.input_pins:
            for pair in pin:
                s.update(pair.indices())
        return sorted(s)

    def output_site_indices(self) -> List[int]:
        s = set()
        for pin in self.output_pins:
            for pair in pin:
                s.update(pair.indices())
        return sorted(s)

    def output_pairs(self) -> List[Tuple[int, BDLPair]]:
        pairs = []
        for out_idx, pin in enumerate(self.output_pins):
            for pair in pin:
                pairs.append((out_idx, pair))
        return pairs

    def input_terminals(self) -> List[int]:
        if self.input_terminal_indices is not None:
            return list(self.input_terminal_indices)
        return self.input_site_indices()

    def output_terminals(self) -> List[int]:
        if self.output_terminal_indices is not None:
            return list(self.output_terminal_indices)
        return self.output_site_indices()


# ============================================================
# Layout context
# ============================================================

@dataclass
class LayoutContext:
    skeleton: Skeleton
    canvas_pool: Sequence[Point]
    combo: Tuple[int, ...]
    func: BoolFunction
    params: PhysParams

    _positions: Optional[List[Point]] = field(default=None, init=False, repr=False)
    _J: Optional[List[List[float]]] = field(default=None, init=False, repr=False)
    _gse_cache: Dict[Tuple[int, int], float] = field(default_factory=dict, init=False, repr=False)

    @property
    def S(self) -> int:
        return len(self.skeleton.positions)

    @property
    def d(self) -> int:
        return len(self.combo)

    @property
    def canvas_positions(self) -> List[Point]:
        return [self.canvas_pool[i] for i in self.combo]

    @property
    def positions(self) -> List[Point]:
        if self._positions is None:
            self._positions = list(self.skeleton.positions) + self.canvas_positions
        return self._positions

    @property
    def J(self) -> List[List[float]]:
        if self._J is None:
            pos = self.positions
            n = len(pos)
            J = [[0.0] * n for _ in range(n)]
            for i in range(n):
                for j in range(i + 1, n):
                    c = screened_coupling(euclidean(pos[i], pos[j]), self.params)
                    J[i][j] = c
                    J[j][i] = c
            self._J = J
        return self._J

    def full_charges(
        self,
        skeleton_charges: ChargeTuple,
        canvas_charges: ChargeTuple,
    ) -> ChargeTuple:
        return tuple(skeleton_charges) + tuple(canvas_charges)


# ============================================================
# Energy and metastability
# ============================================================

def local_qV(i: int, charges: ChargeTuple, J: List[List[float]]) -> float:
    """
    q_e * V_local in eV.
    With our convention:
        local_qV_i = - sum_j J_ij * n_j
    If n_j = -1, contribution is +J_ij.
    """
    s = 0.0
    for j, q in enumerate(charges):
        if i == j or q == 0:
            continue
        s -= J[i][j] * q
    return s


def charge_state_population_stable(q: int, qv: float, p: PhysParams) -> bool:
    """
    Population stability:
        negative if mu_minus + qV < 0
        positive if mu_plus  + qV > 0
        neutral otherwise
    Here pruning uses charges -1 and 0.
    """
    tol = p.tol

    if q == -1:
        return p.mu_minus + qv < tol

    if q == 0:
        return (p.mu_minus + qv >= -tol) and (p.mu_plus + qv <= tol)

    if q == +1:
        return p.mu_plus + qv > -tol

    raise ValueError("Charge must be -1, 0, or +1.")


def is_population_stable(
    charges: ChargeTuple,
    J: List[List[float]],
    p: PhysParams,
) -> bool:
    for i, q in enumerate(charges):
        qv = local_qV(i, charges, J)
        if not charge_state_population_stable(q, qv, p):
            return False
    return True


def electron_hop_delta_energy(
    i_from: int,
    j_to: int,
    charges: ChargeTuple,
    J: List[List[float]],
) -> float:
    """
    Electron hop from i_from with charge -1 to j_to with charge 0.
    Chemical term cancels because number of electrons is unchanged.
    """
    de = 0.0
    for k, qk in enumerate(charges):
        if k == i_from or k == j_to or qk == 0:
            continue
        de += (J[i_from][k] - J[j_to][k]) * qk
    return de


def is_configuration_stable(
    charges: ChargeTuple,
    J: List[List[float]],
    p: PhysParams,
) -> bool:
    n = len(charges)
    for i in range(n):
        if charges[i] != -1:
            continue
        for j in range(n):
            if charges[j] != 0:
                continue
            de = electron_hop_delta_energy(i, j, charges, J)
            if de < -p.tol:
                return False
    return True


def is_metastable(
    charges: ChargeTuple,
    J: List[List[float]],
    p: PhysParams,
) -> bool:
    return (
        is_population_stable(charges, J, p)
        and is_configuration_stable(charges, J, p)
    )


def total_energy(
    charges: ChargeTuple,
    J: List[List[float]],
    p: PhysParams,
) -> float:
    """
    Simplified zero-temperature electrostatic energy:
        E = sum_{i<j} J_ij n_i n_j + mu_minus * N_negative
    Positive charges are not used in this prototype.
    """
    n = len(charges)
    pair_e = 0.0
    for i in range(n):
        qi = charges[i]
        if qi == 0:
            continue
        for j in range(i + 1, n):
            qj = charges[j]
            if qj == 0:
                continue
            pair_e += J[i][j] * qi * qj

    chem = 0.0
    for q in charges:
        if q == -1:
            chem += p.mu_minus
        elif q == +1:
            chem += p.mu_plus

    return pair_e + chem


def canvas_charge_configurations(d: int) -> Iterable[ChargeTuple]:
    return itertools.product((-1, 0), repeat=d)


def ground_state_energy_fixed_io(
    ctx: LayoutContext,
    input_value: int,
    output_value: int,
) -> float:
    """
    Enumerates all canvas charge states for fixed skeleton I/O assignment.
    Returns minimum energy among metastable states.
    """
    key = (input_value, output_value)
    if key in ctx._gse_cache:
        return ctx._gse_cache[key]

    skel_charges = ctx.skeleton.skeleton_charges(
        input_value,
        output_value,
        ctx.func.n_inputs,
        ctx.func.n_outputs,
    )

    best = float("inf")
    for cchg in canvas_charge_configurations(ctx.d):
        charges = ctx.full_charges(skel_charges, cchg)
        if is_metastable(charges, ctx.J, ctx.params):
            e = total_energy(charges, ctx.J, ctx.params)
            if e < best:
                best = e

    ctx._gse_cache[key] = best
    return best


def iter_incorrect_io_assignments(
    func: BoolFunction,
    input_value: int,
    include_input_flips: bool,
) -> Iterable[Tuple[int, int]]:
    correct_y = func.output_int(input_value)

    if include_input_flips:
        input_values = range(1 << func.n_inputs)
    else:
        input_values = [input_value]

    for xi in input_values:
        for y in range(1 << func.n_outputs):
            if xi == input_value and y == correct_y:
                continue
            yield xi, y


# ============================================================
# Phase 1 filters: F1-F4
# ============================================================

def F1_min_distance_pruning(ctx: LayoutContext) -> bool:
    """
    TRUE means discard.
    Reject if any pair of canvas SiDBs is closer than d_min.
    """
    dmin = compute_min_allowed_distance(ctx.params)
    if dmin <= 0:
        return False

    pts = ctx.canvas_positions
    for i in range(len(pts)):
        for j in range(i + 1, len(pts)):
            if euclidean(pts[i], pts[j]) < dmin - ctx.params.tol:
                return True
    return False


def F2_symmetry_pruning(ctx: LayoutContext) -> bool:
    """
    TRUE means discard.
    Keeps only canonical representative under provided canvas symmetries.
    """
    perms = ctx.skeleton.symmetries
    if not perms:
        return False

    combo = tuple(sorted(ctx.combo))
    canonical = combo

    for perm in perms:
        img = tuple(sorted(perm[i] for i in combo))
        if img < canonical:
            canonical = img

    return combo != canonical


def F3_wire_interference_pruning(ctx: LayoutContext) -> bool:
    """
    TRUE means discard.
    Reject canvas SiDBs inside protected wire zones.
    """
    skel = ctx.skeleton
    p = ctx.params

    if not skel.protected_points and not skel.protected_segments:
        return False

    r = p.wire_forbidden_radius
    if r <= 0:
        return False

    for a in ctx.canvas_positions:
        for w in skel.protected_points:
            if euclidean(a, w) < r - p.tol:
                return True

        for seg_a, seg_b in skel.protected_segments:
            if point_segment_distance(a, seg_a, seg_b) < r - p.tol:
                return True

    return False


def F4_positive_charge_pruning(ctx: LayoutContext) -> bool:
    """
    TRUE means discard.
    Original QuickCell PositiveChargePruning.

    Worst case: set all other SiDBs to negative.
    If mu_plus + max_qV > 0 for any site, positive charge is possible.
    """
    J = ctx.J
    p = ctx.params
    n = len(ctx.positions)

    for i in range(n):
        # all other sites negative => qV contribution +J_ij
        max_qv = 0.0
        for j in range(n):
            if i != j:
                max_qv += J[i][j]

        if p.mu_plus + max_qv > p.tol:
            return True

    return False


# ============================================================
# Phase 2 filters: F5-F10
# ============================================================

def F5_charge_count_bound_pruning(ctx: LayoutContext) -> bool:
    """
    TRUE means discard.
    Global negative-charge count consistency.
    This filter needs calibration via charge_min_frac and charge_max_frac.
    """
    p = ctx.params
    N = len(ctx.positions)

    adm_min = math.floor(p.charge_min_frac * N)
    adm_max = math.ceil(p.charge_max_frac * N)

    # disabled if [0, N]
    if adm_min <= 0 and adm_max >= N:
        return False

    for x in range(1 << ctx.func.n_inputs):
        y = ctx.func.output_int(x)
        skel_charges = ctx.skeleton.skeleton_charges(
            x, y, ctx.func.n_inputs, ctx.func.n_outputs
        )
        req = sum(1 for q in skel_charges if q == -1)

        logic_min = req
        logic_max = req + ctx.d

        if logic_max < adm_min or logic_min > adm_max:
            return True

    return False


def _skeleton_base_qv(
    ctx: LayoutContext,
    skel_charges: ChargeTuple,
    site_idx: int,
    exclude: Optional[set] = None,
) -> float:
    if exclude is None:
        exclude = set()

    s = 0.0
    J = ctx.J

    for j, q in enumerate(skel_charges):
        if j == site_idx or j in exclude or q == 0:
            continue
        s -= J[site_idx][j] * q
    return s


def _canvas_max_qv(ctx: LayoutContext, site_idx: int) -> float:
    s = 0.0
    J = ctx.J
    S = ctx.S

    for k in range(ctx.d):
        canvas_idx = S + k
        # all canvas SiDBs negative => contribution +J
        s += J[site_idx][canvas_idx]
    return s


def F6_input_pin_disturbance_pruning(ctx: LayoutContext) -> bool:
    """
    TRUE means discard.
    Checks whether worst-case canvas potential destabilizes input pins.
    """
    input_sites = ctx.skeleton.input_site_indices()
    if not input_sites:
        return False

    for x in range(1 << ctx.func.n_inputs):
        y = ctx.func.output_int(x)
        skel_charges = ctx.skeleton.skeleton_charges(
            x, y, ctx.func.n_inputs, ctx.func.n_outputs
        )

        for i in input_sites:
            q_req = skel_charges[i]
            base = _skeleton_base_qv(ctx, skel_charges, i)
            disturbed = base + _canvas_max_qv(ctx, i)

            if not charge_state_population_stable(q_req, disturbed, ctx.params):
                return True

    return False


def F7_electrostatic_path_connectivity_pruning(ctx: LayoutContext) -> bool:
    """
    TRUE means discard.
    Build graph using r_eff. Reject if no path from input region to output region.
    """
    sources = ctx.skeleton.input_terminals()
    targets = set(ctx.skeleton.output_terminals())

    if not sources or not targets:
        return False

    p = ctx.params
    r_eff = p.r_eff if p.r_eff is not None else 3.0 * p.lambda_tf

    pos = ctx.positions
    n = len(pos)

    adj = [[] for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            if euclidean(pos[i], pos[j]) <= r_eff + p.tol:
                adj[i].append(j)
                adj[j].append(i)

    seen = set()
    stack = list(sources)

    while stack:
        u = stack.pop()
        if u in seen:
            continue
        seen.add(u)

        if u in targets:
            return False

        for v in adj[u]:
            if v not in seen:
                stack.append(v)

    return True


def _charge_window(q: int, p: PhysParams) -> Tuple[float, float]:
    """
    qV stability window for charge q.
    """
    if q == -1:
        return -float("inf"), -p.mu_minus
    if q == 0:
        return -p.mu_minus, -p.mu_plus
    if q == +1:
        return -p.mu_plus, float("inf")
    raise ValueError("Invalid charge.")


def _interval_intersects(
    a: Tuple[float, float],
    b: Tuple[float, float],
    tol: float,
) -> bool:
    return max(a[0], b[0]) <= min(a[1], b[1]) + tol


def F8_output_potential_bound_pruning(ctx: LayoutContext) -> bool:
    """
    TRUE means discard.
    Analytical bound on output-site potential.
    """
    output_sites = ctx.skeleton.output_site_indices()
    if not output_sites:
        return False

    for x in range(1 << ctx.func.n_inputs):
        y = ctx.func.output_int(x)
        skel_charges = ctx.skeleton.skeleton_charges(
            x, y, ctx.func.n_inputs, ctx.func.n_outputs
        )

        for o in output_sites:
            q_req = skel_charges[o]

            base = _skeleton_base_qv(ctx, skel_charges, o)
            max_canvas = _canvas_max_qv(ctx, o)

            attainable = (base, base + max_canvas)
            required = _charge_window(q_req, ctx.params)

            if not _interval_intersects(attainable, required, ctx.params.tol):
                return True

    return False


def F9_output_pressure_pruning(ctx: LayoutContext) -> bool:
    """
    TRUE means discard.
    BDL output pair must be biasable in the required direction.

    For required bit, target negative site must be energetically favored:
        qV_other - qV_target > 0
    """
    out_pairs = ctx.skeleton.output_pairs()
    if not out_pairs:
        return False

    J = ctx.J
    S = ctx.S

    for x in range(1 << ctx.func.n_inputs):
        y = ctx.func.output_int(x)
        out_bits = bits_of_int(y, ctx.func.n_outputs)

        skel_charges = ctx.skeleton.skeleton_charges(
            x, y, ctx.func.n_inputs, ctx.func.n_outputs
        )

        for out_idx, pair in out_pairs:
            bit = out_bits[out_idx]
            target = pair.neg_for_bit(bit)
            other = pair.other_for_bit(bit)

            exclude = set(pair.indices())

            qv_other_fixed = _skeleton_base_qv(ctx, skel_charges, other, exclude)
            qv_target_fixed = _skeleton_base_qv(ctx, skel_charges, target, exclude)

            fixed_bias = qv_other_fixed - qv_target_fixed

            min_canvas_bias = 0.0
            max_canvas_bias = 0.0

            for k in range(ctx.d):
                cidx = S + k
                # If canvas charge is negative, contribution to qV is +J.
                contrib = J[other][cidx] - J[target][cidx]

                min_canvas_bias += min(0.0, contrib)
                max_canvas_bias += max(0.0, contrib)

            min_bias = fixed_bias + min_canvas_bias
            max_bias = fixed_bias + max_canvas_bias

            # Need positive bias possible.
            if max_bias <= ctx.params.tol:
                return True

    return False


def F10_energy_lower_bound_pruning(ctx: LayoutContext) -> bool:
    """
    TRUE means discard.
    Analytical energy comparison using all-neutral canvas as simple bound.
    """
    zeros = tuple(0 for _ in range(ctx.d))

    for x in range(1 << ctx.func.n_inputs):
        y_cor = ctx.func.output_int(x)

        skel_cor = ctx.skeleton.skeleton_charges(
            x, y_cor, ctx.func.n_inputs, ctx.func.n_outputs
        )
        charges_cor = ctx.full_charges(skel_cor, zeros)
        E_cor = total_energy(charges_cor, ctx.J, ctx.params)

        for xi, yi in iter_incorrect_io_assignments(
            ctx.func,
            x,
            ctx.params.include_input_flips_in_instability,
        ):
            skel_inv = ctx.skeleton.skeleton_charges(
                xi, yi, ctx.func.n_inputs, ctx.func.n_outputs
            )
            charges_inv = ctx.full_charges(skel_inv, zeros)
            E_inv = total_energy(charges_inv, ctx.J, ctx.params)

            if E_cor > E_inv + ctx.params.tol:
                return True

    return False


# ============================================================
# Phase 3 filters: F11-F12
# ============================================================

def F11_physical_infeasibility_pruning(ctx: LayoutContext) -> bool:
    """
    TRUE means discard.
    Original QuickCell PhysicalInfeasibilityPruning.

    For every input pattern, at least one metastable canvas charge
    configuration must exist under correct I/O assignment.
    """
    for x in range(1 << ctx.func.n_inputs):
        y = ctx.func.output_int(x)
        e = ground_state_energy_fixed_io(ctx, x, y)
        if not math.isfinite(e):
            return True
    return False


def F12_io_signal_instability_pruning(ctx: LayoutContext) -> bool:
    """
    TRUE means discard.
    Original QuickCell I/O-SignalInstabilityPruning.

    Reject if any incorrect I/O assignment has lower metastable energy
    than the correct I/O assignment.
    """
    for x in range(1 << ctx.func.n_inputs):
        y_cor = ctx.func.output_int(x)
        E_cor = ground_state_energy_fixed_io(ctx, x, y_cor)

        if not math.isfinite(E_cor):
            return True

        for xi, yi in iter_incorrect_io_assignments(
            ctx.func,
            x,
            ctx.params.include_input_flips_in_instability,
        ):
            E_inv = ground_state_energy_fixed_io(ctx, xi, yi)

            if math.isfinite(E_inv) and E_inv < E_cor - ctx.params.tol:
                return True

    return False


# ============================================================
# Final simplified exact verification
# ============================================================

def simplified_exact_verify(ctx: LayoutContext) -> bool:
    """
    Simplified final verification.

    For each applied input x, input pins are fixed to x.
    Output assignment y is varied.
    The correct output must have strictly lowest metastable energy.

    For publication-grade results, replace this with QuickExact/fiction.
    """
    for x in range(1 << ctx.func.n_inputs):
        y_cor = ctx.func.output_int(x)
        E_cor = ground_state_energy_fixed_io(ctx, x, y_cor)

        if not math.isfinite(E_cor):
            return False

        for y in range(1 << ctx.func.n_outputs):
            if y == y_cor:
                continue

            E_y = ground_state_energy_fixed_io(ctx, x, y)

            if math.isfinite(E_y):
                if E_y < E_cor - ctx.params.final_energy_tol:
                    return False
                if abs(E_y - E_cor) <= ctx.params.final_energy_tol:
                    return False

    return True


# ============================================================
# Filter lists for QuickCell and QuickCell-12
# ============================================================

FILTERS_QC12: List[Tuple[str, Callable[[LayoutContext], bool]]] = [
    ("F1_MinDistance", F1_min_distance_pruning),
    ("F2_Symmetry", F2_symmetry_pruning),
    ("F3_WireInterference", F3_wire_interference_pruning),
    ("F4_PositiveCharge", F4_positive_charge_pruning),
    ("F5_ChargeCountBound", F5_charge_count_bound_pruning),
    ("F6_InputPinDisturbance", F6_input_pin_disturbance_pruning),
    ("F7_ElectrostaticConnectivity", F7_electrostatic_path_connectivity_pruning),
    ("F8_OutputPotentialBound", F8_output_potential_bound_pruning),
    ("F9_OutputPressure", F9_output_pressure_pruning),
    ("F10_EnergyLowerBound", F10_energy_lower_bound_pruning),
    ("F11_PhysicalInfeasibility", F11_physical_infeasibility_pruning),
    ("F12_IOSignalInstability", F12_io_signal_instability_pruning),
]

FILTERS_QC3: List[Tuple[str, Callable[[LayoutContext], bool]]] = [
    ("QC_F4_PositiveCharge", F4_positive_charge_pruning),
    ("QC_F11_PhysicalInfeasibility", F11_physical_infeasibility_pruning),
    ("QC_F12_IOSignalInstability", F12_io_signal_instability_pruning),
]


# ============================================================
# Runner and result reporting
# ============================================================

@dataclass
class RunResult:
    benchmark: str
    mode: str
    initial_layouts: int
    processed_layouts: int

    filter_names: List[str]
    after_filter_counts: List[int]
    filter_times: List[float]

    sim_calls: int
    valid_count: int
    valid_layouts: List[Tuple[int, ...]]

    sim_time: float
    total_wall_time: float

    def reduction_before_sim(self) -> float:
        if self.sim_calls == 0:
            return float("inf")
        return self.processed_layouts / self.sim_calls

    def print_summary(self) -> None:
        print(f"\n=== {self.benchmark} | {self.mode} ===")
        print(f"Initial layouts:     {self.initial_layouts}")
        print(f"Processed layouts:   {self.processed_layouts}")

        for name, cnt, t in zip(
            self.filter_names,
            self.after_filter_counts,
            self.filter_times,
        ):
            pct = 100.0 * cnt / max(1, self.processed_layouts)
            print(f"{name:32s}: {cnt:12d}  ({pct:8.4f}%)   time={t:.4f}s")

        print(f"Simulation calls:    {self.sim_calls}")
        print(f"Valid layouts |L*|:  {self.valid_count}")
        print(f"Reduction pre-sim:   {self.reduction_before_sim():.3f}x")
        print(f"Simulation time:     {self.sim_time:.4f}s")
        print(f"Total wall time:     {self.total_wall_time:.4f}s")


def run_pipeline(
    benchmark: str,
    func: BoolFunction,
    skeleton: Skeleton,
    canvas_pool: Sequence[Point],
    d: int,
    params: PhysParams,
    mode: str = "qc12",
    keep_layouts: bool = False,
    max_layouts: Optional[int] = None,
    external_verifier: Optional[Callable[[LayoutContext], bool]] = None,
) -> RunResult:
    """
    mode:
        "qc12" -> twelve-filter pipeline
        "qc3"  -> original QuickCell three-filter pipeline

    external_verifier:
        Optional function receiving LayoutContext and returning True/False.
        Use this to connect QuickExact or fiction.
    """
    if mode.lower() == "qc12":
        filters = FILTERS_QC12
    elif mode.lower() == "qc3":
        filters = FILTERS_QC3
    else:
        raise ValueError("mode must be 'qc12' or 'qc3'.")

    filter_names = [name for name, _ in filters]
    after_counts = [0] * len(filters)
    filter_times = [0.0] * len(filters)

    valid_layouts: List[Tuple[int, ...]] = []
    valid_count = 0
    sim_calls = 0
    sim_time = 0.0

    initial = math.comb(len(canvas_pool), d)
    processed = 0

    t_wall0 = time.perf_counter()

    for combo in itertools.combinations(range(len(canvas_pool)), d):
        if max_layouts is not None and processed >= max_layouts:
            break

        processed += 1

        ctx = LayoutContext(
            skeleton=skeleton,
            canvas_pool=canvas_pool,
            combo=tuple(combo),
            func=func,
            params=params,
        )

        alive = True

        for k, (_, filt) in enumerate(filters):
            t0 = time.perf_counter()
            discard = filt(ctx)
            filter_times[k] += time.perf_counter() - t0

            if discard:
                alive = False
                break

            after_counts[k] += 1

        if not alive:
            continue

        sim_calls += 1

        t0 = time.perf_counter()
        if external_verifier is not None:
            ok = external_verifier(ctx)
        else:
            ok = simplified_exact_verify(ctx)
        sim_time += time.perf_counter() - t0

        if ok:
            valid_count += 1
            if keep_layouts:
                valid_layouts.append(tuple(combo))

    total_wall = time.perf_counter() - t_wall0

    return RunResult(
        benchmark=benchmark,
        mode=mode,
        initial_layouts=initial,
        processed_layouts=processed,
        filter_names=filter_names,
        after_filter_counts=after_counts,
        filter_times=filter_times,
        sim_calls=sim_calls,
        valid_count=valid_count,
        valid_layouts=valid_layouts,
        sim_time=sim_time,
        total_wall_time=total_wall,
    )


def compare_results(qc3: RunResult, qc12: RunResult) -> Dict[str, float]:
    """
    Returns key comparison metrics.
    """
    return {
        "runtime_speedup_qc3_over_qc12":
            qc3.total_wall_time / qc12.total_wall_time
            if qc12.total_wall_time > 0 else float("inf"),

        "simulation_call_reduction":
            qc3.sim_calls / qc12.sim_calls
            if qc12.sim_calls > 0 else float("inf"),

        "pre_sim_reduction_qc3":
            qc3.reduction_before_sim(),

        "pre_sim_reduction_qc12":
            qc12.reduction_before_sim(),

        "valid_count_qc3":
            qc3.valid_count,

        "valid_count_qc12":
            qc12.valid_count,
    }


def write_ablation_csv(result: RunResult, path: str) -> None:
    """
    Writes one-row ablation table similar to the paper.
    """
    headers = (
        ["Benchmark", "Mode", "|Ld|"]
        + [f"After {name}" for name in result.filter_names]
        + ["SimulationCalls", "|L*|", "TotalTime[s]"]
    )

    row = (
        [result.benchmark, result.mode, result.initial_layouts]
        + result.after_filter_counts
        + [result.sim_calls, result.valid_count, result.total_wall_time]
    )

    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerow(row)


# ============================================================
# Helpers for canvas generation and symmetry
# ============================================================

def make_rect_grid(
    xmin: float,
    xmax: float,
    ymin: float,
    ymax: float,
    spacing: float,
) -> List[Point]:
    pts = []
    nx = int(round((xmax - xmin) / spacing))
    ny = int(round((ymax - ymin) / spacing))

    for ix in range(nx + 1):
        x = xmin + ix * spacing
        for iy in range(ny + 1):
            y = ymin + iy * spacing
            pts.append((round(x, 12), round(y, 12)))

    return pts


def infer_canvas_symmetries(
    canvas_pool: Sequence[Point],
    tol_digits: int = 9,
) -> List[Tuple[int, ...]]:
    """
    Infers simple symmetries that map the canvas point set onto itself:
        identity, mirror-x, mirror-y, rot-180,
        and if possible rot-90/270 and diagonal mirrors.

    Use with caution: F2 is valid only if skeleton and function are also
    symmetric under these operations.
    """
    pts = list(canvas_pool)
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]

    cx = 0.5 * (min(xs) + max(xs))
    cy = 0.5 * (min(ys) + max(ys))

    def key(p: Point):
        return (round(p[0], tol_digits), round(p[1], tol_digits))

    idx = {key(p): i for i, p in enumerate(pts)}

    transforms = [
        lambda x, y: (x, y),                       # identity
        lambda x, y: (2 * cx - x, y),             # mirror x
        lambda x, y: (x, 2 * cy - y),             # mirror y
        lambda x, y: (2 * cx - x, 2 * cy - y),    # rot 180
        lambda x, y: (cx - (y - cy), cy + (x - cx)),  # rot 90
        lambda x, y: (cx + (y - cy), cy - (x - cx)),  # rot 270
        lambda x, y: (cx + (y - cy), cy + (x - cx)),  # diagonal
        lambda x, y: (cx - (y - cy), cy - (x - cx)),  # anti-diagonal
    ]

    perms = []
    seen = set()

    for tr in transforms:
        perm = []
        ok = True
        for x, y in pts:
            q = key(tr(x, y))
            if q not in idx:
                ok = False
                break
            perm.append(idx[q])

        if ok:
            tup = tuple(perm)
            if tup not in seen:
                perms.append(tup)
                seen.add(tup)

    return perms


# ============================================================
# Small demo problem
# ============================================================

def make_demo_and3_problem():
    """
    A small illustrative AND3 standard-cell problem.
    This is not the exact benchmark geometry from the paper.
    Replace positions with your real skeleton/canvas to reproduce tables.
    """
    positions: List[Point] = []
    input_pins: List[List[BDLPair]] = []

    # Three input BDL pairs
    for y in (-2.0, 0.0, 2.0):
        i0 = len(positions)
        positions.append((-4.0, y))
        i1 = len(positions)
        positions.append((-3.4, y))
        input_pins.append([BDLPair(bit0_neg=i0, bit1_neg=i1)])

    # One output BDL pair
    o0 = len(positions)
    positions.append((4.0, 0.0))
    o1 = len(positions)
    positions.append((4.6, 0.0))
    output_pins = [[BDLPair(bit0_neg=o0, bit1_neg=o1)]]

    # Canvas grid
    canvas = make_rect_grid(-1.2, 1.2, -1.2, 1.2, 0.6)

    skel = Skeleton(
        positions=positions,
        input_pins=input_pins,
        output_pins=output_pins,
        protected_points=[],
        protected_segments=[],
        symmetries=[],  # set below if safe
        input_terminal_indices=[0, 1, 2, 3, 4, 5],
        output_terminal_indices=[6, 7],
    )

    # Use symmetry only if valid for your skeleton/function.
    # For this demo, keep disabled.
    # skel.symmetries = infer_canvas_symmetries(canvas)

    f_and3 = BoolFunction.from_hex(3, 0x80)

    params = PhysParams(
        mu_minus=-0.31,
        mu_plus=-0.80,
        lambda_tf=5.0,
        eps_r=5.6,
        d_min=0.45,
        wire_forbidden_radius=0.8,
        charge_min_frac=0.0,
        charge_max_frac=1.0,
        include_input_flips_in_instability=True,
    )

    d = 3

    return f_and3, skel, canvas, d, params


if __name__ == "__main__":
    f, skel, canvas, d, params = make_demo_and3_problem()

    # For quick test, limit layouts. Remove max_layouts for full exhaustive run.
    res12 = run_pipeline(
        benchmark="AND3_demo",
        func=f,
        skeleton=skel,
        canvas_pool=canvas,
        d=d,
        params=params,
        mode="qc12",
        keep_layouts=False,
        max_layouts=5000,
    )

    res3 = run_pipeline(
        benchmark="AND3_demo",
        func=f,
        skeleton=skel,
        canvas_pool=canvas,
        d=d,
        params=params,
        mode="qc3",
        keep_layouts=False,
        max_layouts=5000,
    )

    res12.print_summary()
    res3.print_summary()

    print("\nComparison:")
    comp = compare_results(res3, res12)
    for k, v in comp.items():
        print(f"{k}: {v}")

    write_ablation_csv(res12, "ablation_qc12_demo.csv")
    write_ablation_csv(res3, "ablation_qc3_demo.csv")