
from __future__ import annotations
from typing import List, Tuple
import numpy as np

from .data_structures import Skeleton

def skeleton_2in_1out(bdl_spacing:  float = 0.76) -> Skeleton:
    s = float(bdl_spacing)

    return Skeleton(
        input_pins_coords=[
            [(-5.26, 2.50), (-5.26 + s, 2.50)],
            [(-5.26, -2.50), (-5.26 + s, -2.50)],
        ],
        output_pins_coords=[
            [(4.50, 0.00), (4.50 + s,0.00)],
        ],
        wire_coords=[],
    )


def skeleton_3in_1out(bdl_spacing: float = 0.76) -> Skeleton:
    s = float(bdl_spacing)

    return Skeleton(
        input_pins_coords=[
            [(-6.26, 3.50), (-6.26 + s,3.50)],
            [(-6.26, 0.00), (-6.26 + s, 0.00)],
            [(-6.26, -3.50), (-6.26 + s, -3.50)],
        ],
        output_pins_coords=[
            [(5.50, 0.00), (5.50 + s, 0.00)],
        ],
        wire_coords=[],
    )


def grid_canvas(
    x_range: Tuple[float, float],
    y_range: Tuple[float, float],
    step: float,
) -> List[Tuple[float, float]]:
    positions: List[Tuple[float, float]] = []

    x0, x1 = x_range
    y0, y1 = y_range

    for x in np.arange(x0, x1 + 0.5 * step, step):
        for y in np.arange(y0, y1 + 0.5 * step, step):
            positions.append((float(x), float(y)))

    return positions