"""
Package the submission ZIP.

Only the files touched by this task, the tests/demo harness and the final
artifacts are included - not the entire repository.
"""

import os
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ARTIFACTS = os.path.join(ROOT, "artifacts")

SOURCE_FILES = [
    "README_SUBSTRUCTURE.md",
    "SUBMISSION.md",
    "src/osdagbridge/core/bridge_components/reinforcement.py",
    "src/osdagbridge/core/bridge_components/sub_structure/assembly.py",
    "src/osdagbridge/core/bridge_components/sub_structure/pier/builder.py",
    "src/osdagbridge/core/bridge_components/sub_structure/pier_cap/builder.py",
    "src/osdagbridge/core/bridge_components/sub_structure/pedestal/builder.py",
    "src/osdagbridge/core/bridge_components/foundation/pile/builder.py",
    "src/osdagbridge/core/bridge_components/foundation/pile_cap/builder.py",
    "src/osdagbridge/core/ifc_export_bridge/substructure_ifc.py",
    "src/osdagbridge/core/ifc_export_bridge/bridge_geometry_mapper.py",
    "src/osdagbridge/core/ifc_export_bridge/bridge_cad_extraction.py",
    "src/osdagbridge/core/ifc_export_bridge/bridge_ifc_generator.py",
    "src/osdagbridge/core/bridge_types/plate_girder/cad_generator.py",
    "src/osdagbridge/desktop/ui/cad_3d.py",
    "tests/unit/test_substructure.py",
    "demo/run_demo.py",
    "demo/make_video.py",
    "demo/make_report.py",
    "demo/make_zip.py",
]

ARTIFACT_FILES = [
    "OsdagBridge_Substructure_Report.pdf",
    "osdagbridge_substructure_demo.mp4",
    "osdagbridge_substructure.ifc",
    "summary.json",
    "substructure_iso.png",
    "substructure_front.png",
    "pier_detail.png",
    "full_bridge_iso.png",
    "full_bridge_front.png",
]

PREFIX = "OsdagBridge_Substructure"


def main():
    out_path = os.path.join(ARTIFACTS, "OsdagBridge_Substructure_Submission.zip")
    missing = []
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for rel in SOURCE_FILES:
            path = os.path.join(ROOT, rel)
            if not os.path.exists(path):
                missing.append(rel)
                continue
            zf.write(path, f"{PREFIX}/{rel}")
        for name in ARTIFACT_FILES:
            path = os.path.join(ARTIFACTS, name)
            if not os.path.exists(path):
                missing.append(name)
                continue
            zf.write(path, f"{PREFIX}/artifacts/{name}")
    print(f"Wrote {out_path}")
    if missing:
        print("Missing (skipped):")
        for item in missing:
            print(f"  - {item}")


if __name__ == "__main__":
    main()
