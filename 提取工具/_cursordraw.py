# -*- coding: utf-8 -*-
"""决定性测量：把光标真正【画出来】，量它的像素尺寸。
用 DrawIconEx(hdc, 0,0, hCursor, 0,0, 0, NULL, DI_NORMAL) —— cx=cy=0 表示用系统认定的默认绘制尺寸，
这正是桌面上看到的大小。再用 LoadCursorFromFileW 分别量每个 .cur / 光栅的自然绘制尺寸。
"""
import ctypes
import os
import struct
import winreg
from ctypes import wintypes
from PIL import Image

u32 = ctypes.WinDLL('user32', use_last_error=True)
gdi = ctypes.WinDLL('gdi32', use_last_error=True)

ROOT = r'G:\ArknightsCursorExtract'
OUT = os.path.join(ROOT, '_diag')
os.makedirs(OUT, exist_ok=True)
REG = r'Control Panel\Cursors'


class ICONINFO(ctypes.Structure):
    _fields_ = [('fIcon', wintypes.BOOL), ('xHotspot', wintypes.DWORD),
                ('yHotspot', wintypes.DWORD), ('hbmMask', wintypes.HANDLE),
                ('hbmColor', wintypes.HANDLE)]


class CURSORINFO(ctypes.Structure):
    _fields_ = [('cbSize', wintypes.DWORD), ('flags', wintypes.DWORD),
                ('hCursor', wintypes.HANDLE), ('ptScreenPos', wintypes.POINT)]


class BITMAP(ctypes.Structure):
    _fields_ = [('bmType', wintypes.LONG), ('bmWidth', wintypes.LONG),
                ('bmHeight', wintypes.LONG), ('bmWidthBytes', wintypes.LONG),
                ('bmPlanes', wintypes.WORD), ('bmBitsPixel', wintypes.WORD),
                ('bmBits', ctypes.c_void_p)]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [('biSize', wintypes.DWORD), ('biWidth', wintypes.LONG),
                ('biHeight', wintypes.LONG), ('biPlanes', wintypes.WORD),
                ('biBitCount', wintypes.WORD), ('biCompression', wintypes.DWORD),
                ('biSizeImage', wintypes.DWORD),
                ('biXPelsPerMeter', wintypes.LONG),
                ('biYPelsPerMeter', wintypes.LONG),
                ('biClrUsed', wintypes.DWORD),
                ('biClrImportant', wintypes.DWORD)]


u32.GetCursorInfo.argtypes = [ctypes.POINTER(CURSORINFO)]
u32.GetCursorInfo.restype = wintypes.BOOL
u32.GetIconInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(ICONINFO)]
u32.GetIconInfo.restype = wintypes.BOOL
gdi.GetObjectW.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p]
gdi.GetObjectW.restype = ctypes.c_int
gdi.DeleteObject.argtypes = [wintypes.HANDLE]
gdi.DeleteObject.restype = wintypes.BOOL
u32.LoadCursorFromFileW.argtypes = [ctypes.c_wchar_p]
u32.LoadCursorFromFileW.restype = wintypes.HANDLE
u32.DrawIconEx.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int,
                           wintypes.HANDLE, ctypes.c_int, ctypes.c_int,
                           wintypes.UINT, wintypes.HANDLE, wintypes.UINT]
u32.DrawIconEx.restype = wintypes.BOOL
gdi.CreateCompatibleDC.argtypes = [wintypes.HDC]
gdi.CreateCompatibleDC.restype = wintypes.HDC
gdi.CreateDIBSection.argtypes = [wintypes.HDC, ctypes.c_void_p,
                                 wintypes.UINT, ctypes.c_void_p,
                                 wintypes.HANDLE, wintypes.DWORD]
gdi.CreateDIBSection.restype = wintypes.HBITMAP
gdi.SelectObject.argtypes = [wintypes.HDC, wintypes.HANDLE]
gdi.SelectObject.restype = wintypes.HANDLE
gdi.DeleteDC.argtypes = [wintypes.HDC]

CANVAS = 512
DI_NORMAL = 0x0003


class DC:
    """一块 512x512 的 32bpp 顶向下 DIB，先刷成纯白。"""

    def __init__(self):
        self.hdc = gdi.CreateCompatibleDC(None)
        self.bih = BITMAPINFOHEADER()
        self.bih.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        self.bih.biWidth = CANVAS
        self.bih.biHeight = -CANVAS
        self.bih.biPlanes = 1
        self.bih.biBitCount = 32
        self.bih.biCompression = 0
        self.bits = ctypes.c_void_p()
        self.hbm = gdi.CreateDIBSection(self.hdc, ctypes.byref(self.bih), 0,
                                        ctypes.byref(self.bits), None, 0)
        self.old = gdi.SelectObject(self.hdc, self.hbm)
        self.clear()

    def clear(self):
        ctypes.memset(self.bits, 0xFF, CANVAS * CANVAS * 4)

    def read(self):
        buf = ctypes.string_at(self.bits, CANVAS * CANVAS * 4)
        return Image.frombytes('RGBA', (CANVAS, CANVAS), buf, 'raw', 'BGRA')

    def __del__(self):
        try:
            gdi.SelectObject(self.hdc, self.old)
            gdi.DeleteObject(self.hbm)
            gdi.DeleteDC(self.hdc)
        except Exception:
            pass


