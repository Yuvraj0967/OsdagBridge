"""
Headless demonstration of the OsdagBridge substructure.

This script is the reproducible counterpart of the GUI workflow:

    File -> Save 3D CAD Model -> Save as type: .ifc

It builds the complete plate-girder bridge (superstructure + substructure),
exports the IFC file, validates it, and renders PNG inspection views using
pythonOCC's offscreen viewer.  It needs no X server and no Qt.

Run from the repository root with the project's conda environment:

    python demo/run_demo.py

Artifacts are written to ``artifacts/``.
"""

import argparse
import json
import os
import sys

# Allow running directly from a checkout without installing the package.
_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.join(os.path.dirname(_HERE), "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

import ifcopenshell  # noqa: E402

from osdagbridge.core.bridge_types.plate_girder.cad_generator import (  # noqa: E402
    PlateGirderCADGenerator,
)
from osdagbridge.core.bridge_types.plate_girder.dto import (  # noqa: E402
    BridgeParametersDTO,
    GirderSegmentDTO,
    ISectionDimsDTO,
    SectionDimsDTO,
    ShearStudParamsDTO,
)
from osdagbridge.core.ifc_export_bridge.export_ifc_handler import (  # noqa: E402
    PlateGirderIfcExportHandler,
)


def demo_design(span=25_000):
    """A 25 m two-lane plate-girder bridge on three girders."""
    return BridgeParametersDTO(
        steel_grade="E250",
        concrete_grade="M30",
        span_length_L=span,
        girder_section_d=1_400,
        girder_section_bf=450,
        girder_section_bf_b=450,
        girder_section_tf=40,
        girder_section_tf_b=40,
        girder_section_tw=16,
        num_girders=3,
        girder_spacing=2_900,
        skew_angle=0,
        carriageway_width=7_500,
        deck_thickness=250,
        footpath_config="NONE",
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
        intermediate_stiffener_thickness=12,
        intermediate_stiffener_outstand=None,
        num_end_stiffener_pairs=4,
        end_stiffener_thickness=20,
        end_stiffener_outstand=None,
        include_longitudinal_stiffeners=True,
        num_longitudinal_stiffeners=2,
        longitudinal_stiffener_thickness=12,
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
        girder_segments=[GirderSegmentDTO(span, 1_400, 16, 40, 40, 450, 450)],
        girder_segments_dict=None,
    )


# ---------------------------------------------------------------------------
# rendering
# ---------------------------------------------------------------------------

SUPERSTRUCTURE_KEYS = [
    ("girder_web", (0.18, 0.18, 0.14)),
    ("girder_top_flanges", (0.52, 0.52, 0.39)),
    ("girder_bottom_flanges", (0.52, 0.52, 0.39)),
    ("stiffeners", (0.28, 0.28, 0.21)),
    ("cross_bracings", (0.23, 0.23, 0.23)),
    ("deck_slab", (0.55, 0.55, 0.55)),
    ("crash_barriers", (0.22, 0.22, 0.22)),
    ("crash_barrier_w_beams", (0.50, 0.50, 0.50)),
    ("median_barriers", (0.22, 0.22, 0.22)),
    ("median_w_beams", (0.50, 0.50, 0.50)),
    ("railings", (0.47, 0.47, 0.47)),
]

CONCRETE_COLOR = (0.45, 0.48, 0.52)
REBAR_COLOR = (0.30, 0.12, 0.02)


def _as_list(value):
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]


class OffscreenRenderer:
    def __init__(self, width=1600, height=1000):
        from OCC.Display.OCCViewer import Viewer3d

        self.viewer = Viewer3d()
        self.viewer.Create()
        self.viewer.SetSize(width, height)
        self.viewer.SetModeShaded()
        self.viewer.set_bg_gradient_color([248, 249, 252], [178, 190, 208])

    def _color(self, rgb):
        from OCC.Core.Quantity import Quantity_Color, Quantity_TOC_RGB

        return Quantity_Color(rgb[0], rgb[1], rgb[2], Quantity_TOC_RGB)

    def _material(self):
        from OCC.Core.Graphic3d import Graphic3d_NOM_PLASTIC

        # Without an explicit material OCC's default shading washes the
        # supplied colours out almost completely on a light background.
        return Graphic3d_NOM_PLASTIC

    def erase(self):
        self.viewer.EraseAll()

    def display(self, shapes, rgb, transparency=None):
        for shape in _as_list(shapes):
            if shape is None:
                continue
            kwargs = {
                "material": self._material(),
                "color": self._color(rgb),
                "update": False,
            }
            if transparency is not None:
                kwargs["transparency"] = float(transparency)
            self.viewer.DisplayShape(shape, **kwargs)

    def save(self, path, view="iso"):
        view_fn = {
            "iso": self.viewer.View_Iso,
            "front": self.viewer.View_Front,
            "right": self.viewer.View_Right,
            "top": self.viewer.View_Top,
        }[view]
        view_fn()
        self.viewer.FitAll()
        self.viewer.ExportToImage(path)


