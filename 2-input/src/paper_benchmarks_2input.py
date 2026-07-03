from __future__ import annotations
from typing import List, Tuple
from .data_structures import Skeleton, Canvas

_A1X = 0.384   
_A2Y = 0.768   
_B1Y = 0.225   

def _latt(n: int, m: int) -> Tuple[float, float]:
    return (n * _A1X, m * _A2Y + _B1Y)


def paper_like_skeleton_2in_1out() -> Skeleton:
    input_pins = [
        [_latt(-30, 6), _latt(-30, 7)],     
        [_latt(-30, -7), _latt(-30, -6)],    
    ]
    output_pins = [
        [_latt(26, 0), _latt(26, 1)],        
    ]
    wire_coords = [
        _latt(-22, 5),  _latt(-14, 3),  _latt(-6, 1),    
        _latt(-22, -6), _latt(-14, -4), _latt(-6, -2),     
        _latt(2, 0),    _latt(10, 0),   _latt(18, 0),     
    ]
    return Skeleton(input_pins_coords=input_pins,
                    output_pins_coords=output_pins,
                    wire_coords=wire_coords)


def paper_like_skeleton_2in_2out() -> Skeleton:
    input_pins = [
        [_latt(-30, 6), _latt(-30, 7)],
        [_latt(-30, -7), _latt(-30, -6)],
    ]
    output_pins = [
        [_latt(26, 4), _latt(26, 5)],       
        [_latt(26, -5), _latt(26, -4)],     
    ]
    wire_coords = [
        _latt(-22, 5), _latt(-14, 3),  _latt(-6, 1),     
        _latt(-22, -6), _latt(-14, -4), _latt(-6, -2),     
        _latt(2, 0),                                        
        _latt(10, 2), _latt(18, 4),                       
        _latt(10, -2),  _latt(18, -4),                     
    ]
    return Skeleton(input_pins_coords=input_pins,
                    output_pins_coords=output_pins,
                    wire_coords=wire_coords)



def paper_like_skeleton_1in_1out() -> Skeleton:
    input_pins = [
        [_latt(-30, 0), _latt(-30, 1)],
    ]
    output_pins = [
        [_latt(26, 0), _latt(26, 1)],
    ]
    wire_coords = [
        _latt(-22, 0), _latt(-14, 0), _latt(-6, 0),
        _latt(2, 0),   _latt(10, 0),  _latt(18, 0),
    ]
    return Skeleton(input_pins_coords=input_pins,
                    output_pins_coords=output_pins,
                    wire_coords=wire_coords)


def paper_like_canvas_2in_1out() -> Canvas:
    n_vals = [-26, -18, -10, -2, 6, 14, 22, 30, 34]
    m_vals = [-10, -8, -6, -4, -2, 0, 2, 4, 6, 8, 10]
    positions = [_latt(n, m) for n in n_vals for m in m_vals]
    assert len(positions) == 99, f"Got {len(positions)}"
    return Canvas(positions)


def paper_like_canvas_2in_2out() -> Canvas:
    n_vals = [-26, -18, -10, -2, 6, 14, 22, 30, 34, 38, 42]
    m_vals = list(range(-16, 17, 2))  # 17 values
    positions = [_latt(n, m) for n in n_vals for m in m_vals]
    assert len(positions) == 187, f"Got {len(positions)}"
    return Canvas(positions)


def paper_like_canvas_1in_1out() -> Canvas:
    n_vals = [-34, -26, -18, -10, -2, 6, 14, 22, 30, 34, 38, 42, 46]
    m_vals = list(range(-16, 17, 2))  # 17 values
    positions = [_latt(n, m) for n in n_vals for m in m_vals]
    assert len(positions) == 221, f"Got {len(positions)}"
    return Canvas(positions)