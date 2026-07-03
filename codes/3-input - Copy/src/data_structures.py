from __future__ import annotations
from itertools import product
from typing import Callable, Iterable, List, Optional, Sequence, Tuple, Dict, Any
import numpy as np


def _and2_func(x: Tuple[int, int]) -> int:
    return int(x[0] & x[1])

def _or2_func(x: Tuple[int, int]) -> int:
    return int(x[0] | x[1])

def _xor2_func(x: Tuple[int, int]) -> int:
    return int(x[0] ^ x[1])

def _const0_2_func(x: Tuple[int, int]) -> int:
    return 0

def _const1_2_func(x: Tuple[int, int]) -> int:
    return 1

def _and3_func(x: Tuple[int, int, int]) -> int:
    return int(x[0] & x[1] & x[2])

def _xor3_func(x: Tuple[int, int, int]) -> int:
    return int(x[0] ^ x[1] ^ x[2])


def _maj3_func(x: Tuple[int, int, int]) -> int:
    return int((x[0] + x[1] + x[2]) >= 2)

def as_3d_array(p: Sequence[float]) -> np.ndarray:
    if len(p) == 2:
        return np.array([float(p[0]), float(p[1]), 0.0], dtype=float)

    if len(p) >= 3:
        return np.array([float(p[0]),float(p[1]), float(p[2])], dtype=float)

    raise ValueError("Coordinate must have length 2 or 3.")


def coord_key(
    p: Sequence[float] | np.ndarray,
    ndigits: int = 9,
) -> Tuple[float, float, float]:
    a = np.asarray(p, dtype=float)

    return (
        round(float(a[0]), ndigits),
        round(float(a[1]),ndigits),
        round(float(a[2]), ndigits),
    )


class SiDB:
    def __init__(self, x: float, y: float, z: float = 0.0):
        self.coords = np.array([float(x), float(y), float(z)], dtype=float)


class Skeleton:
    class Pin:
        def __init__(self, index: int, sidbs: List[SiDB]):
            if len(sidbs) != 2:
                raise ValueError("Each BDL pin must contain exactly two SiDB coordinates.")

            self.pin_index = index
            self.sidbs = sidbs
            self.pos_a =sidbs[0].coords
            self.pos_b = sidbs[1].coords

        def charges_for_bit(self, bit: int) -> List[Tuple[np.ndarray, int]]:
            bit = int(bit)

            if bit == 0:
                return [(self.pos_a, -1), (self.pos_b, 0)]

            if bit == 1:
                return [(self.pos_a, 0), (self.pos_b, -1)]

            raise ValueError("BDL bit must be 0 or 1.")

        def positions(self) -> List[np.ndarray]:
            return [self.pos_a, self.pos_b]

    def __init__(
        self,
        input_pins_coords: List[List[Tuple[float, ...]]],
        output_pins_coords: List[List[Tuple[float, ...]]],
        wire_coords: Optional[List[Tuple[float, ...]]] = None,
    ):
        wire_coords = wire_coords or []

        self.n_in = len(input_pins_coords)
        self.n_out = len(output_pins_coords)

        self.input_pins = [
            self._create_pin(i, coords)
            for i, coords in enumerate(input_pins_coords)
        ]

        self.output_pins = [
            self._create_pin(i, coords)
            for i, coords in enumerate(output_pins_coords)
        ]

        self.wire_sidbs = []

        for p in wire_coords:
            a = as_3d_array(p)
            self.wire_sidbs.append(SiDB(a[0], a[1], a[2]))

        self.all_sidbs = (
            [sdb for pin in self.input_pins for sdb in pin.sidbs]
            + [sdb for pin in self.output_pins for sdb in pin.sidbs]
            + self.wire_sidbs
        )

    def _create_pin(
        self,
        index: int,
        coords_list: List[Tuple[float, ...]],
    ) -> Pin:
        sidbs = []

        for p in coords_list:
            a = as_3d_array(p)
            sidbs.append(SiDB(a[0], a[1], a[2]))

        return self.Pin(index, sidbs)

    def input_charge_config(
        self,
        x: Tuple[int, ...],
    ) -> List[Tuple[np.ndarray, int]]:
        if len(x) != self.n_in:
            raise ValueError(f"Expected {self.n_in} input bits, got {len(x)}.")

        config: List[Tuple[np.ndarray, int]] = []

        for i, pin in enumerate(self.input_pins):
            config.extend(pin.charges_for_bit(int(x[i])))

        return config

    def output_charge_config(
        self,
        y: Tuple[int, ...],
    ) -> List[Tuple[np.ndarray, int]]:
        if len(y) != self.n_out:
            raise ValueError(f"Expected {self.n_out} output bits, got {len(y)}.")

        config: List[Tuple[np.ndarray, int]] = []

        for i, pin in enumerate(self.output_pins):
            config.extend(pin.charges_for_bit(int(y[i])))

        return config

    def io_charge_config(
        self,
        x: Tuple[int, ...],
        y: Tuple[int, ...],
    ) -> List[Tuple[np.ndarray, int]]:
        return self.input_charge_config(x) + self.output_charge_config(y)

    def input_positions(self) -> List[np.ndarray]:
        return [p for pin in self.input_pins for p in pin.positions()]

    def output_positions(self) -> List[np.ndarray]:
        return [p for pin in self.output_pins for p in pin.positions()]

    def all_positions(self) -> List[np.ndarray]:
        return [s.coords for s in self.all_sidbs]


