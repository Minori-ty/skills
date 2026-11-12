#!/usr/bin/env python3
"""Capture a few cold-start samples. No universal stable-frame timing exists.

Default keeps display mode unchanged. Explicit --night restores the old mode.
Requires adb and Pillow. Does not install, uninstall or operate business UI.
"""
import argparse
import math
from pathlib import Path
import re
import shlex
import subprocess
import sys
import time
import uuid
from PIL import Image


def adb(serial, *args):
    cmd = ['adb']+(['-s',serial] if serial else [])+list(args)
    result = subprocess.run(cmd,capture_output=True,timeout=45)
    if result.returncode:
        raise RuntimeError(f'adb failed ({result.returncode}): {result.stderr.decode("utf-8",errors="replace")}')
    return result.stdout.decode('utf-8',errors='replace')


def capture(serial, component, delay, output):
    remote = f'/sdcard/_splash_{uuid.uuid4().hex}.png'
    try:
        adb(serial,'shell','am','force-stop',component.split('/')[0])
        time.sleep(.8)
        adb(serial,'shell',f'am start -n {shlex.quote(component)} >/dev/null 2>&1 '
            f'&& sleep {delay:.6f} && screencap -p {remote}')
        adb(serial,'pull',remote,str(output))
        with Image.open(output) as im:
            if im.format != 'PNG':
                raise RuntimeError('Screenshot is not PNG')
            im.verify()
    finally:
        adb(serial,'shell','rm','-f',remote)


def main():
    if hasattr(sys.stdout,'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--pkg',required=True)
    ap.add_argument('--activity',default='.MainActivity')
    ap.add_argument('--series',default='0.40,0.55')
    ap.add_argument('--out',required=True,help='Task temporary directory, e.g. D:/Temp/splash/shots')
    ap.add_argument('--serial')
    ap.add_argument('--night',choices=['yes','no','keep'],default='keep')
    a = ap.parse_args()
    if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_.]*',a.pkg) or not re.fullmatch(r'\.?[A-Za-z_][A-Za-z0-9_.$]*',a.activity):
        ap.error('Invalid package/activity')
    try:
        delays = [float(v.strip()) for v in a.series.split(',')]
        if not delays or any(not math.isfinite(v) or not 0 <= v <= 30 for v in delays):
            raise ValueError('delays must be finite, between 0 and 30 seconds')
        if len(delays) != len(set(delays)):
            raise ValueError('duplicate delays')
    except ValueError as exc:
        ap.error(f'Invalid --series: {exc}')
    directory = Path(a.out)
    directory.mkdir(parents=True,exist_ok=True)
    old_mode = None
    try:
        if a.night != 'keep':
            match = re.search(r'Night mode:\s*(yes|no|auto)\b',adb(a.serial,'shell','cmd','uimode','night'))
            if not match:
                raise RuntimeError('Cannot restore original mode reliably; refusing to change it')
            old_mode = match[1]
            adb(a.serial,'shell','cmd','uimode','night',a.night)
            time.sleep(1.5)
        for delay in delays:
            output = directory/f'splash_{delay:.6f}.png'
            if output.exists():
                raise FileExistsError(f'Refusing to overwrite {output}')
            capture(a.serial,f'{a.pkg}/{a.activity}',delay,output)
            print(f'{delay:.6f}s -> {output}')
    finally:
        if old_mode is not None:
            adb(a.serial,'shell','cmd','uimode','night',old_mode)
    print('Review frame phase before measuring; these samples do not prove which rendering layer was captured.')


if __name__ == '__main__':
    main()
