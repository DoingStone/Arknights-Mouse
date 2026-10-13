# -*- coding: utf-8 -*-
"""决定性：Windows 光标大小设置到底有没有用？
方法：造一枚【极其醒目】的洋红测试光标（单光栅），按注册表方案路径应用（不调 SetSystemCursor），
然后查 GetCursorInfo 的位图尺寸，并同时报告鼠标悬停处的窗口类名（判断读到的是谁的光标）。
再对比 CursorBaseSize / Accessibility\CursorSize 的影响。
"""
import ctypes
import os
import struct
import time
import winreg
from ctypes import wintypes

u32 = ctypes.WinDLL('user32', use_last_error=True)
gdi = ctypes.WinDLL('gdi32', use_last_error=True)

ROOT = r'G:\ArknightsCursorExtract'
OUT = os.path.join(ROOT, '_diag')
os.makedirs(OUT, exist_ok=True)
REG = r'Control Panel\Cursors'
ACC = r'Software\Microsoft\Accessibility'


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


class POINT(ctypes.Structure):
    _fields_ = [('x', wintypes.LONG), ('y', wintypes.LONG)]


u32.GetCursorInfo.argtypes = [ctypes.POINTER(CURSORINFO)]
u32.GetCursorInfo.restype = wintypes.BOOL
u32.GetIconInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(ICONINFO)]
u32.GetIconInfo.restype = wintypes.BOOL
gdi.GetObjectW.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p]
gdi.GetObjectW.restype = ctypes.c_int
gdi.DeleteObject.argtypes = [wintypes.HANDLE]
gdi.DeleteObject.restype = wintypes.BOOL
u32.SystemParametersInfoW.argtypes = [wintypes.UINT, wintypes.UINT,
                                      ctypes.c_void_p, wintypes.UINT]
u32.SystemParametersInfoW.restype = wintypes.BOOL
u32.WindowFromPoint.argtypes = [POINT]
u32.WindowFromPoint.restype = wintypes.HWND
u32.GetClassNameW.argtypes = [wintypes.HWND, ctypes.c_wchar_p, ctypes.c_int]
u32.GetClassNameW.restype = ctypes.c_int
u32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
u32.SetCursorPos.restype = wintypes.BOOL
u32.GetCursorPos.argtypes = [ctypes.POINTER(POINT)]
u32.GetCursorPos.restype = wintypes.BOOL
u32.GetSystemMetrics.argtypes = [ctypes.c_int]
u32.GetSystemMetrics.restype = ctypes.c_int


def bitmap_size(hcur):
    ii = ICONINFO()
    if not u32.GetIconInfo(hcur, ctypes.byref(ii)):
        return None, None
    sz = None
    if ii.hbmColor:
        bm = BITMAP()
        if gdi.GetObjectW(ii.hbmColor, ctypes.sizeof(BITMAP), ctypes.byref(bm)):
            sz = (int(bm.bmWidth), int(bm.bmHeight))
        gdi.DeleteObject(ii.hbmColor)
    if ii.hbmMask:
        gdi.DeleteObject(ii.hbmMask)
    return sz, (int(ii.xHotspot), int(ii.yHotspot))


def live():
    ci = CURSORINFO()
    ci.cbSize = ctypes.sizeof(CURSORINFO)
    if not u32.GetCursorInfo(ctypes.byref(ci)) or not ci.hCursor:
        return None
    return bitmap_size(ci.hCursor)


def where():
    p = POINT()
    u32.GetCursorPos(ctypes.byref(p))
    h = u32.WindowFromPoint(p)
    buf = ctypes.create_unicode_buffer(256)
    n = u32.GetClassNameW(h, buf, 256) if h else 0
    return (p.x, p.y), (buf.value if n else '<null>'), h


def poke():
    r = ctypes.c_ulong()
    u32.SendMessageTimeoutW(0xFFFF, 0x001A, 0, REG, 0x0002, 2000,
                            ctypes.byref(r))
    u32.SystemParametersInfoW(0x0057, 0, None, 0x01 | 0x02)
    time.sleep(0.8)


