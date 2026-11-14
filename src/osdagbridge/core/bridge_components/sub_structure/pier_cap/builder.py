"""
Parametric 3D CAD builder for a tapered (hammerhead) pier cap.

The trapezoidal cross-section lies in the X-Z plane, narrow at the bottom, and
is extruded along Y, the deck-width direction.

Local frame: origin at the centre of the bottom face, +Z up, cap length from
``-length/2`` to ``+length/2`` along Y.
"""

import math

from OCC.Core.BRepBuilderAPI import (
    BRepBuilderAPI_MakeFace,
    BRepBuilderAPI_MakePolygon,
)
from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakePrism
from OCC.Core.gp import gp_Pnt, gp_Vec

from osdagbridge.core.bridge_components.reinforcement import (
    REBAR_COVER,
    REBAR_MAIN_DIAMETER,
    REBAR_SPACING_LONGITUDINAL,
    REBAR_SPACING_TRANSVERSE,
    REBAR_TRANSVERSE_DIAMETER,
    bar_group,
    bars_to_compound,
    line_bar,
    spread,
    stations,
)

# Defaults from the screening brief (mm)
PIER_CAP_TOP_WIDTH = 3000.0
PIER_CAP_BOTTOM_WIDTH = 1200.0
PIER_CAP_DEPTH = 600.0


def inset_half_width(z, inset, bottom_width, top_width, depth):
    """
    Half-width at height ``z`` of the section offset inwards by ``inset``.

    The sloping faces are offset along their normal, so a horizontal distance
    of ``inset / cos(slope)`` is removed, not just ``inset``.  Using the plain
    horizontal value would leave the bars near the top corners with less than
    the specified cover.
    """
    run = (top_width - bottom_width) / 2.0
    half_width = bottom_width / 2.0 + run * z / depth
    return half_width - inset * math.hypot(depth, run) / depth


def _concrete(bottom_width, top_width, depth, length):
    hb, ht = bottom_width / 2.0, top_width / 2.0
    y0 = -length / 2.0
    section = BRepBuilderAPI_MakePolygon()
    for x, z in ((-hb, 0.0), (hb, 0.0), (ht, depth), (-ht, depth)):
        section.Add(gp_Pnt(x, y0, z))
    section.Close()
    face = BRepBuilderAPI_MakeFace(section.Wire()).Face()
    return BRepPrimAPI_MakePrism(face, gp_Vec(0.0, float(length), 0.0)).Shape()


def _main_bars(length, bottom_width, top_width, depth, cover, main_d, tie_d, spacing):
    """
    Top and bottom layers of bars running along the cap, inside the stirrups.
    The taper leaves room for fewer bars in the bottom layer.
    """
    inset = cover + tie_d + main_d / 2.0
    y1 = -length / 2.0 + cover
    y2 = length / 2.0 - cover
    bars = []
    for z in (inset, depth - inset):
        half = inset_half_width(z, inset, bottom_width, top_width, depth)
        if half < 0.0:
            continue
        for x in spread(half, spacing):
            bars.append(line_bar((x, y1, z), (x, y2, z), main_d))
    return bars


def _tie_bars(length, bottom_width, top_width, depth, cover, tie_d, spacing):
    """Closed trapezoidal stirrups, four straight legs each, along the cap."""
    inset = cover + tie_d / 2.0
    zb, zt = inset, depth - inset
    xb = inset_half_width(zb, inset, bottom_width, top_width, depth)
    xt = inset_half_width(zt, inset, bottom_width, top_width, depth)
    bars = []
    for y in stations(-length / 2.0 + inset, length / 2.0 - inset, spacing):
        corners = [(-xb, y, zb), (xb, y, zb), (xt, y, zt), (-xt, y, zt)]
        for i in range(4):
            bars.append(line_bar(corners[i], corners[(i + 1) % 4], tie_d))
    return bars


def build_pier_cap(
    *,
    length,
    top_width=PIER_CAP_TOP_WIDTH,
    bottom_width=PIER_CAP_BOTTOM_WIDTH,
    depth=PIER_CAP_DEPTH,
    cover=REBAR_COVER,
    main_rebar_diameter=REBAR_MAIN_DIAMETER,
    main_spacing=REBAR_SPACING_LONGITUDINAL,
    tie_rebar_diameter=REBAR_TRANSVERSE_DIAMETER,
    tie_spacing=REBAR_SPACING_TRANSVERSE,
    name="Pier Cap",
):
    """Build the trapezoidal cap concrete solid and its reinforcement cage."""
    if length <= 2.0 * cover or depth <= 2.0 * cover:
        raise ValueError("Pier cap length and depth must exceed twice the cover")
    if bottom_width <= 0:
        raise ValueError("Pier cap widths must be positive")
    if top_width < bottom_width:
        raise ValueError("Pier cap top width must not be smaller than the bottom width")
    tie_inset = cover + tie_rebar_diameter / 2.0
    if inset_half_width(tie_inset, tie_inset, bottom_width, top_width, depth) <= 0.0:
        raise ValueError("Pier cap bottom width is too small for the specified cover")

    concrete = _concrete(bottom_width, top_width, depth, length)
    main_bars = _main_bars(length, bottom_width, top_width, depth, cover,
                           main_rebar_diameter, tie_rebar_diameter, main_spacing)
    tie_bars = _tie_bars(length, bottom_width, top_width, depth, cover,
                         tie_rebar_diameter, tie_spacing)
    bars = main_bars + tie_bars

    return {
        "name": name,
        "concrete": concrete,
        "rebar": bars_to_compound(bars),
        "bars": bars,
        "bar_groups": [
            bar_group(f"{name} - Main Bars", main_bars, "MAIN", component=name),
            bar_group(f"{name} - Stirrups", tie_bars, "SHEAR", component=name),
        ],
        "meta": {
            "kind": "trapezoid",
            "ifc_class": "IfcBeam",
            "name": name,
            "bottom_width": float(bottom_width),
            "top_width": float(top_width),
            "depth": float(depth),
            "length": float(length),
            "cover": float(cover),
            "main_bar_diameter": float(main_rebar_diameter),
            "main_spacing": float(main_spacing),
            "tie_bar_diameter": float(tie_rebar_diameter),
            "tie_spacing": float(tie_spacing),
        },
    }
