# -*- coding: utf-8 -*-
"""决定性：绕开 .cur 文件加载，直接在内存里造【指定像素尺寸】的 HCURSOR。
先杀 PRTS-Motion（它会每 5 秒重设光标，干扰测量）。

A 基线（LoadCursorFromFileW）
B LoadCursorFromFileW 一个「只有 256px 单光栅」的 .cur
C CreateIconFromResourceEx（正确的 ICONIMAGE 载荷 + fIcon=FALSE + 0x00020000）
D CreateIconIndirect（自建 32bpp 色 DIB + 零 mask，指定尺寸 + 显式热点）  <-- 主候选
结束还原注册表方案 + 重启 PRTS。
"""
import ctypes
import json
import os
import struct
import subprocess
import time
import winreg
from ctypes import wintypes

u32 = ctypes.WinDLL('user32', use_last_error=True)
gdi = ctypes.WinDLL('gdi32', use_last_error=True)

ROOT = r'G:\ArknightsCursorExtract'
OUT = os.path.join(ROOT, '_diag')
TMP = os.path.join(OUT, '_tmp')
os.makedirs(TMP, exist_ok=True)
REG = r'Control Panel\Cursors'
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
u32.CreateIconFromResourceEx.argtypes = [
    ctypes.c_void_p, wintypes.DWORD, wintypes.BOOL, wintypes.DWORD,
    ctypes.c_int, ctypes.c_int, wintypes.UINT]
u32.CreateIconFromResourceEx.restype = wintypes.HANDLE
u32.CreateIconIndirect.argtypes = [ctypes.POINTER(ICONINFO)]
u32.CreateIconIndirect.restype = wintypes.HANDLE
u32.CopyIcon.argtypes = [wintypes.HANDLE]
u32.CopyIcon.restype = wintypes.HANDLE
u32.DestroyCursor.argtypes = [wintypes.HANDLE]
u32.DestroyCursor.restype = wintypes.BOOL
u32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
u32.GetCursorPos.argtypes = [ctypes.POINTER(POINT)]
u32.WindowFromPoint.argtypes = [POINT]
u32.WindowFromPoint.restype = wintypes.HWND
u32.GetClassNameW.argtypes = [wintypes.HWND, ctypes.c_wchar_p, ctypes.c_int]
u32.GetClassNameW.restype = ctypes.c_int
u32.SystemParametersInfoW.argtypes = [wintypes.UINT, wintypes.UINT,
                                      ctypes.c_void_p, wintypes.UINT]
u32.SystemParametersInfoW.restype = wintypes.BOOL
gdi.CreateDIBSection.argtypes = [wintypes.HDC, ctypes.c_void_p, wintypes.UINT,
                                 ctypes.POINTER(ctypes.c_void_p),
                                 wintypes.HANDLE, wintypes.DWORD]
gdi.CreateDIBSection.restype = wintypes.HBITMAP

OCR_NORMAL = 32512
DIB_RGB_COLORS = 0


def ps(cmd):
    try:
        r = subprocess.run(['powershell', '-NoProfile', '-Command', cmd],
                           capture_output=True, text=True, timeout=60)
        return (r.stdout or '').strip()
    except Exception as e:
        return 'ERR %s' % e


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


def desktop_measure():
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
        return None, None, (buf.value if n else '')
    sz, hs = bmp_size(ci.hCursor)
    return sz, hs, (buf.value if n else '')


def make_color_dib(w, h, painter):
    """32bpp 顶向下 DIB，pixels[0]=左上。"""
    bi = BITMAPINFOHEADER()
    bi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bi.biWidth = w
    bi.biHeight = -h
    bi.biPlanes = 1
    bi.biBitCount = 32
    bi.biCompression = 0
    bits = ctypes.c_void_p()
    hbm = gdi.CreateDIBSection(None, ctypes.byref(bi), DIB_RGB_COLORS,
                               ctypes.byref(bits), None, 0)
    if not hbm:
        raise OSError('CreateDIBSection color failed')
    buf = (ctypes.c_ubyte * (w * h * 4)).from_address(bits.value)
    for y in range(h):
        for x in range(w):
            r, g, b, a = painter(x, y)
            o = (y * w + x) * 4
            buf[o] = b
            buf[o + 1] = g
            buf[o + 2] = r
            buf[o + 3] = a
    return hbm


