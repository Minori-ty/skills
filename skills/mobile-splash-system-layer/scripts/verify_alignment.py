#!/usr/bin/env python3
"""Measure stable-frame regions; animated or incorrect frames require visual review.

Requires numpy and Pillow. Reference pixels must equal the design canvas.
Exit codes: 0 within tolerance; 1 beyond tolerance; 2 invalid/missing input.
"""
import argparse
import json
import math
from pathlib import Path
import sys
import numpy as np
from PIL import Image


def background(im):
    colors, counts = np.unique((im // 8 * 8).reshape(-1, 3), axis=0, return_counts=True)
    return colors[counts.argmax()].astype(int)


def bbox(mask, y0, y1, x0=0, x1=None):
    ys, xs = np.where(mask[y0:y1, x0:x1])
    if not len(ys):
        return None
    return np.array([xs.min()+x0, ys.min()+y0, xs.max()+x0, ys.max()+y0], dtype=float)


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--ref', required=True)
    ap.add_argument('--shot')
    ap.add_argument('--device')
    ap.add_argument('--band', action='append', default=[], metavar='NAME:Y0:Y1')
    ap.add_argument('--scan', action='store_true')
    ap.add_argument('--pad', type=int, default=6, help='Search padding in screenshot pixels')
    ap.add_argument('--threshold', type=int, default=24, help='RGB background distance')
    ap.add_argument('--tolerance', type=float, default=6, help='Maximum boundary error in px')
    ap.add_argument('--json-out', help='Optional machine-readable results')
    a = ap.parse_args()
    if a.pad < 0 or a.threshold < 0 or not math.isfinite(a.tolerance) or a.tolerance < 0:
        ap.error('pad, threshold and tolerance must be nonnegative and finite')
    ref = np.asarray(Image.open(a.ref).convert('RGB')).astype(int)
    ink = np.abs(ref-background(ref)).sum(2) > a.threshold
    if a.scan or not a.shot:
        rows = np.where(ink.sum(1) >= 3)[0]
        groups = np.split(rows, np.where(np.diff(rows) > 3)[0]+1)
        print('Reference ink bands (design pixels):')
        for group in groups:
            if len(group):
                print(int(group[0]), int(group[-1]))
        if not a.shot:
            return 0
    if not a.device or not a.band:
        ap.error('Comparison needs --device and at least one --band')
    d = json.loads(Path(a.device).read_text(encoding='utf-8'))
    dw, dh = d['design']
    s, lb, dpr = d['scale'], d['letterbox'], d['dpr']
    if not all(math.isfinite(float(v)) for v in [dw,dh,s,lb,dpr,*d['view_dp']]) or min(dw,dh,s,dpr) <= 0:
        ap.error('Invalid device geometry')
    if ref.shape[:2] != (round(dh), round(dw)):
        ap.error('Reference dimensions must equal design dimensions, not a supersampled image')
    shot = np.asarray(Image.open(a.shot).convert('RGB')).astype(int)
    if shot.shape[:2] != tuple(reversed(d['size_px'])):
        ap.error('Screenshot dimensions differ from the probed device')
    shot_ink = np.abs(shot-background(shot)).sum(2) > a.threshold
    regions = []
    try:
        for spec in a.band:
            name, start, end = spec.split(':')
            start, end = int(start), int(end)
            if not name or not 0 <= start <= end < ref.shape[0]:
                raise ValueError('band outside reference')
            regions.append((name,start,end))
        regions.sort(key=lambda item: item[1])
        if len({r[0] for r in regions}) != len(regions):
            raise ValueError('duplicate band names')
        if any(x[2] >= y[1] for x,y in zip(regions, regions[1:])):
            raise ValueError('bands overlap')
    except ValueError as exc:
        ap.error(f'Invalid NAME:Y0:Y1 bands: {exc}')
    sx = (d['view_dp'][0]-dw*s)/2
    offset = np.array([sx,lb,sx,lb])*dpr
    results, missing = [], False
    for i,(name,start,end) in enumerate(regions):
        rb = bbox(ink,start,end+1)
        if rb is None:
            print(f'{name}: no reference ink')
            results.append({'name':name,'error':'missing reference ink'})
            missing = True
            continue
        expected = rb*s*dpr+offset
        x0,y0 = np.floor(expected[:2]-a.pad).astype(int)
        x1,y1 = np.ceil(expected[2:]+a.pad+1).astype(int)
        # Partition at adjacent design bands, preventing the old 60px cross-line bug.
        if i:
            y0 = max(y0,math.ceil(((regions[i-1][2]+start)/2*s+lb)*dpr))
        if i+1 < len(regions):
            y1 = min(y1,math.ceil(((end+regions[i+1][1])/2*s+lb)*dpr))
        sb = bbox(shot_ink,max(0,y0),min(shot.shape[0],y1),max(0,x0),min(shot.shape[1],x1))
        if sb is None:
            print(f'{name}: no screenshot ink in search region')
            results.append({'name':name,'error':'missing screenshot ink'})
            missing = True
            continue
        delta = sb-expected
        center = (delta[:2]+delta[2:])/2
        size = delta[2:]-delta[:2]
        error = float(np.abs(delta).max())
        results.append({'name':name,'expected':expected.tolist(),'actual':sb.tolist(),
                        'center_delta':center.tolist(),'size_delta':size.tolist(),'boundary_error':error})
        print(f'{name}: center dx/dy={center[0]:+.2f}/{center[1]:+.2f}px; '
              f'size dw/dh={size[0]:+.2f}/{size[1]:+.2f}px; boundary={error:.2f}px')
    worst = max((r.get('boundary_error',0) for r in results),default=0)
    status = 'incomplete' if missing else ('within tolerance' if worst <= a.tolerance else 'outside tolerance')
    print(f'{status}; max boundary error={worst:.2f}px; soft edges and frame phase require visual review')
    if a.json_out:
        path = Path(a.json_out)
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps({'status':status,'results':results},indent=2),encoding='utf-8')
    return 2 if missing else int(worst > a.tolerance)


if __name__ == '__main__':
    sys.exit(main())
