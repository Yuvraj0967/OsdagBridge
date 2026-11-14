"""
IFC writer for the OsdagBridge substructure.

The substructure is authored in the screening-task frame (origin at mid-span
and deck level).  The caller gives this writer the ``Substructure`` storey,
whose object placement carries the conversion into the bridge's global IFC
coordinate system, so all element placements written here stay in the simple
task-local frame.

Concrete members are written as native IFC extruded solids (circular, box or
trapezoidal profiles), and reinforcement is written as IfcReinforcingBar
elements.  Each element also receives:

* a material association (concrete or steel),
* an IfcElementQuantity set (volume / count / length / weight), and
* a Pset_OsdagBridgeSubstructure property set with the key dimensions.
"""

import math

from osdagbridge.core.ifc_export_bridge.bridge_geometry_mapper import create_ifc_guid

CONCRETE_RGB = (0.85, 0.85, 0.82)
REBAR_RGB = (0.45, 0.28, 0.12)
CONCRETE_MATERIAL = "Concrete M30"
STEEL_MATERIAL = "Fe500"

_IFC_UNIT_SCALE = 0.001  # mm -> m


def _mm(value):
    return float(value) * _IFC_UNIT_SCALE


def _orthogonal_x(z_dir):
    """Return a stable X direction orthogonal to the extrusion direction."""
    zx, zy, zz = z_dir
    if abs(zz) > 0.999:
        return (1.0, 0.0, 0.0)
    mag = math.sqrt(zx * zx + zy * zy)
    if mag < 1e-12:
        return (1.0, 0.0, 0.0)
    return (-zy / mag, zx / mag, 0.0)


def _identity(mapper):
    return mapper.create_axis2placement_3d((0.0, 0.0, 0.0),
                                          z_dir=(0.0, 0.0, 1.0),
                                          x_dir=(1.0, 0.0, 0.0))


