# -*- coding: utf-8 -*-
"""② 的决定性探针：把「屏幕上此刻显示的指针位图」抠出来，看 set_raw 到底改没改屏幕。

前面的验收只证明了「钩子收到事件 + frames_for 推出正确帧序 + set_raw 返回 True」，
没证明屏幕上的位图变了。这个脚本直接读实时指针位图，前后对比。
"""
import atexit
import ctypes
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '源码', 'arkmouse'))

from PIL import Image
import cursorwin as cw
import paths
import artpack
import prtsfx as px

u32, gdi = cw.u32, cw.gdi


@atexit.register
def _restore():
    try:
        u32.SystemParametersInfoW(0x0057, 0, None, 0)
    except Exception:
        pass


gdi.GetDIBits.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint,
                          ctypes.c_uint, ctypes.c_void_p, ctypes.c_void_p,
                          ctypes.c_uint]
gdi.GetDIBits.restype = ctypes.c_int


def live_dib():
    """当前屏幕指针的 (RGBA, (hx,hy), 句柄)。"""
    ci = cw.CURSORINFO()
    ci.cbSize = ctypes.sizeof(cw.CURSORINFO)
    if not u32.GetCursorInfo(ctypes.byref(ci)):
        return None, None, 0
    ii = cw.ICONINFO()
    if not u32.GetIconInfo(ii and ctypes.c_void_p(int(ci.hCursor)),
                           ctypes.byref(ii)):
        return None, None, int(ci.hCursor or 0)
    try:
        bm = cw.BITMAP()
        gdi.GetObjectW(ii.hbmColor, ctypes.sizeof(cw.BITMAP), ctypes.byref(bm))
        w, h = int(bm.bmWidth), int(bm.bmHeight)
        bi = cw.BITMAPINFOHEADER()
        bi.biSize = ctypes.sizeof(cw.BITMAPINFOHEADER)
        bi.biWidth, bi.biHeight = w, -h
        bi.biPlanes, bi.biBitCount, bi.biCompression = 1, 32, 0
        buf = ctypes.create_string_buffer(w * h * 4)
        n = gdi.GetDIBits(u32.GetDC(None), ii.hbmColor, 0, h, buf,
                          ctypes.byref(bi), 0)
        im = Image.frombuffer('RGBA', (w, h), buf, 'raw', 'BGRA', 0, 1).copy()
        return im, (int(ii.xHotspot), int(ii.yHotspot)), int(ci.hCursor or 0)
    finally:
        for h_ in (ii.hbmColor, ii.hbmMask):
            if h_:
                gdi.DeleteObject(h_)


def ink(im):
    """非透明像素数 + bbox —— 位图内容有没有变，这两个数最直观。"""
    if im is None:
        return None
    a = im.getchannel('A')
    return (sum(1 for v in a.getdata() if v > 8), im.getbbox())


def diff(a, b):
    if a is None or b is None:
        return None
    if a.size != b.size:
        return 'size %s != %s' % (a.size, b.size)
    return sum(1 for p, q in zip(a.getdata(), b.getdata()) if p != q)


pack = artpack.load(paths.find_art())
eng = cw.Engine()
eng.build(cw.NATIVE * 0.75, pack)
print('apply_all ->', eng.apply_all())
time.sleep(0.2)
u32.SetCursorPos(600, 400)
time.sleep(0.3)

base, hot, hnd = live_dib()
print()
print('== 先看：装了常态包之后，屏幕上的指针 ==')
print('  句柄=0x%x 热点=%s 墨迹=%s' % (hnd, hot, ink(base)))
base.save(os.path.join(HERE, '_p_base.png'))

fx = px.FxFrames()
print()
print('== 逐帧 set_raw 到 Arrow(32512)，每换一帧读一次屏幕 ==')
prev = base
for fam, idx in (('hand_normal', 6), ('hand_normal', 40),
                 ('hand_normal', 80), ('hand_normal', 106),
                 ('grab_loop', 0), ('grab_enter', 0)):
    hc = fx.icon(fam, idx, eng.size)
    ok = eng.set_raw('Arrow', hc)
    time.sleep(0.25)
    im, hh, hnd2 = live_dib()
    d = diff(prev, im)
    print('  set_raw(%s:%d)=%s  屏幕句柄=0x%x 墨迹=%s  与上一张差 %s 像素'
          % (fam, idx, ok, hnd2, ink(im), d))
    im.save(os.path.join(HERE, '_p_%s_%d.png' % (fam, idx)))
    prev = im

print()
print('== 对照：直接调 SetSystemCursor（apply_all 走的那条路）换成 Hand ==')
eng.apply('Hand', 0)
time.sleep(0.25)
u32.SetCursorPos(600, 400)
time.sleep(0.2)
im, hh, hnd3 = live_dib()
print('  屏幕句柄=0x%x 热点=%s 墨迹=%s 与上一张差 %s 像素'
      % (hnd3, hh, ink(im), diff(prev, im)))
im.save(os.path.join(HERE, '_p_hand.png'))

fx.close()
eng.destroy()
u32.SystemParametersInfoW(0x0057, 0, None, 0)
print()
print('指针已复位')
