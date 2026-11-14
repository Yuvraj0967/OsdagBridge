# Screening Task Submission

**Task:** Parametric 3D CAD Modeling of Bridge Substructure and IFC Workflow Integration
**Category:** Software Development
**Programme:** FOSSEE Osdag Winter Internship 2026
**Candidate:** Yuvraj Pateria

| Item | Location |
|---|---|
| Branch | `feature/substructure-ifc` (based on `dev` of `Nidhikhare12/OsdagBridge`) |
| Documentation | [README_SUBSTRUCTURE.md](README_SUBSTRUCTURE.md) |
| Report (PDF) | `artifacts/OsdagBridge_Substructure_Report.pdf` |
| Sample IFC | `artifacts/osdagbridge_substructure.ifc` |
| Rendered views | `artifacts/*.png` |
| Demo video | `artifacts/osdagbridge_substructure_demo.mp4` |

`artifacts/` is generated output and is not tracked in git. Recreate it with:

```bash
python demo/run_demo.py      # CAD, IFC export, schema validation, renders
python demo/make_video.py    # demo video
python demo/make_report.py   # report PDF
python demo/make_zip.py      # submission ZIP
```
