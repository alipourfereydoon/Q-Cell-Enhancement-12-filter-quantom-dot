from __future__ import annotations
from typing import List, Tuple
from .data_structures import Skeleton, Canvas

_A1X = 0.384   
_A2Y = 0.768   
_B1Y = 0.225   


def _latt(n: int, m: int) -> Tuple[float, float]:
    return (n * _A1X, m * _A2Y + _B1Y)

def paper_like_skeleton_3in_1out_25(bdl_spacing: float = 0.76) -> Skeleton:
    input_pins = [
        [_latt(-15, 9), _latt(-15, 10)],   
        [_latt(-15,0), _latt(-15,  1)],   
        [_latt(-15,-10), _latt(-15, -9)],    
    ]
    output_pins = [
        [_latt(10, 0), _latt(10, 1)],        
    ]
    wire_coords = [
        _latt(-10, 9), _latt(-5,  6), _latt(0,  3),
        _latt(-10,  0), _latt(-5, 0), _latt(0,  0),
        _latt(-10, -9), _latt(-5, -6), _latt(0, -3),
        _latt(5, 0),
    ]
    return Skeleton(
        input_pins_coords=input_pins,
        output_pins_coords=output_pins,
        wire_coords=wire_coords,
    )


def paper_like_canvas_143() -> Canvas:
    n_vals = [-13, -11, -6, -3, -1, 3, 6, 8, 11, 14, 17]
    m_vals = [-12, -9, -6, -4, -3, -1, 0, 1, 3, 4, 6, 9, 12]

    positions = [_latt(n, m) for n in n_vals for m in m_vals]
    assert len(positions) == 143, f"Expected 143, got {len(positions)}"
    return Canvas(positions)