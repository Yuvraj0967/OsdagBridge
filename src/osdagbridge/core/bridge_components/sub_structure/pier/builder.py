"""
Parametric 3D CAD builder for a circular reinforced-concrete pier.

Local frame: origin at the centre of the bottom face, +Z up.  The assembly
places the pier between the pile cap and the pier cap.
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
PIER_DIAMETER = 800.0
PIER_HEIGHT = 3000.0
MAIN_BAR_COUNT = 12


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

    Returns a dict with the ``concrete`` solid, the ``rebar`` compound, the
    ``bars`` / ``bar_groups`` descriptors and the ``meta`` record consumed by
    the assembly and the IFC writer.
    """
    if diameter <= 0 or height <= 2.0 * cover:
        raise ValueError("Pier diameter and height must be positive and exceed the cover")

    concrete = BRepPrimAPI_MakeCylinder(diameter / 2.0, height).Shape()
    main_bars, tie_bars = circular_cage(
        diameter, height, cover, main_rebar_diameter,
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
            "ifc_class": "IfcColumn",
            "name": name,
            "diameter": float(diameter),
            "height": float(height),
            "cover": float(cover),
            "main_bar_count": int(main_bar_count),
            "main_bar_diameter": float(main_rebar_diameter),
            "tie_bar_diameter": float(tie_rebar_diameter),
            "tie_spacing": float(tie_spacing),
        },
    }
