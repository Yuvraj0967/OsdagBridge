"""
Parametric 3D CAD builder for a rectangular pile cap.

Default geometry (mm) from the substructure screening brief:

    pile_cap_length = 2200 (X)
    pile_cap_width  = 1200 (Y)
    pile_cap_depth  = 600  (Z)

Local frame: origin at the centre of the bottom face, +Z up.
"""

import math

from osdagbridge.core.bridge_components.reinforcement import (
    bar_group,
    bars_to_compound,
    line_bar,
    make_box,
    rectangular_tie,
    translate,
)

PILE_CAP_LENGTH = 2200.0
PILE_CAP_WIDTH = 1200.0
PILE_CAP_DEPTH = 600.0
REBAR_MAIN_DIAMETER = 16.0
REBAR_SPACING_LONGITUDINAL = 150.0
REBAR_TRANSVERSE_DIAMETER = 8.0
REBAR_SPACING_TRANSVERSE = 200.0
REBAR_COVER = 40.0


def _even_positions(usable_half, spacing):
    if usable_half <= 0:
        return []
    n = int(math.floor((2.0 * usable_half) / spacing)) + 1
    if n <= 1:
        return [0.0]
    return [-usable_half + i * (2.0 * usable_half) / (n - 1) for i in range(n)]


def _mat_bars(length, width, depth, cover, main_d, spacing):
    """Two orthogonal mats, one near the top and one near the bottom."""
    bars = []
    usable_x = length / 2.0 - cover - main_d / 2.0
    usable_y = width / 2.0 - cover - main_d / 2.0
    xs = _even_positions(usable_x, spacing)
    ys = _even_positions(usable_y, spacing)

    for z in (cover + main_d / 2.0, depth - cover - main_d / 2.0):
        # Bars running along X, distributed across Y.
        for y in ys:
            bars.append(line_bar((-usable_x, y, z), (usable_x, y, z), main_d))
        # Bars running along Y, distributed across X.
        for x in xs:
            bars.append(line_bar((x, -usable_y, z), (x, usable_y, z), main_d))
    return bars


def _tie_bars(length, width, depth, cover, tie_d, spacing):
    bars = []
    half_x = length / 2.0 - cover - tie_d / 2.0
    half_y = width / 2.0 - cover - tie_d / 2.0
    z = cover + tie_d / 2.0
    while z <= depth - cover - tie_d / 2.0 + 1e-6:
        bars.extend(rectangular_tie(
            (0.0, 0.0), z, 2.0 * half_x, 2.0 * half_y, tie_d
        ))
        z += spacing
    return bars


def build_pile_cap(
    *,
    length=PILE_CAP_LENGTH,
    width=PILE_CAP_WIDTH,
    depth=PILE_CAP_DEPTH,
    cover=REBAR_COVER,
    main_rebar_diameter=REBAR_MAIN_DIAMETER,
    main_spacing=REBAR_SPACING_LONGITUDINAL,
    tie_rebar_diameter=REBAR_TRANSVERSE_DIAMETER,
    tie_spacing=REBAR_SPACING_TRANSVERSE,
    name="Pile Cap",
):
    """Build the pile cap concrete solid and its reinforcement."""
    if min(length, width, depth) <= 2.0 * cover:
        raise ValueError("Pile cap dimensions are too small for the specified cover")

    concrete = make_box(length, width, depth,
                        origin=(-length / 2.0, -width / 2.0, 0.0))
    main_bars = _mat_bars(length, width, depth, cover,
                          main_rebar_diameter, main_spacing)
    tie_bars = _tie_bars(length, width, depth, cover,
                         tie_rebar_diameter, tie_spacing)
    bars = main_bars + tie_bars

    bar_groups = [
        bar_group(f"{name} - Mat Bars", main_bars, "MAIN",
                  main_rebar_diameter, component=name),
        bar_group(f"{name} - Perimeter Ties", tie_bars, "SHEAR",
                  tie_rebar_diameter, component=name),
    ]

    return {
        "name": name,
        "kind": "pile_cap",
        "concrete": concrete,
        "rebar": bars_to_compound(bars),
        "bars": bars,
        "bar_groups": bar_groups,
        "meta": {
            "kind": "box",
            "ifc_class": "IfcFooting",
            "predefined_type": "PAD_FOOTING",
            "name": name,
            "origin": [0.0, 0.0, 0.0],
            "length": float(length),
            "width": float(width),
            "height": float(depth),
            "cover": float(cover),
            "concrete_grade": "M30",
            "main_bar_diameter": float(main_rebar_diameter),
            "main_spacing": float(main_spacing),
            "tie_bar_diameter": float(tie_rebar_diameter),
            "tie_spacing": float(tie_spacing),
        },
    }