class _Writer:
    def __init__(self, file, mapper, owner_history, storey, layout):
        self.file = file
        self.mapper = mapper
        self.owner = owner_history
        self.storey = storey
        self.layout = layout
        self.concrete = file.createIfcMaterial(CONCRETE_MATERIAL)
        self.steel = file.createIfcMaterial(STEEL_MATERIAL)

    # -- helpers ---------------------------------------------------------

    def _bind(self, element):
        self.file.createIfcRelContainedInSpatialStructure(
            create_ifc_guid(), self.owner,
            RelatingStructure=self.storey,
            RelatedElements=[element],
        )

    def _associate(self, element, material):
        self.file.createIfcRelAssociatesMaterial(
            GlobalId=create_ifc_guid(),
            OwnerHistory=self.owner,
            Name=None,
            Description=None,
            RelatedObjects=[element],
            RelatingMaterial=material,
        )

    def _element_from_rep(self, ifc_class, name, shape_rep, extra=None):
        extra = extra or {}
        prod_def = self.file.createIfcProductDefinitionShape(None, None, [shape_rep])
        placement = self.file.createIfcLocalPlacement(
            self.storey.ObjectPlacement, _identity(self.mapper)
        )
        elem = self.file.create_entity(
            ifc_class,
            GlobalId=create_ifc_guid(),
            OwnerHistory=self.owner,
            Name=name,
            ObjectPlacement=placement,
            Representation=prod_def,
            Tag=name,
            **extra,
        )
        self._bind(elem)
        return elem

    def _add_property_set(self, element, name, props):
        values = []
        for prop_name, prop_value in props.items():
            if isinstance(prop_value, str):
                nominal = self.file.createIfcLabel(prop_value)
            elif isinstance(prop_value, int):
                nominal = self.file.createIfcInteger(prop_value)
            else:
                nominal = self.file.createIfcReal(float(prop_value))
            values.append(self.file.createIfcPropertySingleValue(
                Name=prop_name,
                Description=None,
                NominalValue=nominal,
                Unit=None,
            ))
        pset = self.file.createIfcPropertySet(
            GlobalId=create_ifc_guid(),
            OwnerHistory=self.owner,
            Name=name,
            Description=None,
            HasProperties=values,
        )
        self.file.createIfcRelDefinesByProperties(
            GlobalId=create_ifc_guid(),
            OwnerHistory=self.owner,
            Name=None,
            Description=None,
            RelatedObjects=[element],
            RelatingPropertyDefinition=pset,
        )

    def _add_quantities(self, element, quantities):
        qto_values = []
        for kind, qname, value in quantities:
            if kind == "volume":
                qto_values.append(self.file.createIfcQuantityVolume(
                    Name=qname, Description=None, Unit=None,
                    VolumeValue=float(value),
                ))
            elif kind == "count":
                qto_values.append(self.file.createIfcQuantityCount(
                    Name=qname, Description=None, Unit=None,
                    CountValue=int(value),
                ))
            elif kind == "length":
                qto_values.append(self.file.createIfcQuantityLength(
                    Name=qname, Description=None, Unit=None,
                    LengthValue=float(value),
                ))
            elif kind == "weight":
                qto_values.append(self.file.createIfcQuantityWeight(
                    Name=qname, Description=None, Unit=None,
                    WeightValue=float(value),
                ))
        qto = self.file.createIfcElementQuantity(
            GlobalId=create_ifc_guid(),
            OwnerHistory=self.owner,
            Name="BaseQuantities",
            Description=None,
            MethodOfMeasurement="BaseQuantities",
            Quantities=qto_values,
        )
        self.file.createIfcRelDefinesByProperties(
            GlobalId=create_ifc_guid(),
            OwnerHistory=self.owner,
            Name=None,
            Description=None,
            RelatedObjects=[element],
            RelatingPropertyDefinition=qto,
        )

    # -- concrete --------------------------------------------------------

    def _concrete_rep(self, meta):
        kind = meta["kind"]
        origin = [v * _IFC_UNIT_SCALE for v in meta["origin"]]

        if kind == "cylinder":
            radius = _mm(meta["radius"])
            height = _mm(meta["height"])
            profile = self.mapper.create_circular_profile(radius)
            solid = self.mapper.create_extruded_solid(
                profile, height, _identity(self.mapper)
            )
            place = self.mapper.create_axis2placement_3d(origin)
            rep = self.file.createIfcShapeRepresentation(
                self.mapper._context3d, "Body", "SweptSolid", [solid]
            )
            volume = math.pi * radius * radius * height
            length = height
        elif kind == "box":
            lx = _mm(meta["length"])
            ly = _mm(meta["width"])
            hz = _mm(meta["height"])
            profile = self.mapper.create_rectangular_profile(lx, ly)
            solid = self.mapper.create_extruded_solid(
                profile, hz, _identity(self.mapper)
            )
            place = self.mapper.create_axis2placement_3d(origin)
            rep = self.file.createIfcShapeRepresentation(
                self.mapper._context3d, "Body", "SweptSolid", [solid]
            )
            volume = lx * ly * hz
            length = hz
        elif kind == "trapezoid":
            bw = _mm(meta["bottom_width"])
            tw = _mm(meta["top_width"])
            depth = _mm(meta["depth"])
            length_m = _mm(meta["length"])
            pts = [(-bw / 2.0, 0.0), (bw / 2.0, 0.0),
                   (tw / 2.0, depth), (-tw / 2.0, depth)]
            profile = self.mapper.create_polygonal_profile(pts, meta["name"])
            solid = self.mapper.create_extruded_solid(
                profile, length_m, _identity(self.mapper)
            )
            # Local X -> global X, local Y -> global Z, local Z -> global -Y.
            # Start at the +Y end so the extrusion runs towards -Y.
            place = self.mapper.create_axis2placement_3d(
                (origin[0], origin[1] + length_m / 2.0, origin[2]),
                z_dir=(0.0, -1.0, 0.0),
                x_dir=(1.0, 0.0, 0.0),
            )
            rep = self.file.createIfcShapeRepresentation(
                self.mapper._context3d, "Body", "SweptSolid", [solid]
            )
            volume = ((bw + tw) / 2.0) * depth * length_m
            length = length_m
        else:
            raise ValueError(f"Unknown substructure kind: {kind}")
        return rep, place, volume, length

    def write_concrete(self):
        for meta in self.layout.get("components", []):
            rep, place, volume, length = self._concrete_rep(meta)
            self.mapper.apply_color(rep, CONCRETE_RGB)

            extra = {}
            if meta.get("ifc_class") == "IfcPile":
                extra["PredefinedType"] = meta.get("pile_type", "BORED")
            elif meta.get("ifc_class") == "IfcFooting":
                extra["PredefinedType"] = meta.get("predefined_type", "PAD_FOOTING")

            prod_def = self.file.createIfcProductDefinitionShape(None, None, [rep])
            placement = self.file.createIfcLocalPlacement(
                self.storey.ObjectPlacement, place
            )
            elem = self.file.create_entity(
                meta["ifc_class"],
                GlobalId=create_ifc_guid(),
                OwnerHistory=self.owner,
                Name=meta["name"],
                ObjectPlacement=placement,
                Representation=prod_def,
                Tag=meta["name"],
                **extra,
            )
            self._bind(elem)
            self._associate(elem, self.concrete)

            props = {
                "ComponentType": meta.get("kind", ""),
                "ConcreteGrade": meta.get("concrete_grade", CONCRETE_MATERIAL),
            }
            for key in ("diameter", "height", "length", "width", "depth",
                        "top_width", "bottom_width", "main_bar_diameter",
                        "tie_bar_diameter", "cover"):
                if key in meta:
                    props[key] = float(meta[key])
            self._add_property_set(elem, "Pset_OsdagBridgeSubstructure", props)
            self._add_quantities(elem, [
                ("volume", "NetVolume", volume),
                ("length", "Length", length),
                ("count", "Count", 1),
            ])

    # -- reinforcement ---------------------------------------------------

    def _bar_item(self, bar):
        d_m = _mm(bar["diameter"])
        radius = d_m / 2.0
        if bar["kind"] == "line":
            p1 = [v * _IFC_UNIT_SCALE for v in bar["p1"]]
            p2 = [v * _IFC_UNIT_SCALE for v in bar["p2"]]
            dx, dy, dz = (p2[0] - p1[0], p2[1] - p1[1], p2[2] - p1[2])
            length = math.sqrt(dx * dx + dy * dy + dz * dz)
            if length <= 0:
                raise ValueError("Zero length rebar segment in IFC export")
            z_dir = (dx / length, dy / length, dz / length)
            x_dir = _orthogonal_x(z_dir)
            place = self.mapper.create_axis2placement_3d(p1, z_dir=z_dir, x_dir=x_dir)
            profile = self.mapper.create_circular_profile(radius)
            # The solid's own placement carries the bar's world position.
            solid = self.mapper.create_extruded_solid(profile, length, place)
            return solid, length
        elif bar["kind"] == "ring":
            center = [v * _IFC_UNIT_SCALE for v in bar["center"]]
            ring_radius = _mm(bar["radius"])
            place = self.mapper.create_axis2placement_3d(center)
            solid = self.mapper.create_revolved_circular_solid(
                radius, ring_radius, place
            )
            return solid, 2.0 * math.pi * ring_radius
        raise ValueError(f"Unknown bar kind: {bar['kind']}")

    def write_rebar(self):
        for group in self.layout.get("rebar_groups", []):
            items = []
            total_length = 0.0
            count = 0
            nominal_d = _mm(group["diameter"])
            for bar in group["bars"]:
                item, length = self._bar_item(bar)
                items.append(item)
                total_length += length
                count += 1

            rep = self.file.createIfcShapeRepresentation(
                self.mapper._context3d, "Body", "SweptSolid", items
            )
            self.mapper.apply_color(rep, REBAR_RGB)
            prod_def = self.file.createIfcProductDefinitionShape(None, None, [rep])
            placement = self.file.createIfcLocalPlacement(
                self.storey.ObjectPlacement, _identity(self.mapper)
            )

            bar_length = total_length / count if count else 0.0
            area = math.pi * (nominal_d / 2.0) ** 2
            weight = total_length * area * 7850.0
            ptype = group.get("bar_type", "MAIN")
            if ptype not in ("MAIN", "SHEAR", "RING", "ANCHORING", "LIGATURE"):
                ptype = "MAIN"

            elem = self.file.create_entity(
                "IfcReinforcingBar",
                GlobalId=create_ifc_guid(),
                OwnerHistory=self.owner,
                Name=group["name"],
                ObjectPlacement=placement,
                Representation=prod_def,
                Tag=group["name"],
                SteelGrade=STEEL_MATERIAL,
                NominalDiameter=nominal_d,
                CrossSectionArea=area,
                BarLength=bar_length,
                PredefinedType=ptype,
            )
            self._bind(elem)
            self._associate(elem, self.steel)
            self._add_property_set(elem, "Pset_OsdagBridgeReinforcement", {
                "Component": group.get("component", ""),
                "BarType": ptype,
                "NominalDiameter": float(group["diameter"]),
                "BarCount": int(count),
            })
            self._add_quantities(elem, [
                ("count", "Count", count),
                ("length", "Length", total_length),
                ("weight", "Weight", weight),
            ])


def export_substructure(ifc_file, mapper, owner_history, storey, layout):
    """Write all substructure concrete members and rebar groups into ``ifc_file``."""
    if not layout or not layout.get("components"):
        return
    writer = _Writer(ifc_file, mapper, owner_history, storey, layout)
    writer.write_concrete()
    writer.write_rebar()
