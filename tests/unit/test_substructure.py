"""
Tests for the OsdagBridge parametric substructure and its IFC integration.

These tests need pythonocc-core and ifcopenshell, which are provided by the
project's conda environment.  They are skipped automatically when those
optional dependencies are unavailable.
"""

import pytest

pytest.importorskip("OCC.Core.BRepPrimAPI")
ifcopenshell = pytest.importorskip("ifcopenshell")

from OCC.Core.Bnd import Bnd_Box
from OCC.Core.BRepBndLib import brepbndlib
from OCC.Core.BRepCheck import BRepCheck_Analyzer

from osdagbridge.core.bridge_components.foundation.pile.builder import build_pile
from osdagbridge.core.bridge_components.foundation.pile_cap.builder import build_pile_cap
from osdagbridge.core.bridge_components.sub_structure.assembly import (
    SubstructureParameters,
    build_substructure,
)
from osdagbridge.core.bridge_components.sub_structure.pedestal.builder import build_pedestal
from osdagbridge.core.bridge_components.sub_structure.pier.builder import build_pier
from osdagbridge.core.bridge_components.sub_structure.pier_cap.builder import (
    build_pier_cap,
    inset_half_width,
)
from osdagbridge.core.bridge_types.plate_girder.cad_generator import PlateGirderCADGenerator
from osdagbridge.core.bridge_types.plate_girder.dto import (
    BridgeParametersDTO,
    GirderSegmentDTO,
    ISectionDimsDTO,
    SectionDimsDTO,
    ShearStudParamsDTO,
)
from osdagbridge.core.ifc_export_bridge.export_ifc_handler import PlateGirderIfcExportHandler


def _bbox(shape):
    # AddOptimal gives exact analytic bounds; the simple Add() over-estimates
    # the bounding box of full tori (circular stirrups).
    box = Bnd_Box()
    brepbndlib.AddOptimal(shape, box, False, False)
    return box.Get()


def _dto(span=20_000, include_longitudinal=False):
    return BridgeParametersDTO(
        steel_grade="E250",
        concrete_grade="M30",
        span_length_L=span,
        girder_section_d=900,
        girder_section_bf=500,
        girder_section_bf_b=500,
        girder_section_tf=260,
        girder_section_tf_b=260,
        girder_section_tw=100,
        num_girders=4,
        girder_spacing=2_500,
        skew_angle=0,
        carriageway_width=7_000,
        deck_thickness=400,
        footpath_config="BOTH",
        footpath_width=1_500,
        railing_width=300,
        barrier_type="Rigid",
        crash_barrier_subtype="IRC-5R",
        enable_median=False,
        median_type="Raised Kerb",
        rail_count=3,
        railing_type="rcc",
        include_intermediate_stiffeners=True,
        intermediate_stiffener_spacing=2_000,
        intermediate_stiffener_thickness=20,
        intermediate_stiffener_outstand=None,
        num_end_stiffener_pairs=4,
        end_stiffener_thickness=30,
        end_stiffener_outstand=None,
        include_longitudinal_stiffeners=include_longitudinal,
        num_longitudinal_stiffeners=2,
        longitudinal_stiffener_thickness=20,
        longitudinal_stiffener_outstand=None,
        cross_bracing_spacing=4_000,
        bracing_type="X",
        x_bracket_option="BOTH",
        k_top_bracket=True,
        diagonal_section_type="ANGLE",
        diagonal_section_dims=SectionDimsDTO(100, 50, "LONGER_LEG"),
        diagonal_thickness=5,
        top_chord_section_type="DOUBLE_CHANNEL",
        top_chord_section_dims=SectionDimsDTO(80, 40, "LONGER_LEG"),
        top_chord_thickness=5,
        bottom_chord_section_type="ANGLE",
        bottom_chord_section_dims=SectionDimsDTO(80, 40, "LONGER_LEG"),
        bottom_chord_thickness=5,
        end_diaphragm_type="Cross Bracing",
        end_diaphragm_spacing=100,
        end_diaphragm_bracing_type="K",
        end_diaphragm_diagonal_section_type="ANGLE",
        end_diaphragm_diagonal_section_dims=SectionDimsDTO(100, 50, "LONGER_LEG"),
        end_diaphragm_diagonal_thickness=5,
        end_diaphragm_top_chord_section_type="CHANNEL",
        end_diaphragm_top_chord_section_dims=SectionDimsDTO(80, 40, "LONGER_LEG"),
        end_diaphragm_top_chord_thickness=5,
        end_diaphragm_bottom_chord_section_type="ANGLE",
        end_diaphragm_bottom_chord_section_dims=SectionDimsDTO(80, 40, "LONGER_LEG"),
        end_diaphragm_bottom_chord_thickness=5,
        end_diaphragm_section="I_SECTION",
        end_diaphragm_dims=ISectionDimsDTO(800, 250, 12, 100),
        shear_stud_params=ShearStudParamsDTO(50, 70, 150, 50, 4, 305, 500),
        girder_segments=[GirderSegmentDTO(span, 900, 100, 260, 260, 500, 500)],
        girder_segments_dict=None,
    )


