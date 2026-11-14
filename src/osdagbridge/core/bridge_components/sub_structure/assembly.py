"""
Substructure assembly for OsdagBridge.

The assembly is authored in the coordinate system required by the screening
brief:

    X -> longitudinal direction (span), origin at mid-span
    Y -> transverse direction (deck width), origin at the bridge centreline
    Z -> vertical, origin at deck level, positive upwards

Concrete members therefore sit at negative Z.  ``model_offset`` converts the
assembly into the existing OsdagBridge CAD/IFC frame, whose origin is at the
start of the span and at mid-girder height:

    model_x = x + span_length / 2
    model_z = z + deck_top_z

The resulting layout dictionary is deliberately free of pythonOCC objects so
that the IFC exporter can consume the same parameter data without
reconstructing geometry by hand.
"""

import copy
import math
from dataclasses import asdict, dataclass, field
from typing import List, Optional

from osdagbridge.core.bridge_components.foundation.pile.builder import build_pile
from osdagbridge.core.bridge_components.foundation.pile_cap.builder import build_pile_cap
from osdagbridge.core.bridge_components.reinforcement import bar_length, translate
from osdagbridge.core.bridge_components.sub_structure.pedestal.builder import build_pedestal
from osdagbridge.core.bridge_components.sub_structure.pier.builder import build_pier
from osdagbridge.core.bridge_components.sub_structure.pier_cap.builder import build_pier_cap


@dataclass
class SubstructureParameters:
    """All dimensions are millimetres."""

    # layout
    n_piers: int = 2
    pier_edge_offset: float = 1200.0
    cap_end_clearance: float = 500.0
    model_offset_z: float = 0.0

    # pier
    pier_diameter: float = 800.0
    pier_height: float = 3000.0

    # pier cap
    pier_cap_top_width: float = 3000.0
    pier_cap_bottom_width: float = 1200.0
    pier_cap_depth: float = 600.0
    pier_cap_length: Optional[float] = None  # None -> derive from deck width

    # pedestal
    pedestal_length: float = 600.0
    pedestal_width: float = 400.0
    pedestal_height: float = 150.0
    n_pedestals_per_cap: int = 2

    # pile cap
    pile_cap_length: float = 2200.0
    pile_cap_width: float = 1200.0
    pile_cap_depth: float = 600.0

    # piles
    n_piles_per_cap: int = 4
    pile_diameter: float = 400.0
    pile_length: float = 5000.0
    pile_spacing: float = 600.0

    # reinforcement
    rebar_main_diameter: float = 16.0
    rebar_spacing_longitudinal: float = 150.0
    rebar_transverse_diameter: float = 8.0
    rebar_spacing_transverse: float = 200.0
    rebar_cover: float = 40.0

    concrete_grade: str = "M30"
    steel_grade: str = "Fe500"


@dataclass
class SubstructureBuild:
    concrete: List[object] = field(default_factory=list)
    rebar: List[object] = field(default_factory=list)
    components: List[dict] = field(default_factory=list)
    rebar_groups: List[dict] = field(default_factory=list)
    summary: dict = field(default_factory=dict)


def _translate_bar(bar, dx, dy, dz):
    bar = copy.deepcopy(bar)
    if bar["kind"] == "line":
        bar["p1"] = [bar["p1"][0] + dx, bar["p1"][1] + dy, bar["p1"][2] + dz]
        bar["p2"] = [bar["p2"][0] + dx, bar["p2"][1] + dy, bar["p2"][2] + dz]
    elif bar["kind"] == "ring":
        bar["center"] = [
            bar["center"][0] + dx,
            bar["center"][1] + dy,
            bar["center"][2] + dz,
        ]
    else:
        raise ValueError(f"Unknown bar kind: {bar['kind']}")
    return bar


def _translate_groups(groups, dx, dy, dz):
    out = []
    for group in groups:
        g = copy.deepcopy(group)
        g["bars"] = [_translate_bar(b, dx, dy, dz) for b in group["bars"]]
        out.append(g)
    return out


def _pedestal_y_positions(cap_length, pedestal_width, count):
    if count <= 0:
        return []
    if count == 1:
        return [0.0]
    usable = cap_length / 2.0 - pedestal_width / 2.0 - 40.0
    # Place the outer pedestals under the outer girders, evenly spaced.
    return [-usable + i * (2.0 * usable) / (count - 1) for i in range(count)]


def _pile_offsets(n_piles, spacing):
    """2x2 grid offsets for the default four-pile group."""
    if n_piles != 4:
        # Generic single row fallback, still centred under the column.
        return [((i - (n_piles - 1) / 2.0) * spacing, 0.0) for i in range(n_piles)]
    half = spacing / 2.0
    return [(-half, -half), (half, -half), (half, half), (-half, half)]


