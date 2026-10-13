# -*- coding: utf-8 -*-
"""判定 CreateIconIndirect 的 32bpp DIB 走【straight alpha】还是【premultiplied alpha】。

原理：造一个 alpha 渐变（alpha=128，RGB=200）的刀口像素，用 CreateIconIndirect 造成光标，
再用 DrawIconEx 画到【黑色】背景 DIB 上，读回该像素：
  straight 语义 -> 结果 ≈ RGB * a/255      = 200*128/255 ≈ 100
  premul   语义 -> 结果 ≈ RGB * a²/255²    = 200*0.25    ≈  50
再对【文件式 .cur】（走 LoadCursorFromFileW，已知在系统里显示正常）做同样测量作为参照。
"""
import ctypes
import os
import struct
from ctypes import wintypes

from PIL import Image

u32 = ctypes.WinDLL('user32', use_last_error=True)
gdi = ctypes.WinDLL('gdi32', use_last_error=True)

ROOT = r'G:\ArknightsCursorExtract'
OUT = os.path.join(ROOT, '_diag')
TMP = os.path.join(OUT, '_tmp')
os.makedirs(TMP, exist_ok=True)


class ICONINFO(ctypes.Structure):
    _fields_ = [('fIcon', wintypes.BOOL), ('xHotspot', wintypes.DWORD),
                ('yHotspot', wintypes.DWORD), ('hbmMask', wintypes.HANDLE),
                ('hbmColor', wintypes.HANDLE)]


class BMIH(ctypes.Structure):
    _fields_ = [('biSize', wintypes.DWORD), ('biWidth', wintypes.LONG),
                ('biHeight', wintypes.LONG), ('biPlanes', wintypes.WORD),
                ('biBitCount', wintypes.WORD),
                ('biCompression', wintypes.DWORD),
                ('biSizeImage', wintypes.DWORD),
                ('biXPelsPerMeter', wintypes.LONG),
                ('biYPelsPerMeter', wintypes.LONG),
                ('biClrUsed', wintypes.DWORD),
                ('biClrImportant', wintypes.DWORD)]


gdi.CreateDIBSection.argtypes = [wintypes.HDC, ctypes.c_void_p, wintypes.UINT,
                                 ctypes.POINTER(ctypes.c_void_p),
                                 wintypes.HANDLE, wintypes.DWORD]
gdi.CreateDIBSection.restype = wintypes.HBITMAP
gdi.CreateCompatibleDC.argtypes = [wintypes.HDC]
gdi.CreateCompatibleDC.restype = wintypes.HDC
gdi.SelectObject.argtypes = [wintypes.HDC, wintypes.HANDLE]
gdi.SelectObject.restype = wintypes.HANDLE
gdi.DeleteObject.argtypes = [wintypes.HANDLE]
u32.CreateIconIndirect.argtypes = [ctypes.POINTER(ICONINFO)]
u32.CreateIconIndirect.restype = wintypes.HANDLE
u32.CopyIcon.argtypes = [wintypes.HANDLE]
u32.CopyIcon.restype = wintypes.HANDLE
u32.DestroyCursor.argtypes = [wintypes.HANDLE]
u32.LoadCursorFromFileW.argtypes = [ctypes.c_wchar_p]
u32.LoadCursorFromFileW.restype = wintypes.HANDLE
u32.DrawIconEx.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int,
                           wintypes.HANDLE, ctypes.c_int, ctypes.c_int,
                           wintypes.UINT, wintypes.HANDLE, wintypes.UINT]
u32.DrawIconEx.restype = wintypes.BOOL

DI_NORMAL = 0x0003
N = 96


def make_dib32(w, h, fill):
    bi = BMIH()
    bi.biSize = ctypes.sizeof(BMIH)
    bi.biWidth = w
    bi.biHeight = -h
    bi.biPlanes = 1
    bi.biBitCount = 32
    bi.biCompression = 0
    bits = ctypes.c_void_p()
    hbm = gdi.CreateDIBSection(None, ctypes.byref(bi), 0, ctypes.byref(bits),
                               None, 0)
    ctypes.memset(bits, fill, w * h * 4)
    return hbm, bits