class Canvas:
    def __init__(self, positions: List[Tuple[float, ...]]):
        self.positions = [as_3d_array(p) for p in positions]
        self.n_pos = len(self.positions)

        self.position_to_index = {}

        for i, p in enumerate(self.positions):
            k = coord_key(p)

            if k in self.position_to_index:
                raise ValueError(f"Duplicate canvas position detected: {k}")

            self.position_to_index[k] = i

    def index_of(self, p: Sequence[float] | np.ndarray) -> Optional[int]:
        return self.position_to_index.get(coord_key(p), None)


class Layout:
    def __init__(
        self,
        skeleton: Skeleton,
        canvas_positions: Optional[List[np.ndarray]] = None,
        canvas_indices: Optional[Sequence[Optional[int]]] = None,
    ):
        self.skeleton = skeleton
        self.canvas_positions = list(canvas_positions or [])

        if canvas_indices is None:
            self.canvas_indices: Tuple[Optional[int], ...] = tuple(
                [None] * len(self.canvas_positions)
            )
        else:
            self.canvas_indices = tuple(canvas_indices)

        self.all_positions = (
            [s.coords for s in skeleton.all_sidbs]
            + self.canvas_positions
        )
        self.n_canvas = len(self.canvas_positions)
        self.cache: Dict[Any, Any] = {}

    def add_canvas_sdb(
        self,
        position: np.ndarray,
        index: Optional[int] = None,
    ) -> "Layout":
        return Layout(
            skeleton=self.skeleton,
            canvas_positions=self.canvas_positions + [np.asarray(position, dtype=float)],
            canvas_indices=self.canvas_indices + (index,),
        )

    def canvas_key(self) -> Tuple:
        if all(i is not None for i in self.canvas_indices):
            return tuple(sorted(int(i) for i in self.canvas_indices if i is not None))

        return tuple(sorted(coord_key(p) for p in self.canvas_positions))


class BooleanFunction:
    def __init__(
        self,
        name: str,
        num_inputs: int,
        func: Callable[[Tuple[int, ...]], int | Tuple[int, ...]],
        num_outputs: int = 1,
    ):
        self.name = name
        self.num_inputs = int(num_inputs)
        self.num_outputs = int(num_outputs)
        self._func = func

    def eval(self, inputs: Tuple[int, ...]) -> Tuple[int, ...]:
        if len(inputs) != self.num_inputs:
            raise ValueError(
                f"{self.name}: expected {self.num_inputs} inputs, got {len(inputs)}."
            )

        res = self._func(tuple(int(v) for v in inputs))

        if isinstance(res, (int, bool, np.integer)):
            return (int(res),)

        return tuple(int(v) for v in res)

    def all_inputs(self) -> Iterable[Tuple[int, ...]]:
        return product([0, 1], repeat=self.num_inputs)

    def all_outputs(self) -> Iterable[Tuple[int, ...]]:
        return product([0, 1], repeat=self.num_outputs)
    @classmethod
    def AND2(cls) -> "BooleanFunction":
        return cls("AND2", 2, _and2_func, 1)

    @classmethod
    def OR2(cls) -> "BooleanFunction":
        return cls("OR2", 2, _or2_func, 1)

    @classmethod
    def XOR2(cls) -> "BooleanFunction":
        return cls("XOR2", 2, _xor2_func, 1)

    @classmethod
    def CONST0_2(cls) -> "BooleanFunction":
        return cls("CONST0_2", 2, _const0_2_func, 1)

    @classmethod
    def CONST1_2(cls) -> "BooleanFunction":
        return cls("CONST1_2", 2, _const1_2_func, 1)

    @classmethod
    def AND3(cls) -> "BooleanFunction":
        return cls("AND3", 3, _and3_func, 1)

    @classmethod
    def XOR3(cls) -> "BooleanFunction":
        return cls("XOR3", 3, _xor3_func, 1)

    @classmethod
    def MAJ3(cls) -> "BooleanFunction":
        return cls("MAJ3", 3, _maj3_func, 1)