def test_pier_dimensions_and_rebar():
    pier = build_pier()
    assert not pier["concrete"].IsNull()
    assert BRepCheck_Analyzer(pier["concrete"]).IsValid()
    assert len(pier["bars"]) > 20
    xmin, ymin, zmin, xmax, ymax, zmax = _bbox(pier["concrete"])
    assert xmax - xmin == pytest.approx(800, abs=1e-6)
    assert ymax - ymin == pytest.approx(800, abs=1e-6)
    assert zmax - zmin == pytest.approx(3000, abs=1e-6)
    # Rebar stays inside the concrete with the requested cover.
    rxmin, rymin, rzmin, rxmax, rymax, rzmax = _bbox(pier["rebar"])
    assert rxmin >= xmin + 40 - 1e-6
    assert rxmax <= xmax - 40 + 1e-6
    assert rzmin >= zmin + 40 - 1e-6
    assert rzmax <= zmax - 40 + 1e-6


def test_pier_cap_dimensions_and_trapezoid():
    cap = build_pier_cap(length=14_000)
    xmin, ymin, zmin, xmax, ymax, zmax = _bbox(cap["concrete"])
    # Top (widest) section governs the bounding box.
    assert xmax - xmin == pytest.approx(3000, abs=1e-6)
    assert ymax - ymin == pytest.approx(14_000, abs=1e-6)
    assert zmax - zmin == pytest.approx(600, abs=1e-6)
    assert cap["meta"]["top_width"] == 3000
    assert cap["meta"]["bottom_width"] == 1200
    assert BRepCheck_Analyzer(cap["concrete"]).IsValid()
    rxmin, rymin, rzmin, rxmax, rymax, rzmax = _bbox(cap["rebar"])
    assert rymin >= ymin + 40 - 1e-6
    assert rymax <= ymax - 40 + 1e-6
    assert rzmin >= zmin + 40 - 1e-6
    assert rzmax <= zmax - 40 + 1e-6


def test_pier_cap_rebar_keeps_cover_to_sloping_faces():
    # A bounding box cannot see the taper, so check every bar end against the
    # section offset inwards by the cover plus the bar radius.
    cap = build_pier_cap(length=6_000)
    for bar in cap["bars"]:
        inset = 40 + bar["diameter"] / 2
        for x, _, z in (bar["p1"], bar["p2"]):
            assert inset - 1e-6 <= z <= 600 - inset + 1e-6
            assert abs(x) <= inset_half_width(z, inset, 1200, 3000, 600) + 1e-6


def test_main_bar_pitch_does_not_exceed_requested_spacing():
    cap = build_pile_cap(main_spacing=150)
    mat = cap["bar_groups"][0]["bars"]
    bottom_x_bars = sorted(
        b["p1"][1] for b in mat
        if b["p1"][1] == b["p2"][1] and b["p1"][2] == mat[0]["p1"][2]
    )
    pitches = [b - a for a, b in zip(bottom_x_bars, bottom_x_bars[1:])]
    assert pitches and max(pitches) <= 150 + 1e-6


def test_pile_and_pile_cap_dimensions():
    pile = build_pile()
    xmin, ymin, zmin, xmax, ymax, zmax = _bbox(pile["concrete"])
    assert xmax - xmin == pytest.approx(400, abs=1e-6)
    assert zmax - zmin == pytest.approx(5000, abs=1e-6)
    assert BRepCheck_Analyzer(pile["concrete"]).IsValid()

    cap = build_pile_cap()
    xmin, ymin, zmin, xmax, ymax, zmax = _bbox(cap["concrete"])
    assert xmax - xmin == pytest.approx(2200, abs=1e-6)
    assert ymax - ymin == pytest.approx(1200, abs=1e-6)
    assert zmax - zmin == pytest.approx(600, abs=1e-6)
    assert BRepCheck_Analyzer(cap["concrete"]).IsValid()


def test_pedestal_dimensions():
    ped = build_pedestal()
    xmin, ymin, zmin, xmax, ymax, zmax = _bbox(ped["concrete"])
    assert xmax - xmin == pytest.approx(600, abs=1e-6)
    assert ymax - ymin == pytest.approx(400, abs=1e-6)
    assert zmax - zmin == pytest.approx(150, abs=1e-6)
    # Four vertical bars plus at least one closed tie (four bars).
    assert len(ped["bars"]) >= 8


