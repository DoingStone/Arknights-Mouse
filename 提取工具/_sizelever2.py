# -*- coding: utf-8 -*-
"""确认 cursor 模式（fIcon=FALSE）是否尊重热点，并用真实水晶美术按尺寸造指针 + 桌面截图取证。"""
import ctypes
import json
import os
import subprocess
import sys
import time
from ctypes import wintypes

from PIL import Image, ImageDraw, ImageGrab

u32 = ctypes.WinDLL('user32', use_last_error=True)
gdi = ctypes.WinDLL('gdi32', use_last_error=True)

ROOT = r'G:\ArknightsCursorExtract'
OUT = os.path.join(ROOT, '_diag')
ART = os.path.join(ROOT, 'CrystalCursorPack', 'extracted',
                   'Arknights_Crystal_Arrow_native96.png')
DP = (1536, 1036)


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
                ('biClrUsed', wintypes.DWORD), ('biClrImportant', wintypes.DWORD)]


class POINT(ctypes.Structure):
    _fields_ = [('x', wintypes.LONG), ('y', wintypes.LONG)]


u32.GetIconInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(ICONINFO)]
u32.GetIconInfo.restype = wintypes.BOOL
u32.GetCursorInfo.argtypes = [ctypes.POINTER(CURSORINFO)]
u32.GetCursorInfo.restype = wintypes.BOOL
gdi.GetObjectW.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p]
gdi.GetObjectW.restype = ctypes.c_int
gdi.DeleteObject.argtypes = [wintypes.HANDLE]
u32.SetSystemCursor.argtypes = [wintypes.HANDLE, wintypes.DWORD]
u32.SetSystemCursor.restype = wintypes.BOOL
u32.CreateIconIndirect.argtypes = [ctypes.POINTER(ICONINFO)]
u32.CreateIconIndirect.restype = wintypes.HANDLE
u32.CopyIcon.argtypes = [wintypes.HANDLE]
u32.CopyIcon.restype = wintypes.HANDLE
u32.DestroyCursor.argtypes = [wintypes.HANDLE]
u32.LoadCursorFromFileW.argtypes = [ctypes.c_wchar_p]
u32.LoadCursorFromFileW.restype = wintypes.HANDLE
u32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
u32.GetCursorPos.argtypes = [ctypes.POINTER(POINT)]
u32.WindowFromPoint.argtypes = [POINT]
u32.WindowFromPoint.restype = wintypes.HWND
u32.GetClassNameW.argtypes = [wintypes.HWND, ctypes.c_wchar_p, ctypes.c_int]
gdi.CreateDIBSection.argtypes = [wintypes.HDC, ctypes.c_void_p, wintypes.UINT,
                                 ctypes.POINTER(ctypes.c_void_p),
                                 wintypes.HANDLE, wintypes.DWORD]
gdi.CreateDIBSection.restype = wintypes.HBITMAP

OCR_NORMAL = 32512
NATIVE = 96.0
HS96 = (28.0, 20.0)


def ps(cmd):
    try:
        r = subprocess.run(['powershell', '-NoProfile', '-Command', cmd],
                           capture_output=True, text=True, timeout=90)
        return (r.stdout or '').strip()
    except Exception as e:
        return 'ERR %s' % e


def premul_resize(im, size):
    im = im.convert('RGBA')
    if im.size == (size, size):
        return im.copy()
    px = im.load()
    w, h = im.size
    pm = Image.new('RGBA', (w, h))
    pp = pm.load()
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            f = a / 255.0
            pp[x, y] = (int(r * f + 0.5), int(g * f + 0.5), int(b * f + 0.5), a)
    small = pm.resize((size, size), Image.LANCZOS)
    sp = small.load()
    out = Image.new('RGBA', (size, size))
    op = out.load()
    for y in range(size):
        for x in range(size):
            r, g, b, a = sp[x, y]
            if a == 0:
                op[x, y] = (0, 0, 0, 0)
            else:
                f = 255.0 / a
                op[x, y] = (min(255, int(r * f + 0.5)), min(255, int(g * f + 0.5)),
                            min(255, int(b * f + 0.5)), a)
    return out


def dib_from_image(im, w, h):
    bi = BITMAPINFOHEADER()
    bi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bi.biWidth = w
    bi.biHeight = -h
    bi.biPlanes = 1
    bi.biBitCount = 32
    bi.biCompression = 0
    bits = ctypes.c_void_p()
    hbm = gdi.CreateDIBSection(None, ctypes.byref(bi), 0, ctypes.byref(bits),
                               None, 0)
    if not hbm:
        raise OSError('DIB 创建失败')
    data = im.convert('RGBA').tobytes('raw', 'BGRA')
    ctypes.memmove(bits, data, min(len(data), w * h * 4))
    return hbm