def _register_component(build, result, dx, dy, dz, index_suffix):
    """Place one builder result and append it to the assembly."""
    name = result["name"]
    concrete = translate(result["concrete"], dx, dy, dz)
    rebar = translate(result["rebar"], dx, dy, dz)
    build.concrete.append(concrete)
    build.rebar.append(rebar)

    meta = copy.deepcopy(result["meta"])
    meta["name"] = name
    meta["origin"] = [dx, dy, dz]
    meta["index"] = index_suffix
    build.components.append(meta)

    groups = _translate_groups(result["bar_groups"], dx, dy, dz)
    for group in groups:
        group["name"] = group["name"].replace(result["name"], name, 1)
        group["component"] = name
    build.rebar_groups.extend(groups)


def _concrete_volume_cylinder(diameter, height):
    return math.pi * (diameter / 2.0) ** 2 * height


def compute_summary(components):
    """Approximate concrete volumes in m3 and reinforcement weight in kg."""
    concrete_m3 = 0.0
    steel_kg = 0.0
    rebar_m = 0.0
    for meta in components:
        kind = meta["kind"]
        if kind == "cylinder":
            concrete_m3 += _concrete_volume_cylinder(meta["diameter"], meta["height"])
        elif kind == "box":
            concrete_m3 += meta["length"] * meta["width"] * meta["height"]
        elif kind == "trapezoid":
            area = ((meta["bottom_width"] + meta["top_width"]) / 2.0) * meta["depth"]
            concrete_m3 += area * meta["length"]
    concrete_m3 /= 1e9

    # Rebar weight is accumulated from the grouped bar descriptors by the
    # caller (see build_substructure) because the components list alone does
    # not carry bar lengths.
    return {"concrete_m3": concrete_m3, "steel_kg": steel_kg, "rebar_m": rebar_m}