def make_dib1(w, h):
    bi = BMIH()
    bi.biSize = ctypes.sizeof(BMIH)
    bi.biWidth = w
    bi.biHeight = -h
    bi.biPlanes = 1
    bi.biBitCount = 1
    bits = ctypes.c_void_p()
    hbm = gdi.CreateDIBSection(None, ctypes.byref(bi), 0, ctypes.byref(bits),
                               None, 0)
    ctypes.memset(bits, 0, ((w + 31) // 32) * 4 * h)
    return hbm


def read_px(bits, w, x, y):
    o = (y * w + x) * 4
    b = (ctypes.c_ubyte * (w * w * 4)).from_address(bits.value)
    return int(b[o + 2]), int(b[o + 1]), int(b[o]), int(b[o + 3])


def render(hcur, size):
    """把光标画到黑色 DIB 上，返回 (bits, w, hbm, hdc)。"""
    hbm, bits = make_dib32(size, size, 0)
    hdc = gdi.CreateCompatibleDC(None)
    old = gdi.SelectObject(hdc, hbm)
    ok = u32.DrawIconEx(hdc, 0, 0, hcur, size, size, 0, None, DI_NORMAL)
    gdi.SelectObject(hdc, old)
    gdi.DeleteDC(hdc)
    return ok, bits


print('=== 造一个 alpha 渐变刀口图案 ===')
im = Image.new('RGBA', (N, N), (0, 0, 0, 0))
p = im.load()
# 左半：完全不透明的 (200,200,200)，右半：alpha 渐变
for y in range(N):
    for x in range(N):
        if x < N // 2:
            p[x, y] = (200, 200, 200, 255)
        else:
            a = max(0, 255 - int((x - N // 2) * 255 / (N // 2)))
            p[x, y] = (200, 200, 200, a)
        if x == N // 2:
            p[x, y] = (200, 200, 200, 128)     # 探测列

color_bits = im.tobytes('raw', 'BGRA')
bi = BMIH()
bi.biSize = ctypes.sizeof(BMIH)
bi.biWidth = N
bi.biHeight = -N
bi.biPlanes = 1
bi.biBitCount = 32
cb = ctypes.c_void_p()
hcolor = gdi.CreateDIBSection(None, ctypes.byref(bi), 0, ctypes.byref(cb),
                              None, 0)
ctypes.memmove(cb, color_bits, N * N * 4)
hmask = make_dib1(N, N)

ii = ICONINFO()
ii.fIcon = False
ii.xHotspot, ii.yHotspot = 0, 0
ii.hbmMask = hmask
ii.hbmColor = hcolor
hcur = u32.CreateIconIndirect(ctypes.byref(ii))
print('  CreateIconIndirect ->', 'OK' if hcur else 'FAIL err=%d' % ctypes.get_last_error())

ok, bits = render(hcur, N)
print('  DrawIconEx ok =', bool(ok))
print()
print('  探测列 x=%d（源 alpha=128, RGB=200）:' % (N // 2))
print('    读到 =', read_px(bits, N, N // 2, N // 2))
print('    straight 语义期望 ≈ (100,100,100)')
print('    premul  语义期望 ≈ ( 50, 50, 50)')
print('  不透明区 x=%d 读到 =' % (10,), read_px(bits, N, 10, 10))

# 参照：原图直接贴到黑底（straight 合成）
ref = Image.new('RGB', (N, N), (0, 0, 0))
rp = ref.load()
ip = im.load()
for y in range(N):
    for x in range(N):
        r, g, b, a = ip[x, y]
        rp[x, y] = (int(r * a / 255), int(g * a / 255), int(b * a / 255))
print('  参照（PIL straight 合成到黑底）x=%d =' % (N // 2), rp[N // 2, N // 2])

# 文件式 .cur 对照
shipped = os.path.join(ROOT, 'CrystalCursorPack', 'cursors', 'large',
                       'Arknights_Crystal_Arrow_large.cur')
hf = u32.LoadCursorFromFileW(shipped)
ok2, bits2 = render(hf, 32)
print()
print('  文件式 .cur（32px，参照路径）非透明中心区 =',
      read_px(bits2, 32, 16, 16))

gdi.DeleteObject(hcolor)
gdi.DeleteObject(hmask)
if hcur:
    u32.DestroyCursor(hcur)
if hf:
    u32.DestroyCursor(hf)

print()
print('结论：若读数接近 100 -> straight alpha（我们的 DIB 正确）；')
print('      若接近  50 -> premultiplied（需要预乘后再交 DIB）。')
