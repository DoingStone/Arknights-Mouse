# -*- coding: utf-8 -*-
"""决定性实验：Windows 到底按什么决定桌面上光标的【渲染像素尺寸】。
A) 单档 .cur（只有 1 个光栅）→ 活光标位图多大？说明 Windows 是否缩放。
B) CursorBaseSize (REG_SZ) 各值 → 活光标多大？
每次实验后还原。
"""
import ctypes
import glob
import json
import os
import struct
import time
import winreg
from ctypes import wintypes
from PIL import Image

u32 = ctypes.WinDLL('user32', use_last_error=True)
gdi = ctypes.WinDLL('gdi32', use_last_error=True)
shell = ctypes.WinDLL('shell32', use_last_error=True)

REG = r'Control Panel\Cursors'
ACC = r'Software\Microsoft\Accessibility'
ROOT = r'G:\ArknightsCursorExtract'
OUT = os.path.join(ROOT, '_diag')
os.makedirs(OUT, exist_ok=True)


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
u32.SetSystemCursor.argtypes = [wintypes.HANDLE, wintypes.DWORD]
u32.SetSystemCursor.restype = wintypes.BOOL
u32.SystemParametersInfoW.argtypes = [wintypes.UINT, wintypes.UINT,
                                      ctypes.c_void_p, wintypes.UINT]
u32.SystemParametersInfoW.restype = wintypes.BOOL

OCR_ARROW = 32512
CUR_DIR = 0x7F00


def live():
    ci = CURSORINFO()
    ci.cbSize = ctypes.sizeof(CURSORINFO)
    if not u32.GetCursorInfo(ctypes.byref(ci)) or not ci.hCursor:
        return None
    ii = ICONINFO()
    if not u32.GetIconInfo(ci.hCursor, ctypes.byref(ii)):
        return None
    res = None
    if ii.hbmColor:
        bm = BITMAP()
        if gdi.GetObjectW(ii.hbmColor, ctypes.sizeof(BITMAP), ctypes.byref(bm)):
            res = (int(bm.bmWidth), int(bm.bmHeight))
        gdi.DeleteObject(ii.hbmColor)
    if ii.hbmMask:
        gdi.DeleteObject(ii.hbmMask)
    ii2 = ICONINFO()
    hs = None
    if u32.GetIconInfo(ci.hCursor, ctypes.byref(ii2)):
        hs = (int(ii2.xHotspot), int(ii2.yHotspot))
        if ii2.hbmColor:
            gdi.DeleteObject(ii2.hbmColor)
        if ii2.hbmMask:
            gdi.DeleteObject(ii2.hbmMask)
    return res, hs


def poke():
    """刷新光标：广播 + 移动鼠标（触发重新加载）"""
    r = ctypes.c_ulong()
    u32.SendMessageTimeoutW(0xFFFF, 0x001A, 0, REG, 0x0002, 2000, ctypes.byref(r))
    u32.SystemParametersInfoW(0x0057, 0, None, 0x01 | 0x02)
    p = wintypes.POINT()
    u32.GetCursorPos(ctypes.byref(p))
    for dx in (3, -3):
        u32.SetCursorPos(p.x + dx, p.y)
        time.sleep(0.05)
    u32.SetCursorPos(p.x, p.y)
    time.sleep(0.6)


