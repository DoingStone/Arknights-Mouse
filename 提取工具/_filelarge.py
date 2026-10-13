# -*- coding: utf-8 -*-
"""决定工具架构：文件路径能不能给出大尺寸光标？
1) 造「单光栅」.cur（96/128/192/256，正确头 + 有效热点）-> LoadCursorFromFileW -> 量位图
2) 造 .ani（3 帧，每帧是单光栅大 .cur）-> LoadCursorFromFileW -> 量位图
3) 对照：多光栅 .cur（我们已分发的 6 光栅包）-> 量位图
输出结论：动画角色能否靠文件拿到大尺寸。
"""
import ctypes
import json
import os
import struct
import time
from ctypes import wintypes

from PIL import Image

u32 = ctypes.WinDLL('user32', use_last_error=True)
gdi = ctypes.WinDLL('gdi32', use_last_error=True)

ROOT = r'G:\ArknightsCursorExtract'
OUT = os.path.join(ROOT, '_diag')
TMP = os.path.join(OUT, '_tmp')
os.makedirs(TMP, exist_ok=True)
ART = os.path.join(ROOT, 'CrystalCursorPack', 'extracted',
                   'Arknights_Crystal_Arrow_native96.png')
SHIPPED = os.path.join(ROOT, 'CrystalCursorPack', 'cursors', 'large',
                       'Arknights_Crystal_Arrow_large.cur')


class ICONINFO(ctypes.Structure):
    _fields_ = [('fIcon', wintypes.BOOL), ('xHotspot', wintypes.DWORD),
                ('yHotspot', wintypes.DWORD), ('hbmMask', wintypes.HANDLE),
                ('hbmColor', wintypes.HANDLE)]


class BITMAP(ctypes.Structure):
    _fields_ = [('bmType', wintypes.LONG), ('bmWidth', wintypes.LONG),
                ('bmHeight', wintypes.LONG), ('bmWidthBytes', wintypes.LONG),
                ('bmPlanes', wintypes.WORD), ('bmBitsPixel', wintypes.WORD),
                ('bmBits', ctypes.c_void_p)]


u32.GetIconInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(ICONINFO)]
u32.GetIconInfo.restype = wintypes.BOOL
gdi.GetObjectW.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p]
gdi.GetObjectW.restype = ctypes.c_int
gdi.DeleteObject.argtypes = [wintypes.HANDLE]
u32.LoadCursorFromFileW.argtypes = [ctypes.c_wchar_p]
u32.LoadCursorFromFileW.restype = wintypes.HANDLE
u32.DestroyCursor.argtypes = [wintypes.HANDLE]


def probe(h):
    if not h:
        return None, None
    ii = ICONINFO()
    if not u32.GetIconInfo(h, ctypes.byref(ii)):
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
                op[x, y] = (min(255, int(r * f + 0.5)),
                            min(255, int(g * f + 0.5)),
                            min(255, int(b * f + 0.5)), a)
    return out


