# src/paper_benchmarks.py

from __future__ import annotations

from typing import List, Tuple

from .data_structures import Skeleton, Canvas


def paper_like_skeleton_3in_1out_25(bdl_spacing: float = 0.76) -> Skeleton:
    s = float(bdl_spacing)

    input_pins = [
        [(-25.00, 12.00), (-25.00 + s, 12.00)],
        [(-25.00, 0.00), (-25.00 + s, 0.00)],
        [(-25.00, -12.00), (-25.00 + s, -12.00)],
    ]

    output_pins = [
        [(10.00, 0.00), (10.00 + s, 0.00)],
    ]

    wire_coords = [
        (-20.0, 12.0),
        (-17.0, 10.0),
        (-14.0, 8.0),
        (-11.0, 6.0),
        (-8.0, 4.0),

        (-20.0, 0.0),
        (-17.0, 0.0),
        (-14.0, 0.0),
        (-11.0, 0.0),
        (-8.0, 0.0),

        (-20.0, -12.0),
        (-17.0, -10.0),
        (-14.0, -8.0),
        (-11.0, -6.0),
        (-8.0, -4.0),

        (-4.0, 0.0),
        (0.0, 0.0),
    ]

    return Skeleton(
        input_pins_coords=input_pins,
        output_pins_coords=output_pins,
        wire_coords=wire_coords,
    )


def paper_like_canvas_143() -> Canvas:
    positions: List[Tuple[float, float]] = []

    xs = [-8.5 + 3.0 * i for i in range(13)]
    ys = [-15.0 + 3.0 * j for j in range(11)]

    for x in xs:
        for y in ys:
            positions.append((float(x), float(y)))

    assert len(positions) == 143

    return Canvas(positions)