# -*- coding: utf-8 -*-
"""Characterise the crystal pointer's colour/luminance structure.

If it is a flat-shaded low-poly mesh (each facet one solid grey, straight edges)
then it can be traced to polygons and re-rendered at ANY size analytically.
"""
import collections

from PIL import Image

SRC = r"G:\ArknightsCursorExtract\_probe_crystal\img_00_96x96_hot28_20.png"
im = Image.open(SRC).convert("RGBA")
w, h = im.size
px = im.load()
print("size=%dx%d" % (w, h))

# --- is it greyscale?
nong = 0
for y in range(h):
    for x in range(w):
        r, g, b, a = px[x, y]
        if a > 8 and not (r == g == b):
            nong += 1
print("non-greyscale pixels (a>8): %d" % nong)

# --- luminance histogram of opaque-ish pixels
hist = collections.Counter()
for y in range(h):
    for x in range(w):
        r, g, b, a = px[x, y]
        if a > 200:
            hist[r] += 1
print("\nluminance histogram (alpha>200), non-zero bins:")
tot = sum(hist.values())
run = []
for v in range(256):
    if hist[v]:
        run.append((v, hist[v]))
for v, c in run:
    print("   %3d  %5d  %.2f%%" % (v, c, 100.0 * c / tot))
print("   distinct luminance values among opaque: %d   total px: %d" % (len(run), tot))

# --- facet test: how many 3x3 neighbourhoods are perfectly uniform?
uniform = 0
partial = 0
for y in range(1, h - 1):
    for x in range(1, w - 1):
        vals = [px[x + dx, y + dy] for dy in (-1, 0, 1) for dx in (-1, 0, 1)]
        if any(v[3] < 200 for v in vals):
            continue
        if len({(v[0], v[3]) for v in vals}) == 1:
            uniform += 1
        else:
            partial += 1
print("\n3x3 flat test: uniform=%d  gradient=%d  (%.1f%% flat)" % (
    uniform, partial, 100.0 * uniform / max(1, uniform + partial)))

# --- edge detection: count strong-gradient pixels (facet seams)
edges = 0
for y in range(1, h - 1):
    for x in range(1, w - 1):
        r, g, b, a = px[x, y]
        if a < 200:
            continue
        best = 0
        for dx, dy in ((1, 0), (0, 1)):
            r2, g2, b2, a2 = px[x + dx, y + dy]
            if a2 > 200:
                best = max(best, abs(r - r2))
        if best > 25:
            edges += 1
print("strong-gradient pixels (facet seams): %d  (%.1f%% of opaque)" % (
    edges, 100.0 * edges / max(1, tot)))

# --- ASCII map of luminance bands (to read the facet layout)
print("\nluminance band map (# dark .. @ bright, blank = transparent):")
bands = " .:-=+*#%@"[::-1]
for y in range(0, h, 2):
    line = []
    for x in range(0, w, 1):
        r, g, b, a = px[x, y]
        if a < 40:
            line.append(" ")
        else:
            line.append(bands[min(9, r * 10 // 256)])
    print("   " + "".join(line))
