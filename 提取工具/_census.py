# -*- coding: utf-8 -*-
"""Census of every Texture2D in one Unity asset file, plus a contact sheet.

Purpose: the task requires listing ALL pointer-like resources and their
provenance, and requires deciding whether the art in question is really the
game's pointer art.  This enumerates the file exhaustively instead of guessing,
and renders every texture into one sheet so the shapes can be compared.
"""
import os
import sys

import UnityPy
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ASSET = sys.argv[1] if len(sys.argv) > 1 else \
    r"G:\Hypergryph Launcher\games\Arknights\Arknights_Data\sharedassets0.assets"

FMT = {1: "Alpha8", 2: "ARGB4444", 3: "RGB24", 4: "RGBA32", 5: "ARGB32",
       7: "RGB565", 10: "DXT1", 12: "DXT5", 25: "ASTC_RGB_8x8",
       47: "ASTC_RGBA_8x8", 48: "ASTC_RGBA_6x6", 63: "ETC_RGB4"}


def cjk_font(size=12):
    for p in (r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\simhei.ttf",
              r"C:\Windows\Fonts\simsun.ttc"):
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()


print("asset: %s" % ASSET)
print("bytes: %d" % os.path.getsize(ASSET))
env = UnityPy.load(ASSET)

types = {}
for o in env.objects:
    types[o.type.name] = types.get(o.type.name, 0) + 1
print("\nobject types in this file:")
for t in sorted(types, key=lambda k: -types[k]):
    print("  %-24s %d" % (t, types[t]))

tex = [o for o in env.objects if o.type.name == "Texture2D"]
print("\nTexture2D objects: %d" % len(tex))

rows = []
for o in tex:
    d = o.read()
    name = getattr(d, "m_Name", "?")
    w, h, fmt = d.m_Width, d.m_Height, d.m_TextureFormat
    cis = getattr(d, "m_CompleteImageSize", None)
    mips = getattr(d, "m_MipCount", None)
    try:
        im = d.image.convert("RGBA")
        err = ""
    except Exception as e:
        im = None
        err = str(e)[:60]
    rows.append(dict(pid=o.path_id, name=name, w=w, h=h, fmt=fmt, cis=cis,
                     mips=mips, im=im, err=err))
    print("  path_id=%-8d %-34s %3dx%-3d fmt=%-2d %-11s complete=%s mips=%s%s"
          % (o.path_id, name, w, h, fmt, FMT.get(fmt, "?"), cis, mips,
             ("  ERR:" + err) if err else ""))

# non-texture objects that mention cursor, for provenance
print("\nnon-Texture2D objects whose name mentions cursor/pointer/arrow:")
for o in env.objects:
    if o.type.name == "Texture2D":
        continue
    try:
        d = o.read()
    except Exception:
        continue
    nm = getattr(d, "m_Name", "")
    if nm and any(k in nm.lower() for k in ("cursor", "pointer", "arrow")):
        print("  %-22s path_id=%-8d %s" % (o.type.name, o.path_id, nm))

# contact sheet
if rows:
    CELL = 132
    PAD = 8
    CAP = 34
    cols = 4
    n = len(rows)
    nrows = (n + cols - 1) // cols
    W = cols * (CELL + PAD) + PAD
    H = nrows * (CELL + CAP + PAD) + PAD
    sheet = Image.new("RGB", (W, H), (28, 30, 36))
    dr = ImageDraw.Draw(sheet)
    f = cjk_font(12)
    fs = cjk_font(10)
    for i, r in enumerate(rows):
        cx = PAD + (i % cols) * (CELL + PAD)
        cy = PAD + (i // cols) * (CELL + CAP + PAD)
        dr.text((cx, cy), "%d %s" % (r["pid"], r["name"][:17]), fill=(240, 240, 240), font=f)
        dr.text((cx, cy + 15), "%dx%d fmt=%d" % (r["w"], r["h"], r["fmt"]),
                fill=(150, 195, 255), font=fs)
        # checkerboard so alpha is visible
        cellimg = Image.new("RGB", (CELL, CELL), (60, 62, 70))
        d2 = ImageDraw.Draw(cellimg)
        for yy in range(0, CELL, 11):
            for xx in range(0, CELL, 11):
                if ((xx // 11) + (yy // 11)) % 2:
                    d2.rectangle([xx, yy, xx + 10, yy + 10], fill=(78, 80, 90))
        if r["im"] is not None:
            im = r["im"]
            k = max(1, CELL // max(im.size))
            big = im.resize((im.size[0] * k, im.size[1] * k), Image.NEAREST) \
                if im.size[0] * k <= CELL and im.size[1] * k <= CELL else im
            ox = cx + (CELL - big.size[0]) // 2
            oy = cy + 28 + (CELL - big.size[1]) // 2
            cellimg_rgba = cellimg.convert("RGBA")
            cellimg_rgba.alpha_composite(big, (ox - cx, oy - cy - 28))
            cellimg = cellimg_rgba.convert("RGB")
        sheet.paste(cellimg, (cx, cy + 28))
    out = os.path.join(HERE, "extracted", "_census_%s.png"
                       % os.path.basename(ASSET).replace(".", "_"))
    sheet.save(out)
    print("\ncontact sheet -> %s  (%dx%d)" % (out, sheet.size[0], sheet.size[1]))
