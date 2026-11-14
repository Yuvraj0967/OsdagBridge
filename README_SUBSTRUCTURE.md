# OsdagBridge Substructure - Parametric 3D CAD and IFC Integration

This branch adds the missing bridge substructure to OsdagBridge:

- parametric pythonOCC builders for **pier, pier cap, pedestal, pile and pile cap**;
- internal **reinforcement** (16 mm main bars, 8 mm ties, 40 mm cover);
- a substructure **assembly** in the screening-task coordinate system;
- **native IFC4 export** using `IfcColumn`, `IfcBeam`, `IfcFooting`, `IfcPile`
  and `IfcReinforcingBar`, with materials, quantities and a dedicated
  `Substructure` storey;
- automatic inclusion in the existing
  **File -> Save 3D CAD Model -> Save as type: .ifc** workflow;
- semi-transparent concrete and opaque reinforcement in the 3D viewer.

The dimensions are the illustrative defaults from the screening task. They are
not a structurally verified foundation design.

---

## 1. What was added

```
src/osdagbridge/core/bridge_components/
├── reinforcement.py                     shared bar descriptors, cylinders, tori, compounds
├── sub_structure/
│   ├── assembly.py                      placement, summaries, task -> model conversion
│   ├── pier/builder.py                  800 x 3000 circular pier + cage
│   ├── pier_cap/builder.py              3000/1200 x 600 hammerhead cap + cage
│   └── pedestal/builder.py              600 x 400 x 150 bearing pedestal + cage
└── foundation/
    ├── pile/builder.py                  400 x 5000 bored pile + cage
    └── pile_cap/builder.py              2200 x 1200 x 600 pile cap + mats

src/osdagbridge/core/ifc_export_bridge/
├── substructure_ifc.py                  IFC writer for concrete, rebar and quantities
├── bridge_geometry_mapper.py            + circular profile and revolved solid helpers
├── bridge_cad_extraction.py             exposes the substructure layout
└── bridge_ifc_generator.py              adds the Substructure storey and invokes the writer

src/osdagbridge/core/bridge_types/plate_girder/
└── cad_generator.py                     builds the substructure with the superstructure

src/osdagbridge/desktop/ui/
└── cad_3d.py                            "Substructure" and "Rebar" visibility controls

tests/unit/test_substructure.py          six geometry / assembly / IFC tests
demo/run_demo.py                         headless CAD + IFC + offscreen renders
demo/make_video.py                       silent MP4 walkthrough
demo/make_report.py                      report PDF
```

No existing superstructure or solver logic was rewritten. All integration is
additive.

---

## 2. Coordinate system

The builders are authored in the frame required by the task:

| Axis | Direction | Origin |
|---|---|---|
| X | along the span | mid-span |
| Y | across the deck | bridge centreline |
| Z | vertical | deck level, positive up |

Concrete therefore sits at negative Z. The existing OsdagBridge CAD frame uses
X from 0 to the span length and Z = 0 at mid-girder height, so the assembly
applies one documented conversion at the boundary:

```
model_x = x + span_length / 2
model_z = z + deck_top_z
```

The same offset is used as the IFC `Substructure` storey placement. Element
placements remain task-local, while the world coordinates line up with the
superstructure in Revit/FreeCAD.

---

## 3. Parametric defaults

| Component | Parameter | Default |
|---|---|---|
| Pier | diameter / height | 800 mm / 3000 mm |
| Pier cap | top / bottom width / depth | 3000 / 1200 / 600 mm |
| Pier cap | length | deck width - 2 x 500 mm |
| Pedestal | L x W x H | 600 x 400 x 150 mm |
| Pile cap | L x W x D | 2200 x 1200 x 600 mm |
| Piles | count / diameter / length | 4 (2x2) / 400 mm / 5000 mm |
| Piles | spacing | 600 mm c/c |
| Rebar | main / ties | 16 mm / 8 mm |
| Rebar | spacing | 150 mm / 200 mm |
| Rebar | cover | 40 mm |

Every value is a keyword argument on the corresponding `build_*` function, and
the assembly defaults are collected in `SubstructureParameters`.

---

## 4. Running the demo

The project uses a conda environment. On the ARM64 Windows development machine
no win-arm64 pythonocc-core build is published, so the demo and tests were run
in **WSL2 Ubuntu (aarch64)** with conda-forge packages:

```bash
micromamba create -n osdagbridge-env -c conda-forge \
    python=3.11 pythonocc-core=7.9.0 ifcopenshell numpy pytest \
    reportlab pillow imageio imageio-ffmpeg
micromamba activate osdagbridge-env

cd OsdagBridge
python demo/run_demo.py          # CAD -> IFC -> validation -> PNG renders
python demo/make_video.py        # silent MP4 walkthrough
python demo/make_report.py       # submission report PDF
```