def make_cur(path, size, src_png=None):
    """从源 PNG 生成【只有一个光栅】的 .cur。"""
    if src_png is None:
        src_png = os.path.join(OUT, 'arrow_src.png')
        im = Image.open(os.path.join(
            ROOT, 'CrystalCursorPack', 'extracted', 'large',
            'Arknights_Crystal_Arrow_large_native96.png')).convert('RGBA')
        im.save(src_png)
    im = Image.open(src_png).convert('RGBA')
    im = im.resize((size, size), Image.LANCZOS)
    hsx = int(round(28.0 * size / 96.0))
    hsy = int(round(20.0 * size / 96.0))
    w, h = im.size
    px = im.load()
    xor = bytearray()
    for y in range(h - 1, -1, -1):
        for x in range(w):
            r_, g_, b_, a_ = px[x, y]
            xor += bytes((b_, g_, r_, a_))
    maskrow = ((w + 31) // 32) * 4
    andmask = bytes(maskrow * h)
    bih = struct.pack('<IiiHHIIiiII', 40, w, h * 2, 1, 32, 0,
                      len(xor) + len(andmask), 0, 0, 0, 0)
    img = bih + bytes(xor) + andmask
    dir_ = struct.pack('<HHH', 0, 2, 1)
    ent = struct.pack('<BBBBHHII', w if w < 256 else 0, h if h < 256 else 0,
                      0, 0, hsx, hsy, len(img), 22)
    with open(path, 'wb') as f:
        f.write(dir_ + ent + img)
    return hsx, hsy


def set_arrow(path):
    h = u32.LoadCursorFromFileW(path)
    if not h:
        return 'LoadCursorFromFileW 失败 err=%d' % ctypes.get_last_error()
    if not u32.SetSystemCursor(h, OCR_ARROW):
        return 'SetSystemCursor 失败 err=%d' % ctypes.get_last_error()
    poke()
    return 'ok'


def set_cbs(val):
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG, 0,
                        winreg.KEY_SET_VALUE) as k:
        winreg.SetValueEx(k, 'CursorBaseSize', 0, winreg.REG_SZ, val)
    poke()


def get_cbs():
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG) as k:
        return winreg.QueryValueEx(k, 'CursorBaseSize')


def get_cs():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, ACC) as k:
            return winreg.QueryValueEx(k, 'CursorSize')
    except OSError:
        return (None, None)


res = {}
print('=== 前置 ===')
print('  DPI =', u32.GetDpiForSystem())
print('  CursorBaseSize =', get_cbs())
print('  CursorSize =', get_cs())
print('  活光标 =', live())

print()
print('=== A) 单档 .cur 的实验：Windows 会不会缩放？ ===')
orig_arrow = None
with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG) as k:
    orig_arrow = winreg.QueryValueEx(k, 'Arrow')[0]
print('  当前 Arrow 注册表值 =', orig_arrow)
tmpdir = os.path.join(OUT, 'single')
os.makedirs(tmpdir, exist_ok=True)
A = []
for size in (32, 48, 64, 96, 128, 256):
    p = os.path.join(tmpdir, 'arrow_%d.cur' % size)
    hs = make_cur(p, size)
    r = set_arrow(p)
    m = live()
    A.append({'raster': size, 'hotspot_written': hs, 'live': m})
    print('  单档 {0:>3}px .cur  ->  活光标 {1}   [{2}]'.format(size, m, r))
res['A_single_raster'] = A

print()
print('=== B) CursorBaseSize (REG_SZ) 的影响（用当前 large 方案）===')
big = os.path.join(ROOT, 'CrystalCursorPack', 'cursors', 'large',
                   'Arknights_Crystal_Arrow_large.cur')
set_arrow(big)
B = []
orig_val = get_cbs()[0]
for val in ('32', '48', '64', '96', '128', '256'):
    set_cbs(val)
    m = live()
    B.append({'CursorBaseSize': val, 'live': m})
    print("  CursorBaseSize='{0}'  ->  活光标 {1}".format(val, m))
res['B_base_size'] = B

print()
print('=== 还原 ===')
set_cbs(orig_val)
with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG, 0,
                    winreg.KEY_SET_VALUE) as k:
    if orig_arrow:
        winreg.SetValueEx(k, 'Arrow', 0, winreg.REG_EXPAND_SZ, orig_arrow)
poke()
print('  CursorBaseSize =', get_cbs())
print('  Arrow =', end=' ')
with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG) as k:
    print(winreg.QueryValueEx(k, 'Arrow'))
print('  活光标 =', live())

with open(os.path.join(OUT, 'size_lever.json'), 'w', encoding='utf-8') as f:
    json.dump(res, f, ensure_ascii=False, indent=1)
print('  写入 _diag\\size_lever.json')