def test_assembly_counts_and_coordinate_conversion():
    build = build_substructure(
        span_length=25_000,
        deck_width=15_000,
        soffit_z=-1540,
        model_offset=(12_500, 0, 1540),
    )
    assert build.summary["pier_count"] == 2
    # Per bent: cap, 2 default pedestals, pier, pile cap, 4 piles.
    assert build.summary["component_count"] == 18
    assert len(build.concrete) == 18
    assert len(build.rebar) == 18
    assert build.summary["bar_count"] > 900
    assert build.summary["concrete_m3"] > 0
    assert build.summary["steel_kg"] > 0

    # Piles are 2x2 at 600 mm c/c under each pier.
    components = build.layout["components"]
    piles = [c for c in components if c["ifc_class"] == "IfcPile"]
    assert len(piles) == 8
    bent_1 = sorted((p["origin"][0], p["origin"][1]) for p in piles if p["bent"] == 1)
    assert bent_1 == [(-12_800, -300), (-12_800, 300), (-12_200, -300), (-12_200, 300)]

    # Members stack without gaps from the pile toe up to the girder soffit.
    top = {c["name"]: c["origin"][2] + c.get("height", c.get("depth")) for c in components}
    base = {c["name"]: c["origin"][2] for c in components}
    assert top["Pile 1-1"] == pytest.approx(base["Pile Cap 1"])
    assert top["Pile Cap 1"] == pytest.approx(base["Pier 1"])
    assert top["Pier 1"] == pytest.approx(base["Pier Cap 1"])
    assert top["Pier Cap 1"] == pytest.approx(base["Pedestal 1-1"])
    assert top["Pedestal 1-1"] == pytest.approx(-1540)

    # Layout stays in the task frame while shapes are translated into the
    # bridge CAD frame.
    meta_cap = next(c for c in components if c["name"] == "Pier Cap 1")
    assert meta_cap["origin"][0] == pytest.approx(-12_500, abs=1e-6)
    assert build.layout["storey_offset"] == [12_500, 0, 1540]
    xmin, *_ = _bbox(build.concrete[0])
    assert xmin == pytest.approx(-1_500, abs=1e-6)


def test_pedestals_follow_bearing_lines():
    lines = [-3_750, -1_250, 1_250, 3_750]
    build = build_substructure(
        span_length=20_000, deck_width=10_000, soffit_z=-1_500, bearing_ys=lines,
    )
    pedestals = [c for c in build.layout["components"]
                 if c["name"].startswith("Pedestal 1-")]
    assert [c["origin"][1] for c in pedestals] == lines

    with pytest.raises(ValueError, match="too short"):
        build_substructure(
            span_length=20_000, deck_width=10_000, soffit_z=-1_500,
            bearing_ys=[-6_000, 6_000],
        )


def test_full_cad_and_ifc_export(tmp_path):
    generator = PlateGirderCADGenerator()
    design = _dto()
    data = generator.generate(design)

    # Four girders, so four pedestals per bent: 2 x (1 + 4 + 1 + 1 + 4).
    assert len(data["substructure_concrete"]) == 22
    assert len(data["substructure_rebar"]) == 22
    assert generator.substructure_layout is not None

    # Pedestals finish exactly at the underside of the bottom flanges.
    *_, pedestal_top = _bbox(data["substructure_concrete"][1])
    _, _, girder_soffit, *_ = _bbox(data["girder_bottom_flanges"][0])
    assert pedestal_top == pytest.approx(girder_soffit, abs=1e-6)
    assert data["substructure_summary"]["bar_count"] > 700

    path = str(tmp_path / "bridge.ifc")
    messages = []
    handler = PlateGirderIfcExportHandler(
        generator, path, lambda ok, msg: messages.append((ok, msg))
    )
    handler.export()
    assert messages and messages[0][0], messages

    ifc = ifcopenshell.open(path)
    assert len(ifc.by_type("IfcPile")) == 8
    assert len(ifc.by_type("IfcColumn")) == 2
    assert len(ifc.by_type("IfcFooting")) == 2
    assert len(ifc.by_type("IfcBeam")) == 2
    assert len(ifc.by_type("IfcBuildingElementProxy")) == 8
    assert len(ifc.by_type("IfcReinforcingBar")) == 44

    # The superstructure is still exported alongside the substructure.
    assert len(ifc.by_type("IfcPlate")) > 0
    assert len(ifc.by_type("IfcSlab")) > 0

    substoreys = [s for s in ifc.by_type("IfcBuildingStorey") if s.Name == "Substructure"]
    assert len(substoreys) == 1

    # Every substructure element has geometry, a material and quantities.
    elements = [
        e for cls in ("IfcPile", "IfcColumn", "IfcFooting", "IfcBeam",
                      "IfcBuildingElementProxy", "IfcReinforcingBar")
        for e in ifc.by_type(cls)
    ]
    assert len(elements) == 22 + 44
    for element in elements:
        assert element.Representation is not None
        assert any(r.is_a("IfcRelAssociatesMaterial") for r in element.HasAssociations)
        definitions = [r.RelatingPropertyDefinition for r in element.IsDefinedBy]
        assert any(d.is_a("IfcElementQuantity") for d in definitions)
    materials = [m.Name for m in ifc.by_type("IfcMaterial")]
    assert "Concrete M30" in materials
    assert "Fe500" in materials

    # Run the IFC4 schema validator when the optional lark dependency is
    # installed.  A missing lark must not turn this into a false failure.
    try:
        from ifcopenshell import validate as ifc_validate
    except ImportError:
        ifc_validate = None
    if ifc_validate is not None:
        logger = ifc_validate.json_logger()
        ifc_validate.validate(ifc, logger)
        errors = [s for s in logger.statements if s.get("level") == "error"]
        assert errors == [], errors[:5]
