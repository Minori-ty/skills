#!/usr/bin/env python3
"""第二步「生成」的最后一段：把位图摆到正确的 dp 上，输出 layer-list XML。

    python emit_xml.py --device D:/Temp/splash/device.json \
        --color @color/splash_bg_fill \
        --elem icon_splash_group=center:400 \
        --elem icon_splash_lockup=bottom:110 \
        --out android/app/src/main/res/drawable/splash_bg.xml

元素两种锚法，都按**设计稿坐标**给：

  center:Y   元素中心在设计稿 y=Y 处（Flutter 侧通常写在 Column 里居中）
  bottom:Y   元素底边距设计稿底边 Y dp（Flutter 侧是 `Positioned(bottom: Y)`）

原理：`<item android:bottom="X">` 会把 item 可用框从底部裁掉 X，
`gravity=center` 随之上移 X/2；`gravity=bottom` 就是底边距 X。

  center:  X = 视口高 − 2 × (letterbox + Y×s)
  bottom:  X = (视口高 − (letterbox + 画布高×s)) + Y×s

这两个式子看起来朴素，但它们是整套方案能不能「交接无感」的全部 —— 
中间的 s 和 letterbox 只要漏一个，错位就是几十上百像素。
"""

import argparse
import json
import os
import sys

TEMPLATE = """<?xml version="1.0" encoding="utf-8"?>
<!-- 由 mobile-splash-system-layer 生成，请勿手改数字。

     目标机：{w_px}×{h_px}px @{density}dpi → 视口 {view_w:.2f}×{view_h:.2f}dp
     画布：{dw:g}×{dh:g} → s = {s:.7f}，letterbox = {lb:.4f}dp
     （s 是 Flutter FittedBox contain 的缩放比；系统层的每个坐标都要乘它）

{derivation}
-->
<layer-list xmlns:android="http://schemas.android.com/apk/res/android">

    <!-- 底色 -->
    <item android:drawable="{color}" />
{items}
</layer-list>
"""

ITEM = """
    <!-- {src}：{why} -->
    <item android:bottom="{bottom:.2f}dp">
        <bitmap
            android:gravity="{gravity}"
            android:src="@drawable/{src}" />
    </item>
"""


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", required=True, help="probe_device.py 产出的 json")
    ap.add_argument("--color", required=True, help="底色，如 @color/splash_bg_fill")
    ap.add_argument("--elem", action="append", default=[],
                    metavar="SRC=ANCHOR:Y",
                    help="可重复；ANCHOR 是 center 或 bottom")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    d = json.load(open(a.device, encoding="utf-8"))
    s, lb = d["scale"], d["letterbox"]
    view_h = d["view_dp"][1]
    dh = d["design"][1]

    items, derivation = [], []
    for spec in a.elem:
        try:
            src, anchor = spec.split("=", 1)
            kind, y = anchor.split(":", 1)
            y = float(y)
        except ValueError:
            raise SystemExit("--elem 格式应为 SRC=center:400 或 SRC=bottom:110，收到 %r" % spec)

        if kind == "center":
            bottom = view_h - 2 * (lb + y * s)
            gravity = "center"
            why = ("中心在设计稿 y=%g → 屏上 %.2fdp；"
                   "bottom = %.2f − 2×%.2f = %.2f"
                   % (y, lb + y * s, view_h, lb + y * s, bottom))
        elif kind == "bottom":
            bottom = (view_h - (lb + dh * s)) + y * s
            gravity = "bottom|center_horizontal"
            why = ("距画布底 %g dp → 屏上 %g×%.4f = %.2fdp；"
                   "bottom = %.2f + %.2f = %.2f"
                   % (y, y, s, y * s,
                      view_h - (lb + dh * s), y * s, bottom))
        else:
            raise SystemExit("锚法只有 center / bottom，收到 %r" % kind)

        if bottom < 0:
            raise SystemExit("%s 算出的 bottom 是负数（%.2f），说明它比视口还高"
                             % (src, bottom))
        items.append(ITEM.format(src=src, why=why, bottom=bottom, gravity=gravity))
        derivation.append("       · %-28s bottom=%.2fdp" % (src, bottom))

    xml = TEMPLATE.format(
        w_px=d["size_px"][0], h_px=d["size_px"][1], density=d["density"],
        view_w=d["view_dp"][0], view_h=view_h, dw=d["design"][0], dh=dh,
        s=s, lb=lb, color=a.color, items="".join(items),
        derivation="\n".join(derivation),
    )

    if a.out:
        os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
        open(a.out, "w", encoding="utf-8", newline="\n").write(xml)
        print(xml)
        print("→ %s" % a.out)
    else:
        print(xml)


if __name__ == "__main__":
    main()