def dib_payload(im, size, hsx, hsy):
    """返回完整 .cur 字节（单光栅）。"""
    px = bytearray()
    p = im.load()
    for y in range(size - 1, -1, -1):
        for x in range(size):
            r, g, b, a = p[x, y]
            px += bytes((b, g, r, a))
    stride = ((size + 31) // 32) * 4
    andmask = bytes(stride * size)
    bih = struct.pack('<IiiHHIIiiII', 40, size, size * 2, 1, 32, 0,
                      len(px) + len(andmask), 0, 0, 0, 0)
    img = bih + bytes(px) + andmask
    wb = size if size < 256 else 0
    return (struct.pack('<HHH', 0, 2, 1)
            + struct.pack('<BBBBHHII', wb, wb, 0, 0, hsx, hsy, len(img), 22)
            + img)


def write_ani(path, frame_blobs, rate=6):
    """frame_blobs = list of 完整 .cur 字节。"""
    n = len(frame_blobs)
    anih = struct.pack('<IIIIIIIII', 36, n, n, 0, 0, 0, rate, 0x1, 0)
    anih_data = struct.pack('<I', 36) + anih[4:]
    rate_data = b''.join(struct.pack('<I', rate) for _ in range(n))
    frames = b''
    for b in frame_blobs:
        pad = b'\x00' if (len(b) % 2) else b''
        frames += b'icon' + struct.pack('<I', len(b)) + b + pad
    if len(frames) % 2:
        frames += b'\x00'
    fram = b'fram' + frames
    list_data = fram
    body = (b'ANIH' + struct.pack('<I', 36) + anih_data[4:]
            + b'rate' + struct.pack('<I', len(rate_data)) + rate_data
            + b'LIST' + struct.pack('<I', len(list_data)) + list_data)
    riff = b'RIFF' + struct.pack('<I', 4 + len(body)) + b'ACON' + body
    with open(path, 'wb') as f:
        f.write(riff)
    return len(riff)


art = Image.open(ART)
HS = (28.0, 20.0)
NAT = 96.0
rows = []

print('=== A) 单光栅 .cur ===')
for size in (96, 128, 192, 256):
    hsx = int(round(HS[0] * size / NAT))
    hsy = int(round(HS[1] * size / NAT))
    blob = dib_payload(premul_resize(art, size), size, hsx, hsy)
    p = os.path.join(TMP, 'single_%d.cur' % size)
    with open(p, 'wb') as f:
        f.write(blob)
    ctypes.set_last_error(0)
    h = u32.LoadCursorFromFileW(p)
    err = ctypes.get_last_error()
    sz, hs = probe(h)
    print('  %4dpx 文件(%6d B) -> 载入位图 %-12s 热点 %-10s err=%d' % (
        size, len(blob), str(sz), str(hs), err))
    rows.append({'kind': 'single_cur', 'requested': size, 'file_bytes': len(blob),
                 'loaded': sz, 'hotspot': hs, 'err': err})
    if h:
        u32.DestroyCursor(h)

print()
print('=== B) 多光栅 .cur（已分发的 6 光栅包）===')
ctypes.set_last_error(0)
h = u32.LoadCursorFromFileW(SHIPPED)
err = ctypes.get_last_error()
sz, hs = probe(h)
print('  已分发 large 包 -> 载入位图 %-12s 热点 %-10s err=%d' % (str(sz), str(hs), err))
rows.append({'kind': 'shipped_multi', 'loaded': sz, 'hotspot': hs, 'err': err})
if h:
    u32.DestroyCursor(h)

print()
print('=== C) .ani（3 帧，每帧=单光栅大 .cur）===')
for size in (96, 192):
    hsx = int(round(HS[0] * size / NAT))
    hsy = int(round(HS[1] * size / NAT))
    blob = dib_payload(premul_resize(art, size), size, hsx, hsy)
    p = os.path.join(TMP, 'anim_%d.ani' % size)
    nb = write_ani(p, [blob, blob, blob])
    ctypes.set_last_error(0)
    h = u32.LoadCursorFromFileW(p)
    err = ctypes.get_last_error()
    sz, hs = probe(h)
    print('  %4dpx .ani(%7d B) -> 载入位图 %-12s 热点 %-10s err=%d' % (
        size, nb, str(sz), str(hs), err))
    rows.append({'kind': 'ani', 'requested': size, 'file_bytes': nb,
                 'loaded': sz, 'hotspot': hs, 'err': err})
    if h:
        u32.DestroyCursor(h)

print()
print('=== D) 对照：多光栅 .cur（96 主档 + 小档）===')
blobs = []
for size in (32, 48, 64, 96, 128, 256):
    hsx = int(round(HS[0] * size / NAT))
    hsy = int(round(HS[1] * size / NAT))
    blobs.append(dib_payload(premul_resize(art, size), size, hsx, hsy))
off = 6 + 16 * len(blobs)
ents = b''
data = b''
for size, b in zip((32, 48, 64, 96, 128, 256), blobs):
    wb = size if size < 256 else 0
    ents += struct.pack('<BBBBHHII', wb, wb, 0, 0, 0, 0, len(b), off + len(data))
    data += b
p = os.path.join(TMP, 'multi.cur')
with open(p, 'wb') as f:
    f.write(struct.pack('<HHH', 0, 2, 6) + ents + data)
ctypes.set_last_error(0)
h = u32.LoadCursorFromFileW(p)
err = ctypes.get_last_error()
sz, hs = probe(h)
print('  6 光栅 32..256 -> 载入位图 %-12s 热点 %-10s err=%d' % (str(sz), str(hs), err))
rows.append({'kind': 'multi_cur', 'loaded': sz, 'hotspot': hs, 'err': err})
if h:
    u32.DestroyCursor(h)

with open(os.path.join(OUT, 'filelarge.json'), 'w', encoding='utf-8') as f:
    json.dump(rows, f, ensure_ascii=False, indent=1)
print()
print('写入 _diag\\filelarge.json')