Artifacts are written to `artifacts/`:

```
osdagbridge_substructure.ifc            full bridge IFC4 file
OsdagBridge_Substructure_Report.pdf     report
osdagbridge_substructure_demo.mp4       silent demo video
substructure_iso.png                    substructure with rebar
substructure_front.png                  substructure elevation
pier_detail.png                         one pier bent
full_bridge_iso.png                     complete bridge
full_bridge_front.png                   complete bridge elevation
summary.json                            counts, quantities, validation result
```

For the normal GUI workflow, use the project's `environment.yml`, launch
`python -m osdagbridge.desktop`, run a design and save an `.ifc`. The
substructure is included automatically.

### Windows ARM note

If WSL2 is used, run the commands from `/mnt/c/...` inside Ubuntu. Qt/WSLg is
only needed for the desktop application; the demo, tests and renders are
headless.

---

## 5. Tests

```bash
PYTHONPATH=src python -m pytest tests/unit/test_substructure.py -q
```

The six tests cover:

1. pier dimensions, solid validity and rebar cover;
2. hammerhead cap dimensions and trapezoidal rebar;
3. pile and pile-cap dimensions;
4. pedestal dimensions;
5. assembly counts, 2x2 pile layout and task-to-model conversion;
6. full bridge CAD, IFC export/reopen, entity counts, materials and quantities.

Expected result:

```
6 passed
```

The full demo also runs `ifcopenshell.validate` on the exported file. The
current output reports **0 issues**.

---

## 6. IFC mapping

| Substructure part | IFC entity | Geometry |
|---|---|---|
| Pier | `IfcColumn` | circular extrusion |
| Pier cap | `IfcBeam` | trapezoidal extrusion |
| Pedestal | `IfcBuildingElementProxy` | rectangular extrusion |
| Pile cap | `IfcFooting` (`PAD_FOOTING`) | rectangular extrusion |
| Pile | `IfcPile` (`BORED`) | circular extrusion |
| Straight bar | `IfcReinforcingBar` | circular extrusion |
| Circular tie | `IfcReinforcingBar` | 360-degree revolved circle (torus) |

Each element also receives:

- an `IfcMaterial` association (`Concrete M30` or `Fe500`);
- an `IfcElementQuantity` set (net volume, length, count, rebar weight);
- a `Pset_OsdagBridgeSubstructure` property set;
- a stable name/tag such as `Pier Cap 1`, `Pile 2-3`.

The IFC file keeps the existing superstructure (`IfcPlate`, `IfcSlab`,
barriers, railings) and adds a separate `Substructure` building storey under the
same project.

---

## 7. Implementation notes

- **Compounds, not fuses.** Each reinforcement cage is a `TopoDS_Compound`.
  Fusing hundreds of bars would make the CAD viewer slow and the shape expensive
  to tessellate.
- **Single source of truth.** Bars are described as `line`/`ring` records.
  The same records drive both pythonOCC display geometry and IFC export.
- **Cover is to the bar face.** Bar centre-lines are inset by one bar radius, so
  the 40 mm cover is measured to the outside of the reinforcement.
- **Torus bounding boxes.** `BRepBndLib.Add` over-estimates full tori by about
  9%; the tests use `AddOptimal` for exact bounds.
- **Pre-existing IFC fix.** `IfcSurfaceStyleRendering` was missing its mandatory
  `ReflectanceMethod`; it now uses `NOTDEFINED`, which removes 59 schema errors
  from the whole file.

---

## 8. Known limitations

- Dimensions are screening-task defaults, not checked against IRC loading,
  bearing pressure or pile capacity.
- One pier is used under each long cap; a production design would check cap
  bending, punching shear and bearing spacing.
- The substructure does not yet follow the superstructure skew angle.
- Rebar has no hooks, laps, curtailment or anchorage detailing.
- The IFC output uses element quantities rather than a full cost schedule.
- The headless geometry and IFC path is fully exercised; the Qt window itself
  still needs a visual run on a machine with the complete osdag environment.

---

## 9. Submission checklist

- [ ] Push this branch to your fork of `Nidhikhare12/OsdagBridge`.
- [ ] Add `Nidhikhare12` as a collaborator.
- [ ] Upload `artifacts/osdagbridge_substructure_demo.mp4` as an unlisted video;
      put the URL in `SUBMISSION.md`.
- [ ] Submit the report PDF, repository link, video URL and ZIP through the
      FOSSEE form.
- [ ] Attach the NOC/undertaking if required.
- [ ] Check the deadline: **23 November 2026**.
