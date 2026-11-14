"""
Substructure assembly for OsdagBridge.

The assembly is authored in the coordinate system given in the screening
brief:

    X  along the span, origin at mid-span
    Y  across the deck, origin on the bridge centreline
    Z  vertical, origin at deck level, positive upwards

so every member sits at negative Z.  ``model_offset`` moves the finished
shapes into the existing OsdagBridge CAD frame (origin at the start of the
span, at mid-girder height):

    model_x = x + span_length / 2
    model_z = z + deck_top_z

``SubstructureBuild.layout`` holds the same model as plain numbers and bar
descriptors, in the brief's frame.  The IFC writer works from that record, so
it never has to measure pythonOCC shapes.
"""

import math
from dataclasses import asdict, dataclass, field
from typing import List, Optional, Sequence

from osdagbridge.core.bridge_components.foundation.pile.builder import build_pile
from osdagbridge.core.bridge_components.foundation.pile_cap.builder import build_pile_cap
from osdagbridge.core.bridge_components.reinforcement import (
    REBAR_COVER,
    REBAR_MAIN_DIAMETER,
    REBAR_SPACING_LONGITUDINAL,
    REBAR_SPACING_TRANSVERSE,
    REBAR_TRANSVERSE_DIAMETER,
    bar_length,
    steel_mass,
    translate,
    translate_bar,
)
from osdagbridge.core.bridge_components.sub_structure.pedestal.builder import build_pedestal
from osdagbridge.core.bridge_components.sub_structure.pier.builder import build_pier
from osdagbridge.core.bridge_components.sub_structure.pier_cap.builder import build_pier_cap


@dataclass
class SubstructureParameters:
    """Substructure dimensions in millimetres."""

    # layout
    n_piers: int = 2
    pier_edge_offset: float = 0.0      # pier centreline to the bearing line at the span end
    cap_end_clearance: float = 500.0   # deck edge to the end of the pier cap

    # pier
    pier_diameter: float = 800.0
    pier_height: float = 3000.0

    # pier cap
    pier_cap_top_width: float = 3000.0
    pier_cap_bottom_width: float = 1200.0
    pier_cap_depth: float = 600.0
    pier_cap_length: Optional[float] = None  # None: deck width less the end clearances

    # pedestal
    pedestal_length: float = 600.0
    pedestal_width: float = 400.0
    pedestal_height: float = 150.0

    # pile cap
    pile_cap_length: float = 2200.0
    pile_cap_width: float = 1200.0
    pile_cap_depth: float = 600.0

    # piles, 2 x 2 group under each pile cap
    pile_diameter: float = 400.0
    pile_length: float = 5000.0
    pile_spacing: float = 600.0

    # reinforcement
    rebar_main_diameter: float = REBAR_MAIN_DIAMETER
    rebar_spacing_longitudinal: float = REBAR_SPACING_LONGITUDINAL
    rebar_transverse_diameter: float = REBAR_TRANSVERSE_DIAMETER
    rebar_spacing_transverse: float = REBAR_SPACING_TRANSVERSE
    rebar_cover: float = REBAR_COVER

    concrete_grade: str = "M30"
    steel_grade: str = "Fe500"


@dataclass
class SubstructureBuild:
    """Result of :func:`build_substructure`.

    ``concrete`` and ``rebar`` are parallel lists of shapes in the CAD frame,
    one entry per member.  ``layout`` describes the same members in the
    brief's frame for the IFC writer and ``summary`` holds the totals.
    """

    concrete: List[object] = field(default_factory=list)
    rebar: List[object] = field(default_factory=list)
    layout: dict = field(default_factory=dict)
    summary: dict = field(default_factory=dict)


def _volume_mm3(meta):
    kind = meta["kind"]
    if kind == "cylinder":
        return math.pi * (meta["diameter"] / 2.0) ** 2 * meta["height"]
    if kind == "box":
        return meta["length"] * meta["width"] * meta["height"]
    if kind == "trapezoid":
        mean_width = (meta["bottom_width"] + meta["top_width"]) / 2.0
        return mean_width * meta["depth"] * meta["length"]
    raise ValueError(f"Unknown component kind: {kind}")


def _pier_stations(span_length, edge_offset, count):
    """Pier X positions measured from mid-span."""
    if count == 1:
        return [0.0]
    edge = span_length / 2.0 - edge_offset
    return [-edge + i * 2.0 * edge / (count - 1) for i in range(count)]


def _validate(p, span_length, deck_width, cap_length, bearing_ys):
    if p.n_piers < 1:
        raise ValueError("At least one pier is required")
    if deck_width <= 0:
        raise ValueError("Deck width must be positive")
    if p.n_piers > 1 and span_length <= 2.0 * p.pier_edge_offset:
        raise ValueError("Span is too short for the configured pier edge offset")
    if p.pier_diameter > min(p.pier_cap_bottom_width, p.pile_cap_length, p.pile_cap_width):
        raise ValueError("Pier is wider than the pier cap soffit or the pile cap")
    pile_group = p.pile_spacing + p.pile_diameter
    if pile_group > min(p.pile_cap_length, p.pile_cap_width):
        raise ValueError("Pile group does not fit inside the pile cap")
    if p.pedestal_length > p.pier_cap_top_width:
        raise ValueError("Pedestal is longer than the pier cap top width")
    reach = max(abs(y) for y in bearing_ys) + p.pedestal_width / 2.0
    if reach > cap_length / 2.0:
        raise ValueError("Pier cap is too short to carry the outer pedestals")


