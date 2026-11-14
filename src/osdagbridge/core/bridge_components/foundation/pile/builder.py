"""
Parametric 3D CAD builder for a bored circular pile.

Default geometry (mm) from the substructure screening brief:

    pile_diameter = 400
    pile_length   = 5000

Local frame: origin at the centre of the pile cut-off (top) face is *not* used;
the builder models the pile from its bottom face upwards so that the same
convention is shared with the pier.  Assembly code places the bottom at
``pile_top_z - pile_length``.
"""

import math

from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeCylinder

from osdagbridge.core.bridge_components.reinforcement import (
    bar_group,
    bars_to_compound,
    line_bar,
    ring_bar,
)

PILE_DIAMETER = 400.0
PILE_LENGTH = 5000.0
REBAR_MAIN_DIAMETER = 16.0
REBAR_TRANSVERSE_DIAMETER = 8.0
REBAR_SPACING_TRANSVERSE = 200.0
REBAR_COVER = 40.0
MAIN_BAR_COUNT = 8


def build_pile(
    *,
    diameter=PILE_DIAMETER,
    length=PILE_LENGTH,
    cover=REBAR_COVER,
    main_rebar_diameter=REBAR_MAIN_DIAMETER,
    tie_rebar_diameter=REBAR_TRANSVERSE_DIAMETER,
    tie_spacing=REBAR_SPACING_TRANSVERSE,
    main_bar_count=MAIN_BAR_COUNT,
    name="Pile",
):
    """Build a circular pile and its reinforcement cage."""
    if diameter <= 0 or length <= 2.0 * cover:
        raise ValueError("Invalid pile dimensions")
    if cover * 2.0 >= diameter:
        raise ValueError("Rebar cover is too large for the pile diameter")

    concrete = BRepPrimAPI_MakeCylinder(diameter / 2.0, length).Shape()

    main_radius = diameter / 2.0 - cover - tie_rebar_diameter - main_rebar_diameter / 2.0
    z1 = cover + main_rebar_diameter / 2.0
    z2 = length - cover - main_rebar_diameter / 2.0
    main_bars = []
    for i in range(main_bar_count):
        angle = 2.0 * math.pi * i / main_bar_count
        x = main_radius * math.cos(angle)
        y = main_radius * math.sin(angle)
        main_bars.append(line_bar((x, y, z1), (x, y, z2), main_rebar_diameter))

    tie_radius = diameter / 2.0 - cover - tie_rebar_diameter / 2.0
    tie_bars = []
    z = cover + tie_rebar_diameter / 2.0
    while z <= length - cover - tie_rebar_diameter / 2.0 + 1e-6:
        tie_bars.append(ring_bar((0.0, 0.0, z), tie_radius, tie_rebar_diameter))
        z += tie_spacing

    bars = main_bars + tie_bars
    bar_groups = [
        bar_group(f"{name} - Main Bars", main_bars, "MAIN",
                  main_rebar_diameter, component=name),
        bar_group(f"{name} - Ties", tie_bars, "RING",
                  tie_rebar_diameter, component=name),
    ]

    return {
        "name": name,
        "kind": "pile",
        "concrete": concrete,
        "rebar": bars_to_compound(bars),
        "bars": bars,
        "bar_groups": bar_groups,
        "meta": {
            "kind": "cylinder",
            "ifc_class": "IfcPile",
            "name": name,
            "origin": [0.0, 0.0, 0.0],
            "diameter": float(diameter),
            "height": float(length),
            "radius": float(diameter) / 2.0,
            "pile_type": "BORED",
            "cover": float(cover),
            "concrete_grade": "M30",
            "main_bar_count": int(main_bar_count),
            "main_bar_diameter": float(main_rebar_diameter),
            "tie_bar_diameter": float(tie_rebar_diameter),
            "tie_spacing": float(tie_spacing),
        },
    }
