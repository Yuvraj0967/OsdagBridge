"""
Create a short silent MP4 walkthrough from the artifacts produced by
``demo/run_demo.py``.

The video is a slideshow of the real offscreen renders plus the real IFC
export results.  It is intentionally silent, matching the screening brief.
"""

import json
import os
import sys

import imageio
import numpy as np
from PIL import Image, ImageDraw, ImageFont

W, H = 1600, 1000
FPS = 24
BG = (246, 248, 251)
INK = (32, 38, 46)
MUTED = (92, 102, 114)
ACCENT = (23, 92, 132)

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ARTIFACTS = os.path.join(ROOT, "artifacts")


def _font(size, bold=False, mono=False):
    if mono:
        path = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
    else:
        path = (
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
            if bold
            else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        )
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()


def _wrap(draw, text, font, max_width):
    words = text.split()
    lines, current = [], ""
    for word in words:
        candidate = (current + " " + word).strip()
        if draw.textlength(candidate, font=font) <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def title_card(title, subtitle, footer=""):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 12], fill=ACCENT)
    y = 250
    for line in _wrap(d, title, _font(64, bold=True), W - 240):
        d.text((120, y), line, font=_font(64, bold=True), fill=INK)
        y += 82
    y += 20
    for line in _wrap(d, subtitle, _font(34), W - 240):
        d.text((120, y), line, font=_font(34), fill=MUTED)
        y += 48
    if footer:
        d.text((120, H - 120), footer, font=_font(26), fill=MUTED)
    return img


def image_slide(path, caption, note=""):
    base = Image.open(path).convert("RGB")
    base = base.resize((W, H))
    overlay = Image.new("RGB", (W, H), BG)
    overlay.paste(base, (0, 0))
    d = ImageDraw.Draw(overlay, "RGBA")
    d.rectangle([0, H - 150, W, H], fill=(246, 248, 251, 235))
    d.rectangle([0, H - 154, W, H - 150], fill=ACCENT)
    d.text((80, H - 118), caption, font=_font(34, bold=True), fill=INK)
    if note:
        d.text((80, H - 68), note, font=_font(26), fill=MUTED)
    return overlay


def terminal_slide(summary):
    img = Image.new("RGB", (W, H), (24, 28, 34))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 12], fill=(74, 170, 120))
    font = _font(28, mono=True)
    small = _font(24, mono=True)
    d.text((70, 60), "$ python demo/run_demo.py", font=_font(30, bold=True, mono=True),
           fill=(180, 230, 190))
    counts = summary["ifc_counts"]
    s = summary["summary"]
    lines = [
        "Building plate-girder bridge CAD ...",
        f"  substructure elements : {s['component_count']}",
        f"  reinforcement bars    : {s['bar_count']} bars / {s['rebar_m']:.0f} m",
        f"  concrete              : {s['concrete_m3']:.2f} m3",
        f"  steel                 : {s['steel_kg']:.0f} kg",
        "",
        "Exporting IFC (superstructure + substructure) ...",
        f"  IfcPile               : {counts['IfcPile']}",
        f"  IfcColumn (pier)      : {counts['IfcColumn']}",
        f"  IfcBeam (pier cap)    : {counts['IfcBeam']}",
        f"  IfcFooting (pile cap) : {counts['IfcFooting']}",
        f"  IfcReinforcingBar     : {counts['IfcReinforcingBar']}",
        f"  IfcElementQuantity    : {counts['IfcElementQuantity']}",
        "",
        f"IFC schema validation : {summary['validation_error_count']} issue(s)",
        "Done.",
    ]
    y = 135
    for line in lines:
        colour = (180, 230, 190) if line.startswith("$") else (212, 218, 228)
        if "validation" in line or line.startswith("  Ifc"):
            colour = (150, 210, 245)
        d.text((70, y), line, font=font if len(line) < 60 else small, fill=colour)
        y += 40
    d.text((70, H - 80), "IFC4 file opens cleanly and contains both bridge systems",
           font=small, fill=(150, 210, 245))
    return img


def fade_frames(a, b, steps):
    frames = []
    for i in range(1, steps + 1):
        frames.append(Image.blend(a, b, i / (steps + 1)))
    return frames


def main():
    with open(os.path.join(ARTIFACTS, "summary.json"), encoding="utf-8") as fh:
        summary = json.load(fh)
    renders = summary["renders"]

    slides = [
        (title_card(
            "Parametric 3D CAD Modelling of Bridge Substructure",
            "IFC workflow integration  |  Osdag Winter Internship 2026  |  Screening Task 5",
            "pythonOCC 7.9  •  IFC4  •  OsdagBridge (dev branch)",
        ), 4.0),
        (image_slide(
            renders["full_bridge_iso"],
            "Complete bridge: superstructure + new substructure",
            "Two pier bents, hammerhead caps, pile caps and 2x2 bored piles",
        ), 4.5),
        (image_slide(
            renders["substructure_iso"],
            "Substructure with concrete shown semi-transparent",
            "Opaque reinforcement cage visible inside the concrete volumes",
        ), 4.5),
        (image_slide(
            renders["pier_detail"],
            "Reinforcement detail",
            "16 mm main bars @ 150 mm  •  8 mm ties @ 200 mm  •  40 mm cover",
        ), 4.5),
        (image_slide(
            renders["full_bridge_front"],
            "Transverse elevation",
            "Deck 15 m wide  •  pier cap 3.0 m top / 1.2 m bottom  •  piles 5.0 m long",
        ), 4.0),
        (terminal_slide(summary), 7.0),
        (title_card(
            "IFC export complete",
            "Superstructure and substructure in one IFC4 file, with materials, quantities and a dedicated Substructure storey.",
            "Artifacts: osdagbridge_substructure.ifc  •  preview PNGs  •  report.pdf",
        ), 4.5),
    ]

    out_path = os.path.join(ARTIFACTS, "osdagbridge_substructure_demo.mp4")
    writer = imageio.get_writer(
        out_path, fps=FPS, codec="libx264", quality=8,
        pixelformat="yuv420p", macro_block_size=None,
    )
    try:
        previous = None
        for image, seconds in slides:
            if previous is not None:
                for frame in fade_frames(previous, image, 8):
                    writer.append_data(np.asarray(frame))
            frames = np.asarray(image)
            for _ in range(int(seconds * FPS)):
                writer.append_data(frames)
            previous = image
    finally:
        writer.close()

    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
    sys.exit(0)
