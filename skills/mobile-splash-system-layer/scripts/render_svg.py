#!/usr/bin/env python3
"""Render SVG at 4*s for xxxhdpi, optionally produce a 1x reference.

Requires resvg-py (validated with 0.5.0), not an app runtime dependency.
"""
import argparse
import json
import math
from pathlib import Path
import sys
import xml.etree.ElementTree as ET


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--svg', required=True)
    ap.add_argument('--device', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--reference')
    a = ap.parse_args()
    source = Path(a.svg).resolve()
    targets = [Path(p).resolve() for p in (a.out, a.reference) if p]
    if source in targets or len(set(targets)) != len(targets):
        ap.error('Source, output and reference must be different paths')
    box = [float(v) for v in ET.parse(source).getroot().attrib['viewBox'].replace(',', ' ').split()]
    if len(box) != 4 or not all(math.isfinite(v) for v in box) or min(box[2:]) <= 0:
        ap.error('Invalid SVG viewBox')
    d = json.loads(Path(a.device).read_text(encoding='utf-8'))
    if len(d['design']) != 2 or any(abs(x-y) > .01 for x,y in zip(box[2:], d['design'])):
        ap.error('SVG dimensions differ from device design canvas')
    scale = float(d['scale']) * 4
    if not math.isfinite(scale) or scale <= 0:
        ap.error('Invalid device scale')
    import resvg_py
    png = resvg_py.svg_to_bytes(svg_path=str(source), zoom=scale)
    reference = resvg_py.svg_to_bytes(svg_path=str(source)) if a.reference else None
    targets[0].parent.mkdir(parents=True, exist_ok=True)
    targets[0].write_bytes(png)
    if reference is not None:
        targets[1].parent.mkdir(parents=True, exist_ok=True)
        targets[1].write_bytes(reference)
    print(f'4*s={scale:.7f}; intrinsic={box[2]*scale/4:.3f}x{box[3]*scale/4:.3f}dp')


if __name__ == '__main__':
    main()