def make_mask_dib(w, h):
    bi = BITMAPINFOHEADER()
    bi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bi.biWidth = w
    bi.biHeight = -h
    bi.biPlanes = 1
    bi.biBitCount = 1
    bi.biCompression = 0
    bits = ctypes.c_void_p()
    hbm = gdi.CreateDIBSection(None, ctypes.byref(bi), DIB_RGB_COLORS,
                               ctypes.byref(bits), None, 0)
    if not hbm:
        raise OSError('CreateDIBSection mask failed')
    stride = ((w + 31) // 32) * 4
    ctypes.memset(bits, 0, stride * h)
    return hbm


def magenta_painter(cut):
    def p(x, y):
        if x < cut and y < cut:
            return (0, 0, 0, 0)
        return (255, 0, 255, 255)
    return p


def single_raster_cur(size):
    art = size
    px = bytearray()
    for y in range(size - 1, -1, -1):
        for x in range(size):
            inside = x < art and y < art
            corner = x < max(2, size // 8) and y < max(2, size // 8)
            px += bytes((255, 0, 255, 255)) if (inside and not corner) \
                else bytes((0, 0, 0, 0))
    andmask = bytes(((size + 31) // 32) * 4 * size)
    bih = struct.pack('<IiiHHIIiiII', 40, size, size * 2, 1, 32, 0,
                      len(px) + len(andmask), 0, 0, 0, 0)
    img = bih + bytes(px) + andmask
    return (struct.pack('<HHH', 0, 2, 1)
            + struct.pack('<BBBBHHII', size if size < 256 else 0,
                          size if size < 256 else 0, 0, 0, 0, 0,
                          len(img), 22) + img)


orig_arrow = None
try:
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG) as k:
        orig_arrow = winreg.QueryValueEx(k, 'Arrow')[0]
except OSError:
    pass
print('注册表 Arrow =', orig_arrow)

print()
print('=== 杀 PRTS-Motion（避免它 5 秒一次重设光标）===')
info = ps("Get-CimInstance Win32_Process -Filter \"Name='PRTS-Motion-96.exe'\" "
          "| Select-Object ProcessId,ExecutablePath,CommandLine "
          "| ConvertTo-Json -Compress")
print(' ', info)
prts = {}
try:
    d = json.loads(info)
    prts = d[0] if isinstance(d, list) else d
except Exception:
    prts = {}
if prts.get('ProcessId'):
    ps("Stop-Process -Id %d -Force" % prts['ProcessId'])
    time.sleep(2.0)
print('  剩余 =', ps("(Get-Process -Name 'PRTS-Motion-96' -ErrorAction SilentlyContinue "
                     "| Measure-Object).Count"))

rows = []

print()
print('=== A) 基线 ===')
h = u32.LoadCursorFromFileW(orig_arrow) if orig_arrow else None
if h:
    u32.SetSystemCursor(h, OCR_NORMAL)
    time.sleep(1.0)
print('  A =', desktop_measure())

print()
print('=== B) LoadCursorFromFileW：只有 256px 单光栅的 .cur ===')
p256 = os.path.join(TMP, 'mag256.cur')
with open(p256, 'wb') as f:
    f.write(single_raster_cur(256))
hb = u32.LoadCursorFromFileW(p256)
print('  LoadCursorFromFileW(256px 单光栅) ->', bmp_size(hb) if hb else 'FAIL', 
      'err', ctypes.get_last_error())
if hb:
    u32.SetSystemCursor(u32.CopyIcon(hb), OCR_NORMAL)
    time.sleep(1.0)
    m = desktop_measure()
    print('  桌面 =', m)
    rows.append({'case': 'B_loadfile_256', 'desktop': m})

print()
print('=== C) CreateIconFromResourceEx（ICONIMAGE 载荷, fIcon=FALSE, 0x20000）===')
raw = single_raster_cur(128)
img_payload = raw[22:]          # 跳过 ICONDIR + 条目，得到 ICONIMAGE
print('  ICONIMAGE 长度 =', len(img_payload))
for want in (64, 128, 192):
    buf = ctypes.create_string_buffer(img_payload, len(img_payload))
    hc = u32.CreateIconFromResourceEx(buf, len(img_payload), False,
                                      0x00020000, want, want, 0)
    err = ctypes.get_last_error()
    if not hc:
        print('  @%-4d 失败 err=%d' % (want, err))
        continue
    print('  @%-4d 造出 ->' % want, bmp_size(hc))
    u32.SetSystemCursor(hc, OCR_NORMAL)
    time.sleep(1.0)
    m = desktop_measure()
    print('        桌面 =', m)
    rows.append({'case': 'C_resex_%d' % want, 'desktop': m})

print()
print('=== D) CreateIconIndirect（自建 DIB + 显式热点）===')
for want in (32, 64, 96, 128, 192, 256):
    hsx, hsy = int(round(28 * want / 96.0)), int(round(20 * want / 96.0))
    color = make_color_dib(want, want, magenta_painter(max(2, want // 8)))
    mask = make_mask_dib(want, want)
    ii = ICONINFO()
    ii.fIcon = True
    ii.xHotspot = hsx
    ii.yHotspot = hsy
    ii.hbmMask = mask
    ii.hbmColor = color
    hc = u32.CreateIconIndirect(ctypes.byref(ii))
    err = ctypes.get_last_error()
    gdi.DeleteObject(color)
    gdi.DeleteObject(mask)
    if not hc:
        print('  @%-4d CreateIconIndirect 失败 err=%d' % (want, err))
        continue
    made = bmp_size(hc)
    u32.SetSystemCursor(u32.CopyIcon(hc), OCR_NORMAL)
    time.sleep(1.0)
    m = desktop_measure()
    print('  @%-4d 造出 %-12s 桌面位图 %-12s 热点 %-10s [%s]' % (
        want, str(made[0]), str(m[0]), str(m[1]), m[2]))
    rows.append({'case': 'D_indirect_%d' % want, 'made': made, 'desktop': m})
    u32.DestroyCursor(hc)

print()
print('=== 还原 ===')
u32.SystemParametersInfoW(0x0057, 0, None, 0x01 | 0x02)
time.sleep(1.0)
h = u32.LoadCursorFromFileW(orig_arrow) if orig_arrow else None
if h:
    u32.SetSystemCursor(h, OCR_NORMAL)
time.sleep(1.0)
print('  桌面 =', desktop_measure())

if prts.get('ExecutablePath'):
    argdir = os.path.dirname(prts['ExecutablePath'])
    cdir = ps("(Get-Content 'G:\\ArknightsCursorExtract\\_diag\\prts_cmd.txt' "
              "-ErrorAction SilentlyContinue)")
    cmdline = prts.get('CommandLine') or ''
    extra = cmdline.replace(prts['ExecutablePath'], '').strip().strip('"')
    if 'cursors-' in cmdline:
        extra = cmdline.split('" "')[-1].strip('"')
    print('  重启 PRTS: "%s" "%s"' % (prts['ExecutablePath'], extra))
    ps('Start-Process -FilePath "%s" -ArgumentList \'%s\'' % (
        prts['ExecutablePath'], extra))
    time.sleep(2.0)
    print('  PRTS 进程数 =',
          ps("(Get-Process -Name 'PRTS-Motion-96' -ErrorAction SilentlyContinue "
             "| Measure-Object).Count"))

with open(os.path.join(OUT, 'createicon.json'), 'w', encoding='utf-8') as f:
    json.dump(rows, f, ensure_ascii=False, indent=1)
print('  写入 _diag\\createicon.json')
