# -*- coding: utf-8 -*-
"""模板匹配定标：把 96px 原生美术按各比例合成到游戏背景色上，
与游戏截图里的指针区域做归一化相关，取最佳比例。"""
import os, importlib.machinery
from PIL import Image

TOOL = r'G:\ArknightsCursorExtract\CursorSizeTool\ArknightsCursorSize.pyw'
NAT = r'G:\ArknightsCursorExtract\CrystalCursorPack\extracted\Arknights_Crystal_Arrow_native96.png'
OUT = r'G:\ArknightsCursorExtract\_diag\gameptr'
mod = importlib.machinery.SourceFileLoader('acsize', TOOL).load_module()
nat = Image.open(NAT).convert('RGBA')
game = Image.open(os.path.join(OUT, 'user_game.png')).convert('RGB')

# 游戏区域，含足够留白
GX, GY, GW2, GH2 = 328, 326, 197, 206
gsub = game.crop((GX, GY, GX+GW2, GY+GH2)).convert('L')
gp = gsub.load()

# 背景色：取区域四角中位数
corner = []
for (x, y) in [(2,2), (GW2-3,2), (2,GH2-3), (GW2-3,GH2-3), (2,GH2//2), (GW2-3,GH2//2)]:
    corner.append(gp[x, y])
corner.sort(); BG = corner[len(corner)//2]
print('game crop %dx%d  background L=%d' % (GW2, GH2, BG))

# 游戏裁剪里的指针亮度场（减背景、归一化）
gf = [[max(0, gp[x, y] - BG) / float(255 - BG) for x in range(GW2)] for y in range(GH2)]
# 定位重心，用于对齐
def centroid(f, w, h):
    s = sx = sy = 0.0
    for y in range(h):
        for x in range(w):
            v = f[y][x]
            if v > 0.02:
                s += v; sx += v*x; sy += v*y
    return (sx/s, sy/s, s) if s else (0, 0, 0)
gcx, gcy, gmass = centroid(gf, GW2, GH2)
print('game: centroid=(%.2f,%.2f) mass=%.1f' % (gcx, gcy, gmass))

print()
print('scale  size   NCC      best_offset   mass_ratio')
np_ = nat.load()
nat_a = [[np_[x, y][3] / 255.0 for x in range(96)] for y in range(96)]

results = []
for s in [round(0.90 + 0.02*i, 2) for i in range(36)]:
    size = int(round(96 * s))
    im = mod.premul_resize(nat, size)
    p = im.load()
    f = [[p[x, y][3] / 255.0 for x in range(size)] for y in range(size)]
    cx, cy, mass = centroid(f, size, size)
    best = (-2.0, None)
    for dy in range(-14, 15, 1):
        for dx in range(-14, 15, 1):
            ox = int(round(gcx - cx)) + dx
            oy = int(round(gcy - cy)) + dy
            # NCC
            n = 0; sa = 0.0; sb = 0.0; saa = 0.0; sbb = 0.0; sab = 0.0
            for y in range(size):
                gy = oy + y
                if gy < 0 or gy >= GH2: continue
                row = f[y]; grow = gf[gy]
                for x in range(size):
                    gx = ox + x
                    if gx < 0 or gx >= GW2: continue
                    a = row[x]
                    if a < 0.02: continue
                    b = grow[gx]
                    n += 1; sa += a; sb += b
                    saa += a*a; sbb += b*b; sab += a*b
            if n < 200: continue
            ma = sa/n; mb = sb/n
            va = saa/n - ma*ma; vb = sbb/n - mb*mb
            if va <= 0 or vb <= 0: continue
            ncc = (sab/n - ma*mb) / ((va*vb) ** 0.5)
            if ncc > best[0]:
                best = (ncc, (ox, oy), n, mass)
    if best[1]:
        results.append((best[0], s, size, best[1], best[3]))
results.sort(reverse=True)
for ncc, s, size, off, mass in results[:12]:
    print('%5.2f  %4d  %.4f  %-12s  %.3f' % (s, size, ncc, str(off), mass/gmass))
print()
print('BEST: scale=%.2f  size=%dpx  NCC=%.4f' % (results[0][1], results[0][2], results[0][0]))
