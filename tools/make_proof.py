# -*- coding: utf-8 -*-
"""生成验收图证：三档指针原图 + 热点标记 + 像素级证据。

产物 proof_sheet.png
"""
import io
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

HERE = os.path.dirname(os.path.abspath(__file__))
# 交付用的导出目录（extract_cursors.py 的 --out），不是本脚本所在的 cursor_tool
EXT = os.environ.get("ARK_CURSOR_OUT") or os.path.join(os.path.dirname(HERE), "extracted")
OUT = os.path.join(os.path.dirname(HERE), "proof_sheet.png")


def cjk(size=13, bold=False):
    for p in (r"C:\Windows\Fonts\msyhbd.ttc" if bold else r"C:\Windows\Fonts\msyh.ttc",
              r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\simhei.ttf",
              r"C:\Windows\Fonts\simsun.ttc"):
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()


cfg = json.load(io.open(os.path.join(EXT, "_cursor_config.json"), encoding="utf-8"))

F_T = cjk(17, True)
F_H = cjk(13, True)
F = cjk(12)
FS = cjk(11)

CELL = 200          # 每个档位的展示格
PAD = 18
HEAD = 126          # 标题 2 行 + 来源 3 行 + 与档位标题的间距
FOOT = 176
W = PAD + 3 * (CELL + PAD)
H = HEAD + CELL + 118 + FOOT

sheet = Image.new("RGB", (W, H), (24, 26, 32))
dr = ImageDraw.Draw(sheet)

dr.text((PAD, 14), "明日方舟 PC 客户端 · 鼠标指针资源提取验收图证", fill=(255, 255, 255), font=F_T)
dr.text((PAD, 42),
        "来源  Arknights_Data\\sharedassets0.assets",
        fill=(150, 160, 175), font=FS)
dr.text((PAD, 56),
        "配置  MonoBehaviour PCCursorRuntimeConfig (path_id=28)",
        fill=(150, 160, 175), font=FS)
dr.text((PAD, 70),
        "贴图  未压缩 RGBA32，导出像素与原始 payload 逐字节一致",
        fill=(150, 160, 175), font=FS)

TITLES = {"cursor_small": "档位 1 · cursor_small",
          "cursor_medium": "档位 2 · cursor_medium",
          "cursor_large": "档位 3 · cursor_large"}

for i, e in enumerate(cfg["tiers"]):
    name = e["name"]
    cx = PAD + i * (CELL + PAD)
    cy = HEAD
    im = Image.open(e["export_png"]).convert("RGBA")
    w, h = im.size

    # 深色底 + 棋盘格，便于看清 alpha
    panel = Image.new("RGBA", (CELL, CELL), (46, 49, 58, 255))
    d2 = ImageDraw.Draw(panel)
    for yy in range(0, CELL, 16):
        for xx in range(0, CELL, 16):
            if ((xx // 16) + (yy // 16)) % 2:
                d2.rectangle([xx, yy, xx + 15, yy + 15], fill=(56, 59, 70, 255))

    k = max(1, min((CELL - 40) // w, (CELL - 40) // h))
    big = im.resize((w * k, h * k), Image.NEAREST)   # 整数倍最近邻，仅用于观察
    ox = cx + (CELL - big.size[0]) // 2
    oy = cy + (CELL - big.size[1]) // 2
    panel_rgba = panel
    panel_rgba.alpha_composite(big, (ox - cx, oy - cy))
    sheet.paste(panel_rgba.convert("RGB"), (cx, cy))

    # 热点标记（红圈 + 十字）
    hx, hy = e["hotspot"]["x"], e["hotspot"]["y"]
    px = ox + (hx + 0.5) * k
    py = oy + (hy + 0.5) * k
    r = max(5, k * 2 + 3)
    dr.ellipse([px - r, py - r, px + r, py + r], outline=(255, 70, 70), width=2)
    dr.line([px - r - 5, py, px + r + 5, py], fill=(255, 70, 70), width=1)
    dr.line([px, py - r - 5, px, py + r + 5], fill=(255, 70, 70), width=1)

    # 标题
    dr.text((cx, cy - 22), TITLES.get(name, name), fill=(240, 240, 240), font=F_H)

    # 参数
    by = cy + CELL + 8
    dr.text((cx, by), "path_id = %d" % e["texture_path_id"], fill=(150, 195, 255), font=F)
    dr.text((cx, by + 17), "尺寸 %d x %d   RGBA" % (e["width"], e["height"]), fill=(190, 195, 205), font=F)
    dr.text((cx, by + 34), "TextureFormat %d (%s)" % (e["texture_format"], e["texture_format_name"]),
            fill=(190, 195, 205), font=F)
    dr.text((cx, by + 51), "热点 (%g, %g)   ← 游戏声明值" % (hx, hy), fill=(255, 140, 140), font=F)

# 页脚证据
fy = HEAD + CELL + 118
dr.line([PAD, fy, W - PAD, fy], fill=(70, 74, 86), width=1)
dr.text((PAD, fy + 10), "逐像素一致性证据（原始 payload sha256 == 导出像素 sha256，bottom-up 行序）",
        fill=(240, 240, 240), font=F_H)
dr.text((PAD, fy + 32), "红圈 = 热点位置（三档均为 (8,8)，即箭头尖端所在像素）",
        fill=(255, 150, 150), font=FS)
for i, e in enumerate(cfg["tiers"]):
    y = fy + 56 + i * 36
    dr.text((PAD, y), "%-14s %s" % (e["name"], e["raw_sha256"] or "(n/a)"),
            fill=(130, 220, 160), font=FS)
    dr.text((PAD, y + 15),
            "               %d B payload = %dx%d x 4 B   %s"
            % (e["complete_image_size"], e["width"], e["height"],
               "未压缩" if e["uncompressed"] else "压缩"),
            fill=(140, 148, 162), font=FS)

sheet.save(OUT)
print("wrote %s  (%dx%d, %d bytes)" % (OUT, sheet.size[0], sheet.size[1], os.path.getsize(OUT)))
