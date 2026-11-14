# Screening Task Submission

**Project:** Parametric 3D CAD Modeling of Bridge Substructure and IFC Workflow Integration
**Category:** Software Development
**Programme:** FOSSEE Osdag Winter Internship 2026
**Candidate:** Yuvraj Pateria

---

## Deliverables

| Item | Location / value |
|---|---|
| Forked repository | `https://github.com/<your-username>/OsdagBridge` |
| Branch | `dev` (or a feature branch, e.g. `feature/substructure-ifc`) |
| Report (PDF) | `artifacts/OsdagBridge_Substructure_Report.pdf` |
| Demo video (unlisted) | `<paste YouTube / cloud URL here>` |
| ZIP | `artifacts/OsdagBridge_Substructure_Submission.zip` |
| IFC sample | `artifacts/osdagbridge_substructure.ifc` |
| Rendered views | `artifacts/*.png` |

Submission form (from the task page):

`https://docs.google.com/forms/d/e/1FAIpQLSdED-LhYmCoaI6AkLBfhfnRjS_LSNf-KX88vLQqej4-oKsdZw/viewform`

## Deadline

**23 November 2026** (results 28 November 2026; internship starts 7 December 2026).

---

## What to do before submitting

1. Create the fork and push this branch.
2. Add `Nidhikhare12` as a collaborator.
3. Upload `osdagbridge_substructure_demo.mp4` as an unlisted video and paste the
   URL above.
4. Verify the report still says 0 IFC validation issues:
   `python demo/run_demo.py`.
5. Run the tests:
   `PYTHONPATH=src python -m pytest tests/unit/test_substructure.py -q`.
6. Zip the source modules, report, video and IFC sample:
   `python demo/make_zip.py` (or use the prepared ZIP in `artifacts/`).
7. Submit the form with:
   - resume (PDF),
   - report (PDF),
   - repository link,
   - video URL,
   - ZIP.
8. Attach the NOC/undertaking if the form requires it (mandatory for a
   semester-long internship; can follow after selection).

---

## Notes for the interview

Be ready to explain:

- why the assembly keeps the task frame and converts only at the CAD/IFC
  boundary;
- why each rebar cage is a `TopoDS_Compound` instead of a boolean fuse;
- how a circular tie becomes an `IfcRevolvedAreaSolid` rather than a tessellated
  mesh;
- why the IFC `Substructure` storey has a placement offset and how Revit uses
  it;
- the 59 pre-existing schema errors fixed by adding
  `IfcSurfaceStyleRendering.ReflectanceMethod`;
- the difference between the screening-task dimensions and a verified design.

The code is deliberately modular: every builder can be called and tested on its
own, and the same bar descriptors feed both the viewer and the IFC writer.