def empty_mask(w, h):
    bi = BITMAPINFOHEADER()
    bi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bi.biWidth = w
    bi.biHeight = -h
    bi.biPlanes = 1
    bi.biBitCount = 1
    bits = ctypes.c_void_p()
    hbm = gdi.CreateDIBSection(None, ctypes.byref(bi), 0, ctypes.byref(bits),
                               None, 0)
    ctypes.memset(bits, 0, ((w + 31) // 32) * 4 * h)
    return hbm


def build_cursor(art96, size, ficon):
    im = premul_resize(art96, size)
    color = dib_from_image(im, size, size)
    mask = empty_mask(size, size)
    ii = ICONINFO()
    ii.fIcon = ficon
    ii.xHotspot = int(round(HS96[0] * size / NATIVE))
    ii.yHotspot = int(round(HS96[1] * size / NATIVE))
    ii.hbmMask = mask
    ii.hbmColor = color
    hc = u32.CreateIconIndirect(ctypes.byref(ii))
    err = ctypes.get_last_error()
    gdi.DeleteObject(color)
    gdi.DeleteObject(mask)
    if not hc:
        raise OSError('CreateIconIndirect 失败 err=%d' % err)
    return hc, (ii.xHotspot, ii.yHotspot)


def probe(hcur):
    ii = ICONINFO()
    if not u32.GetIconInfo(hcur, ctypes.byref(ii)):
        return None
    sz = None
    if ii.hbmColor:
        bm = BITMAP()
        if gdi.GetObjectW(ii.hbmColor, ctypes.sizeof(BITMAP), ctypes.byref(bm)):
            sz = (int(bm.bmWidth), int(bm.bmHeight))
        gdi.DeleteObject(ii.hbmColor)
    if ii.hbmMask:
        gdi.DeleteObject(ii.hbmMask)
    return sz, (int(ii.xHotspot), int(ii.yHotspot))


def desktop_probe():
    u32.SetCursorPos(DP[0], DP[1])
    time.sleep(0.7)
    p = POINT()
    u32.GetCursorPos(ctypes.byref(p))
    h = u32.WindowFromPoint(p)
    buf = ctypes.create_unicode_buffer(256)
    n = u32.GetClassNameW(h, buf, 256) if h else 0
    ci = CURSORINFO()
    ci.cbSize = ctypes.sizeof(CURSORINFO)
    if not u32.GetCursorInfo(ctypes.byref(ci)) or not ci.hCursor:
        return None, None, buf.value if n else ''
    sz, hs = probe(ci.hCursor)
    return sz, hs, (buf.value if n else '')


info = ps("Get-CimInstance Win32_Process -Filter \"Name='PRTS-Motion-96.exe'\" "
          "| Select-Object ProcessId,ExecutablePath | ConvertTo-Json -Compress")
prts = {}
try:
    d = json.loads(info)
    prts = d[0] if isinstance(d, list) else d
except Exception:
    pass
if prts.get('ProcessId'):
    ps("Stop-Process -Id %d -Force" % prts['ProcessId'])
    time.sleep(2.0)
print('PRTS-Motion 已停（测量期间）')

orig = None
import winreg
try:
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Control Panel\Cursors') as k:
        orig = winreg.QueryValueEx(k, 'Arrow')[0]
except OSError:
    pass

art = Image.open(ART)
print('美术源 =', ART, art.size, art.mode)
print()
print('  %-6s %-8s %-14s %-14s %s' % ('尺寸', 'fIcon', '造出位图', '桌面位图', '桌面热点'))
rows = []
for size, fic in ((96, True), (96, False), (128, False), (192, False), (256, False)):
    hc, hs = build_cursor(art, size, fic)
    made = probe(hc)
    u32.SetSystemCursor(hc, OCR_NORMAL)     # 接管所有权
    time.sleep(0.9)
    dsz, dhs, cls = desktop_probe()
    rows.append({'size': size, 'fIcon': fic, 'made': made, 'desktop_bitmap': dsz,
                 'desktop_hotspot': dhs, 'class': cls})
    print('  %-6s %-8s %-14s %-14s %s [%s]' % (size, fic, made[0], dsz, dhs, cls))

print()
print('=== 桌面截图取证（192px）===')
hc, _ = build_cursor(art, 192, False)
u32.SetSystemCursor(hc, OCR_NORMAL)
u32.SetCursorPos(1200, 700)
time.sleep(1.5)
g = ImageGrab.grab()
shot = os.path.join(OUT, 'big_cursor_192.png')
crop = os.path.join(OUT, 'big_cursor_192_crop.png')
g.save(shot)
g.crop((1200 - 130, 700 - 130, 1200 + 130, 700 + 130)).resize(
    (520, 520), Image.NEAREST).save(crop)
print('  写入', shot)
print('  写入', crop)

print()
print('=== 还原 ===')
u32.SystemParametersInfoW(0x0057, 0, None, 0x01 | 0x02)
time.sleep(1.0)
if orig:
    u32.SetSystemCursor(u32.LoadCursorFromFileW(orig), OCR_NORMAL)
print('  桌面 =', desktop_probe())
if prts.get('ExecutablePath'):
    print(' ', ps('Start-Process -FilePath "%s" -ArgumentList \'"%s"\'' % (
        prts['ExecutablePath'],
        r'C:\Users\22442\AppData\Local\PRTS\Replica-v8-Windows\cursors-34497b84e5b0d7cf')))
    time.sleep(2.0)
    print('  PRTS 进程数 =', ps("(Get-Process -Name 'PRTS-Motion-96' "
                               "-ErrorAction SilentlyContinue | Measure-Object).Count"))

with open(os.path.join(OUT, 'iconindirect.json'), 'w', encoding='utf-8') as f:
    json.dump(rows, f, ensure_ascii=False, indent=1)
print('  写入 _diag\\iconindirect.json')
