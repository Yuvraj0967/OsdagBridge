"""
Parametric 3D CAD builder for a circular reinforced-concrete pier.

Default geometry (millimetres) follows the OsdagBridge substructure screening
brief:

    pier_diameter = 800
    pier_height   = 3000

The pier is modelled in a local frame with its origin at the centre of the
bottom face and +Z upwards.  Assembly code is responsible for placing it under
the pier cap.
"""

import math

from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeCylinder

from osdagbridge.core.bridge_components.reinforcement import (
    bar_group,
    bars_to_compound,
    line_bar,
    ring_bar,
)

# Defaults (mm)
PIER_DIAMETER = 800.0
PIER_HEIGHT = 3000.0
REBAR_MAIN_DIAMETER = 16.0
REBAR_TRANSVERSE_DIAMETER = 8.0
REBAR_SPACING_TRANSVERSE = 200.0
REBAR_COVER = 40.0
MAIN_BAR_COUNT = 12


def _main_bars(diameter, height, cover, main_d, tie_d, count):
    bar_radius = diameter / 2.0 - cover - tie_d - main_d / 2.0
    # Cover is measured to the outside of the bar, so the bar centre-line is
    # inset by one bar radius.
    z1 = cover + main_d / 2.0
    z2 = height - cover - main_d / 2.0
    bars = []
    for i in range(count):
        angle = 2.0 * math.pi * i / count
        x = bar_radius * math.cos(angle)
        y = bar_radius * math.sin(angle)
        bars.append(line_bar((x, y, z1), (x, y, z2), main_d))
    return bars


def _tie_bars(diameter, height, cover, tie_d, spacing):
    ring_radius = diameter / 2.0 - cover - tie_d / 2.0
    bars = []
    z = cover + tie_d / 2.0
    while z <= height - cover - tie_d / 2.0 + 1e-6:
        bars.append(ring_bar((0.0, 0.0, z), ring_radius, tie_d))
        z += spacing
    return bars


def build_pier(
    *,
    diameter=PIER_DIAMETER,
    height=PIER_HEIGHT,
    cover=REBAR_COVER,
    main_rebar_diameter=REBAR_MAIN_DIAMETER,
    tie_rebar_diameter=REBAR_TRANSVERSE_DIAMETER,
    tie_spacing=REBAR_SPACING_TRANSVERSE,
    main_bar_count=MAIN_BAR_COUNT,
    name="Pier",
):
    """
    Build a circular pier with vertical main bars and circular ties.

    Returns a dictionary with the concrete ``shape``, the rebar ``rebar``
    compound, the raw ``bars`` descriptors and a ``meta`` descriptor used by the
    IFC exporter.
    """
    if diameter <= 0 or height <= 0:
        raise ValueError("Pier diameter and height must be positive")
    if cover * 2.0 >= min(diameter, height):
        raise ValueError("Rebar cover is too large for the pier dimensions")

    concrete = BRepPrimAPI_MakeCylinder(diameter / 2.0, height).Shape()

    main_bars = _main_bars(diameter, height, cover, main_rebar_diameter,
                           tie_rebar_diameter, main_bar_count)
    tie_bars = _tie_bars(diameter, height, cover, tie_rebar_diameter, tie_spacing)
    bars = main_bars + tie_bars
    rebar = bars_to_compound(bars)

    bar_groups = [
        bar_group(f"{name} - Main Bars", main_bars, "MAIN",
                  main_rebar_diameter, component=name),
        bar_group(f"{name} - Ties", tie_bars, "RING",
                  tie_rebar_diameter, component=name),
    ]

    return {
        "name": name,
        "kind": "pier",
        "concrete": concrete,
        "rebar": rebar,
        "bars": bars,
        "bar_groups": bar_groups,
        "meta": {
            "kind": "cylinder",
            "ifc_class": "IfcColumn",
            "name": name,
            "origin": [0.0, 0.0, 0.0],
            "diameter": float(diameter),
            "height": float(height),
            "radius": float(diameter) / 2.0,
            "cover": float(cover),
            "concrete_grade": "M30",
            "main_bar_count": int(main_bar_count),
            "main_bar_diameter": float(main_rebar_diameter),
            "tie_bar_diameter": float(tie_rebar_diameter),
            "tie_spacing": float(tie_spacing),
        },
    }
