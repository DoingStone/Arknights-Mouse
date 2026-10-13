# -*- coding: utf-8 -*-
"""①③ 的原帧证据：把 prtsfx 真正会下发的那几枚 HCURSOR 抠成位图看。

关键点：不是看「源 PNG 长什么样」，而是看 **set_raw 拿到的那个 HCURSOR 抠出来
长什么样** —— 中间要过 frames_with_outline（暗描边补全）+ premul_forward +
make_hcursor_pm 三道，任何一道把原帧改坏了这里都能看见。
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '源码', 'arkmouse'))

import ctypes
from ctypes import wintypes
from PIL import Image

import cursorwin as cw
import artpack
import paths
import prtsfx as px

u32 = cw.u32
gdi = cw.gdi


def dib_of(hcur):
    """HCURSOR -> (RGBA Image, hotspot)。走 GetIconInfo + GetDIBits 原样抠。"""
    ii = cw.ICONINFO()
    if not u32.GetIconInfo(wintypes.HANDLE(hcur), ctypes.byref(ii)):
        return None, None
    try:
        bm = cw.BITMAP()
        gdi.GetObjectW(ii.hbmColor, ctypes.sizeof(cw.BITMAP), ctypes.byref(bm))
        w, h = int(bm.bmWidth), int(bm.bmHeight)
        bi = cw.BITMAPINFOHEADER()
        bi.biSize = ctypes.sizeof(cw.BITMAPINFOHEADER)
        bi.biWidth = w
        bi.biHeight = -h                      # 负 = top-down
        bi.biPlanes = 1
        bi.biBitCount = 32
        bi.biCompression = 0
        buf = ctypes.create_string_buffer(w * h * 4)
        gdi.GetDIBits.argtypes = [wintypes.HDC, wintypes.HBITMAP, wintypes.UINT,
                                  wintypes.UINT, ctypes.c_void_p,
                                  ctypes.POINTER(cw.BITMAPINFOHEADER),
                                  wintypes.UINT]
        gdi.GetDIBits.restype = ctypes.c_int
        gdi.GetDIBits(u32.GetDC(None), ii.hbmColor, 0, h,
                      buf, ctypes.byref(bi), 0)
        im = Image.frombuffer('RGBA', (w, h), buf, 'raw', 'BGRA', 0, 1).copy()
        return im, (int(ii.xHotspot), int(ii.yHotspot))
    finally:
        for h_ in (ii.hbmColor, ii.hbmMask):
            if h_:
                gdi.DeleteObject(h_)


def sheet(cells, cols, out, tile=110, bg=(238, 240, 244, 255)):
    rows = (len(cells) + cols - 1) // cols
    W, H = cols * tile, rows * tile
    canvas = Image.new('RGBA', (W, H), bg)
    for i, (im, hot, label) in enumerate(cells):
        if im is None:
            continue
        x0, y0 = (i % cols) * tile, (i // cols) * tile
        big = im.resize((tile, tile), Image.NEAREST)
        canvas.alpha_composite(big, (x0, y0))
        print('  cell%-2d %-26s %s hot=%s' % (i, label, im.size, hot))
    canvas.convert('RGB').save(out)
    print('->', out, canvas.size)


def main():
    fx = px.FxFrames()
    base = artpack.load(paths.find_art())
    size = 72

    print('== ① 点击：PRTS 原帧 vs 本工程常态 Arrow ==')
    cells = []
    hc, _ = cw.make_hcursor_pm(cw.premul_forward(base.frames('Arrow')[0][0]),
                               size, base.hotspot('Arrow'))
    im, hot = dib_of(hc)
    cells.append((im, hot, 'BASE Arrow'))
    if hc:
        u32.DestroyCursor(hc)
    for f in (6, 40, 80, 106):
        h = fx.icon('hand_normal', f, size)
        im, hot = dib_of(h)
        cells.append((im, hot, 'hand_normal_%03d' % f))
    sheet(cells, 5, os.path.join(HERE, '_ev_click.png'))

    print()
    print('== ③ 待机：PRTS 原帧（进入段 + 循环段） ==')
    cells = []
    for fam, idx in (('idle_enter_frame', 0), ('idle_enter_frame', 20),
                     ('idle_frame', 0), ('idle_frame', 85),
                     ('idle_frame', 170), ('idle_frame', 255)):
        h = fx.icon(fam, idx, size)
        im, hot = dib_of(h)
        cells.append((im, hot, '%s_%d' % (fam, idx)))
    sheet(cells, 6, os.path.join(HERE, '_ev_idle.png'))

    print()
    print('== ② 拖动：PRTS 原帧 ==')
    cells = []
    for fam, idx in (('grab_enter', 0), ('grab_enter', 11),
                     ('grab_begin', 0), ('grab_begin', 11),
                     ('grab_loop', 0), ('grab_end', 20),
                     ('grab_end', 40), ('grab_return', 0), ('grab_return', 11)):
        h = fx.icon(fam, idx, size)
        im, hot = dib_of(h)
        cells.append((im, hot, '%s_%d' % (fam, idx)))
    sheet(cells, 9, os.path.join(HERE, '_ev_grab.png'))

    # 暗描边补全有没有把原帧改坏：同一帧过/不过 frames_with_outline 比一比
    print()
    print('== 暗描边补全对 PRTS 原帧的影响 ==')
    for fam in ('hand_normal', 'idle_frame', 'grab_loop'):
        raw = fx.pack.frames(fam)[0][0]
        post = cw.frames_with_outline(fx.pack, fam)[0][0]
        h = cw.needs_outline(raw)
        diff = sum(1 for a, b in zip(raw.getdata(), post.getdata()) if a != b)
        print('  %-14s needs_outline=%-5s 改动像素=%d / %d'
              % (fam, h, diff, raw.size[0] * raw.size[1]))
    fx.close()


main()
