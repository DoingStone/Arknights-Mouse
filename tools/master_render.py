# -*- coding: utf-8 -*-
"""Resolution-independent renderer for the Arknights pointer master.

Recovered from the game's own three shipped tiers (48 / 64 / 96 px):

  * ONE master polygon in 96 px pixel-corner space, hotspot origin O = (8, 8).
    Every shipped tier is that same polygon scaled about O by
        s = 1/2   (cursor_small,  48 px)
        s = 1/√2  (cursor_medium, 64 px)   <- NOT 2/3
        s = 1     (cursor_large,  96 px)
  * shadow layer  S = P * Gaussian_blur(mask(k*s), sigma*s) shifted by (dx*s, dy*s)
  * composite (straight alpha):
        A = B + S*(1-B)      grey = B/A      RGB = grey
    (the artwork is 100 % greyscale: pure-white body over a pure-black shadow)

Because both the outline and the shadow are *analytic* (a polygon + a Gaussian
field), any output size is re-rendered from the master rather than resampled
from a bitmap -- there is no interpolation step, so no enlargement blur.

Gaussian blur commutes with scaling:
    G_{sigma*s}(scale_s f) == scale_s(G_sigma f)
so the shadow field is computed once on the 96 px grid and resampled, which
makes large sizes cheap and exactly consistent with small ones.
"""
import json
import math
import os

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
EXTRACTED = os.path.join(HERE, "extracted")
DEFAULT_MODEL = os.path.join(EXTRACTED, "_final_model.json")

HOTSPOT96 = (8.0, 8.0)          # game-declared hotspot, identical in all 3 tiers
MASTER_CANVAS = 96


