#!/usr/bin/env python3
"""可选的重新排字样板，已有完整 SVG 时优先使用 scripts/render_svg.py。
先将 CONFIG 中的品牌、版本、字体、坐标替换为真实设计参数。
默认只生成浅色，提供深色设计后才使用 --dark。
请勿复制到用户项目。确需修改时放 D:/Temp，并显式指向技能的 splash_parts 辅助模块；临时字体与校准 JSON 也放 D:/Temp。
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "scripts"))
from splash_parts import (baseline, draw_spaced, finish, font,  # noqa: E402
                          pick_sc_index, pull_device_font, rounded_shadow,
                          spaced_width)
from PIL import Image, ImageDraw  # noqa: E402

# ---------------------------------------------------------------------------
# CONFIG —— 全部用设计稿坐标（dp），与 Dart 里的 const 一一对应
# ---------------------------------------------------------------------------

RES = os.path.join("android", "app", "src", "main", "res")
DEVICE_JSON = "D:/Temp/splash/device.json"
FONT_DIR = "D:/Temp/splash/fonts"

BUCKET = 4.0          # 位图放 drawable-xxxhdpi
SS = 4                # 超采样倍数
PAD = 12.0            # 底板透明边，给投影留位置（左右对称，不影响居中）

# 标记
MARK = 96.0
MARK_RADIUS = 24.0
MARK_FONT = 36.0
MARK_LINE = 45.0
MARK_TEXT_LEFT = 20.8
MARK_TEXT_TOP = 22.4

# 标语
SLOGAN = "让每一次拜访，都有价值"
SLOGAN_SIZE = 16.0
SLOGAN_LINE = 24.0
SLOGAN_TRACKING = 1.4
SLOGAN_GAP = 22.0
SLOGAN_ALPHA = 224   # 0.88

# 底部锁标
WORDMARK = "MF Tool"
WORDMARK_SIZE = 20.0
WORDMARK_LINE = 26.0
WORDMARK_ALPHA = 168  # 0.66
VERSION = "2.0"
VERSION_SIZE = 13.0
VERSION_LINE = 18.0
VERSION_ALPHA = 153   # 0.60
LOCKUP_GAP = 6.0

# 主题
TOKENS = {
    "light": dict(bg=(0xF8, 0xFA, 0xFC), fill=(0x25, 0x63, 0xEB),
                  ink=(0xFF, 0xFF, 0xFF), fg=(0x0F, 0x17, 0x2A),
                  muted=(0x47, 0x55, 0x69), is_dark=False),
    "dark": dict(bg=(0x0B, 0x12, 0x20), fill=(0x60, 0xA5, 0xFA),
                 ink=(0x0B, 0x12, 0x20), fg=(0xE6, 0xED, 0xF8),
                 muted=(0x9F, 0xB0, 0xC7), is_dark=True),
}


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--pull-font", action="store_true",
                    help="从设备拉中文字体到 D:/Temp/splash/fonts（约 30MB）")
    ap.add_argument("--dark", action="store_true", help="仅在已提供深色设计时生成 dark 变体")
    a = ap.parse_args()

    dev = json.load(open(DEVICE_JSON, encoding="utf-8"))
    s = dev["scale"]
    k = BUCKET * s                      # 位图里 1 设计 dp 的像素数
    u = k * SS                          # 渲染时的像素数

    def p(v):
        return v * u

    ttc = pull_device_font(FONT_DIR) if a.pull_font else None
    if ttc is None:
        ttc = os.path.join(FONT_DIR, "NotoSansCJK-Regular.ttc")
    if not os.path.exists(ttc):
        sys.exit("缺中文字体：先跑 probe_device.py --font-dir D:/Temp/splash/fonts，"
                 "或给本脚本 --pull-font")
    cjk_index = pick_sc_index(ttc)

    f_mark = font(os.path.join("assets", "fonts", "Poppins-ExtraBold.ttf"), p(MARK_FONT))
    f_slogan = font(ttc, p(SLOGAN_SIZE), index=cjk_index)
    f_word = font(os.path.join("assets", "fonts", "Poppins-SemiBold.ttf"), p(WORDMARK_SIZE))
    f_ver = font(os.path.join("assets", "fonts", "OpenSans-Regular.ttf"), p(VERSION_SIZE))

    for mode, c in TOKENS.items():
        if mode == "dark" and not a.dark:
            continue
        d = "drawable-night-xxxhdpi" if c["is_dark"] else "drawable-xxxhdpi"
        print("%s（%s）" % (d, "深色" if c["is_dark"] else "浅色"))

        # --- 标记 + 标语：合成一张，内部间距由代码决定，XML 里只需一个 bottom
        slogan_w = spaced_width(SLOGAN, f_slogan, p(SLOGAN_TRACKING)) / u
        group_w = max(MARK, slogan_w)
        w_dp = group_w + PAD * 2
        h_dp = MARK + SLOGAN_GAP + SLOGAN_LINE + PAD * 2

        canvas = Image.new("RGBA", (round(w_dp * u), round(h_dp * u)), (0, 0, 0, 0))
        cx = p(PAD + group_w / 2)
        top = p(PAD)
        left = cx - p(MARK) / 2
        box = (left, top, left + p(MARK), top + p(MARK))
        r = p(MARK_RADIUS)

        # 投影：spreadRadius 是 -5（收缩），写反会变成一圈灰雾
        for off, blur, inflate, color in (
            (p(3), p(10), p(-5), c["fill"] + (0x52,)),
            (p(1), p(3), 0, (0x0F, 0x17, 0x29, 0x0D)),
        ):
            canvas = Image.alpha_composite(
                canvas,
                rounded_shadow(canvas.size, box, r, (0, off), blur, inflate, color),
            )

        draw = ImageDraw.Draw(canvas)
        draw.rounded_rectangle(
            [round(left), round(top), round(left + p(MARK)), round(top + p(MARK))],
            radius=round(r), fill=c["fill"] + (255,))
        draw.text((round(left + p(MARK_TEXT_LEFT)),
                   round(top + p(MARK_TEXT_TOP) + baseline(f_mark, p(MARK_LINE)))),
                  "MF", font=f_mark, fill=c["ink"] + (255,), anchor="ls")

        # ← 品牌专属图形放这里（点、条、斜线等）。
        #   本样板只画了字，原工程还有「绿点 + 绿条」两笔：
        #     draw.ellipse([x0,y0,x1,y1], fill=GREEN+(255,))
        #     draw.rounded_rectangle([x0,y0,x1,y1], radius=h/2, fill=GREEN+(255,))

        bl = p(PAD) + p(MARK + SLOGAN_GAP) + baseline(f_slogan, p(SLOGAN_LINE))
        draw_spaced(draw, cx - spaced_width(SLOGAN, f_slogan, p(SLOGAN_TRACKING)) / 2,
                    bl, SLOGAN, f_slogan, c["muted"] + (SLOGAN_ALPHA,),
                    p(SLOGAN_TRACKING))
        finish(canvas, os.path.join(RES, d, "icon_splash_group.png"), k, BUCKET, SS)

        # --- 底部锁标：同基线，逐级降低存在感
        b1 = baseline(f_word, p(WORDMARK_LINE))
        b2 = baseline(f_ver, p(VERSION_LINE))
        above = max(b1, b2)
        below = max(p(WORDMARK_LINE) - b1, p(VERSION_LINE) - b2)
        w1 = f_word.getlength(WORDMARK)
        w2 = f_ver.getlength(VERSION)
        canvas = Image.new("RGBA", (round(w1 + p(LOCKUP_GAP) + w2), round(above + below)),
                           (0, 0, 0, 0))
        draw = ImageDraw.Draw(canvas)
        draw.text((0, round(above)), WORDMARK, font=f_word,
                  fill=c["fg"] + (WORDMARK_ALPHA,), anchor="ls")
        draw.text((round(w1 + p(LOCKUP_GAP)), round(above)), VERSION, font=f_ver,
                  fill=c["muted"] + (VERSION_ALPHA,), anchor="ls")
        finish(canvas, os.path.join(RES, d, "icon_splash_lockup.png"), k, BUCKET, SS)

    print("\n核对：intrinsic 应等于「设计尺寸 × %.4f」。"
          "再用 emit_xml.py 生成 layer-list。" % s)


if __name__ == "__main__":
    main()
