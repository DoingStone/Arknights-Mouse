# -*- coding: utf-8 -*-
import os
from PIL import Image

NAT = r'G:\ArknightsCursorExtract\CrystalCursorPack\extracted\Arknights_Crystal_Arrow_native96.png'
im = Image.open(NAT).convert('RGBA')
a = im.getchannel('A'); px = a.load()
w, h = im.size
print('source native:', im.size)
for thr in (8, 40, 60, 90, 120, 150, 180):
    x0, y0, x1, y1, n = 999, 999, -1, -1, 0
    for y in range(h):
        for x in range(w):
            if px[x, y] >= thr:
                n += 1; x0=min(x0,x); x1=max(x1,x); y0=min(y0,y); y1=max(y1,y)
    if x1 >= 0:
        print('  a>=%3d -> bbox %3dx%-3d  @(%d,%d)  px=%d' % (thr, x1-x0+1, y1-y0+1, x0, y0, n))

# 游戏内实测（截图，含阴影）
sx, sy = 57, 94
for athr, lab in ((60, 'thr60  58x97'), (90, 'thr90  57x95'), (120, 'thr120 57x94')):
    pass
print()
print('=== 由截图反推游戏内有效比例 ===')
meas = [(60, 58, 97), (90, 57, 95), (120, 57, 94)]
# 源图 a>=60 的 bbox
for thr, mw, mh in meas:
    x0, y0, x1, y1 = 999, 999, -1, -1
    for y in range(h):
        for x in range(w):
            if px[x, y] >= thr:
                x0=min(x0,x); x1=max(x1,x); y0=min(y0,y); y1=max(y1,y)
    bw, bh = x1-x0+1, y1-y0+1
    print('  thr=%3d  源 bbox %3dx%-3d  -> 截图 %3dx%-3d  =>  x %.3f  y %.3f'
          % (thr, bw, bh, mw, mh, mw/float(bw), mh/float(bh)))