class Master(object):
    def __init__(self, model_path=DEFAULT_MODEL):
        with open(model_path, "r", encoding="utf-8") as fh:
            m = json.load(fh)
        self.poly = [(float(p[0]), float(p[1])) for p in m["polygon_96"]]
        self.origin = tuple(HOTSPOT96)
        sh = m["shadow"]
        self.k = float(sh["k"])
        self.sigma = float(sh["sigma"])
        self.dx = float(sh["dx"])
        self.dy = float(sh["dy"])
        self.P = float(sh["P"])
        self.values = [float(v) for v in self.poly[0]]
        self._shadow96 = None

    # ------------------------------------------------------------------ #
    def _scaled(self, s):
        ox, oy = self.origin
        return [(ox + (x - ox) * s, oy + (y - oy) * s) for x, y in self.poly]

    # ---------------------------------------------------------- raster ---
    @staticmethod
    def raster_cov(poly, w, h, ss=6):
        """Analytic supersampled polygon coverage in pixel-CORNER space."""
        cov = [[0.0] * w for _ in range(h)]
        n = len(poly)
        inv = 1.0 / ss
        for y in range(h):
            row = cov[y]
            for sub in range(ss):
                yy = y + (sub + 0.5) * inv
                xs = []
                for i in range(n):
                    x1, y1 = poly[i]
                    x2, y2 = poly[(i + 1) % n]
                    if (y1 > yy) != (y2 > yy):
                        xs.append(x1 + (yy - y1) * (x2 - x1) / (y2 - y1))
                xs.sort()
                for kk in range(0, len(xs) - 1, 2):
                    a = xs[kk]
                    b = xs[kk + 1]
                    if a < 0.0:
                        a = 0.0
                    if b > w:
                        b = float(w)
                    if b <= a:
                        continue
                    ia, ib = int(a), int(b)
                    if ia == ib:
                        row[ia] += (b - a) * inv
                        continue
                    row[ia] += (ia + 1 - a) * inv
                    for x in range(ia + 1, ib):
                        row[x] += inv
                    if ib < w:
                        row[ib] += (b - ib) * inv
        return cov

    # ----------------------------------------------------------- blur ---
    @staticmethod
    def blur(cov, w, h, sigma):
        if sigma <= 0.05:
            return [r[:] for r in cov]
        rad = max(1, int(math.ceil(3.0 * sigma)))
        kk = [math.exp(-0.5 * (i / sigma) ** 2) for i in range(-rad, rad + 1)]
        tot = sum(kk)
        kk = [v / tot for v in kk]
        tmp = [[0.0] * w for _ in range(h)]
        for y in range(h):
            src, dst = cov[y], tmp[y]
            for x in range(w):
                a = 0.0
                lo = x - rad
                if lo < 0:
                    lo = 0
                hi = x + rad
                if hi > w - 1:
                    hi = w - 1
                for xx in range(lo, hi + 1):
                    a += src[xx] * kk[xx - x + rad]
                dst[x] = a
        out = [[0.0] * w for _ in range(h)]
        for y in range(h):
            dst = out[y]
            lo = y - rad
            if lo < 0:
                lo = 0
            hi = y + rad
            if hi > h - 1:
                hi = h - 1
            for x in range(w):
                a = 0.0
                for yy in range(lo, hi + 1):
                    a += tmp[yy][x] * kk[yy - y + rad]
                dst[x] = a
        return out

    def shadow_field96(self):
        """Blurred shadow source mask on the 96 px grid (computed once)."""
        if self._shadow96 is None:
            mask = self.raster_cov(self._scaled(self.k), MASTER_CANVAS,
                                   MASTER_CANVAS, ss=4)
            self._shadow96 = self.blur(mask, MASTER_CANVAS, MASTER_CANVAS,
                                       self.sigma)
        return self._shadow96

    @staticmethod
    def _sample(field, w, h, fx, fy):
        if fx < 0.0 or fy < 0.0 or fx > w - 1 or fy > h - 1:
            # outside -> zero, with bilinear falloff from the border
            if fx < -1.0 or fy < -1.0 or fx > w or fy > h:
                return 0.0
        x0 = int(math.floor(fx))
        y0 = int(math.floor(fy))
        tx = fx - x0
        ty = fy - y0
        a = 0.0
        for yy, wy in ((y0, 1 - ty), (y0 + 1, ty)):
            if wy <= 0.0 or yy < 0 or yy >= h:
                continue
            row = field[yy]
            for xx, wx in ((x0, 1 - tx), (x0 + 1, tx)):
                if wx <= 0.0 or xx < 0 or xx >= w:
                    continue
                a += row[xx] * wx * wy
        return a

    # --------------------------------------------------------- render ---
    def render(self, size, ss=6):
        """Render the pointer into a size x size RGBA PIL image."""
        s = float(size) / MASTER_CANVAS
        body = self.raster_cov(self._scaled(s), size, size, ss=ss)
        field = self.shadow_field96()
        W = MASTER_CANVAS
        P = self.P
        dx, dy = self.dx, self.dy
        out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        px = out.load()
        inv = 1.0 / s
        for j in range(size):
            fj = (j + 0.5) * inv - 0.5 - dy
            rowb = body[j]
            for i in range(size):
                B = rowb[i]
                if B > 1.0:
                    B = 1.0
                fi = (i + 0.5) * inv - 0.5 - dx
                Sv = P * self._sample(field, W, W, fi, fj)
                if Sv < 0.0:
                    Sv = 0.0
                elif Sv > 1.0:
                    Sv = 1.0
                A = B + Sv * (1.0 - B)
                if A <= 0.0:
                    continue
                g = B / A
                if g > 1.0:
                    g = 1.0
                av = int(A * 255.0 + 0.5)
                if av <= 0:
                    continue
                gv = int(g * 255.0 + 0.5)
                px[i, j] = (gv, gv, gv, av)
        return out

    def hotspot(self, size):
        """Windows cursor hotspot in the size x size bitmap."""
        s = float(size) / MASTER_CANVAS
        # the game keeps the tip at pixel (8,8) in every tier, and declares the
        # hotspot as (8,8) in every tier -- so the hotspot does NOT scale.
        _ = s
        return (int(self.origin[0]), int(self.origin[1]))


# ------------------------------------------------------------------ CLI ---
def _main():
    import sys
    master = Master()
    print("master polygon: %d vertices" % len(master.poly))
    print("shadow: k=%.4f sigma=%.3f d=(%.3f,%.3f) P=%.4f"
          % (master.k, master.sigma, master.dx, master.dy, master.P))
    outdir = os.path.join(HERE, "render")
    if not os.path.isdir(outdir):
        os.makedirs(outdir)
    sizes = [int(a) for a in sys.argv[1:]] or [32, 48, 64, 96, 128, 256]
    for s in sizes:
        im = master.render(s)
        p = os.path.join(outdir, "render_%03d.png" % s)
        im.save(p)
        print("  %3dpx -> %s   hotspot=%s" % (s, p, master.hotspot(s)))


if __name__ == "__main__":
    _main()
