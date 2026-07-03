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


GATE_HEX_3IN: Dict[str, int] = {
    "AND3": 0x80,
    "XOR-AND": 0x28,
     "OR-AND": 0xA8,
    "ONEHOT": 0x16,
     "MAJ": 0xE8,
    "GAMBLE": 0x81,
    "DOT": 0x52,
    "ITE": 0xD8,
    "AND-XOR": 0x6A,
    "XOR3": 0x96,
}


def normalize_gate_name(name: str) -> str:
    return str(name).strip().upper()


def get_3input_gate(name: str) -> BooleanFunction:
    name = normalize_gate_name(name)

    if name not in GATE_HEX_3IN:
        raise ValueError(
            f"Unknown 3-input gate '{name}'. "
            f"Available gates: {list(GATE_HEX_3IN.keys())}"
        )

    return BooleanFunction(
        name=name,
         num_inputs=3,
        func=HexTruthTable(3, GATE_HEX_3IN[name]),
        num_outputs=1,
    )
def get_all_3input_gate_names() -> List[str]:
    return list(GATE_HEX_3IN.keys())