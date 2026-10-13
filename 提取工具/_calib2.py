# -*- coding: utf-8 -*-
"""用「实心白」区域做尺度标定：背景混合对 >=240 的像素影响可忽略。"""
import os, importlib.machinery
from PIL import Image

TOOL = r'G:\ArknightsCursorExtract\CursorSizeTool\ArknightsCursorSize.pyw'
NAT = r'G:\ArknightsCursorExtract\CrystalCursorPack\extracted\Arknights_Crystal_Arrow_native96.png'
OUT = r'G:\ArknightsCursorExtract\_diag\gameptr'
mod = importlib.machinery.SourceFileLoader('acsize', TOOL).load_module()
nat = Image.open(NAT).convert('RGBA')
game = Image.open(os.path.join(OUT, 'user_game.png')).convert('RGB')
gsub = game.crop((328, 326, 328+197, 326+206))
gp = gsub.load()

def solid_bbox_rgb(im, thr=240):
    p = im.load(); w, h = im.size
    x0, y0, x1, y1, n = 9999, 9999, -1, -1, 0
    for y in range(h):
        for x in range(w):
            r, g, b = p[x, y]
            if r >= thr and g >= thr and b >= thr:
                n += 1
                x0=min(x0,x); x1=max(x1,x); y0=min(y0,y); y1=max(y1,y)
    return (x1-x0+1, y1-y0+1, x0, y0, n) if x1 >= 0 else (0,0,0,0,0)

def solid_bbox_rgba(im, thr=240):
    p = im.load(); w, h = im.size
    x0, y0, x1, y1, n = 9999, 9999, -1, -1, 0
    for y in range(h):
        for x in range(w):
            r, g, b, a = p[x, y]
            if a >= thr and r >= thr and g >= thr and b >= thr:
                n += 1
                x0=min(x0,x); x1=max(x1,x); y0=min(y0,y); y1=max(y1,y)
    return (x1-x0+1, y1-y0+1, x0, y0, n) if x1 >= 0 else (0,0,0,0,0)

gw, gh, gx, gy, gn = solid_bbox_rgb(gsub)
print('GAME crop solid-white bbox = %dx%d @(%d,%d) px=%d' % (gw, gh, gx, gy, gn))
nw, nh, nx, ny, nn = solid_bbox_rgba(nat)
print('NATIVE96 solid-white bbox  = %dx%d @(%d,%d) px=%d' % (nw, nh, nx, ny, nn))
print()
print('scale   size  bbox        area    w_ratio  h_ratio  area_ratio')
for s in [0.50,0.60,0.70,0.75,0.80,0.90,1.00,1.10,1.20,1.30,1.50]:
    size = int(round(96*s))
    im = mod.premul_resize(nat, size)
    w, h, x, y, n = solid_bbox_rgba(im)
    print('%5.2f  %4d  %3dx%-3d  %6d   %.3f    %.3f    %.3f'
          % (s, size, w, h, n, w/float(gw), h/float(gh), n/float(gn)))
