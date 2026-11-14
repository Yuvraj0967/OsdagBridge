"""
Parametric 3D CAD builder for a bearing pedestal.

Pedestals are the short concrete blocks on top of the pier cap that carry the
bearings.  The screening brief does not give pedestal dimensions, so the
defaults below are assumed.

Local frame: origin at the centre of the bottom face, +Z up; ``length`` runs
along X and ``width`` along Y.
"""

from osdagbridge.core.bridge_components.reinforcement import (
    REBAR_COVER,
    REBAR_MAIN_DIAMETER,
    REBAR_SPACING_TRANSVERSE,
    REBAR_TRANSVERSE_DIAMETER,
    bar_group,
    bars_to_compound,
    line_bar,
    make_box,
    rectangular_tie,
    stations,
)

# Assumed defaults (mm)
PEDESTAL_LENGTH = 600.0
PEDESTAL_WIDTH = 400.0
PEDESTAL_HEIGHT = 150.0


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
    """Build a rectangular pedestal with four corner bars and closed ties."""
    if min(length, width, height) <= 2.0 * cover:
        raise ValueError("Pedestal dimensions are too small for the specified cover")

    concrete = make_box(length, width, height,
                        origin=(-length / 2.0, -width / 2.0, 0.0))

    # One vertical bar in each corner, inside the ties.
    corner = cover + tie_rebar_diameter + main_rebar_diameter / 2.0
    x = length / 2.0 - corner
    y = width / 2.0 - corner
    main_bars = [
        line_bar((sx * x, sy * y, cover), (sx * x, sy * y, height - cover),
                 main_rebar_diameter)
        for sx in (-1.0, 1.0)
        for sy in (-1.0, 1.0)
    ]

    inset = cover + tie_rebar_diameter / 2.0
    tie_bars = []
    for z in stations(inset, height - inset, tie_spacing):
        tie_bars.extend(rectangular_tie(
            (0.0, 0.0), z, length - 2.0 * inset, width - 2.0 * inset,
            tie_rebar_diameter,
        ))

    bars = main_bars + tie_bars
    return {
        "name": name,
        "concrete": concrete,
        "rebar": bars_to_compound(bars),
        "bars": bars,
        "bar_groups": [
            bar_group(f"{name} - Main Bars", main_bars, "MAIN", component=name),
            bar_group(f"{name} - Ties", tie_bars, "SHEAR", component=name),
        ],
        "meta": {
            "kind": "box",
            # IFC4 has no bearing-plinth entity; a proxy keeps the element
            # honest instead of mislabelling it as a footing or column.
            "ifc_class": "IfcBuildingElementProxy",
            "name": name,
            "length": float(length),
            "width": float(width),
            "height": float(height),
            "cover": float(cover),
            "main_bar_diameter": float(main_rebar_diameter),
            "tie_bar_diameter": float(tie_rebar_diameter),
            "tie_spacing": float(tie_spacing),
        },
    }
