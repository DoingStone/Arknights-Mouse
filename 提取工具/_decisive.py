# -*- coding: utf-8 -*-
"""决定性实验（修正测量方法）：
GetCursorInfo 返回的是【鼠标所在窗口】的光标 —— 必须先把鼠标钉在桌面(SysListView32/Progman)上再量。
测三件事：
 1) SetSystemCursor 单光栅 .cur  -> 桌面箭头真实像素尺寸（原生尺寸还是被压到 32？）
 2) CursorBaseSize 写成 REG_DWORD -> 是否有缩放效果
 3) Accessibility\CursorSize      -> 是否有缩放效果
全部还原。
"""
import ctypes
import json
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
u32.SetSystemCursor.argtypes = [wintypes.HANDLE, wintypes.DWORD]
u32.SetSystemCursor.restype = wintypes.BOOL
u32.LoadCursorFromFileW.argtypes = [ctypes.c_wchar_p]
u32.LoadCursorFromFileW.restype = wintypes.HANDLE
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
gdi.CreateCompatibleDC.argtypes = [wintypes.HDC]
gdi.CreateCompatibleDC.restype = wintypes.HDC
gdi.CreateDIBSection.argtypes = [wintypes.HDC, ctypes.c_void_p,
                                 wintypes.UINT, ctypes.c_void_p,
                                 wintypes.HANDLE, wintypes.DWORD]
gdi.CreateDIBSection.restype = wintypes.HBITMAP
gdi.SelectObject.argtypes = [wintypes.HDC, wintypes.HANDLE]
gdi.SelectObject.restype = wintypes.HANDLE
gdi.DeleteDC.argtypes = [wintypes.HDC]
u32.DrawIconEx.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int,
                           wintypes.HANDLE, ctypes.c_int, ctypes.c_int,
                           wintypes.UINT, wintypes.HANDLE, wintypes.UINT]
u32.DrawIconEx.restype = wintypes.BOOL

OCR_ARROW = 32512
DESKTOP_CLASSES = {'SysListView32', 'Progman', 'WorkerW', 'SHELLDLL_DefView'}


def bmp_size(hcur):
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


def winclass():
    p = POINT()
    u32.GetCursorPos(ctypes.byref(p))
    h = u32.WindowFromPoint(p)
    buf = ctypes.create_unicode_buffer(256)
    n = u32.GetClassNameW(h, buf, 256) if h else 0
    return (p.x, p.y), (buf.value if n else '')


def find_desktop_point():
    """扫一圈找 WindowFromPoint 返回桌面类的坐标。"""
    w = u32.GetSystemMetrics(0)
    hgt = u32.GetSystemMetrics(1)
    cands = []
    for fy in (0.90, 0.95, 0.85, 0.75):
        for fx in (0.75, 0.85, 0.92, 0.60, 0.50):
            x, y = int(w * fx), int(hgt * fy)
            u32.SetCursorPos(x, y)
            time.sleep(0.12)
            p, c = winclass()
            if c in DESKTOP_CLASSES:
                cands.append((x, y, c))
    return cands


def pin(pt):
    u32.SetCursorPos(pt[0], pt[1])
    time.sleep(0.55)


def measure_desktop(pt):
    """钉在桌面点上量箭头。"""
    pin(pt)
    p, c = winclass()
    ci = CURSORINFO()
    ci.cbSize = ctypes.sizeof(CURSORINFO)
    if not u32.GetCursorInfo(ctypes.byref(ci)) or not ci.hCursor:
        return None, None, c
    sz, hs = bmp_size(ci.hCursor)
    return sz, hs, c


