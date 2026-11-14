"""
IFC writer for the OsdagBridge substructure.

Works from the plain layout record produced by
``bridge_components.sub_structure.assembly`` (component dimensions, origins
and bar descriptors in millimetres, in the screening brief's frame).  The
caller supplies the ``Substructure`` storey, whose placement carries the
offset into the bridge's IFC coordinate system, so the placements written
here stay in the brief's frame.

Concrete members are swept solids (circular, rectangular or trapezoidal
profiles) and each bar group is one IfcReinforcingBar.  Every element gets a
material, base quantities and a property set with its key dimensions.
"""

import math

from osdagbridge.core.bridge_components.reinforcement import STEEL_DENSITY
from osdagbridge.core.ifc_export_bridge.bridge_geometry_mapper import create_ifc_guid

CONCRETE_RGB = (0.85, 0.85, 0.82)
REBAR_RGB = (0.45, 0.28, 0.12)

MM = 0.001  # layout is in mm, the IFC file in metres

_DIMENSION_KEYS = (
    "diameter", "height", "length", "width", "depth", "top_width",
    "bottom_width", "cover", "main_bar_diameter", "tie_bar_diameter",
)
_BAR_ROLES = ("MAIN", "SHEAR", "RING", "ANCHORING", "LIGATURE")


def _metres(point):
    return [float(v) * MM for v in point]


def _perpendicular(direction):
    """Unit vector perpendicular to ``direction`` (reference X for a sweep)."""
    x, y, _ = direction
    norm = math.hypot(x, y)
    if norm < 1e-9:  # direction is vertical
        return (1.0, 0.0, 0.0)
    return (-y / norm, x / norm, 0.0)


