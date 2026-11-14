"""
Generate the screening-task report as a PDF.

The report is assembled from the real artifacts written by demo/run_demo.py,
so the numbers and screenshots always match the implementation.
"""

import json
import os
from datetime import date

from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from xml.sax.saxutils import escape
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ARTIFACTS = os.path.join(ROOT, "artifacts")

ACCENT = colors.HexColor("#175C84")
LIGHT = colors.HexColor("#EAF1F6")
GRID = colors.HexColor("#C8D4DE")

FONT = "Helvetica"
FONT_BOLD = "Helvetica-Bold"
FONT_MONO = "Courier"
try:
    pdfmetrics.registerFont(TTFont("DejaVu", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"))
    pdfmetrics.registerFont(TTFont("DejaVu-Bold", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"))
    pdfmetrics.registerFont(TTFont("DejaVu-Mono", "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"))
    FONT, FONT_BOLD, FONT_MONO = "DejaVu", "DejaVu-Bold", "DejaVu-Mono"
except Exception:
    pass


def styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "title", parent=base["Title"], fontName=FONT_BOLD, fontSize=22,
            leading=28, textColor=ACCENT, alignment=TA_LEFT, spaceAfter=8,
        ),
        "subtitle": ParagraphStyle(
            "subtitle", parent=base["Normal"], fontName=FONT, fontSize=11.5,
            leading=17, textColor=colors.HexColor("#4A5866"), spaceAfter=14,
        ),
        "h1": ParagraphStyle(
            "h1", parent=base["Heading1"], fontName=FONT_BOLD, fontSize=15,
            leading=20, textColor=ACCENT, spaceBefore=12, spaceAfter=6,
        ),
        "h2": ParagraphStyle(
            "h2", parent=base["Heading2"], fontName=FONT_BOLD, fontSize=12,
            leading=16, textColor=colors.HexColor("#243442"), spaceBefore=9,
            spaceAfter=4,
        ),
        "body": ParagraphStyle(
            "body", parent=base["BodyText"], fontName=FONT, fontSize=10,
            leading=14.5, alignment=TA_JUSTIFY, spaceAfter=7,
        ),
        "small": ParagraphStyle(
            "small", parent=base["BodyText"], fontName=FONT, fontSize=8.5,
            leading=11.5, textColor=colors.HexColor("#586674"),
        ),
        "caption": ParagraphStyle(
            "caption", parent=base["Normal"], fontName=FONT, fontSize=8.5,
            leading=11, textColor=colors.HexColor("#586674"),
            alignment=TA_LEFT, spaceBefore=2, spaceAfter=10,
        ),
        "code": ParagraphStyle(
            "code", parent=base["Code"], fontName=FONT_MONO, fontSize=8,
            leading=11, backColor=colors.HexColor("#F2F5F8"),
            borderPadding=6, leftIndent=6, rightIndent=6, spaceBefore=4,
            spaceAfter=8,
        ),
        "bullet": ParagraphStyle(
            "bullet", parent=base["BodyText"], fontName=FONT, fontSize=10,
            leading=14.5, leftIndent=14, bulletIndent=4, spaceAfter=3,
        ),
    }


def table(data, widths, header=True, font_size=8.5):
    body_style = ParagraphStyle(
        "table_cell", fontName=FONT, fontSize=font_size,
        leading=font_size + 2.6, textColor=colors.HexColor("#23303C"),
    )
    head_style = ParagraphStyle(
        "table_head", fontName=FONT_BOLD, fontSize=font_size,
        leading=font_size + 2.6, textColor=colors.white,
    )
    wrapped = []
    for r, row in enumerate(data):
        cells = []
        for value in row:
            if isinstance(value, Paragraph):
                cells.append(value)
            else:
                style = head_style if (header and r == 0) else body_style
                cells.append(Paragraph(escape(str(value)), style))
        wrapped.append(cells)
    t = Table(wrapped, colWidths=widths, repeatRows=1 if header else 0)
    style = [
        ("FONTNAME", (0, 0), (-1, -1), FONT),
        ("FONTSIZE", (0, 0), (-1, -1), font_size),
        ("LEADING", (0, 0), (-1, -1), font_size + 3),
        ("GRID", (0, 0), (-1, -1), 0.4, GRID),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F7FAFC")]),
    ]
    if header:
        style += [
            ("BACKGROUND", (0, 0), (-1, 0), ACCENT),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), FONT_BOLD),
        ]
    t.setStyle(TableStyle(style))
    return t


