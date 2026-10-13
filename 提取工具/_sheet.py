# -*- coding: utf-8 -*-
"""Render contact sheets of ALL Texture2D >= 20px in every ArKnights .assets,
so a crystal/PRTS-shaped pointer cannot hide."""
import os, sys, traceback

import UnityPy
from PIL import Image

GAME = r"G:\Hypergryph Launcher\games\Arknights\Arknights_Data"
OUT = r"G:\ArknightsCursorExtract\_sheets"
os.makedirs(OUT, exist_ok=True)

MIN = 20
CELL = 96
COLS = 12
MAX_PER_SHEET = 144

found = []          # (assetfile, pathid, name, w, h, PIL)
errors = []

targets = [f for f in sorted(os.listdir(GAME))
           if f.endswith(".assets")]
print("asset files:", len(targets))

for fn in targets:
    p = os.path.join(GAME, fn)
    try:
        env = UnityPy.load(p)
    except Exception as ex:
        errors.append((fn, "load", str(ex)[:120]))
        continue
    n = 0
    for obj in env.objects:
        if obj.type.name != "Texture2D":
            continue
        try:
            d = obj.read()
            w = int(getattr(d, "m_Width", 0) or 0)
            h = int(getattr(d, "m_Height", 0) or 0)
            if w < MIN or h < MIN:
                continue
            name = str(getattr(d, "m_Name", "?"))
            im = d.image
            if im is None:
                continue
            im = im.convert("RGBA")
            found.append((fn, obj.path_id, name, w, h, im))
            n += 1
        except Exception as ex:
            errors.append((fn, str(obj.path_id), str(ex)[:100]))
    print("  %-30s textures>=%d : %d" % (fn, MIN, n))

print("\ntotal big textures: %d   errors: %d" % (len(found), len(errors)))

# ---- contact sheets ----
found.sort(key=lambda t: (t[0], -t[3] * t[4]))
sheets = 0
idx = 0
while idx < len(found):
    batch = found[idx:idx + MAX_PER_SHEET]
    idx += MAX_PER_SHEET
    rows = (len(batch) + COLS - 1) // COLS
    sheet = Image.new("RGB", (COLS * (CELL + 4), rows * (CELL + 22)), (24, 26, 30))
    from PIL import ImageDraw
    dr = ImageDraw.Draw(sheet)
    for k, (af, pid, name, w, h, im) in enumerate(batch):
        cx = (k % COLS) * (CELL + 4)
        cy = (k // COLS) * (CELL + 22)
        th = im.copy()
        th.thumbnail((CELL, CELL), Image.LANCZOS)
        # checkerboard behind
        bg = Image.new("RGB", (CELL, CELL), (60, 62, 68))
        for yy in range(0, CELL, 8):
            for xx in range(0, CELL, 8):
                if ((xx // 8) + (yy // 8)) % 2:
                    for a in range(xx, min(xx + 8, CELL)):
                        for b in range(yy, min(yy + 8, CELL)):
                            bg.putpixel((a, b), (92, 94, 100))
        bg.paste(th, ((CELL - th.width) // 2, (CELL - th.height) // 2), th)
        sheet.paste(bg, (cx, cy))
        dr.text((cx + 2, cy + CELL + 2), "%dx%d %s" % (w, h, name[:13]), fill=(210, 210, 215))
    sp = os.path.join(OUT, "sheet_%02d.png" % sheets)
    sheet.save(sp)
    print("wrote %s  (%d items)" % (sp, len(batch)))
    sheets += 1

print("\nsheets:", sheets)
if errors:
    print("\n[first 20 errors]")
    for e in errors[:20]:
        print("   ", e)
