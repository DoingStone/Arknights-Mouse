# -*- coding: utf-8 -*-
"""Is the crystal pointer FLAT-FACETED (vectorisable) or a continuous render?

If large regions share one constant luminance, the art is a flat-shaded low-poly
render and can be traced to polygons -> re-rendered at ANY size analytically
(genuinely lossless enlargement).  If luminance varies smoothly everywhere,
vectorisation is impossible and upscaling must be interpolation.
"""
import collections

from PIL import Image

SRC = r"G:\ArknightsCursorExtract\_probe_crystal\img_00_96x96_hot28_20.png"
im = Image.open(SRC).convert("RGBA")
w, h = im.size
px = im.load()

# ---------- full luminance histogram of opaque pixels ----------
lum = {}
for y in range(h):
    for x in range(w):
        r, g, b, a = px[x, y]
        if a > 200:
            lum[(x, y)] = r
hist = collections.Counter(lum.values())
tot = len(lum)
print("opaque pixels (a>200): %d" % tot)
print("distinct luminance values: %d" % len(hist))
print("\nluminance histogram (all bins, value:count):")
items = sorted(hist.items())
line = []
for v, c in items:
    line.append("%d:%d" % (v, c))
    if len(line) == 8:
        print("   " + "  ".join(line))
        line = []
if line:
    print("   " + "  ".join(line))

big = [(v, c) for v, c in items if c >= 20]
print("\nbins holding >=20 px (%d of %d bins, covering %d px = %.1f%%):"
      % (len(big), len(items), sum(c for _, c in big), 100.0 * sum(c for _, c in big) / tot))
for v, c in sorted(big, key=lambda kv: -kv[1]):
    print("   lum=%3d  count=%-5d %.1f%%" % (v, c, 100.0 * c / tot))

# ---------- facet segmentation: 4-connected components with luminance tolerance ----------
def segment(tol):
    seen = [[False] * w for _ in range(h)]
    comps = []
    for y0 in range(h):
        for x0 in range(w):
            if seen[y0][x0] or (x0, y0) not in lum:
                continue
            base = lum[(x0, y0)]
            stack = [(x0, y0)]
            seen[y0][x0] = True
            members = []
            while stack:
                x, y = stack.pop()
                members.append((x, y))
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < w and 0 <= ny < h and not seen[ny][nx] and (nx, ny) in lum:
                        if abs(lum[(nx, ny)] - base) <= tol:
                            seen[ny][nx] = True
                            stack.append((nx, ny))
            comps.append((len(members), base, members))
    comps.sort(reverse=True, key=lambda c: c[0])
    return comps


for tol in (0, 2, 4, 8):
    comps = segment(tol)
    covered = sum(c[0] for c in comps)
    top1 = comps[0][0] if comps else 0
    top10 = sum(c[0] for c in comps[:10])
    print("\n[tol=%d] components=%d  px=%d" % (tol, len(comps), covered))
    print("   largest=%d (%.1f%%)  top10=%d (%.1f%%)  comps>=50px: %d"
          % (top1, 100.0 * top1 / covered, top10, 100.0 * top10 / covered,
             sum(1 for c in comps if c[0] >= 50)))
    if tol == 4:
        print("   top 20 facets:")
        for n, base, mem in comps[:20]:
            xs = [m[0] for m in mem]
            ys = [m[1] for m in mem]
            print("      lum=%-4d px=%-5d bbox=(%d,%d)-(%d,%d)" % (base, n, min(xs), min(ys), max(xs), max(ys)))

# ---------- interior gradient test: mean |grad| inside opaque area ----------
gs = []
for y in range(h - 1):
    for x in range(w - 1):
        if (x, y) in lum and (x + 1, y) in lum:
            gs.append(abs(lum[(x, y)] - lum[(x + 1, y)]))
        if (x, y) in lum and (x, y + 1) in lum:
            gs.append(abs(lum[(x, y)] - lum[(x, y + 1)]))
gs.sort()
n = len(gs)
print("\ninterior horizontal/vertical |grad| over %d samples:" % n)
print("   mean=%.2f  median=%d  p90=%d  p99=%d  max=%d  zero=%.1f%%"
      % (sum(gs) / n, gs[n // 2], gs[int(n * 0.9)], gs[int(n * 0.99)], gs[-1],
         100.0 * sum(1 for v in gs if v == 0) / n))