def drawn_extent(im):
    """找非白像素的包围盒 —— 即光标真正被画出来的尺寸。"""
    px = im.load()
    minx, miny, maxx, maxy = CANVAS, CANVAS, -1, -1
    for y in range(CANVAS):
        for x in range(CANVAS):
            r, g, b, a = px[x, y]
            if r < 250 or g < 250 or b < 250:
                if x < minx:
                    minx = x
                if y < miny:
                    miny = y
                if x > maxx:
                    maxx = x
                if y > maxy:
                    maxy = y
    if maxx < 0:
        return None
    return (maxx - minx + 1, maxy - miny + 1, minx, miny)


def natural_size_draw(hcur):
    """cx=cy=0 -> 系统认定的默认尺寸。"""
    dc = DC()
    ok = u32.DrawIconEx(dc.hdc, 0, 0, hcur, 0, 0, 0, None, DI_NORMAL)
    ext = drawn_extent(dc.read())
    return ok, ext


def explicit_size_draw(hcur, cx, cy):
    dc = DC()
    ok = u32.DrawIconEx(dc.hdc, 0, 0, hcur, cx, cy, 0, None, DI_NORMAL)
    ext = drawn_extent(dc.read())
    return ok, ext


def live_cursor():
    ci = CURSORINFO()
    ci.cbSize = ctypes.sizeof(CURSORINFO)
    if not u32.GetCursorInfo(ctypes.byref(ci)) or not ci.hCursor:
        return None, None
    return ci.hCursor, (ci.ptScreenPos.x, ci.ptScreenPos.y)


def bmp_size(hcur):
    ii = ICONINFO()
    if not u32.GetIconInfo(hcur, ctypes.byref(ii)):
        return None
    res = None
    if ii.hbmColor:
        bm = BITMAP()
        if gdi.GetObjectW(ii.hbmColor, ctypes.sizeof(BITMAP), ctypes.byref(bm)):
            res = (int(bm.bmWidth), int(bm.bmHeight))
        gdi.DeleteObject(ii.hbmColor)
    if ii.hbmMask:
        gdi.DeleteObject(ii.hbmMask)
    return res


DPI_CTX_MAP = {-1: ' unaware', -2: ' system', -4: ' per-monitor'}

print('=== 0) DPI 感知 与 SM_CXCURSOR ===')
for dpictx, name in DPI_CTX_MAP.items():
    try:
        u32.SetProcessDpiAwarenessContext(ctypes.c_void_p(dpictx))
    except Exception:
        pass
    print('  dpiCtx{0:<12} SM_CXCURSOR={1:<4} SM_CYICON={2:<4} DPI={3}'.format(
        name, u32.GetSystemMetrics(13), u32.GetSystemMetrics(12),
        u32.GetDpiForSystem()))
# 最终用 per-monitor
try:
    u32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
except Exception:
    pass

SCALE = 1.25  # 由 120 DPI 得来，用于换算实际观感

print()
print('=== 1) 当前桌面光标【真正画出来】的尺寸 ===')
h, pos = live_cursor()
print('  光标屏幕位置 =', pos)
print('  位图尺寸     =', bmp_size(h))
ok, ext = natural_size_draw(h)
print('  DrawIconEx(0,0) 自然尺寸 =', ext, ' [{0}]'.format('ok' if ok else 'FAIL'))
dc = DC()
u32.DrawIconEx(dc.hdc, 0, 0, h, 0, 0, 0, None, DI_NORMAL)
dc.read().crop((0, 0, 96, 96)).save(os.path.join(OUT, 'live_natural_96.png'))
print('  已存 _diag\\live_natural_96.png')

print()
print('=== 2) 我们的 .cur 各档：LoadCursorFromFileW + DrawIconEx 自然尺寸 ===')
files = [
    ('large', 'Arknights_Crystal_Arrow_large.cur'),
    ('medium', 'Arknights_Crystal_Arrow_medium.cur'),
    ('small', 'Arknights_Crystal_Arrow_small.cur'),
]
for tier, fn in files:
    p = os.path.join(ROOT, 'CrystalCursorPack', 'cursors', tier, fn)
    if not os.path.exists(p):
        print('  缺失:', p)
        continue
    hc = u32.LoadCursorFromFileW(p)
    if not hc:
        print('  {0}: LoadCursorFromFileW 失败'.format(tier))
        continue
    nat = natural_size_draw(hc)
    big = explicit_size_draw(hc, 256, 256)
    print('  {0:<7} 位图={1}  自然绘制={2}  强制 256 绘制={3}'.format(
        tier, bmp_size(hc), nat[1], big[1]))
    u32.DestroyCursor(hc)

print()
print('=== 3) 桌面 Arrow 注册表指向的文件（当前实际生效的）===')
with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG) as k:
    for name in ('(default)', 'Arrow', 'CursorBaseSize'):
        try:
            print('  {0:<15} = {1}'.format(name, winreg.QueryValueEx(k, name)))
        except OSError:
            print('  {0:<15} = <无>'.format(name))
