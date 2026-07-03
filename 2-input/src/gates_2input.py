from __future__ import annotations
from typing import Tuple, Dict, List
from .data_structures import BooleanFunction


class HexTruthTable:
    def __init__(self, num_inputs: int, hex_value: int):
        self.num_inputs = int(num_inputs)
        self.hex_value = int(hex_value)

    def __call__(self, x: Tuple[int, ...]) -> int:
        idx = 0
        for bit in x:
            idx = (idx << 1) | int(bit)
        return int((self.hex_value >> idx) & 1)


class MultiOutputHexTruthTable:
    def __init__(self, num_inputs: int, hex_values: List[int]):
        self.num_inputs = int(num_inputs)
        self.hex_values = [int(h) for h in hex_values]
        self.num_outputs = len(hex_values)

    def __call__(self, x: Tuple[int, ...]) -> Tuple[int, ...]:
        idx = 0
        for bit in x:
            idx = (idx << 1) | int(bit)
        return tuple(int((h >> idx) & 1) for h in self.hex_values)


GATE_HEX_2IN_1OUT: Dict[str, int] = {
    "AND": 0x8,
    "NAND": 0x7,
    "OR":0xE,
    "NOR":  0x1,
    "XOR": 0x6,
    "XNOR": 0x9,
    "LT": 0x2,
    "GT":  0x4,
    "LE":0xB,
    "GE":   0xD,
}

GATE_HEX_2IN_2OUT: Dict[str, List[int]] = {
    "DOUBLE_WIRE": [0xC, 0xA],
    "CX":[0xA, 0xC],
    "HA":  [0x6, 0x8],
}

GATE_HEX_1IN_1OUT: Dict[str, int] = {
    "WIRE":0x2,
    "INV":  0x1,
}


def normalize_gate_name(name: str) -> str:
    return str(name).strip().upper().replace("-", "_").replace(" ", "_")


def gate_category(name: str) -> str:
    name = normalize_gate_name(name)
    if name in GATE_HEX_2IN_1OUT:
        return "2in_1out"
    if name in GATE_HEX_2IN_2OUT:
        return "2in_2out"
    if name in GATE_HEX_1IN_1OUT:
        return "1in_1out"
    raise ValueError(f"Unknown gate '{name}'.")


def get_2input_gate(name: str) -> BooleanFunction:
    name = normalize_gate_name(name)
    if name in GATE_HEX_2IN_1OUT:
        return BooleanFunction(
            name=name, num_inputs=2,
            func=HexTruthTable(2, GATE_HEX_2IN_1OUT[name]),
            num_outputs=1,
        )
    if name in GATE_HEX_2IN_2OUT:
        hex_values = GATE_HEX_2IN_2OUT[name]
        return BooleanFunction(
            name=name, num_inputs=2,
            func=MultiOutputHexTruthTable(2, hex_values),
            num_outputs=len(hex_values),
        )
    if name in GATE_HEX_1IN_1OUT:
        return BooleanFunction(
            name=name, num_inputs=1,
            func=HexTruthTable(1, GATE_HEX_1IN_1OUT[name]),
            num_outputs=1,
        )
    available = (list(GATE_HEX_2IN_1OUT.keys())
                 + list(GATE_HEX_2IN_2OUT.keys())
                 + list(GATE_HEX_1IN_1OUT.keys()))
    raise ValueError(f"Unknown gate '{name}'. Available: {available}")


def get_all_2input_gate_names() -> List[str]:
    return (list(GATE_HEX_2IN_1OUT.keys())
            + list(GATE_HEX_2IN_2OUT.keys())
            + list(GATE_HEX_1IN_1OUT.keys()))