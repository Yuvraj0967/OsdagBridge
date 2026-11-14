"""
Tests for the OsdagBridge parametric substructure and its IFC integration.

These tests need pythonocc-core and ifcopenshell, which are provided by the
project's conda environment.  They are skipped automatically when those
optional dependencies are unavailable.
"""

import os
import tempfile

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
from osdagbridge.core.bridge_components.sub_structure.pier_cap.builder import build_pier_cap
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
    assert rxmin >= xmin + 40 - 1e-6
    assert rxmax <= xmax - 40 + 1e-6
    assert rzmin >= zmin + 40 - 1e-6
    assert rzmax <= zmax - 40 + 1e-6


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
    assert build.summary["component_count"] == 18
    assert len(build.concrete) == 18
    assert len(build.rebar) == 18
    assert build.summary["bar_count"] > 900
    assert build.summary["concrete_m3"] > 0
    assert build.summary["steel_kg"] > 0

    # Piles are 2x2 at 600 mm c/c under each pier.
    piles = [c for c in build.components if c["kind"] == "cylinder" and c["name"].startswith("Pile")]
    assert len(piles) == 8
    xs = sorted({round(p["origin"][0], 3) for p in piles})
    assert len(xs) == 4

    # Layout stays in the task frame while shapes are translated into the
    # bridge CAD frame.
    meta_cap = next(c for c in build.components if c["name"] == "Pier Cap 1")
    assert meta_cap["origin"][0] == pytest.approx(-11_300, abs=1e-6)
    assert build.summary["layout"]["storey_offset"] == [12_500, 0, 1540]
    assert build.summary["layout"]["components"][0]["name"] == "Pier Cap 1"


def test_full_cad_and_ifc_export():
    generator = PlateGirderCADGenerator()
    design = _dto()
    data = generator.generate(design)

    assert len(data["substructure_concrete"]) == 18
    assert len(data["substructure_rebar"]) == 18
    assert generator.substructure_layout is not None
    assert data["substructure_summary"]["bar_count"] > 700

    fd, path = tempfile.mkstemp(suffix=".ifc")
    os.close(fd)
    try:
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
        assert len(ifc.by_type("IfcBuildingElementProxy")) == 4
        assert len(ifc.by_type("IfcReinforcingBar")) == 36

        # The superstructure is still exported alongside the substructure.
        assert len(ifc.by_type("IfcPlate")) > 0
        assert len(ifc.by_type("IfcSlab")) > 0

        substoreys = [s for s in ifc.by_type("IfcBuildingStorey") if s.Name == "Substructure"]
        assert len(substoreys) == 1

        # Every substructure element is linked to a material and has quantities.
        elems = ifc.by_type("IfcPile") + ifc.by_type("IfcColumn") + ifc.by_type("IfcFooting")
        assert elems
        for elem in elems:
            assert elem.Representation is not None
        quantities = ifc.by_type("IfcElementQuantity")
        assert len(quantities) >= 18
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
    finally:
        if os.path.exists(path):
            os.remove(path)
