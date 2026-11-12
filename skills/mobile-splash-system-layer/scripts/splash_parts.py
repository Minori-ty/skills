#!/usr/bin/env python3
"""PIL 工具：把 Flutter 的排版 / 阴影语义搬到 PIL 里，供启动屏位图生成器复用。

只做 Flutter → PIL 的**语义映射**，不认识任何具体设计。项目自己的生成器
（见 assets/gen_splash_example.py）import 本模块，把品牌的坐标填进去。

四个映射，每一个都踩过坑：

1. `scale_factor()` —— Flutter 的画布缩放比 s。
   `DsFrame`（FittedBox contain）把设计画布缩进真机视口，真机上任何元素都
   只有 `设计尺寸 × s` 大。位图里 1 设计 dp = `4 × s` 像素，不是 4。

2. `baseline()` —— 固定行高下的基线位置。
   Flutter：`leadingDistribution: even` 时，行高减去字体自然行高 (ascent+descent)
   后**均分**上下，基线 = halfLeading + ascent。

3. `draw_spaced()` / `spaced_width()` —— letterSpacing。
   Flutter 把字距加在**每个字后面（含最后一个）**，所以居中要用含尾字距的总宽。

4. `rounded_shadow()` —— BoxShadow。
   `spreadRadius` 是**正数放大、负数收缩**（设计里常见 -5，让影子只从一边漏出来）；
   `RRect.inflate` 会同步收圆角；模糊 sigma = `blurRadius × 0.57735 + 0.5`。
"""

import os
import subprocess

from PIL import Image, ImageDraw, ImageFilter, ImageFont

# ---------------------------------------------------------------------------
# 几何
# ---------------------------------------------------------------------------


def scale_factor(view_w_dp, view_h_dp, design_w, design_h):
    """Flutter `FittedBox(fit: contain)` 的缩放比。"""
    return min(view_w_dp / design_w, view_h_dp / design_h)


def letterbox(view_h_dp, design_h, s):
    """contain 之后上下各留多少 dp（宽受限时才有值）。"""
    return (view_h_dp - design_h * s) / 2


def device_y(design_y, s, letterbox_dp, dpr):
    """设计稿 y → 真机像素 y。"""
    return (letterbox_dp + design_y * s) * dpr


# ---------------------------------------------------------------------------
# 文字
# ---------------------------------------------------------------------------


def font(path, size_px, index=0):
    return ImageFont.truetype(path, max(1, round(size_px)), index=index)


def baseline(f, line_px):
    """文字在固定行高的行盒里，基线距行盒顶的像素距离。"""
    a, d = f.getmetrics()
    return (line_px - (a + d)) / 2 + a


def spaced_width(text, f, tracking_px):
    """含尾字距的总宽（Flutter 的排版宽度就是这么算的）。"""
    return sum(f.getlength(c) for c in text) + len(text) * tracking_px


def draw_spaced(draw, x, baseline_y, text, f, fill, tracking_px):
    """逐字画以支持 letterSpacing，返回总 advance。"""
    cur = x
    for ch in text:
        draw.text((round(cur), round(baseline_y)), ch, font=f, fill=fill,
                  anchor="ls")
        cur += f.getlength(ch) + tracking_px
    return cur - x


# ---------------------------------------------------------------------------
# 阴影
# ---------------------------------------------------------------------------


def rounded_shadow(canvas_size, box, radius, offset, blur_px, inflate_px, color):
    """还原 Flutter 的 BoxShadow，返回一层待 alpha_composite 的 RGBA。

    box / radius / offset / blur 全部是**像素**。`inflate_px` 就是 Flutter 的
    `spreadRadius`：正数外扩、负数内收。
    """
    layer = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    x0, y0, x1, y1 = box
    x0, x1 = x0 - inflate_px, x1 + inflate_px
    y0, y1 = y0 - inflate_px, y1 + inflate_px
    r = max(0.0, radius - inflate_px)          # RRect.inflate 同步收圆角
    x0 += offset[0]; x1 += offset[0]
    y0 += offset[1]; y1 += offset[1]
    d.rounded_rectangle([round(x0), round(y0), round(x1), round(y1)],
                        radius=round(r), fill=color)
    sigma = blur_px * 0.57735 + 0.5            # Skia: ConvertRadiusToSigma
    return layer.filter(ImageFilter.GaussianBlur(sigma))


# ---------------------------------------------------------------------------
# 字体获取
# ---------------------------------------------------------------------------


def pull_device_font(dest_dir, remote="/system/fonts/NotoSansCJK-Regular.ttc",
                     serial=None):
    """把设备自带的中文字体拉到本地（约 30MB）。返回本地路径或 None。

    用设备自己那份是让标语字形和 Flutter 层同源的关键 —— 桌面上的
    Noto Sans SC 是另一个版本，字宽会差 1~2px。
    """
    os.makedirs(dest_dir, exist_ok=True)
    local = os.path.join(dest_dir, os.path.basename(remote))
    if os.path.exists(local):
        return local
    cmd = ["adb"] + (["-s", serial] if serial else []) + ["pull", remote, local]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        return None
    return local


def pick_sc_index(ttc_path, probe=(0, 1, 2, 3, 4, 5)):
    """在 TTC 里找「SC」（简体）那一面。NotoSansCJK 的顺序是
    JP / KR / SC / TC / HK，但别硬编码，遍历名字更稳。"""
    for i in probe:
        try:
            name = ImageFont.truetype(ttc_path, 40, index=i).getname()[0]
        except Exception:
            break
        if " SC" in name or name.endswith("SC"):
            return i
    return 0


# ---------------------------------------------------------------------------
# 收尾
# ---------------------------------------------------------------------------


def finish(canvas, out_path, k, bucket, ss):
    """超采样画布 → 降采样到 k 像素/设计dp → 写文件 → 报告 intrinsic 尺寸。

    Android 在 `drawable-xxxhdpi` 里认为位图是 `px / 4` dp，所以
    `intrinsic = px / bucket`。这个值必须等于「设计尺寸 × s」，否则交接时
    会看到元素大一点再缩回去。
    """
    target = (max(1, round(canvas.width / ss)),
              max(1, round(canvas.height / ss)))
    out = canvas.resize(target, Image.LANCZOS)
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    out.save(out_path)
    print("  %-46s %4d×%-4dpx → intrinsic %7.2f×%-7.2fdp"
          % (os.path.basename(os.path.dirname(out_path)) + "/"
             + os.path.basename(out_path),
             out.width, out.height, out.width / bucket, out.height / bucket))
    return out.size
