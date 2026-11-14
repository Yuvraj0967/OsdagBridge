# OsdagBridge substructure: parametric CAD and IFC export

This branch adds a bridge substructure to OsdagBridge:

- pythonOCC builders for the **pier, pier cap, pedestal, pile and pile cap**,
  each with its reinforcement;
- an **assembly** that places a pier bent under each bearing line;
- **IFC4 export** of the substructure next to the superstructure, through the
  existing *File -> Save 3D CAD Model -> .ifc* route;
- `Substructure` and `Rebar` toggles in the 3D viewer, with the concrete drawn
  semi-transparent so the bars are visible.

The dimensions are the illustrative defaults from the screening task. This is
a geometry and data-exchange exercise, not a checked structural design.

## Layout of the code

```
src/osdagbridge/core/bridge_components/
  reinforcement.py              rebar defaults, bar descriptors, spacing helpers, OCC primitives
  sub_structure/
    assembly.py                 SubstructureParameters, build_substructure()
    pier/builder.py             circular pier
    pier_cap/builder.py         tapered cap
    pedestal/builder.py         bearing pedestal
  foundation/
    pile/builder.py             bored pile
    pile_cap/builder.py         pile cap

src/osdagbridge/core/ifc_export_bridge/
  substructure_ifc.py           IFC writer for concrete, rebar, materials, quantities
  bridge_geometry_mapper.py     + circular profile, revolved solid, surface-style fix
  bridge_cad_extraction.py      passes the substructure layout to the exporter
  bridge_ifc_generator.py       adds the Substructure storey and calls the writer

src/osdagbridge/core/bridge_types/plate_girder/cad_generator.py
                                builds the substructure with the superstructure
src/osdagbridge/desktop/ui/cad_3d.py
                                display, tooltips and visibility toggles

tests/unit/test_substructure.py
demo/                           headless demo, video, report and ZIP scripts
```

Each `build_*` function returns the concrete solid, a rebar compound, and a
plain-data description of the member (dimensions and bar descriptors). The
assembly collects those descriptions into a layout record, and the IFC writer
works only from that record. The viewer and the IFC file are therefore two
views of the same numbers.

## Coordinate system

The assembly uses the frame given in the task:

| Axis | Direction | Origin |
|---|---|---|
| X | along the span | mid-span |
| Y | across the deck | bridge centreline |
| Z | vertical, positive up | deck level |

The existing CAD generator uses X from 0 to the span length and Z = 0 at the
mid-depth of the girder web, so the finished shapes are shifted once:

```
model_x = x + span_length / 2
model_z = z + deck_top_z
```

The same offset is the placement of the IFC `Substructure` storey, so element
placements inside the IFC file stay in the task frame.

## How the substructure follows the superstructure

| Quantity | Taken from |
|---|---|
| Pedestal top level | underside of the girder bottom flange |
| Pedestal positions | one under each girder line |
| Pier positions | bearing lines at the two ends of the span |
| Pier cap length | deck width less 500 mm at each end |

All other levels are worked downwards from the pedestal top: cap, pier, pile
cap, piles.

## Default dimensions

| Component | Parameter | Default |
|---|---|---|
| Pier | diameter / height | 800 / 3000 mm |
| Pier cap | top width / bottom width / depth | 3000 / 1200 / 600 mm |
| Pedestal | L x W x H (assumed, not in the brief) | 600 x 400 x 150 mm |
| Pile cap | L x W x D | 2200 x 1200 x 600 mm |
| Piles | 2 x 2 group, diameter / length / spacing | 400 / 5000 / 600 mm |
| Rebar | main / transverse diameter | 16 / 8 mm |
| Rebar | maximum spacing, main / transverse | 150 / 200 mm |
| Rebar | cover | 40 mm |

They are fields of `SubstructureParameters` and keyword arguments of the
builders. To change them from the application code:

```python
generator = PlateGirderCADGenerator()
generator.substructure_params.pier_height = 4500.0
generator.substructure_params.pile_length = 8000.0
```