def render_views(generator, cad_data, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    renderer = OffscreenRenderer()
    paths = {}

    # 1. Substructure only, concrete semi-transparent and rebar visible.
    renderer.erase()
    # The viewer uses 0.65 transparency for the required 35 % opacity.  These
    # still frames use a little more opacity so the shading reads clearly on a
    # white page while the rebar stays visible.
    renderer.display(cad_data["substructure_concrete"], CONCRETE_COLOR, 0.45)
    renderer.display(cad_data["substructure_rebar"], REBAR_COLOR)
    paths["substructure_iso"] = os.path.join(out_dir, "substructure_iso.png")
    renderer.save(paths["substructure_iso"], "iso")

    # 2. Front elevation of the substructure.
    paths["substructure_front"] = os.path.join(out_dir, "substructure_front.png")
    renderer.save(paths["substructure_front"], "front")

    # 3. Detailed pier bent: one pier cap, its pedestals, pier and rebar.
    layout_components = generator.substructure_layout["components"]
    keep = [
        i for i, meta in enumerate(layout_components)
        if meta["bent"] == 1
    ]
    renderer.erase()
    renderer.display([cad_data["substructure_concrete"][i] for i in keep],
                     CONCRETE_COLOR, 0.30)
    renderer.display([cad_data["substructure_rebar"][i] for i in keep], REBAR_COLOR)
    paths["pier_detail"] = os.path.join(out_dir, "pier_detail.png")
    renderer.save(paths["pier_detail"], "iso")

    # 4. Complete bridge, superstructure + substructure.
    renderer.erase()
    for key, rgb in SUPERSTRUCTURE_KEYS:
        renderer.display(cad_data.get(key, []), rgb)
    renderer.display(cad_data["substructure_concrete"], CONCRETE_COLOR, 0.55)
    renderer.display(cad_data["substructure_rebar"], REBAR_COLOR)
    paths["full_bridge_iso"] = os.path.join(out_dir, "full_bridge_iso.png")
    renderer.save(paths["full_bridge_iso"], "iso")

    # 5. End view showing the transverse layout.
    paths["full_bridge_front"] = os.path.join(out_dir, "full_bridge_front.png")
    renderer.save(paths["full_bridge_front"], "front")

    return paths


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=os.path.join(os.path.dirname(_HERE), "artifacts"))
    parser.add_argument("--span", type=float, default=25_000)
    parser.add_argument("--no-render", action="store_true")
    args = parser.parse_args()

    os.makedirs(args.out, exist_ok=True)

    print("Building plate-girder bridge CAD ...")
    design = demo_design(span=args.span)
    generator = PlateGirderCADGenerator()
    cad_data = generator.generate(design)
    summary = dict(cad_data["substructure_summary"])
    print(
        f"  superstructure keys: {len(cad_data)} | "
        f"substructure elements: {len(cad_data['substructure_concrete'])} | "
        f"rebar cages: {len(cad_data['substructure_rebar'])}"
    )
    print(
        f"  concrete: {summary['concrete_m3']:.2f} m3 | "
        f"rebar: {summary['rebar_m']:.1f} m | "
        f"steel: {summary['steel_kg']:.0f} kg | "
        f"bars: {summary['bar_count']}"
    )

    ifc_path = os.path.join(args.out, "osdagbridge_substructure.ifc")
    messages = []
    print("Exporting IFC (superstructure + substructure) ...")
    handler = PlateGirderIfcExportHandler(
        generator, ifc_path, lambda ok, msg: messages.append((ok, msg))
    )
    handler.export()
    if not messages or not messages[0][0]:
        raise RuntimeError(f"IFC export failed: {messages}")

    ifc = ifcopenshell.open(ifc_path)
    counts = {
        "IfcProject": len(ifc.by_type("IfcProject")),
        "IfcPile": len(ifc.by_type("IfcPile")),
        "IfcColumn": len(ifc.by_type("IfcColumn")),
        "IfcBeam": len(ifc.by_type("IfcBeam")),
        "IfcFooting": len(ifc.by_type("IfcFooting")),
        "IfcBuildingElementProxy": len(ifc.by_type("IfcBuildingElementProxy")),
        "IfcReinforcingBar": len(ifc.by_type("IfcReinforcingBar")),
        "IfcElementQuantity": len(ifc.by_type("IfcElementQuantity")),
        "IfcPlate": len(ifc.by_type("IfcPlate")),
        "IfcSlab": len(ifc.by_type("IfcSlab")),
    }
    print("IFC entity counts:")
    for key, value in counts.items():
        print(f"  {key:28s} {value}")

    validation_errors = []
    try:
        from ifcopenshell import validate as ifc_validate

        logger = ifc_validate.json_logger()
        ifc_validate.validate(ifc, logger)
        validation_errors = list(logger.statements)
    except Exception as exc:  # validation is optional tooling
        print(f"  schema validation unavailable: {exc}")

    print(f"IFC schema validation: {len(validation_errors)} issue(s)")
    for item in validation_errors[:10]:
        print(f"  {item}")

    renders = {}
    if not args.no_render:
        print("Rendering offscreen inspection views ...")
        renders = render_views(generator, cad_data, args.out)
        for name, path in renders.items():
            print(f"  {name:20s} {path}")

    record = {
        "span_mm": args.span,
        "ifc_path": os.path.basename(ifc_path),
        "ifc_size_bytes": os.path.getsize(ifc_path),
        "ifc_counts": counts,
        "validation_error_count": len(validation_errors),
        "validation_errors": [str(e) for e in validation_errors[:20]],
        "summary": summary,
        "renders": {k: os.path.basename(v) for k, v in renders.items()},
    }
    with open(os.path.join(args.out, "summary.json"), "w", encoding="utf-8") as fh:
        json.dump(record, fh, indent=2)

    print(f"\nArtifacts written to {os.path.abspath(args.out)}")


if __name__ == "__main__":
    main()
    # OCC's offscreen GL context teardown can block under WSLg/llvmpipe after a
    # large model; the artifacts are already flushed, so exit without waiting.
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0)
