#!/usr/bin/env python3
"""第一步「抓取」：探测目标设备，算出启动屏对齐需要的全部几何量。

    python probe_device.py --canvas 412x892 --out D:/Temp/splash/device.json
    python probe_device.py --canvas 412x892 --font-dir D:/Temp/splash/fonts   # 顺手拉设备字体

产物是一份 json，后面 emit_xml.py / verify_alignment.py 都吃它。

三个数必须一起算，缺一个就会在交接时露馅：

  s        = min(视口宽/画布宽, 视口高/画布高)   —— Flutter 的 FittedBox 缩放比
  letterbox = (视口高 − 画布高×s)/2              —— contain 之后上下留的边
  由此得到：位图密度 = 4×s（不是 4），item 的 bottom 见 emit_xml.py

依赖 adb 与 PIL（PIL 只用于 --font-dir 时确认字体面）。
"""

import argparse
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from splash_parts import (letterbox, pick_sc_index, pull_device_font,
                          scale_factor)  # noqa: E402


def adb(serial, *args):
    cmd = ["adb"] + (["-s", serial] if serial else []) + list(args)
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
    if r.returncode != 0:
        sys.exit("adb 失败：%s\n%s" % (" ".join(cmd), r.stderr.strip()))
    return r.stdout


def parse_size(out):
    """`wm size` 可能同时给出 Physical / Override，取 Override 优先。"""
    override = re.search(r"Override size:\s*(\d+)x(\d+)", out)
    if override:
        return int(override.group(1)), int(override.group(2))
    m = re.search(r"Physical size:\s*(\d+)x(\d+)", out)
    if not m:
        sys.exit("解析不了 `wm size` 的输出：%r" % out)
    return int(m.group(1)), int(m.group(2))


def parse_density(out):
    override = re.search(r"Override density:\s*(\d+)", out)
    if override:
        return int(override.group(1))
    m = re.search(r"Physical density:\s*(\d+)", out)
    if not m:
        sys.exit("解析不了 `wm density` 的输出：%r" % out)
    return int(m.group(1))


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--canvas", required=True, help="设计画布尺寸，如 412x892")
    ap.add_argument("--serial", default=None)
    ap.add_argument("--font-dir", default=None,
                    help="给了就把设备中文字体拉到这个目录（约 30MB）")
    ap.add_argument("--out", default=None, help="json 输出路径，默认打印")
    a = ap.parse_args()

    dw, dh = (float(x) for x in a.canvas.lower().split("x"))
    w_px, h_px = parse_size(adb(a.serial, "shell", "wm", "size"))
    density = parse_density(adb(a.serial, "shell", "wm", "density"))
    dpr = density / 160.0
    view_w, view_h = w_px / dpr, h_px / dpr

    s = scale_factor(view_w, view_h, dw, dh)
    lb = letterbox(view_h, dh, s)

    data = {
        "serial": a.serial,
        "size_px": [w_px, h_px],
        "density": density,
        "dpr": dpr,
        "view_dp": [round(view_w, 4), round(view_h, 4)],
        "design": [dw, dh],
        "scale": s,
        "letterbox": lb,
        # 位图里 1 设计 dp 的像素数（xxxhdpi 桶）
        "px_per_design_dp": 4 * s,
    }

    if a.font_dir:
        path = pull_device_font(a.font_dir, serial=a.serial)
        if path is None:
            print("· 拉设备字体失败，生成器需要自己指定一个 CJK 字体")
        else:
            idx = pick_sc_index(path)
            data["font"] = {"path": path, "index": idx}
            print("· 中文字体：%s（index %d）" % (path, idx))

    print("\n设备 %s  %dx%d px  density %d  → 视口 %.2f×%.2f dp"
          % (a.serial or "(默认)", w_px, h_px, density, view_w, view_h))
    print("画布 %g×%g  →  s = %.7f  letterbox = %.4f dp"
          % (dw, dh, s, lb))
    print("位图密度 = 4×s = %.4f px/设计dp（不是 4）" % (4 * s))
    print("画布高在屏上 = %.2f dp；底部富余 = %.2f dp"
          % (dh * s, view_h - lb - dh * s))

    if a.out:
        os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print("\n→ %s" % a.out)
    else:
        print("\n" + json.dumps(data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
