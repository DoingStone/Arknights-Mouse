# -*- coding: utf-8 -*-
"""② 探针 v2：直接读「系统光标槽 32512 的内容」，绕开窗口自己 SetCursor 的干扰。

v1 的 0 像素差异是探针假象：鼠标底下的窗口可能自己 SetCursor，GetCursorInfo 返回
的是那个窗口的私有光标，跟 SetSystemCursor 改的系统槽无关。这里改成
LoadCursorW(None, 32512) + GetIconInfo 直接读系统槽，并且每次改完都把指针挪一格
强制重画。
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
LR_SHARED = 0x8000


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
u32.LoadCursorW.restype = ctypes.c_void_p


def dib(hcur):
    ii = cw.ICONINFO()
    if not u32.GetIconInfo(ctypes.c_void_p(int(hcur)), ctypes.byref(ii)):
        return None, None
    try:
        bm = cw.BITMAP()
        gdi.GetObjectW(ii.hbmColor, ctypes.sizeof(cw.BITMAP), ctypes.byref(bm))
        w, h = int(bm.bmWidth), int(bm.bmHeight)
        bi = cw.BITMAPINFOHEADER()
        bi.biSize = ctypes.sizeof(cw.BITMAPINFOHEADER)
        bi.biWidth, bi.biHeight = w, -h
        bi.biPlanes, bi.biBitCount, bi.biCompression = 1, 32, 0
        buf = ctypes.create_string_buffer(w * h * 4)
        gdi.GetDIBits(u32.GetDC(None), ii.hbmColor, 0, h, buf,
                      ctypes.byref(bi), 0)
        return (Image.frombuffer('RGBA', (w, h), buf, 'raw', 'BGRA', 0, 1).copy(),
                (int(ii.xHotspot), int(ii.yHotspot)))
    finally:
        for h_ in (ii.hbmColor, ii.hbmMask):
            if h_:
                gdi.DeleteObject(h_)


def slot(ocr):
    """读系统光标槽 ocr 现在的内容。"""
    h = u32.LoadCursorW(None, ctypes.c_void_p(ocr))
    if not h:
        return None, None, 0
    im, hot = dib(h)
    return im, hot, int(h)


def ink(im):
    if im is None:
        return None
    a = im.getchannel('A')
    return (sum(1 for v in a.getdata() if v > 8), im.getbbox())


def diff(a, b):
    if a is None or b is None or a.size != b.size:
        return None
    return sum(1 for p, q in zip(a.getdata(), b.getdata()) if p != q)


def repaint():
    """把指针挪一格再挪回来 —— 强制系统重画指针。"""
    p = cw.POINT()
    u32.GetCursorPos(ctypes.byref(p))
    u32.SetCursorPos(p.x + 1, p.y)
    time.sleep(0.06)
    u32.SetCursorPos(p.x, p.y)
    time.sleep(0.10)


ocr = cw.OCR_BY_KEY['Arrow']
print('Arrow -> OCR %d' % ocr)

pack = artpack.load(paths.find_art())
eng = cw.Engine()
eng.build(cw.NATIVE * 0.75, pack)
print('apply_all ->', eng.apply_all())
repaint()
im, hot, h = slot(ocr)
print()
print('== 对照 A：apply_all（已知可见）之后，系统槽 %d ==' % ocr)
print('  句柄=0x%x 热点=%s 墨迹=%s' % (h, hot, ink(im)))
im.save(os.path.join(HERE, '_q_base.png'))
prev = im

fx = px.FxFrames()
print()
print('== 逐帧 set_raw 到 Arrow，每换一帧读一次系统槽 ==')
for fam, idx in (('hand_normal', 6), ('hand_normal', 40), ('hand_normal', 106),
                 ('grab_loop', 0), ('grab_enter', 0)):
    hc = fx.icon(fam, idx, eng.size)
    ok = eng.set_raw('Arrow', hc)
    repaint()
    im, hot, h = slot(ocr)
    print('  set_raw(%s:%d)=%s 槽句柄=0x%x 热点=%s 墨迹=%s 与上一张差 %s 像素'
          % (fam, idx, ok, h, hot, ink(im), diff(prev, im)))
    im.save(os.path.join(HERE, '_q_%s_%d.png' % (fam, idx)))
    prev = im

print()
print('== 对照 B：改用 apply_at（阶梯那条路，② 没用它）==')
eng.apply('Arrow', 0)
repaint()
im, hot, h = slot(ocr)
print('  apply(Arrow,0) 之后 墨迹=%s 与上一张差 %s 像素' % (ink(im), diff(prev, im)))

print()
print('== 对照 C：apply_all 复位后再看 ==')
eng.apply_all()
repaint()
im, hot, h = slot(ocr)
print('  apply_all 之后 墨迹=%s（应回到 %s）' % (ink(im), ink(prev)))

fx.close()
eng.destroy()
u32.SystemParametersInfoW(0x0057, 0, None, 0)
print()
print('指针已复位')