## Reinforcement

- **Pier, pile:** vertical bars on a pitch circle inside circular ties.
- **Pier cap:** top and bottom layers of bars along the cap inside trapezoidal
  stirrups.
- **Pile cap:** top and bottom mats, the second direction laid on the first,
  with perimeter ties.
- **Pedestal:** four corner bars inside closed ties.

Cover is measured to the outer face of the ties and main bars sit inside the
ties. On the sloping faces of the pier cap the offset is taken normal to the
face. Spacing is a maximum: bars are spread evenly at a pitch that does not
exceed it.

Each cage is displayed as one `TopoDS_Compound`. Fusing about a thousand bars
is slow and gives the viewer a much heavier shape to tessellate, for no visual
difference.

## IFC mapping

| Part | IFC entity | Geometry |
|---|---|---|
| Pier | `IfcColumn` | circle, extruded |
| Pier cap | `IfcBeam` | trapezoid, extruded |
| Pedestal | `IfcBuildingElementProxy` | rectangle, extruded |
| Pile cap | `IfcFooting` (`PILE_CAP`) | rectangle, extruded |
| Pile | `IfcPile` (`BORED`) | circle, extruded |
| Straight bars | `IfcReinforcingBar` | circle, extruded |
| Circular ties | `IfcReinforcingBar` | circle, revolved 360 degrees |

One `IfcReinforcingBar` is written per bar group (for example "Pier 1 - Main
Bars"), holding all bars of that group. Every element has an `IfcMaterial`,
an `IfcElementQuantity` (volume and length, or bar count, length and weight)
and a property set with its dimensions.

While validating the output I found that the existing colour helper created
`IfcSurfaceStyleRendering` without the mandatory `ReflectanceMethod`, which
made every styled item in the file fail IFC4 schema validation. It is now set
to `NOTDEFINED` and the complete file validates cleanly.

## Running it

The demo and tests need `pythonocc-core` and `ifcopenshell` from conda-forge:

```bash
micromamba create -n osdagbridge-env -c conda-forge \
    python=3.11 pythonocc-core=7.9.0 ifcopenshell numpy pytest \
    reportlab pillow imageio imageio-ffmpeg
micromamba activate osdagbridge-env

PYTHONPATH=src python -m pytest tests/unit/test_substructure.py -q
python demo/run_demo.py
```

`run_demo.py` builds the bridge, exports the IFC file, runs
`ifcopenshell.validate` on it and writes offscreen renders and a
`summary.json` to `artifacts/`.

In the desktop application nothing changes for the user: run a design and
save the 3D model as `.ifc`; the substructure is included.

I developed this on a Windows ARM64 laptop. conda-forge has no win-arm64 build
of pythonocc-core, so everything above was run in WSL2 (Ubuntu, aarch64).

## Tests

`tests/unit/test_substructure.py` covers:

- dimensions and solid validity of each builder;
- rebar cover, including against the sloping faces of the pier cap;
- bar pitch not exceeding the requested spacing;
- member counts, pile positions and members stacking without gaps;
- pedestals following the girder lines, and rejection of a cap too short for
  them;
- the full bridge: pedestal top equal to girder soffit, IFC entity counts,
  material and quantities on every element, IFC4 schema validation.

## Limitations

- No structural checks: member sizes, bar areas and pile capacity are not
  verified against IRC loading.
- A single pier carries the full-width cap. The cantilevers are long for a
  600 mm deep cap; a real crossing of this width would more likely use a
  multi-column bent.
- Bearings are not modelled. Pedestal tops are at the girder soffit.
- Each pier stands under the bearing line at the end of the span, so half of
  its cap projects beyond the deck, as it would under an adjacent span.
- The substructure does not follow the superstructure skew angle.
- Bars are straight cylinders and full rings: no hooks, laps or anchorage
  into the adjoining member.
- I have exercised the CAD, IFC and rendering paths headlessly. The Qt window
  could not be launched on my machine, so the two new viewer toggles are
  untested on screen.
