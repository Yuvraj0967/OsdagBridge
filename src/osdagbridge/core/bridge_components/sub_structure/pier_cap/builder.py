"""
Parametric 3D CAD builder for a hammerhead (trapezoidal) pier cap.

The cap cross-section is defined in the X-Z plane and extruded along Y (the
deck-width direction), which is how a hammerhead cap is normally detailed:

    top width    = 3000 mm
    bottom width = 1200 mm
    depth        = 600 mm
    length       = supplied by the assembly (normally the deck width)

Local frame: origin at the centre of the bottom face, +Z up, +Y along the cap
length.  The extrusion runs from ``-length/2`` to ``+length/2``.
"""

import math

from OCC.Core.BRepBuilderAPI import (
    BRepBuilderAPI_MakeFace,
    BRepBuilderAPI_MakePolygon,
)
from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakePrism
from OCC.Core.gp import gp_Pnt, gp_Vec

from osdagbridge.core.bridge_components.reinforcement import (
    bar_group,
    bars_to_compound,
    line_bar,
)

# Defaults (mm)
PIER_CAP_TOP_WIDTH = 3000.0
PIER_CAP_BOTTOM_WIDTH = 1200.0
PIER_CAP_DEPTH = 600.0
REBAR_MAIN_DIAMETER = 16.0
REBAR_SPACING_LONGITUDINAL = 150.0
REBAR_TRANSVERSE_DIAMETER = 8.0
REBAR_SPACING_TRANSVERSE = 200.0
REBAR_COVER = 40.0


def _tapered_section(bottom_width, top_width, depth):
    """Closed polygon in the X-Z plane at y = -length/2."""
    half_b = bottom_width / 2.0
    half_t = top_width / 2.0
    poly = BRepBuilderAPI_MakePolygon()
    poly.Add(gp_Pnt(-half_b, 0.0, 0.0))
    poly.Add(gp_Pnt(half_b, 0.0, 0.0))
    poly.Add(gp_Pnt(half_t, 0.0, depth))
    poly.Add(gp_Pnt(-half_t, 0.0, depth))
    poly.Close()
    return BRepBuilderAPI_MakeFace(poly.Wire()).Face()


def _width_at(z, bottom_width, top_width, depth):
    return bottom_width + (top_width - bottom_width) * (z / depth)


def _main_bars(length, bottom_width, top_width, depth, cover, main_d, spacing):
    """
    Longitudinal bars run along Y and are spaced across X at a constant Z.
    Two layers are provided (top and bottom); the tapered section naturally
    allows fewer bars in the bottom layer.
    """
    bars = []
    y1 = -length / 2.0 + cover + main_d / 2.0
    y2 = length / 2.0 - cover - main_d / 2.0
    for z in (cover + main_d / 2.0, depth - cover - main_d / 2.0):
        usable_half = _width_at(z, bottom_width, top_width, depth) / 2.0 - cover - main_d / 2.0
        if usable_half <= 0:
            continue
        n = int(math.floor((2.0 * usable_half) / spacing)) + 1
        if n == 1:
            xs = [0.0]
        else:
            xs = [-usable_half + i * (2.0 * usable_half) / (n - 1) for i in range(n)]
        for x in xs:
            bars.append(line_bar((x, y1, z), (x, y2, z), main_d))
    return bars


def _tie_bars(length, bottom_width, top_width, depth, cover, tie_d, spacing):
    """
    Trapezoidal closed stirrups at the requested spacing along the cap.
    Each stirrup is four straight bars following the tapered outline.
    """
    bars = []
    y = -length / 2.0 + cover + tie_d / 2.0
    while y <= length / 2.0 - cover - tie_d / 2.0 + 1e-6:
        xb = bottom_width / 2.0 - cover - tie_d / 2.0
        xt = top_width / 2.0 - cover - tie_d / 2.0
        zb = cover + tie_d / 2.0
        zt = depth - cover - tie_d / 2.0
        corners = [
            (-xb, y, zb),
            (xb, y, zb),
            (xt, y, zt),
            (-xt, y, zt),
        ]
        for i in range(4):
            bars.append(line_bar(corners[i], corners[(i + 1) % 4], tie_d))
        y += spacing
    return bars


def _pier_cap_concrete(bottom_width, top_width, depth, length):
    section = _tapered_section(bottom_width, top_width, depth)
    prism = BRepPrimAPI_MakePrism(
        section, gp_Vec(0.0, float(length), 0.0)
    ).Shape()
    # The section sits at y=0; move it so the cap is centred on its origin.
    from osdagbridge.core.bridge_components.reinforcement import translate
    return translate(prism, 0.0, -length / 2.0, 0.0)


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
    if length <= 2.0 * cover:
        raise ValueError("Pier cap length must be greater than twice the cover")
    if not (top_width > 0 and bottom_width > 0 and depth > 2.0 * cover):
        raise ValueError("Invalid pier cap dimensions")
    if top_width < bottom_width:
        raise ValueError("Hammerhead cap top width must not be smaller than bottom width")

    concrete = _pier_cap_concrete(bottom_width, top_width, depth, length)
    main_bars = _main_bars(length, bottom_width, top_width, depth, cover,
                           main_rebar_diameter, main_spacing)
    tie_bars = _tie_bars(length, bottom_width, top_width, depth, cover,
                         tie_rebar_diameter, tie_spacing)
    bars = main_bars + tie_bars
    rebar = bars_to_compound(bars)

    bar_groups = [
        bar_group(f"{name} - Main Bars", main_bars, "MAIN",
                  main_rebar_diameter, component=name),
        bar_group(f"{name} - Trapezoidal Ties", tie_bars, "SHEAR",
                  tie_rebar_diameter, component=name),
    ]

    return {
        "name": name,
        "kind": "pier_cap",
        "concrete": concrete,
        "rebar": rebar,
        "bars": bars,
        "bar_groups": bar_groups,
        "meta": {
            "kind": "trapezoid",
            "ifc_class": "IfcBeam",
            "name": name,
            "origin": [0.0, 0.0, 0.0],
            "bottom_width": float(bottom_width),
            "top_width": float(top_width),
            "depth": float(depth),
            "length": float(length),
            "cover": float(cover),
            "concrete_grade": "M30",
            "main_bar_diameter": float(main_rebar_diameter),
            "main_spacing": float(main_spacing),
            "tie_bar_diameter": float(tie_rebar_diameter),
            "tie_spacing": float(tie_spacing),
        },
    }
