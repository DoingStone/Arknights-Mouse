# -*- coding: utf-8 -*-
"""生成三档并排对比图，直观展示尺寸差异。"""
import os, sys, struct
from PIL import Image, ImageDraw

PACK = r"G:\ArknightsCursorExtract\CrystalCursorPack"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_crystal_pack import raster_of

ROLES = ["Arrow", "UpArrow", "NWPen", "Crosshair", "SizeAll", "Person"]
sizes = {"small": 48, "medium": 68, "large": 96}
TIERS = ["small", "medium", "large"]
ZH = {"small": "小 0.50x", "medium": "中 0.71x", "large": "大 1.00x"}

W = len(TIERS) * (110 + 10) + 10
H = len(ROLES) * (110 + 24) + 24
sheet = Image.new("RGB", (W, H), (26, 28, 34))
dr = ImageDraw.Draw(sheet)

for r, role in enumerate(ROLES):
    for c, tier in enumerate(TIERS):
        e = os.path.join(PACK, "cursors", tier, "Arknights_Crystal_%s_%s.%s"
                         % (role, tier, "ani" if role in
                            ("AppStarting", "Wait", "No", "SizeNS", "SizeWE",
                             "SizeNWSE", "SizeNESW", "SizeAll") else "cur"))
        im, hx, hy = raster_of(e, 96)
        # 按档位增益缩小显示（模拟实际观感）
        g = {"small": 0.5, "medium": 2 ** -0.5, "large": 1.0}[tier]
        m = max(1, int(round(96 * g)))
        disp = im.resize((m, m), Image.LANCZOS)
        dhx, dhy = int(round(hx * g)), int(round(hy * g))
        cell = Image.new("RGBA", (110, 110), (58, 66, 80, 255))
        ox = (110 - m) // 2 + 4
        oy = (110 - m) // 2 + 4
        oy = min(oy, 110 - m)
        cell.alpha_composite(disp, (ox, oy))
        sheet.paste(cell.convert("RGB"), (10 + c * 120, 24 + r * 134))
        cx, cy = 10 + c * 120 + ox + dhx, 24 + r * 134 + oy + dhy
        dr.line([(cx - 5, cy), (cx + 5, cy)], fill=(235, 70, 70), width=1)
        dr.line([(cx, cy - 5), (cx, cy + 5)], fill=(235, 70, 70), width=1)
        if r == 0:
            dr.text((10 + c * 120, 8), ZH[tier], fill=(255, 210, 90))
    dr.text((10, 24 + r * 134 + 112), "%s   热点 96px = (%d,%d)" % (role, hx, hy),
            fill=(200, 200, 208))

sheet.save(os.path.join(PACK, "compare_tiers.png"))
print("wrote compare_tiers.png", sheet.size)

# 边缘锐度对比：96 档原图 vs LANCZOS 放大 4 倍，看是否糊
im, hx, hy = raster_of(os.path.join(PACK, "cursors", "large",
                                    "Arknights_Crystal_Arrow_large.cur"), 96)
crop = im.crop((8, 8, 40, 40))
strip = Image.new("RGB", (5 * 132 + 10, 140), (26, 28, 34))
d2 = ImageDraw.Draw(strip)
for i, (label, f) in enumerate([("96 原样 1x", Image.NEAREST),
                                ("2x", Image.NEAREST), ("4x", Image.NEAREST)]):
    z = crop.resize((128, 128), f)
    bg = Image.new("RGBA", (128, 128), (58, 66, 80, 255))
    bg.alpha_composite(z, (0, 0))
    strip.paste(bg.convert("RGB"), (10 + i * 132, 20))
    d2.text((10 + i * 132, 6), label, fill=(255, 210, 90))
z = crop.resize((128, 128), Image.LANCZOS)
bg = Image.new("RGBA", (128, 128), (58, 66, 80, 255))
bg.alpha_composite(z, (0, 0))
strip.paste(bg.convert("RGB"), (10 + 3 * 132, 20))
d2.text((10 + 3 * 132, 6), "4x LANCZOS", fill=(120, 220, 120))
strip.save(os.path.join(PACK, "edge_sharpness.png"))
print("wrote edge_sharpness.png", strip.size)