def make_cur(path, size, draw_px=None):
    """单光栅洋红方块（左上角缺口，热点 (0,0)），若 draw_px 给定则方块只画 draw_px 大。"""
    art = draw_px or size
    px = bytearray()
    for y in range(size - 1, -1, -1):
        for x in range(size):
            if x < art and y < art and not (x < max(2, size // 16) and y < max(2, size // 16)):
                px += bytes((255, 0, 255, 255))
            else:
                px += bytes((0, 0, 0, 0))
    maskrow = ((size + 31) // 32) * 4
    andmask = bytes(maskrow * size)
    bih = struct.pack('<IiiHHIIiiII', 40, size, size * 2, 1, 32, 0,
                      len(px) + len(andmask), 0, 0, 0, 0)
    img = bih + bytes(px) + andmask
    with open(path, 'wb') as f:
        f.write(struct.pack('<HHH', 0, 2, 1))
        f.write(struct.pack('<BBBBHHII', size if size < 256 else 0,
                            size if size < 256 else 0, 0, 0, 0, 0,
                            len(img), 22))
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


orig_arrow = getval(REG, 'Arrow')
orig_cbs = getval(REG, 'CursorBaseSize')
orig_cs = getval(ACC, 'CursorSize')
print('原始: Arrow=%s' % orig_arrow[0])
print('原始: CursorBaseSize=%s  CursorSize=%s' % (orig_cbs, orig_cs))

print()
print('=== 0) 找桌面坐标 ===')
cands = find_desktop_point()
print('  桌面命中:', cands[:6])
if not cands:
    raise SystemExit('!! 找不到桌面坐标，无法可靠测量')
DP = (cands[0][0], cands[0][1])
print('  使用桌面点:', DP, cands[0][2])

print()
print('=== 1) SetSystemCursor 单光栅 .cur -> 桌面箭头真实尺寸 ===')
tmp = os.path.join(OUT, 'mag2')
os.makedirs(tmp, exist_ok=True)
# 先把 Arrow 指向原文件并 SetSystemCursor 复位
hl = u32.LoadCursorFromFileW(orig_arrow[0])
if hl:
    u32.SetSystemCursor(hl, OCR_ARROW)
pin(DP)
print('  复位后基线:', measure_desktop(DP))
rows1 = []
for size in (32, 48, 64, 96, 128, 256):
    p = make_cur(os.path.join(tmp, 'm%03d.cur' % size), size)
    hc = u32.LoadCursorFromFileW(p)
    if not hc:
        print('  加载失败', size)
        continue
    ok = u32.SetSystemCursor(hc, OCR_ARROW)
    sz, hs, c = measure_desktop(DP)
    rows1.append({'single_raster': size, 'set_ok': bool(ok),
                  'desktop_bitmap': sz, 'desktop_hotspot': hs, 'winclass': c})
    print('  单光栅 {0:>3}px  SetSystemCursor={1}  ->  桌面位图 {2}  热点 {3}  [{4}]'
          .format(size, bool(ok), sz, hs, c))

print()
print('=== 2) CursorBaseSize 用 REG_DWORD 写（关键：之前一直写成 REG_SZ）===')
u32.SetSystemCursor(u32.LoadCursorFromFileW(orig_arrow[0]), OCR_ARROW)
rows2 = []
for val in (32, 64, 96, 128, 192, 256):
    setval(REG, 'CursorBaseSize', val, winreg.REG_DWORD)
    r = ctypes.c_ulong()
    u32.SendMessageTimeoutW(0xFFFF, 0x001A, 0, REG, 0x0002, 2000, ctypes.byref(r))
    u32.SystemParametersInfoW(0x0057, 0, None, 0x01 | 0x02)
    hl = u32.LoadCursorFromFileW(orig_arrow[0])
    if hl:
        u32.SetSystemCursor(hl, OCR_ARROW)
    sz, hs, c = measure_desktop(DP)
    rows2.append({'CursorBaseSize_DWORD': val, 'desktop_bitmap': sz,
                  'desktop_hotspot': hs, 'winclass': c})
    print('  CursorBaseSize(DWORD)={0:>3}  ->  桌面位图 {1}  热点 {2}  [{3}]'
          .format(val, sz, hs, c))

print()
print('=== 3) Accessibility\\CursorSize 1..15（Arrow=large 原文件，base=DWORD 96）===')
setval(REG, 'CursorBaseSize', 96, winreg.REG_DWORD)
rows3 = []
for cs in range(1, 16):
    setval(ACC, 'CursorSize', cs, winreg.REG_DWORD)
    r = ctypes.c_ulong()
    u32.SendMessageTimeoutW(0xFFFF, 0x001A, 0, REG, 0x0002, 2000, ctypes.byref(r))
    u32.SystemParametersInfoW(0x0057, 0, None, 0x01 | 0x02)
    hl = u32.LoadCursorFromFileW(orig_arrow[0])
    if hl:
        u32.SetSystemCursor(hl, OCR_ARROW)
    sz, hs, c = measure_desktop(DP)
    rows3.append({'CursorSize': cs, 'desktop_bitmap': sz, 'hotspot': hs})
    print('  CursorSize={0:>2}  ->  桌面位图 {1}  热点 {2}  [{3}]'
          .format(cs, sz, hs, c))

print()
print('=== 还原 ===')
setval(REG, 'Arrow', orig_arrow[0], orig_arrow[1])
setval(REG, 'CursorBaseSize', orig_cbs[0], orig_cbs[1])
setval(ACC, 'CursorSize', orig_cs[0], orig_cs[1])
r = ctypes.c_ulong()
u32.SendMessageTimeoutW(0xFFFF, 0x001A, 0, REG, 0x0002, 2000, ctypes.byref(r))
u32.SystemParametersInfoW(0x0057, 0, None, 0x01 | 0x02)
hl = u32.LoadCursorFromFileW(orig_arrow[0])
if hl:
    u32.SetSystemCursor(hl, OCR_ARROW)
print('  Arrow =', getval(REG, 'Arrow')[0])
print('  CursorBaseSize =', getval(REG, 'CursorBaseSize'))
print('  CursorSize =', getval(ACC, 'CursorSize'))
print('  桌面 =', measure_desktop(DP))

with open(os.path.join(OUT, 'decisive.json'), 'w', encoding='utf-8') as f:
    json.dump({'desktop_point': DP, 's1_single_raster': rows1,
               's2_base_size_dword': rows2, 's3_cursor_size': rows3},
              f, ensure_ascii=False, indent=1)
print('  写入 _diag\\decisive.json')