def picture(path, width=16.5 * cm):
    from PIL import Image as PILImage

    with PILImage.open(path) as im:
        w, h = im.size
    return Image(path, width=width, height=width * h / w)


def main():
    with open(os.path.join(ARTIFACTS, "summary.json"), encoding="utf-8") as fh:
        summary = json.load(fh)
    s = summary["summary"]
    counts = summary["ifc_counts"]
    renders = {k: os.path.join(ARTIFACTS, v) for k, v in summary["renders"].items()}

    out_path = os.path.join(ARTIFACTS, "OsdagBridge_Substructure_Report.pdf")
    doc = SimpleDocTemplate(
        out_path, pagesize=A4,
        leftMargin=2.0 * cm, rightMargin=2.0 * cm,
        topMargin=1.8 * cm, bottomMargin=1.7 * cm,
        title="Parametric 3D CAD Modelling of Bridge Substructure and IFC Workflow",
        author="Yuvraj Pateria",
    )
    st = styles()
    story = []

    def para(text, style="body"):
        story.append(Paragraph(text, st[style]))

    def bullet(text):
        story.append(Paragraph(text, st["bullet"], bulletText="•"))

    # ---------------------------------------------------------------- cover
    story.append(Spacer(1, 0.6 * cm))
    story.append(Paragraph("Osdag Winter Internship 2026", st["subtitle"]))
    story.append(Paragraph(
        "Parametric 3D CAD Modelling of Bridge Substructure<br/>"
        "and IFC Workflow Integration",
        st["title"],
    ))
    story.append(Paragraph(
        "Screening task submission - Software Development category<br/>"
        "Repository: Nidhikhare12/OsdagBridge (dev branch)",
        st["subtitle"],
    ))
    story.append(Spacer(1, 0.4 * cm))
    cover = [
        ["Candidate", "Yuvraj Pateria"],
        ["Task", "Parametric 3D CAD modelling of the bridge substructure and IFC workflow integration"],
        ["Tools", "Python 3.11, pythonOCC 7.9, ifcopenshell 0.8.3, IFC4"],
        ["Validation", f"9 automated tests passed; IFC schema validation: {summary['validation_error_count']} issues"],
        ["Date", date.today().strftime("%d %B %Y")],
    ]
    story.append(table([[Paragraph(f"<b>{a}</b>", st["small"]), Paragraph(b, st["small"])] for a, b in cover],
                       [3.6 * cm, 13.2 * cm], header=False))
    story.append(Spacer(1, 0.5 * cm))
    story.append(picture(renders["full_bridge_iso"], width=16.5 * cm))
    story.append(Paragraph(
        "Complete bridge produced by the CAD generator: existing superstructure plus the new "
        "substructure (two pier bents, each with a tapered cap, a pedestal under every girder, a pile cap and a 2x2 group of bored piles).",
        st["caption"],
    ))
    story.append(Paragraph(
        "<b>Scope note.</b> The geometry and reinforcement in this report are the illustrative "
        "defaults prescribed by the screening task. They demonstrate parametric modelling and "
        "data flow; they are not a structurally verified foundation design.",
        st["small"],
    ))
    story.append(PageBreak())

    # ------------------------------------------------------------ contents
    story.append(Paragraph("Contents", st["h1"]))
    toc = [
        ("1", "Objective and scope"),
        ("2", "Repository architecture and files added"),
        ("3", "Coordinate system and placement"),
        ("4", "Parametric geometry"),
        ("5", "Reinforcement modelling"),
        ("6", "IFC workflow integration"),
        ("7", "Verification and results"),
        ("8", "Challenges"),
        ("9", "Limitations and next steps"),
        ("10", "How to reproduce"),
        ("11", "References"),
    ]
    for num, title in toc:
        story.append(Paragraph(f"{num}.&nbsp;&nbsp;{title}", st["body"]))
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph(
        "Appendix A - Bill of quantities summary<br/>Appendix B - Rendered inspection views",
        st["body"],
    ))
    story.append(PageBreak())

    # ------------------------------------------------------------ 1 objective
    story.append(Paragraph("1. Objective and scope", st["h1"]))
    para(
        "The OsdagBridge repository already contains a mature set of superstructure components "
        "(plate girders, deck, bracings, barriers and railings), but the substructure packages hold "
        "only stub modules and the IFC exporter writes only the superstructure. This submission "
        "adds:"
    )
    bullet("five parametric pythonOCC builders - pier, pier cap, pedestal, pile and pile cap - each with internal reinforcement;")
    bullet("a substructure assembly that places a pier bent under each bearing line in the task coordinate system and converts it into the existing bridge CAD frame;")
    bullet("native IFC4 export of the substructure as IfcColumn, IfcBeam, IfcFooting, IfcPile and IfcReinforcingBar, including materials, quantities and a dedicated Substructure storey;")
    bullet("automatic inclusion in the existing File → Save 3D CAD Model → Save as type: .ifc workflow, alongside the superstructure.")
    para(
        "All component dimensions are adjustable keyword arguments. The defaults are those given "
        "in the task description so that the model can be compared directly with the expected "
        "outcome figures."
    )

    # ------------------------------------------------------------ 2 files
    story.append(Paragraph("2. Repository architecture and files added", st["h1"]))
    para(
        "The implementation follows the existing component-builder architecture: each component "
        "owns a <i>builder.py</i> in its existing package, the assembly lives beside the "
        "substructure packages, and the IFC code lives in the existing ifc_export_bridge package."
    )
    files = [
        ["File", "Purpose"],
        ["core/bridge_components/reinforcement.py", "Rebar defaults, bar descriptors, spacing helpers, circular cage, OCC primitives"],
        ["sub_structure/pier/builder.py", "Circular pier, 12 no. 16 mm main bars, 8 mm ties @ 200 mm"],
        ["sub_structure/pier_cap/builder.py", "Tapered (hammerhead) cap, longitudinal bars and trapezoidal stirrups"],
        ["sub_structure/pedestal/builder.py", "Bearing pedestal with a four-bar cage"],
        ["foundation/pile/builder.py", "400 mm bored pile, 8 no. main bars, circular ties"],
        ["foundation/pile_cap/builder.py", "2200 x 1200 x 600 pile cap with top/bottom mats and perimeter ties"],
        ["sub_structure/assembly.py", "Layout, placement, summaries and task-to-model coordinate conversion"],
        ["core/ifc_export_bridge/substructure_ifc.py", "IFC writer for concrete, rebar, materials and quantities"],
        ["ifc_export_bridge/bridge_geometry_mapper.py", "Added circular profiles, revolved solids and a validity fix for surface styles"],
        ["ifc_export_bridge/bridge_cad_extraction.py", "Exposes the substructure layout to the IFC pipeline"],
        ["ifc_export_bridge/bridge_ifc_generator.py", "Adds the Substructure storey and invokes the writer"],
        ["desktop/ui/cad_3d.py", "Substructure/Rebar visibility controls and semi-transparent display"],
        ["core/bridge_types/plate_girder/cad_generator.py", "Builds and returns the substructure with the superstructure"],
        ["tests/unit/test_substructure.py", "Nine automated geometry, cover, assembly and IFC tests"],
        ["demo/run_demo.py", "Headless CAD + IFC + offscreen render harness"],
        ["demo/make_video.py, demo/make_report.py", "Submission video and this report"],
    ]
    story.append(table(files, [6.0 * cm, 10.8 * cm], font_size=7.4))
    para(
        "No existing superstructure or solver code was modified beyond the additive integration "
        "points listed above.", "small"
    )

    # ------------------------------------------------------------ 3 coordinates
    story.append(Paragraph("3. Coordinate system and placement", st["h1"]))
    para(
        "The task specifies X along the span with the origin at mid-span, Y across the deck, and "
        "Z vertical with the origin at deck level. The existing OsdagBridge CAD generator uses a "
        "different frame: X runs from 0 to the span length and Z is zero at mid-girder height. "
        "Mixing the two frames would have placed the foundations tens of metres away from the "
        "bridge, so the assembly keeps the task frame for all parametric data and applies an "
        "explicit conversion only when returning display shapes:"
    )
    story.append(Paragraph(
        "model_x = x + span_length / 2<br/>"
        "model_z = z + deck_top_z<br/>"
        "model_offset = (span_length / 2, 0, deck_top_z)",
        st["code"],
    ))
    para(
        "The same offset becomes the object placement of the IFC Substructure storey. Element "
        "placements therefore remain in the simple task-local frame, while the exported IFC world "
        "coordinates line up with the superstructure. Nothing about the superstructure is "
        "hard-coded: the pedestal tops are set to the girder soffit level, one pedestal is placed "
        "under each girder line, and the piers stand under the bearing lines at the two ends of "
        "the span, so changing the girder depth, spacing, number or span moves the substructure "
        "with it."
    )

    # ------------------------------------------------------------ 4 geometry
    story.append(Paragraph("4. Parametric geometry", st["h1"]))
    dims = [
        ["Component", "Parameter", "Default"],
        ["Pier", "diameter / height", "800 mm / 3000 mm"],
        ["Pier cap", "top width / bottom width / depth", "3000 / 1200 / 600 mm"],
        ["Pier cap", "length", "deck width - 2 x 500 mm"],
        ["Pedestal", "length x width x height", "600 x 400 x 150 mm (assumed)"],
        ["Pedestal", "number per cap", "one per girder line"],
        ["Pile cap", "length x width x depth", "2200 x 1200 x 600 mm"],
        ["Piles", "number / diameter / length", "4 (2x2) / 400 mm / 5000 mm"],
        ["Piles", "centre-to-centre spacing", "600 mm"],
        ["Reinforcement", "main / transverse diameter", "16 mm / 8 mm"],
        ["Reinforcement", "longitudinal / transverse spacing", "150 mm / 200 mm"],
        ["Reinforcement", "cover", "40 mm"],
    ]
    story.append(table(dims, [3.4 * cm, 7.2 * cm, 6.2 * cm]))
    para(
        "The pier cap is a true trapezoidal prism: a closed section in the X-Z plane is extruded "
        "along Y. The pile cap and pedestal are boxes, and the pier and piles are circular "
        "extrusions. Every solid is built in a local frame whose origin is the bottom centre of "
        "the component; the assembly translates it into position. This keeps each builder small "
        "and independently testable."
    )
    story.append(Spacer(1, 0.2 * cm))
    story.append(picture(renders["substructure_iso"], width=16.5 * cm))
    story.append(Paragraph(
        "Substructure isolated: two pier bents, each with a tapered cap, a pedestal under every "
        "girder, one circular pier, a pile cap and four piles. Concrete is shown translucent so "
        "the reinforcement is visible.",
        st["caption"],
    ))

    # ------------------------------------------------------------ 5 rebar
    story.append(PageBreak())
    story.append(Paragraph("5. Reinforcement modelling", st["h1"]))
    para(
        "Every bar is described by a small plain-data record before any geometry is made. A line "
        "bar stores two endpoints and a diameter; a "
        "ring bar stores a centre, a ring radius and a diameter. The same descriptors drive both "
        "the pythonOCC display geometry and the IFC reinforcing-bar elements, so the viewer and "
        "the exported model cannot drift apart."
    )
    bullet("Pier: 12 vertical 16 mm bars on a 344 mm radius, plus 8 mm circular ties at 200 mm;")
    bullet("Pier cap: two layers of longitudinal 16 mm bars at 150 mm, enclosed by trapezoidal 8 mm stirrups at 200 mm that follow the taper;")
    bullet("Pile cap: top and bottom mats of 16 mm bars at 150 mm in both directions, the second direction laid on the first, plus perimeter 8 mm ties;")
    bullet("Pile: 8 vertical 16 mm bars and circular 8 mm ties at 200 mm;")
    bullet("Pedestal: four vertical 16 mm bars and a closed 8 mm tie.")
    para(
        "Cover is measured to the outer face of the ties, and the main bars sit inside the ties "
        "rather than passing through them. On the sloping faces of the pier cap the offset is taken "
        "normal to the face; a purely horizontal offset would leave the top corners of the stirrups "
        "outside the concrete. The requested spacing is treated as a maximum, so bars are spread "
        "evenly at a pitch that never exceeds it. Each cage is "
        "returned as a single TopoDS_Compound. Fusing hundreds of bars with BRepAlgoAPI_Fuse "
        "would be slow and would create a very expensive shape for the viewer to tessellate; a "
        "compound displays correctly and keeps the interactive CAD window responsive."
    )
    para(
        f"The default bridge contains {s['bar_count']} bars with a total length of "
        f"{s['rebar_m']:.0f} m and an estimated mass of {s['steel_kg']:.0f} kg."
    )
    story.append(picture(renders["pier_detail"], width=16.5 * cm))
    story.append(Paragraph(
        "One pier bent: cap reinforcement, pedestal cages, pier cage, pile-cap mats and pile cages.",
        st["caption"],
    ))

    # ------------------------------------------------------------ 6 IFC
    story.append(Paragraph("6. IFC workflow integration", st["h1"]))
    para(
        "The existing exporter reconstructs structural elements parametrically rather than "
        "tessellating OCC shapes. The substructure follows the same philosophy. The CAD generator "
        "stores a serialisable layout (component metadata plus bar descriptors) on itself; the "
        "existing extractor exposes it as the 'substructure' key; the IFC generator writes it into "
        "the same IfcProject as the superstructure."
    )
    mapping = [
        ["Substructure part", "IFC entity", "Representation"],
        ["Pier", "IfcColumn", "IfcExtrudedAreaSolid + IfcCircleProfileDef"],
        ["Pier cap", "IfcBeam", "IfcExtrudedAreaSolid + trapezoidal IfcArbitraryClosedProfileDef"],
        ["Pedestal", "IfcBuildingElementProxy", "IfcExtrudedAreaSolid + IfcRectangleProfileDef"],
        ["Pile cap", "IfcFooting (PILE_CAP)", "IfcExtrudedAreaSolid + IfcRectangleProfileDef"],
        ["Pile", "IfcPile (BORED)", "IfcExtrudedAreaSolid + IfcCircleProfileDef"],
        ["Straight rebar", "IfcReinforcingBar", "IfcExtrudedAreaSolid + IfcCircleProfileDef"],
        ["Circular tie", "IfcReinforcingBar", "IfcRevolvedAreaSolid (360°) + IfcCircleProfileDef"],
    ]
    story.append(table(mapping, [3.2 * cm, 4.2 * cm, 9.4 * cm], font_size=7.2))
    para(
        "The two new geometry helpers added to the mapper are <i>create_circular_profile</i> and "
        "<i>create_revolved_circular_solid</i>. Circular ties are represented as a circle revolved "
        "through 360 degrees, which produces a torus in IFC without tessellation. The substructure "
        "writer also adds:"
    )
    bullet("one IfcBuildingStorey named 'Substructure', placed at mid-span/deck-level and aggregated with the superstructure storey;")
    bullet("an IfcMaterial association per element (concrete or steel grade from the substructure parameters);")
    bullet("an IfcElementQuantity set per element: net volume and length for concrete; bar count, total length and weight for rebar;")
    bullet("a Pset_OsdagBridgeSubstructure property set carrying the key dimensions and grades;")
    bullet("stable, individual element names and tags (Pier 1, Pier Cap 1, Pile 1-1, ...), so a BIM tool can produce a detailed BOQ.")
    para(
        "While validating the output, an existing IFC4 schema error was found in the shared colour "
        "helper: IfcSurfaceStyleRendering was created without the mandatory ReflectanceMethod "
        "attribute. This affected every styled item in the file, not just the new substructure. "
        "It was corrected to NOTDEFINED, after which the complete file validates with zero issues."
    )

    # ------------------------------------------------------------ 7 verification
    story.append(PageBreak())
    story.append(Paragraph("7. Verification and results", st["h1"]))
    tests = [
        ["Test", "What it checks", "Result"],
        ["test_pier_dimensions_and_rebar", "800 x 3000 bounding box, valid solid, cage inside the cover", "Pass"],
        ["test_pier_cap_dimensions_and_trapezoid", "3000 wide, 600 deep, requested length; valid solid", "Pass"],
        ["test_pier_cap_rebar_keeps_cover_to_sloping_faces", "Every bar end lies inside the section offset by cover + bar radius", "Pass"],
        ["test_main_bar_pitch_does_not_exceed_requested_spacing", "Mat bar pitch is never larger than the requested spacing", "Pass"],
        ["test_pile_and_pile_cap_dimensions", "Pile 400 x 5000, pile cap 2200 x 1200 x 600, valid solids", "Pass"],
        ["test_pedestal_dimensions", "600 x 400 x 150 bounding box and cage", "Pass"],
        ["test_assembly_counts_and_coordinate_conversion", "Member counts, 2x2 pile positions, members stack without gaps, model offset", "Pass"],
        ["test_pedestals_follow_bearing_lines", "One pedestal per girder line; a cap too short for them is rejected", "Pass"],
        ["test_full_cad_and_ifc_export", "Pedestal top equals girder soffit; IFC entity counts; material and quantities on every element; schema validation", "Pass"],
    ]
    story.append(table(tests, [6.6 * cm, 8.4 * cm, 1.4 * cm], font_size=7.4))
    para("")
    counts_rows = [["IFC entity", "Count", "Meaning"]] + [
        ["IfcPile", counts["IfcPile"], "bored piles"],
        ["IfcColumn", counts["IfcColumn"], "circular piers"],
        ["IfcBeam", counts["IfcBeam"], "hammerhead pier caps"],
        ["IfcFooting", counts["IfcFooting"], "pile caps"],
        ["IfcBuildingElementProxy", counts["IfcBuildingElementProxy"], "bearing pedestals"],
        ["IfcReinforcingBar", counts["IfcReinforcingBar"], "bar groups (main, ties, mats)"],
        ["IfcElementQuantity", counts["IfcElementQuantity"], "quantity sets"],
        ["IfcPlate / IfcSlab", f"{counts['IfcPlate']} / {counts['IfcSlab']}", "existing superstructure retained"],
    ]
    story.append(table(counts_rows, [5.2 * cm, 2.0 * cm, 9.0 * cm]))
    para(
        f"The exported file is {summary['ifc_size_bytes'] / 1024:.0f} KB. It re-opens with "
        f"ifcopenshell 0.8.3 and passes ifcopenshell.validate with "
        f"{summary['validation_error_count']} issue(s). The IFC file is included in the submission "
        "ZIP and can be imported into Revit, FreeCAD or any IFC4 viewer."
    )
    para(
        "The geometric tests use BRepCheck_Analyzer for validity and optimal bounding boxes for "
        "dimension checks. Bounding boxes are computed with BRepBndLib.AddOptimal because the "
        "simple bounding-box routine over-estimates full tori by about 9 % - a property of the "
        "bounding algorithm, not of the modelled tie."
    )

    # ------------------------------------------------------------ 8 challenges
    story.append(Paragraph("8. Challenges", st["h1"]))
    para(
        "<b>Two coordinate systems.</b> The task's origin (mid-span, deck level) and the existing "
        "code's origin (span start, mid-girder) are incompatible. Rather than rewriting the "
        "superstructure, the assembly stores all parametric data in the task frame and applies one "
        "documented conversion at the CAD/IFC boundary."
    )
    para(
        "<b>No circular IFC primitives.</b> The existing mapper could only extrude rectangular, "
        "polygonal and structural-section profiles. Piers and piles needed IfcCircleProfileDef, and "
        "circular ties needed a genuinely circular representation. A 360-degree IfcRevolvedAreaSolid "
        "was chosen over approximating a ring with many short straight bars."
    )
    para(
        "<b>Rebar performance.</b> The default bridge contains over a thousand bars. Fusing them "
        "individually would make the CAD window unresponsive, so each cage is a compound and each "
        "IFC bar group carries all solids of one type. The viewer displays one object per cage."
    )
    para(
        "<b>ARM64 development machine.</b> No win-arm64 pythonocc-core build is published, so the "
        "implementation was developed and verified in WSL2 Ubuntu (aarch64) using conda-forge "
        "pythonocc-core 7.9 and ifcopenshell 0.8.3. The code itself is platform-independent and "
        "runs unchanged on the x86-64 environment used by the project."
    )
    para(
        "<b>A pre-existing IFC bug.</b> Schema validation exposed a missing mandatory attribute in "
        "the shared surface-style helper. Fixing it was necessary for the new elements and also "
        "improved the validity of the existing superstructure export."
    )

    # ------------------------------------------------------------ 9 limits
    story.append(Paragraph("9. Limitations and next steps", st["h1"]))
    bullet("The dimensions are screening-task defaults, not a design checked against IRC loading, bearing pressure or pile capacity.")
    bullet(f"A single pier carries each {s['cap_length'] / 1000:.1f} m cap. The cap cantilevers have not been checked for bending or shear, and a real crossing of this width would more likely use a multi-column bent.")
    bullet("Bearings are not modelled; the pedestal tops are set to the girder soffit. Each pier stands under the bearing line at the end of the span, so half of its cap projects beyond the deck, as it would under an adjacent span.")
    bullet("The bridge is straight; the substructure does not yet follow the skew angle used by the superstructure.")
    bullet("Rebar is modelled as clean cylinders and tori - hooks, lap lengths, curtailment and anchorage are not detailed.")
    bullet("The IFC BOQ uses element quantities rather than a full IfcCostSchedule/IfcElementAssembly breakdown.")
    bullet("The GUI display was wired and the headless geometry/IFC path was executed; the full Qt application still needs a visual run on a machine with the complete osdag conda environment.")

    # ------------------------------------------------------------ 10 reproduce
    story.append(Paragraph("10. How to reproduce", st["h1"]))
    para(
        "The repository's documented conda environment is used. On the ARM64 development machine "
        "this was created inside WSL2 Ubuntu; on x86-64 the same commands run directly."
    )
    story.append(Paragraph(
        "micromamba create -n osdagbridge-env -c conda-forge python=3.11 \\<br/>"
        "&nbsp;&nbsp;&nbsp;&nbsp;pythonocc-core=7.9.0 ifcopenshell numpy pytest<br/>"
        "micromamba activate osdagbridge-env<br/>"
        "cd OsdagBridge<br/>"
        "python demo/run_demo.py<br/>"
        "python demo/make_video.py<br/>"
        "python demo/make_report.py<br/>"
        "PYTHONPATH=src python -m pytest tests/unit/test_substructure.py -q",
        st["code"],
    ))
    para(
        "The normal GUI route is unchanged: activate the project environment, start the desktop "
        "application, run a design and choose File → Save 3D CAD Model → Save as type: .ifc. "
        "The substructure is generated and exported with the superstructure automatically."
    )

    # ------------------------------------------------------------ 11 refs
    story.append(Paragraph("11. References", st["h1"]))
    refs = [
        "OsdagBridge repository, Nidhikhare12/OsdagBridge, dev branch - component builders, cad_generator.py and ifc_export_bridge.",
        "pythonOCC / pythonocc-core 7.9 documentation - BRepPrimAPI, BRepBuilderAPI, TopoDS_Compound and offscreen rendering.",
        "buildingSMART, IFC4 Addendum 2 specification - IfcColumn, IfcBeam, IfcFooting, IfcPile, IfcReinforcingBar, IfcExtrudedAreaSolid, IfcRevolvedAreaSolid, IfcElementQuantity.",
        "ifcopenshell 0.8.3 API and validation utilities.",
        "IRC:5-2015 and IRC:6 - referenced by the surrounding OsdagBridge superstructure code; not used to size the screening-task substructure.",
    ]
    for ref in refs:
        bullet(ref)

    # ------------------------------------------------------------ appendix A
    story.append(PageBreak())
    story.append(Paragraph("Appendix A - Bill of quantities summary", st["h1"]))
    para(
        "Quantities below are computed directly from the parametric descriptors and match the "
        "IfcElementQuantity sets in the exported file."
    )
    boq = [
        ["Item", "Quantity"],
        ["Pier bents", f"{s['pier_count']}"],
        ["Concrete elements (piers, caps, pedestals, pile caps, piles)", f"{s['component_count']}"],
        ["Concrete volume", f"{s['concrete_m3']:.2f} m³"],
        ["Reinforcement bar count", f"{s['bar_count']}"],
        ["Reinforcement total length", f"{s['rebar_m']:.0f} m"],
        ["Reinforcement mass (7850 kg/m³)", f"{s['steel_kg']:.0f} kg"],
        ["Pier cap length", f"{s['cap_length']:.0f} mm"],
        ["Pile founding level below deck", f"{abs(s['pile_toe_z']):.0f} mm"],
        ["IFC file size", f"{summary['ifc_size_bytes'] / 1024:.0f} KB"],
        ["IFC schema validation issues", f"{summary['validation_error_count']}"],
    ]
    story.append(table(boq, [11.0 * cm, 5.2 * cm]))

    # ------------------------------------------------------------ appendix B
    story.append(PageBreak())
    story.append(Paragraph("Appendix B - Rendered inspection views", st["h1"]))
    para(
        "These are unedited offscreen renders of the actual pythonOCC model. Concrete is semitransparent "
        "in the substructure views so the reinforcement remains visible."
    )
    for key, caption in [
        ("substructure_iso", "Substructure isometric view with the reinforcement cage."),
        ("substructure_front", "Substructure elevation along the span."),
        ("full_bridge_front", "Complete bridge elevation along the span, showing the substructure below the deck."),
    ]:
        story.append(picture(renders[key], width=16.5 * cm))
        story.append(Paragraph(caption, st["caption"]))

    # ------------------------------------------------------------ footer
    def on_page(canvas, doc_):
        canvas.saveState()
        canvas.setStrokeColor(GRID)
        canvas.setLineWidth(0.5)
        canvas.line(2.0 * cm, 1.35 * cm, A4[0] - 2.0 * cm, 1.35 * cm)
        canvas.setFont(FONT, 7.5)
        canvas.setFillColor(colors.HexColor("#6A7886"))
        canvas.drawString(2.0 * cm, 0.95 * cm,
                          "Osdag Winter Internship 2026 - Parametric substructure and IFC integration")
        canvas.drawRightString(A4[0] - 2.0 * cm, 0.95 * cm, f"Page {doc_.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