def build_substructure(
    *,
    span_length,
    deck_width,
    soffit_z,
    model_offset=(0.0, 0.0, 0.0),
    params: Optional[SubstructureParameters] = None,
    name_prefix="",
):
    """
    Build the complete substructure.

    Parameters
    ----------
    span_length : float
        Bridge span in mm, used to place one pier assembly near each support.
    deck_width : float
        Total deck width in mm; the pier cap length is derived from it.
    soffit_z : float
        Z coordinate of the underside of the superstructure in the task frame
        (negative, measured from deck level).
    model_offset : tuple
        Translation into the existing OsdagBridge model frame.
    params : SubstructureParameters, optional
        Override any of the default screening-task dimensions.
    """
    p = params or SubstructureParameters()
    span_length = float(span_length)
    deck_width = float(deck_width)

    if span_length <= 2.0 * p.pier_edge_offset:
        raise ValueError("Span is too short for the configured pier edge offset")
    if deck_width <= 0:
        raise ValueError("Deck width must be positive")

    cap_length = p.pier_cap_length
    if cap_length is None:
        cap_length = max(3000.0, deck_width - 2.0 * p.cap_end_clearance)
    cap_length = float(cap_length)

    if p.pier_cap_top_width < p.pier_cap_bottom_width:
        raise ValueError("Pier cap top width must be >= bottom width")
    if p.n_piles_per_cap != 4:
        raise ValueError("This implementation supports a 2x2 pile group (n_piles_per_cap=4)")
    if p.pile_spacing + p.pile_diameter > p.pile_cap_width + 1e-6:
        raise ValueError("Pile group does not fit inside the pile cap width")
    if p.pedestal_length > p.pier_cap_top_width:
        raise ValueError("Pedestal is wider than the pier cap top")

    # Pier positions along the span, measured from mid-span.
    if p.n_piers == 1:
        pier_xs = [0.0]
    else:
        edge = span_length / 2.0 - p.pier_edge_offset
        pier_xs = [-edge + i * (2.0 * edge) / (p.n_piers - 1) for i in range(p.n_piers)]

    build = SubstructureBuild()

    # Top of the pier cap is below the superstructure soffit, leaving room for
    # the bearing pedestals.
    cap_top_z = float(soffit_z) - p.pedestal_height
    cap_bottom_z = cap_top_z - p.pier_cap_depth
    pier_bottom_z = cap_bottom_z - p.pier_height
    pile_cap_top_z = pier_bottom_z
    pile_cap_bottom_z = pile_cap_top_z - p.pile_cap_depth
    pile_bottom_z = pile_cap_bottom_z - p.pile_length

    pedestal_ys = _pedestal_y_positions(cap_length, p.pedestal_width, p.n_pedestals_per_cap)
    pile_offsets = _pile_offsets(p.n_piles_per_cap, p.pile_spacing)

    for pi, x in enumerate(pier_xs, start=1):
        suffix = f"{name_prefix}{pi}"
        pier_name = f"Pier {suffix}"
        cap_name = f"Pier Cap {suffix}"
        pile_cap_name = f"Pile Cap {suffix}"

        # --- pier cap -----------------------------------------------------
        cap = build_pier_cap(
            length=cap_length,
            top_width=p.pier_cap_top_width,
            bottom_width=p.pier_cap_bottom_width,
            depth=p.pier_cap_depth,
            cover=p.rebar_cover,
            main_rebar_diameter=p.rebar_main_diameter,
            main_spacing=p.rebar_spacing_longitudinal,
            tie_rebar_diameter=p.rebar_transverse_diameter,
            tie_spacing=p.rebar_spacing_transverse,
            name=cap_name,
        )
        _register_component(build, cap, x, 0.0, cap_bottom_z, suffix)

        # --- pedestals ----------------------------------------------------
        for si, y in enumerate(pedestal_ys, start=1):
            ped = build_pedestal(
                length=p.pedestal_length,
                width=p.pedestal_width,
                height=p.pedestal_height,
                cover=p.rebar_cover,
                main_rebar_diameter=p.rebar_main_diameter,
                tie_rebar_diameter=p.rebar_transverse_diameter,
                tie_spacing=p.rebar_spacing_transverse,
                name=f"Pedestal {suffix}-{si}",
            )
            _register_component(
                build, ped, x, y, cap_top_z, f"{suffix}-{si}"
            )

        # --- pier ---------------------------------------------------------
        pier = build_pier(
            diameter=p.pier_diameter,
            height=p.pier_height,
            cover=p.rebar_cover,
            main_rebar_diameter=p.rebar_main_diameter,
            tie_rebar_diameter=p.rebar_transverse_diameter,
            tie_spacing=p.rebar_spacing_transverse,
            name=pier_name,
        )
        _register_component(build, pier, x, 0.0, pier_bottom_z, suffix)

        # --- pile cap -----------------------------------------------------
        pile_cap = build_pile_cap(
            length=p.pile_cap_length,
            width=p.pile_cap_width,
            depth=p.pile_cap_depth,
            cover=p.rebar_cover,
            main_rebar_diameter=p.rebar_main_diameter,
            main_spacing=p.rebar_spacing_longitudinal,
            tie_rebar_diameter=p.rebar_transverse_diameter,
            tie_spacing=p.rebar_spacing_transverse,
            name=pile_cap_name,
        )
        _register_component(build, pile_cap, x, 0.0, pile_cap_bottom_z, suffix)

        # --- piles --------------------------------------------------------
        for qi, (dx, dy) in enumerate(pile_offsets, start=1):
            pile = build_pile(
                diameter=p.pile_diameter,
                length=p.pile_length,
                cover=p.rebar_cover,
                main_rebar_diameter=p.rebar_main_diameter,
                tie_rebar_diameter=p.rebar_transverse_diameter,
                tie_spacing=p.rebar_spacing_transverse,
                name=f"Pile {suffix}-{qi}",
            )
            _register_component(
                build, pile, x + dx, dy, pile_bottom_z, f"{suffix}-{qi}"
            )

    # Totals for the report / BOQ summary.
    concrete_m3 = 0.0
    for meta in build.components:
        if meta["kind"] == "cylinder":
            concrete_m3 += _concrete_volume_cylinder(meta["diameter"], meta["height"])
        elif meta["kind"] == "box":
            concrete_m3 += meta["length"] * meta["width"] * meta["height"]
        elif meta["kind"] == "trapezoid":
            area = ((meta["bottom_width"] + meta["top_width"]) / 2.0) * meta["depth"]
            concrete_m3 += area * meta["length"]
    concrete_m3 /= 1e9

    rebar_m = 0.0
    steel_kg = 0.0
    for group in build.rebar_groups:
        d = float(group["diameter"])
        area_mm2 = math.pi * (d / 2.0) ** 2
        for bar in group["bars"]:
            length_mm = bar_length(bar)
            rebar_m += length_mm / 1000.0
            steel_kg += length_mm * area_mm2 * 7.85e-6  # kg (7850 kg/m3)

    build.summary = {
        "pier_count": len(pier_xs),
        "component_count": len(build.components),
        "bar_group_count": len(build.rebar_groups),
        "bar_count": sum(g["count"] for g in build.rebar_groups),
        "concrete_m3": concrete_m3,
        "rebar_m": rebar_m,
        "steel_kg": steel_kg,
        "cap_length": cap_length,
        "cap_top_z": cap_top_z,
        "pile_bottom_z": pile_bottom_z,
    }

    dx, dy, dz = [float(v) for v in model_offset]
    if dx or dy or dz:
        build.concrete = [translate(s, dx, dy, dz) for s in build.concrete]
        build.rebar = [translate(s, dx, dy, dz) for s in build.rebar]

    build.summary["layout"] = {
        "components": build.components,
        "rebar_groups": build.rebar_groups,
        "parameters": asdict(p),
        "span_length": span_length,
        "deck_width": deck_width,
        "soffit_z": float(soffit_z),
        "storey_offset": [dx, dy, dz],
    }
    return build
