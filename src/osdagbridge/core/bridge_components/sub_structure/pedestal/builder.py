"""
Parametric 3D CAD builder for a bearing pedestal.

Pedestals are the short concrete blocks that sit on top of the pier cap and
carry the bridge bearings.  The screening brief does not prescribe pedestal
dimensions, so a sensible default is used (mm):

    length (X) = 600
    width  (Y) = 400
    height      = 150

Local frame: origin at the centre of the bottom face, +Z up.
"""

from osdagbridge.core.bridge_components.reinforcement import (
    bar_group,
    bars_to_compound,
    line_bar,
    make_box,
    rectangular_tie,
)

PEDESTAL_LENGTH = 600.0
PEDESTAL_WIDTH = 400.0
PEDESTAL_HEIGHT = 150.0
REBAR_MAIN_DIAMETER = 16.0
REBAR_TRANSVERSE_DIAMETER = 8.0
REBAR_SPACING_TRANSVERSE = 200.0
REBAR_COVER = 40.0


def build_pedestal(
    *,
    length=PEDESTAL_LENGTH,
    width=PEDESTAL_WIDTH,
    height=PEDESTAL_HEIGHT,
    cover=REBAR_COVER,
    main_rebar_diameter=REBAR_MAIN_DIAMETER,
    tie_rebar_diameter=REBAR_TRANSVERSE_DIAMETER,
    tie_spacing=REBAR_SPACING_TRANSVERSE,
    name="Pedestal",
):
    """Build a rectangular pedestal and its reinforcement."""
    if min(length, width, height) <= 2.0 * cover:
        raise ValueError("Pedestal dimensions are too small for the specified cover")

    concrete = make_box(length, width, height,
                        origin=(-length / 2.0, -width / 2.0, 0.0))

    # Four vertical bars, one at each corner inside the ties.
    inset_x = length / 2.0 - cover - tie_rebar_diameter - main_rebar_diameter / 2.0
    inset_y = width / 2.0 - cover - tie_rebar_diameter - main_rebar_diameter / 2.0
    z1 = cover + main_rebar_diameter / 2.0
    z2 = height - cover - main_rebar_diameter / 2.0
    main_bars = []
    for sx in (-1.0, 1.0):
        for sy in (-1.0, 1.0):
            main_bars.append(line_bar(
                (sx * inset_x, sy * inset_y, z1),
                (sx * inset_x, sy * inset_y, z2),
                main_rebar_diameter,
            ))

    # Two rectangular ties, clipped to the pedestal height.
    tie_bars = []
    tie_half_x = length / 2.0 - cover - tie_rebar_diameter / 2.0
    tie_half_y = width / 2.0 - cover - tie_rebar_diameter / 2.0
    z = cover + tie_rebar_diameter / 2.0
    while z <= height - cover - tie_rebar_diameter / 2.0 + 1e-6:
        tie_bars.extend(rectangular_tie(
            (0.0, 0.0), z,
            2.0 * tie_half_x, 2.0 * tie_half_y,
            tie_rebar_diameter,
        ))
        z += tie_spacing

    bars = main_bars + tie_bars
    bar_groups = [
        bar_group(f"{name} - Main Bars", main_bars, "MAIN",
                  main_rebar_diameter, component=name),
        bar_group(f"{name} - Ties", tie_bars, "SHEAR",
                  tie_rebar_diameter, component=name),
    ]

    return {
        "name": name,
        "kind": "pedestal",
        "concrete": concrete,
        "rebar": bars_to_compound(bars),
        "bars": bars,
        "bar_groups": bar_groups,
        "meta": {
            "kind": "box",
            "ifc_class": "IfcBuildingElementProxy",
            "name": name,
            "origin": [0.0, 0.0, 0.0],
            "length": float(length),
            "width": float(width),
            "height": float(height),
            "cover": float(cover),
            "concrete_grade": "M30",
            "main_bar_diameter": float(main_rebar_diameter),
            "tie_bar_diameter": float(tie_rebar_diameter),
            "tie_spacing": float(tie_spacing),
        },
    }
