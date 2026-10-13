# -*- coding: utf-8 -*-
"""Check what RGB the fully-transparent pixels carry.

If they are black (0,0,0), a straight-alpha LANCZOS resize bleeds black into the
edge -> visible dark halo.  Premultiplied resampling avoids that.
"""
import os, struct
from PIL import Image

D = (r"C:\Users\22442\AppData\Local\PRTS\Replica-v8-Windows"
     r"\cursors-34497b84e5b0d7cf")
SRC = os.path.join(D, "PRTS-Replica-v8-96x-normal.cur")
raw = open(SRC, "rb").read()
_r0, rtype, n = struct.unpack_from("<HHH", raw, 0)
w, h, _nc, _res, hsx, hsy, nb, off = struct.unpack_from("<BBBBHHII", raw, 6)
d = raw[off:off + nb]
im = Image.frombytes("RGBA", (w, h), d[40:40 + w * h * 4], "raw", "BGRA") \
          .transpose(Image.FLIP_TOP_BOTTOM)
px = im.load()
print("image %dx%d hotspot=(%d,%d)" % (w, h, hsx, hsy))

from collections import Counter
cnt = Counter()
alpha0_nonblack = 0
for y in range(h):
    for x in range(w):
        r, g, b, a = px[x, y]
        if a == 0:
            cnt[(r, g, b)] += 1
            if (r, g, b) != (0, 0, 0):
                alpha0_nonblack += 1
print("a==0 pixels: %d  (distinct RGB: %d)" % (sum(cnt.values()), len(cnt)))
print("a==0 with non-black RGB: %d" % alpha0_nonblack)
print("top a==0 colours:", cnt.most_common(6))

# what does a straight-alpha LANCZOS upscale do at a transparent edge?
edge = im.crop((40, 40, 56, 56))
up_straight = edge.resize((128, 128), Image.LANCZOS)
print("\nstraight-alpha LANCZOS of a 16x16 crop: min RGB where alpha>200:",
      min((r, g, b) for r, g, b, a in up_straight.getdata() if a > 200))

# premultiplied variant
import itertools
prem = Image.new("RGB", (16, 16))
pa = Image.new("L", (16, 16))
pp, ppa = prem.load(), pa.load()
for y in range(16):
    for x in range(16):
        r, g, b, a = edge.getpixel((x, y))
        f = a / 255.0
        pp[x, y] = (int(r * f + 0.5), int(g * f + 0.5), int(b * f + 0.5))
        ppa[x, y] = a
ups, upa = prem.resize((128, 128), Image.LANCZOS), pa.resize((128, 128), Image.LANCZOS)
sp, sap = ups.load(), upa.load()
mn = 255
for y in range(128):
    for x in range(128):
        a = sap[x, y]
        if a > 200:
            f = 255.0 / a
            r, g, b = sp[x, y]
            mn = min(mn, int(r * f + 0.5), int(g * f + 0.5), int(b * f + 0.5))
print("premultiplied LANCZOS, same criterion:      ", mn)