class _SubstructureWriter:
    def __init__(self, ifc_file, mapper, owner_history, storey, layout):
        self.file = ifc_file
        self.mapper = mapper
        self.owner = owner_history
        self.storey = storey
        self.layout = layout

        grades = layout.get("parameters", {})
        self.concrete_grade = grades.get("concrete_grade", "M30")
        self.steel_grade = grades.get("steel_grade", "Fe500")
        self.concrete = ifc_file.createIfcMaterial(f"Concrete {self.concrete_grade}")
        self.steel = ifc_file.createIfcMaterial(self.steel_grade)

    # -- element plumbing --------------------------------------------------

    def _add_element(self, ifc_class, name, solids, rgb, material,
                     location=(0.0, 0.0, 0.0), **attributes):
        """Create a product in the substructure storey from swept solids."""
        body = self.file.createIfcShapeRepresentation(
            self.mapper._context3d, "Body", "SweptSolid", solids
        )
        self.mapper.apply_color(body, rgb)
        element = self.file.create_entity(
            ifc_class,
            GlobalId=create_ifc_guid(),
            OwnerHistory=self.owner,
            Name=name,
            ObjectPlacement=self.file.createIfcLocalPlacement(
                self.storey.ObjectPlacement,
                self.mapper.create_axis2placement_3d(location),
            ),
            Representation=self.file.createIfcProductDefinitionShape(None, None, [body]),
            Tag=name,
            **attributes,
        )
        self.file.createIfcRelContainedInSpatialStructure(
            create_ifc_guid(), self.owner,
            RelatingStructure=self.storey, RelatedElements=[element],
        )
        self.file.createIfcRelAssociatesMaterial(
            create_ifc_guid(), self.owner,
            RelatedObjects=[element], RelatingMaterial=material,
        )
        return element

    def _define(self, element, definition):
        self.file.createIfcRelDefinesByProperties(
            create_ifc_guid(), self.owner,
            RelatedObjects=[element], RelatingPropertyDefinition=definition,
        )

    def _add_properties(self, element, name, values):
        properties = []
        for key, value in values.items():
            if isinstance(value, str):
                nominal = self.file.createIfcLabel(value)
            elif isinstance(value, int):
                nominal = self.file.createIfcInteger(value)
            else:
                nominal = self.file.createIfcReal(float(value))
            properties.append(
                self.file.createIfcPropertySingleValue(Name=key, NominalValue=nominal)
            )
        self._define(element, self.file.createIfcPropertySet(
            create_ifc_guid(), self.owner, Name=name, HasProperties=properties,
        ))

    def _add_quantities(self, element, *, volume=None, length=None,
                        count=None, weight=None):
        quantities = []
        if volume is not None:
            quantities.append(self.file.createIfcQuantityVolume(
                Name="NetVolume", VolumeValue=float(volume)))
        if length is not None:
            quantities.append(self.file.createIfcQuantityLength(
                Name="Length", LengthValue=float(length)))
        if count is not None:
            quantities.append(self.file.createIfcQuantityCount(
                Name="Count", CountValue=int(count)))
        if weight is not None:
            quantities.append(self.file.createIfcQuantityWeight(
                Name="NetWeight", WeightValue=float(weight)))
        self._define(element, self.file.createIfcElementQuantity(
            create_ifc_guid(), self.owner, Name="BaseQuantities",
            Quantities=quantities,
        ))

    # -- concrete ----------------------------------------------------------

    def _upright(self):
        return self.mapper.create_axis2placement_3d((0.0, 0.0, 0.0))

    def _concrete_solid(self, meta):
        """Return ``(solid, volume_m3, length_m)`` in the member's own frame."""
        kind = meta["kind"]
        if kind == "cylinder":
            radius = meta["diameter"] / 2.0 * MM
            height = meta["height"] * MM
            profile = self.mapper.create_circular_profile(radius)
            solid = self.mapper.create_extruded_solid(profile, height, self._upright())
            return solid, math.pi * radius ** 2 * height, height

        if kind == "box":
            length, width, height = (meta[k] * MM for k in ("length", "width", "height"))
            profile = self.mapper.create_rectangular_profile(length, width)
            solid = self.mapper.create_extruded_solid(profile, height, self._upright())
            return solid, length * width * height, height

        if kind == "trapezoid":
            bottom, top, depth, length = (
                meta[k] * MM for k in ("bottom_width", "top_width", "depth", "length")
            )
            profile = self.mapper.create_polygonal_profile(
                [(-bottom / 2.0, 0.0), (bottom / 2.0, 0.0),
                 (top / 2.0, depth), (-top / 2.0, depth)],
                meta["name"],
            )
            # The profile is drawn in X-Z and swept along the cap (-Y), so the
            # profile's Y axis maps to global Z and the sweep starts at the +Y end.
            position = self.mapper.create_axis2placement_3d(
                (0.0, length / 2.0, 0.0), z_dir=(0.0, -1.0, 0.0), x_dir=(1.0, 0.0, 0.0),
            )
            solid = self.mapper.create_extruded_solid(profile, length, position)
            return solid, (bottom + top) / 2.0 * depth * length, length

        raise ValueError(f"Unknown substructure component kind: {kind}")

    def write_concrete(self):
        for meta in self.layout["components"]:
            solid, volume, length = self._concrete_solid(meta)
            attributes = {}
            if "predefined_type" in meta:
                attributes["PredefinedType"] = meta["predefined_type"]
            element = self._add_element(
                meta["ifc_class"], meta["name"], [solid], CONCRETE_RGB,
                self.concrete, location=_metres(meta["origin"]), **attributes,
            )
            properties = {
                "Shape": meta["kind"],
                "ConcreteGrade": meta.get("concrete_grade", self.concrete_grade),
            }
            properties.update(
                {key: float(meta[key]) for key in _DIMENSION_KEYS if key in meta}
            )
            self._add_properties(element, "Pset_OsdagBridgeSubstructure", properties)
            self._add_quantities(element, volume=volume, length=length)

    # -- reinforcement -----------------------------------------------------

    def _bar_solid(self, bar):
        """Return ``(solid, length_m)`` for one bar descriptor."""
        radius = bar["diameter"] / 2.0 * MM
        if bar["kind"] == "line":
            start, end = _metres(bar["p1"]), _metres(bar["p2"])
            length = math.dist(start, end)
            axis = tuple((e - s) / length for s, e in zip(start, end))
            position = self.mapper.create_axis2placement_3d(
                start, z_dir=axis, x_dir=_perpendicular(axis)
            )
            profile = self.mapper.create_circular_profile(radius)
            return self.mapper.create_extruded_solid(profile, length, position), length

        if bar["kind"] == "ring":
            ring_radius = bar["radius"] * MM
            position = self.mapper.create_axis2placement_3d(_metres(bar["center"]))
            solid = self.mapper.create_revolved_circular_solid(radius, ring_radius, position)
            return solid, 2.0 * math.pi * ring_radius

        raise ValueError(f"Unknown bar kind: {bar['kind']}")

    def write_rebar(self):
        for group in self.layout["rebar_groups"]:
            solids, lengths = zip(*(self._bar_solid(bar) for bar in group["bars"]))
            total_length = sum(lengths)
            diameter = group["diameter"] * MM
            area = math.pi * diameter ** 2 / 4.0
            role = group["bar_type"] if group["bar_type"] in _BAR_ROLES else "MAIN"

            element = self._add_element(
                "IfcReinforcingBar", group["name"], list(solids), REBAR_RGB,
                self.steel,
                SteelGrade=self.steel_grade,
                NominalDiameter=diameter,
                CrossSectionArea=area,
                BarLength=total_length / len(lengths),
                PredefinedType=role,
            )
            self._add_properties(element, "Pset_OsdagBridgeReinforcement", {
                "Component": group["component"],
                "BarRole": role,
                "NominalDiameter": float(group["diameter"]),
                "BarCount": len(lengths),
            })
            self._add_quantities(
                element, count=len(lengths), length=total_length,
                weight=total_length * area * STEEL_DENSITY,
            )


def export_substructure(ifc_file, mapper, owner_history, storey, layout):
    """Write the substructure concrete members and rebar groups into ``ifc_file``."""
    if not layout or not layout.get("components"):
        return
    writer = _SubstructureWriter(ifc_file, mapper, owner_history, storey, layout)
    writer.write_concrete()
    writer.write_rebar()
