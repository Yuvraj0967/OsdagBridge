"""
Parametric 3D CAD builder for a bored circular pile.

Local frame: origin at the centre of the pile toe, +Z up, so the pile shares
the bottom-up convention of the other builders.  The assembly places the toe
at ``pile_cap_bottom - pile_length``.
"""

from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeCylinder

from osdagbridge.core.bridge_components.reinforcement import (
    REBAR_COVER,
    REBAR_MAIN_DIAMETER,
    REBAR_SPACING_TRANSVERSE,
    REBAR_TRANSVERSE_DIAMETER,
    bar_group,
    bars_to_compound,
    circular_cage,
)

# Defaults from the screening brief (mm)
PILE_DIAMETER = 400.0
PILE_LENGTH = 5000.0
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
        raise ValueError("Pile diameter and length must be positive and exceed the cover")

    concrete = BRepPrimAPI_MakeCylinder(diameter / 2.0, length).Shape()
    main_bars, tie_bars = circular_cage(
        diameter, length, cover, main_rebar_diameter,
        tie_rebar_diameter, tie_spacing, main_bar_count,
    )
    bars = main_bars + tie_bars

    return {
        "name": name,
        "concrete": concrete,
        "rebar": bars_to_compound(bars),
        "bars": bars,
        "bar_groups": [
            bar_group(f"{name} - Main Bars", main_bars, "MAIN", component=name),
            bar_group(f"{name} - Ties", tie_bars, "RING", component=name),
        ],
        "meta": {
            "kind": "cylinder",
            "ifc_class": "IfcPile",
            "predefined_type": "BORED",
            "name": name,
            "diameter": float(diameter),
            "height": float(length),
            "cover": float(cover),
            "main_bar_count": int(main_bar_count),
            "main_bar_diameter": float(main_rebar_diameter),
            "tie_bar_diameter": float(tie_rebar_diameter),
            "tie_spacing": float(tie_spacing),
        },
    }