def make_magenta(path, size):
    """纯洋红实心方块 + 右上角挖空，热点在 (0,0)。"""
    w = h = size
    px = bytearray()
    for y in range(h - 1, -1, -1):
        for x in range(w):
            if x >= w - max(4, w // 8) and y >= h - max(4, h // 8):
                px += bytes((0, 0, 0, 0))
            else:
                px += bytes((255, 0, 255, 255))
    maskrow = ((w + 31) // 32) * 4
    andmask = bytes(maskrow * h)
    bih = struct.pack('<IiiHHIIiiII', 40, w, h * 2, 1, 32, 0,
                      len(px) + len(andmask), 0, 0, 0, 0)
    img = bih + bytes(px) + andmask
    with open(path, 'wb') as f:
        f.write(struct.pack('<HHH', 0, 2, 1))
        f.write(struct.pack('<BBBBHHII', w if w < 256 else 0,
                            h if h < 256 else 0, 0, 0, 0, 0, len(img), 22))
        f.write(img)
    return path


def getval(path, name):
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as k:
            return winreg.QueryValueEx(k, name)
    except OSError:
        return (None, None)


def setval(path, name, val, typ):
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path, 0,
                        winreg.KEY_SET_VALUE) as k:
        winreg.SetValueEx(k, name, 0, typ, val)


print('=== 环境 ===')
print('  远程会话 =', bool(u32.GetSystemMetrics(0x1000)))
print('  屏幕 =', u32.GetSystemMetrics(0), 'x', u32.GetSystemMetrics(1))
print('  SM_CXCURSOR =', u32.GetSystemMetrics(13))
pos, cls, _ = where()
print('  鼠标位置 {0}  窗口类 {1!r}'.format(pos, cls))
print('  live 位图/热点 =', live())

orig_arrow = getval(REG, 'Arrow')
orig_cbs = getval(REG, 'CursorBaseSize')
orig_cs = getval(ACC, 'CursorSize')
print('  原始 Arrow =', orig_arrow[0])
print('  原始 CursorBaseSize =', orig_cbs)
print('  原始 CursorSize =', orig_cs)

testdir = os.path.join(OUT, 'magenta')
os.makedirs(testdir, exist_ok=True)
mag = {}
for s in (32, 96, 256):
    mag[s] = make_magenta(os.path.join(testdir, 'mag_%d.cur' % s), s)
    print('  造好', mag[s], os.path.getsize(mag[s]), 'B')

print()
print('=== 实验：注册表方案路径（不做 SetSystemCursor）===')
print('  逻辑：设 Arrow=洋红测试光标, 设 CursorBaseSize=X, SPI_SETCURSORS, 读 live 位图')
print('  {0:<28} {1:<26} {2}'.format('CursorBaseSize / 文件', 'live 位图', 'live 热点'))
rows = []
for fsize in (32, 256):
    setval(REG, 'Arrow', mag[fsize], winreg.REG_EXPAND_SZ)
    for cbs in ('32', '48', '64', '96', '128', '192', '256'):
        setval(REG, 'CursorBaseSize', cbs, winreg.REG_SZ)
        poke()
        sz, hs = live()
        p, c, _ = where()
        rows.append({'file_raster': fsize, 'CursorBaseSize': cbs,
                     'live_bitmap': sz, 'live_hotspot': hs, 'winclass': c})
        print('  {0:<28} {1:<26} {2}   @{3} {4!r}'.format(
            'file=%dpx base=%s' % (fsize, cbs), str(sz), str(hs), p, c))

print()
print('=== 实验：Accessibility\\CursorSize 1..15（Arrow=256px 洋红）===')
setval(REG, 'Arrow', mag[256], winreg.REG_EXPAND_SZ)
setval(REG, 'CursorBaseSize', '256', winreg.REG_SZ)
rows2 = []
for cs in range(1, 16):
    setval(ACC, 'CursorSize', cs, winreg.REG_DWORD)
    poke()
    sz, hs = live()
    rows2.append({'CursorSize': cs, 'live_bitmap': sz, 'live_hotspot': hs})
    print('  CursorSize={0:>2}  ->  live 位图 {1}  热点 {2}'.format(cs, sz, hs))

print()
print('=== 还原 ===')
setval(REG, 'Arrow', orig_arrow[0], winreg.REG_EXPAND_SZ)
setval(REG, 'CursorBaseSize', orig_cbs[0], winreg.REG_SZ)
setval(ACC, 'CursorSize', orig_cs[0], winreg.REG_DWORD)
poke()
print('  CursorBaseSize =', getval(REG, 'CursorBaseSize'))
print('  CursorSize =', getval(ACC, 'CursorSize'))
print('  Arrow =', getval(REG, 'Arrow')[0])
print('  live =', live())

import json
with open(os.path.join(OUT, 'real_size_probe.json'), 'w', encoding='utf-8') as f:
    json.dump({'rows_cbs': rows, 'rows_cs': rows2}, f, ensure_ascii=False,
              indent=1)
print('  写入 _diag\\real_size_probe.json')
