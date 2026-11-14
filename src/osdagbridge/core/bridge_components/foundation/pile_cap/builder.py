"""
Parametric 3D CAD builder for a rectangular pile cap.

Local frame: origin at the centre of the bottom face, +Z up; ``length`` runs
along X and ``width`` along Y.
"""

from osdagbridge.core.bridge_components.reinforcement import (
    REBAR_COVER,
    REBAR_MAIN_DIAMETER,
    REBAR_SPACING_LONGITUDINAL,
    REBAR_SPACING_TRANSVERSE,
    REBAR_TRANSVERSE_DIAMETER,
    bar_group,
    bars_to_compound,
    line_bar,
    make_box,
    rectangular_tie,
    spread,
    stations,
)

# Defaults from the screening brief (mm)
PILE_CAP_LENGTH = 2200.0
PILE_CAP_WIDTH = 1200.0
PILE_CAP_DEPTH = 600.0


def _mat_bars(length, width, depth, cover, main_d, tie_d, spacing):
    """
    Top and bottom mats.  In each mat the X bars form the outer layer and the
    Y bars sit directly on them, so crossing bars do not occupy the same
    space.  Both layers lie inside the perimeter ties.
    """
    side = cover + tie_d + main_d / 2.0
    half_x = length / 2.0 - side
    half_y = width / 2.0 - side
    xs = spread(half_x, spacing)
    ys = spread(half_y, spacing)

    bars = []
    for z_outer, inward in ((side, 1.0), (depth - side, -1.0)):
        z_inner = z_outer + inward * main_d
        for y in ys:
            bars.append(line_bar((-half_x, y, z_outer), (half_x, y, z_outer), main_d))
        for x in xs:
            bars.append(line_bar((x, -half_y, z_inner), (x, half_y, z_inner), main_d))
    return bars


def _tie_bars(length, width, depth, cover, tie_d, spacing):
    inset = cover + tie_d / 2.0
    bars = []
    for z in stations(inset, depth - inset, spacing):
        bars.extend(rectangular_tie(
            (0.0, 0.0), z, length - 2.0 * inset, width - 2.0 * inset, tie_d
        ))
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
    main_bars = _mat_bars(length, width, depth, cover, main_rebar_diameter,
                          tie_rebar_diameter, main_spacing)
    tie_bars = _tie_bars(length, width, depth, cover,
                         tie_rebar_diameter, tie_spacing)
    bars = main_bars + tie_bars

    return {
        "name": name,
        "concrete": concrete,
        "rebar": bars_to_compound(bars),
        "bars": bars,
        "bar_groups": [
            bar_group(f"{name} - Mat Bars", main_bars, "MAIN", component=name),
            bar_group(f"{name} - Perimeter Ties", tie_bars, "SHEAR", component=name),
        ],
        "meta": {
            "kind": "box",
            "ifc_class": "IfcFooting",
            "predefined_type": "PILE_CAP",
            "name": name,
            "length": float(length),
            "width": float(width),
            "height": float(depth),
            "cover": float(cover),
            "main_bar_diameter": float(main_rebar_diameter),
            "main_spacing": float(main_spacing),
            "tie_bar_diameter": float(tie_rebar_diameter),
            "tie_spacing": float(tie_spacing),
        },
    }
