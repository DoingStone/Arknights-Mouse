# -*- coding: utf-8 -*-
"""A/B: straight-alpha vs premultiplied-alpha LANCZOS, at matched alpha levels.

Both resamplers produce the same ALPHA plane, so any RGB difference at equal
alpha is resampler bleed.  We report how much darker straight-alpha goes in the
band that matters (mid alpha, adjacent to transparency).
"""
import os, struct
from PIL import Image

D = (r"C:\Users\22442\AppData\Local\PRTS\Replica-v8-Windows"
     r"\cursors-34497b84e5b0d7cf")
raw = open(os.path.join(D, "PRTS-Replica-v8-96x-normal.cur"), "rb").read()
w, h, _nc, _res, hsx, hsy, nb, off = struct.unpack_from("<BBBBHHII", raw, 6)
src = Image.frombytes("RGBA", (w, h), raw[off + 40:off + 40 + w * h * 4],
                      "raw", "BGRA").transpose(Image.FLIP_TOP_BOTTOM)


def premul_resize(im, size):
    w, h = im.size
    s = im.load()
    pm = Image.new("RGB", (w, h)); al = Image.new("L", (w, h))
    p, a_ = pm.load(), al.load()
    for y in range(h):
        for x in range(w):
            r, g, b, a = s[x, y]
            f = a / 255.0
            p[x, y] = (int(r * f), int(g * f), int(b * f))
            a_[x, y] = a
    ps, as_ = pm.resize((size, size), Image.LANCZOS), al.resize((size, size), Image.LANCZOS)
    out = Image.new("RGBA", (size, size))
    o, sp, ap = out.load(), ps.load(), as_.load()
    for y in range(size):
        for x in range(size):
            a = ap[x, y]
            if a == 0:
                continue
            f = 255.0 / a
            r, g, b = sp[x, y]
            o[x, y] = (min(255, int(r * f)), min(255, int(g * f)), min(255, int(b * f)), a)
    return out, as_


for size in (32, 48, 64, 128):
    st = src.resize((size, size), Image.LANCZOS)
    pm, alpha = premul_resize(src, size)
    sp, pp, ap = st.load(), pm.load(), alpha.load()
    diffs, worse_than_expected = [], 0
    for y in range(size):
        for x in range(size):
            a = ap[x, y]
            if a < 24:
                continue
            sr = sum(sp[x, y][:3]) / 3.0
            pr = sum(pp[x, y][:3]) / 3.0
            diffs.append(pr - sr)
            if pr < sr - 4:
                worse_than_expected += 1
    n = len(diffs)
    print("%3dpx  compared %5d px (alpha>=24):  mean(premul-straight)=%+7.2f  "
          "min=%+7.2f  max=%+7.2f  premul-brighter-in=%d (%.1f%%)"
          % (size, n, sum(diffs) / n, min(diffs), max(diffs),
             worse_than_expected, 100.0 * worse_than_expected / n))
    # count how many pixels straight-alpha drove to near-black that premul kept light
    dark_straight = sum(1 for y in range(size) for x in range(size)
                        if ap[x, y] >= 64 and sum(sp[x, y][:3]) / 3.0 < 40
                        and sum(pp[x, y][:3]) / 3.0 >= 40)
    print("        straight-alpha forced near-black while premul kept light: %d px" % dark_straight)