def build_substructure(
    *,
    span_length,
    deck_width,
    soffit_z,
    bearing_ys: Optional[Sequence[float]] = None,
    model_offset=(0.0, 0.0, 0.0),
    params: Optional[SubstructureParameters] = None,
):
    """
    Build one pier bent under the bearing line at each end of the span.

    Parameters
    ----------
    span_length, deck_width : float
        Superstructure dimensions in mm.
    soffit_z : float
        Underside of the girders in the brief's frame (negative).  The
        pedestals finish at this level.
    bearing_ys : sequence of float, optional
        Girder lines measured from the bridge centreline.  One pedestal is
        placed under each.  Defaults to a single pair near the cap ends.
    model_offset : tuple
        Translation from the brief's frame into the bridge CAD frame.
    params : SubstructureParameters, optional
        Dimension overrides.
    """
    p = params or SubstructureParameters()
    span_length = float(span_length)
    deck_width = float(deck_width)
    soffit_z = float(soffit_z)

    cap_length = p.pier_cap_length
    if cap_length is None:
        cap_length = max(p.pier_cap_top_width, deck_width - 2.0 * p.cap_end_clearance)
    cap_length = float(cap_length)

    if bearing_ys is None:
        edge = cap_length / 2.0 - p.cap_end_clearance
        bearing_ys = [-edge, edge]
    bearing_ys = [float(y) for y in bearing_ys]

    _validate(p, span_length, deck_width, cap_length, bearing_ys)

    # Levels, working down from the girder soffit.
    cap_top_z = soffit_z - p.pedestal_height
    cap_bottom_z = cap_top_z - p.pier_cap_depth
    pile_cap_top_z = cap_bottom_z - p.pier_height
    pile_cap_bottom_z = pile_cap_top_z - p.pile_cap_depth
    pile_toe_z = pile_cap_bottom_z - p.pile_length

    half_pitch = p.pile_spacing / 2.0
    pile_offsets = [(sx * half_pitch, sy * half_pitch)
                    for sx in (-1.0, 1.0) for sy in (-1.0, 1.0)]

    cage = dict(
        cover=p.rebar_cover,
        main_rebar_diameter=p.rebar_main_diameter,
        tie_rebar_diameter=p.rebar_transverse_diameter,
        tie_spacing=p.rebar_spacing_transverse,
    )

    build = SubstructureBuild()
    components = []
    rebar_groups = []

    def place(member, bent, x, y, z):
        build.concrete.append(translate(member["concrete"], x, y, z))
        build.rebar.append(translate(member["rebar"], x, y, z))
        components.append({
            **member["meta"],
            "bent": bent,
            "origin": [x, y, z],
            "concrete_grade": p.concrete_grade,
        })
        for group in member["bar_groups"]:
            rebar_groups.append({
                **group,
                "bars": [translate_bar(b, x, y, z) for b in group["bars"]],
            })

    pier_xs = _pier_stations(span_length, p.pier_edge_offset, p.n_piers)
    for bent, x in enumerate(pier_xs, start=1):
        place(build_pier_cap(
            length=cap_length,
            top_width=p.pier_cap_top_width,
            bottom_width=p.pier_cap_bottom_width,
            depth=p.pier_cap_depth,
            main_spacing=p.rebar_spacing_longitudinal,
            name=f"Pier Cap {bent}",
            **cage,
        ), bent, x, 0.0, cap_bottom_z)

        for i, y in enumerate(bearing_ys, start=1):
            place(build_pedestal(
                length=p.pedestal_length,
                width=p.pedestal_width,
                height=p.pedestal_height,
                name=f"Pedestal {bent}-{i}",
                **cage,
            ), bent, x, y, cap_top_z)

        place(build_pier(
            diameter=p.pier_diameter,
            height=p.pier_height,
            name=f"Pier {bent}",
            **cage,
        ), bent, x, 0.0, pile_cap_top_z)

        place(build_pile_cap(
            length=p.pile_cap_length,
            width=p.pile_cap_width,
            depth=p.pile_cap_depth,
            main_spacing=p.rebar_spacing_longitudinal,
            name=f"Pile Cap {bent}",
            **cage,
        ), bent, x, 0.0, pile_cap_bottom_z)

        for i, (dx, dy) in enumerate(pile_offsets, start=1):
            place(build_pile(
                diameter=p.pile_diameter,
                length=p.pile_length,
                name=f"Pile {bent}-{i}",
                **cage,
            ), bent, x + dx, dy, pile_toe_z)

    offset = [float(v) for v in model_offset]
    if any(offset):
        build.concrete = [translate(s, *offset) for s in build.concrete]
        build.rebar = [translate(s, *offset) for s in build.rebar]

    all_bars = [bar for group in rebar_groups for bar in group["bars"]]
    build.summary = {
        "pier_count": len(pier_xs),
        "component_count": len(components),
        "bar_group_count": len(rebar_groups),
        "bar_count": len(all_bars),
        "concrete_m3": sum(_volume_mm3(c) for c in components) * 1e-9,
        "rebar_m": sum(bar_length(b) for b in all_bars) * 1e-3,
        "steel_kg": steel_mass(all_bars),
        "main_bar_diameter": p.rebar_main_diameter,
        "tie_bar_diameter": p.rebar_transverse_diameter,
        "cap_length": cap_length,
        "cap_top_z": cap_top_z,
        "pile_toe_z": pile_toe_z,
    }
    build.layout = {
        "components": components,
        "rebar_groups": rebar_groups,
        "parameters": asdict(p),
        "span_length": span_length,
        "deck_width": deck_width,
        "soffit_z": soffit_z,
        "storey_offset": offset,
    }
    return build
