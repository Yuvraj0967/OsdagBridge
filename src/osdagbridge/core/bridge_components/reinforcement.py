"""
Shared reinforcement and solid helpers for OsdagBridge substructure builders.

The substructure builders all follow the same pattern:

* build the concrete solid in a *local* frame whose origin is the bottom
  centre of the component;
* describe every reinforcing bar with a small, serialisable descriptor
  (``line`` or ``ring``) so the same data can be reused by the IFC exporter;
* convert the bar descriptors to pythonOCC cylinders/tori and place them in a
  single ``TopoDS_Compound`` for display.

Keeping rebar as a compound (instead of fusing hundreds of solids) is
important: boolean fusion of a full reinforcement cage is slow and produces a
shape that is expensive to tessellate for the 3D viewer.
"""

import math

from OCC.Core.BRep import BRep_Builder
from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCC.Core.BRepPrimAPI import (
    BRepPrimAPI_MakeBox,
    BRepPrimAPI_MakeCylinder,
    BRepPrimAPI_MakeTorus,
)
from OCC.Core.gp import gp_Ax1, gp_Dir, gp_Pnt, gp_Trsf, gp_Vec
from OCC.Core.TopoDS import TopoDS_Compound


# ---------------------------------------------------------------------------
# transforms / primitives
# ---------------------------------------------------------------------------

def translate(shape, dx=0.0, dy=0.0, dz=0.0):
    """Translate a shape by (dx, dy, dz) millimetres."""
    if shape is None or shape.IsNull():
        return shape
    trsf = gp_Trsf()
    trsf.SetTranslation(gp_Vec(float(dx), float(dy), float(dz)))
    return BRepBuilderAPI_Transform(shape, trsf, True).Shape()


def make_box(dx, dy, dz, origin=(0.0, 0.0, 0.0)):
    """Axis-aligned box; origin is the corner with the smallest coordinates."""
    box = BRepPrimAPI_MakeBox(
        gp_Pnt(*[float(v) for v in origin]),
        float(dx), float(dy), float(dz),
    ).Shape()
    return box


def make_cylinder_between(p1, p2, diameter):
    """Cylinder of ``diameter`` joining two 3D points."""
    p1 = [float(v) for v in p1]
    p2 = [float(v) for v in p2]
    vec = gp_Vec(gp_Pnt(*p1), gp_Pnt(*p2))
    length = vec.Magnitude()
    if length <= 0.0:
        raise ValueError("Rebar segment has zero length")
    radius = float(diameter) / 2.0
    cylinder = BRepPrimAPI_MakeCylinder(radius, length).Shape()

    # Rotate the default +Z cylinder onto the requested axis, then move its
    # base point to p1.  (gp_Trsf.SetTransformation(a, b) is a change of
    # coordinate system, not a mapping from the local to the global frame.)
    direction = gp_Dir(vec)
    z_axis = gp_Dir(0.0, 0.0, 1.0)
    trsf = gp_Trsf()
    dot = max(-1.0, min(1.0, z_axis.Dot(direction)))
    if abs(dot) < 1.0 - 1e-12:
        axis = z_axis.Crossed(direction)
        trsf.SetRotation(gp_Ax1(gp_Pnt(0.0, 0.0, 0.0), axis), math.acos(dot))
    elif dot < 0.0:
        trsf.SetRotation(gp_Ax1(gp_Pnt(0.0, 0.0, 0.0), gp_Dir(1.0, 0.0, 0.0)), math.pi)
    trsf.SetTranslationPart(gp_Vec(*p1))
    return BRepBuilderAPI_Transform(cylinder, trsf, True).Shape()


def make_vertical_cylinder(center_xy, z_bottom, diameter, height):
    """Vertical cylinder whose bottom face is at ``z_bottom``."""
    x, y = center_xy
    cylinder = BRepPrimAPI_MakeCylinder(float(diameter) / 2.0, float(height)).Shape()
    return translate(cylinder, x, y, z_bottom)


def make_ring(center, ring_radius, bar_diameter):
    """Circular stirrup/tie modelled as a torus in the XY plane."""
    torus = BRepPrimAPI_MakeTorus(float(ring_radius), float(bar_diameter) / 2.0).Shape()
    return translate(torus, center[0], center[1], center[2])


def make_compound(shapes):
    """Collect shapes into a single TopoDS_Compound (never fuse a rebar cage)."""
    builder = BRep_Builder()
    compound = TopoDS_Compound()
    builder.MakeCompound(compound)
    for shape in shapes:
        if shape is not None and not shape.IsNull():
            builder.Add(compound, shape)
    return compound


# ---------------------------------------------------------------------------
# bar descriptors
# ---------------------------------------------------------------------------

def line_bar(p1, p2, diameter):
    """Descriptor for a straight bar between two points."""
    return {
        "kind": "line",
        "p1": [float(v) for v in p1],
        "p2": [float(v) for v in p2],
        "diameter": float(diameter),
    }


def ring_bar(center, radius, diameter):
    """Descriptor for a closed circular bar in the XY plane."""
    return {
        "kind": "ring",
        "center": [float(v) for v in center],
        "radius": float(radius),
        "diameter": float(diameter),
    }


def bar_length(bar):
    if bar["kind"] == "line":
        dx = bar["p2"][0] - bar["p1"][0]
        dy = bar["p2"][1] - bar["p1"][1]
        dz = bar["p2"][2] - bar["p1"][2]
        return math.sqrt(dx * dx + dy * dy + dz * dz)
    if bar["kind"] == "ring":
        return 2.0 * math.pi * bar["radius"]
    raise ValueError(f"Unknown bar kind: {bar['kind']}")


def bar_to_shape(bar):
    if bar["kind"] == "line":
        return make_cylinder_between(bar["p1"], bar["p2"], bar["diameter"])
    if bar["kind"] == "ring":
        return make_ring(bar["center"], bar["radius"], bar["diameter"])
    raise ValueError(f"Unknown bar kind: {bar['kind']}")


def bars_to_compound(bars):
    return make_compound([bar_to_shape(b) for b in bars])


def rectangular_tie(center_xy, z, width_x, width_y, bar_diameter):
    """
    Four straight bars forming a closed rectangular stirrup.

    ``width_x`` / ``width_y`` are the centre-line dimensions of the tie, so the
    caller is responsible for applying the concrete cover.
    """
    cx, cy = center_xy
    hx, hy = width_x / 2.0, width_y / 2.0
    corners = [
        (cx - hx, cy - hy),
        (cx + hx, cy - hy),
        (cx + hx, cy + hy),
        (cx - hx, cy + hy),
    ]
    bars = []
    for i in range(4):
        x1, y1 = corners[i]
        x2, y2 = corners[(i + 1) % 4]
        bars.append(line_bar((x1, y1, z), (x2, y2, z), bar_diameter))
    return bars


def bar_group(name, bars, bar_type="MAIN", diameter=None, component=""):
    """
    Group bar descriptors for IFC export.

    ``bar_type`` is one of MAIN / SHEAR / RING.  ``diameter`` is taken from the
    first bar when omitted.
    """
    if not bars:
        raise ValueError(f"Bar group {name!r} is empty")
    if diameter is None:
        diameter = bars[0]["diameter"]
    return {
        "name": name,
        "component": component,
        "bar_type": bar_type,
        "diameter": float(diameter),
        "count": len(bars),
        "bars": bars,
    }
