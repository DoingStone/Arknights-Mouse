# -*- coding: utf-8 -*-
"""Verify the built pack: 96 raster must be pixel-identical to the source,
small rasters must be halo-free, and every raster's hotspot must be correct."""
import json, os, struct
from PIL import Image

PACK = r"G:\ArknightsCursorExtract\CrystalCursorPack"
D = (r"C:\Users\22442\AppData\Local\PRTS\Replica-v8-Windows"
     r"\cursors-34497b84e5b0d7cf")
SRC = os.path.join(D, "PRTS-Replica-v8-96x-normal.cur")


def parse_cur(path):
    raw = open(path, "rb").read()
    _r0, rtype, n = struct.unpack_from("<HHH", raw, 0)
    assert rtype == 2, path
    out = []
    for i in range(n):
        w, h, _nc, _res, hsx, hsy, nb, off = struct.unpack_from("<BBBBHHII", raw, 6 + 16 * i)
        w, h = w or 256, h or 256
        d = raw[off:off + nb]
        assert d[:4] != b"\x89PNG", "PNG payload not handled here"
        im = Image.frombytes("RGBA", (w, h), d[40:40 + w * h * 4], "raw", "BGRA")
        out.append((im.transpose(Image.FLIP_TOP_BOTTOM), hsx, hsy, w, h))
    return out


src_im = parse_cur(SRC)[0][0]
print("source normal.cur raster: %dx%d" % src_im.size)

dst = parse_cur(os.path.join(PACK, "cursors", "Arknights_Crystal_Arrow.cur"))
print("pack Arrow rasters: %s" % [(r[3], r[4], "hot=%d,%d" % (r[1], r[2])) for r in dst])

# 1. the 96 raster must be bit-identical
r96 = [r for r in dst if r[3] == 96][0]
same = (list(r96[0].getdata()) == list(src_im.getdata()))
print("\n96 raster identical to source: %s" % same)

# 2. halo check: for every raster, compute the min RGB among partially-transparent
#    edge pixels that sit next to transparency.  A black-bleed halo shows up as
#    near-black RGB on a pixel that should still be light grey.
for im, hx, hy, w, h in sorted(dst, key=lambda r: r[3]):
    px = im.load()
    worst = 255
    worstat = None
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if 40 < a < 255:
                # a mid-alpha edge pixel of the crystal should be reasonably light
                lum = (r + g + b) / 3.0
                if lum < worst:
                    worst, worstat = lum, (x, y, (r, g, b, a))
    print("  %3dx%-3d  darkest mid-alpha edge px: lum=%6.1f  at %s" % (w, h, worst, worstat))

# 3. hotspot scaling for the 32 raster (the Windows default size)
r32 = [r for r in dst if r[3] == 32][0]
print("\n32px raster hotspot = (%d,%d)  [expected round(28*32/96)=%d, round(20*32/96)=%d]"
      % (r32[1], r32[2], round(28 * 32 / 96), round(20 * 32 / 96)))

mf = os.path.join(PACK, "_manifest.json")
if os.path.exists(mf):
    man = json.load(open(mf, encoding="utf-8"))
    print("\nmanifest roles: %d" % len(man) if isinstance(man, list) else "\nmanifest keys: %s" % list(man)[:8])
print("\nfiles in pack:")
for root, dirs, files in os.walk(PACK):
    for f in sorted(files)[:40]:
        p = os.path.join(root, f)
        print("   %-58s %9d B" % (os.path.relpath(p, PACK), os.path.getsize(p)))
