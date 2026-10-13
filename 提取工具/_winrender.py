# -*- coding: utf-8 -*-
"""End-to-end acceptance test: let Windows draw our .cur files itself.

For every variant and every embedded raster:
  * LoadImageW(..., IMAGE_CURSOR, w, w, LR_LOADFROMFILE)   -> does it load?
  * GetIconInfo                                            -> hotspot Windows uses
  * DrawIconEx into a 32bpp top-down DIB                   -> Windows' own pixels
  * compare those pixels against our in-process render()

If Windows' own rasteriser reproduces our art and reports our hotspot, the
package is correct by the only authority that matters.
"""
import ctypes
import ctypes.wintypes as wt
import importlib.util
import os

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.join(HERE, "package", "cursors")

IMAGE_CURSOR = 2
LR_LOADFROMFILE = 0x0010
DI_NORMAL = 0x0003
BI_RGB = 0
DIB_RGB_COLORS = 0
SRCCOPY = 0x00CC0020


class ICONINFO(ctypes.Structure):
    _fields_ = [("fIcon", wt.BOOL), ("xHotspot", wt.DWORD), ("yHotspot", wt.DWORD),
                ("hbmMask", wt.HBITMAP), ("hbmColor", wt.HBITMAP)]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", wt.DWORD), ("biWidth", ctypes.c_long),
                ("biHeight", ctypes.c_long), ("biPlanes", wt.WORD),
                ("biBitCount", wt.WORD), ("biCompression", wt.DWORD),
                ("biSizeImage", wt.DWORD), ("biXPelsPerMeter", ctypes.c_long),
                ("biYPelsPerMeter", ctypes.c_long), ("biClrUsed", wt.DWORD),
                ("biClrImportant", wt.DWORD)]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", wt.DWORD * 3)]


_u32 = ctypes.WinDLL("user32", use_last_error=True)
_g32 = ctypes.WinDLL("gdi32", use_last_error=True)
_u32.LoadImageW.restype = wt.HANDLE
_u32.LoadImageW.argtypes = [wt.HINSTANCE, wt.LPCWSTR, wt.UINT,
                           ctypes.c_int, ctypes.c_int, wt.UINT]
_u32.GetIconInfo.argtypes = [wt.HANDLE, ctypes.POINTER(ICONINFO)]
_u32.GetIconInfo.restype = wt.BOOL
_u32.DrawIconEx.argtypes = [wt.HDC, ctypes.c_int, ctypes.c_int, wt.HANDLE,
                            ctypes.c_int, ctypes.c_int, wt.UINT, wt.HBRUSH, wt.UINT]
_u32.DrawIconEx.restype = wt.BOOL
_u32.DestroyCursor.argtypes = [wt.HANDLE]
_g32.DeleteObject.argtypes = [wt.HANDLE]
_g32.CreateCompatibleDC.argtypes = [wt.HDC]
_g32.CreateCompatibleDC.restype = wt.HDC
_g32.DeleteDC.argtypes = [wt.HDC]
_g32.SelectObject.argtypes = [wt.HDC, wt.HANDLE]
_g32.SelectObject.restype = wt.HANDLE
_g32.CreateDIBSection.restype = wt.HBITMAP
_g32.CreateDIBSection.argtypes = [wt.HDC, ctypes.POINTER(BITMAPINFO), wt.UINT,
                                  ctypes.POINTER(ctypes.c_void_p), wt.HANDLE, wt.DWORD]


DRAW_AT = 8        # where DrawIconEx is asked to put the image's upper-left corner


def win_draw(path, size, pad=48):
    """Ask Windows to draw the cursor; return (hotspot, RGBA pixels, W, H)."""
    hcur = _u32.LoadImageW(None, path, IMAGE_CURSOR, size, size, LR_LOADFROMFILE)
    if not hcur:
        return None, None, 0, 0
    ii = ICONINFO()
    if not _u32.GetIconInfo(hcur, ctypes.byref(ii)):
        _u32.DestroyCursor(hcur)
        return None, None, 0, 0
    hs = (ii.xHotspot, ii.yHotspot)
    _g32.DeleteObject(ii.hbmMask)
    _g32.DeleteObject(ii.hbmColor)

    W = H = size + pad + 8
    hdc = _g32.CreateCompatibleDC(None)
    bi = BITMAPINFO()
    bi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bi.bmiHeader.biWidth = W
    bi.bmiHeader.biHeight = -H                      # negative => top-down
    bi.bmiHeader.biPlanes = 1
    bi.bmiHeader.biBitCount = 32
    bi.bmiHeader.biCompression = BI_RGB
    bits = ctypes.c_void_p()
    hbm = _g32.CreateDIBSection(hdc, ctypes.byref(bi), DIB_RGB_COLORS,
                                ctypes.byref(bits), None, 0)
    old = _g32.SelectObject(hdc, hbm)
    # start from a known opaque magenta so "transparent" is unambiguous
    n = W * H
    buf = (ctypes.c_ubyte * (n * 4)).from_address(bits.value)
    for i in range(n):
        buf[i * 4 + 0] = 255
        buf[i * 4 + 1] = 0
        buf[i * 4 + 2] = 255
        buf[i * 4 + 3] = 255
    ok = _u32.DrawIconEx(hdc, DRAW_AT, DRAW_AT, hcur, size, size, 0, None, DI_NORMAL)
    px = [(buf[i * 4 + 2], buf[i * 4 + 1], buf[i * 4], 255) for i in range(n)]
    _g32.SelectObject(hdc, old)
    _g32.DeleteObject(hbm)
    _g32.DeleteDC(hdc)
    _u32.DestroyCursor(hcur)
    return (hs if ok else None), px, W, H


def load_render():
    spec = importlib.util.spec_from_file_location("bc", os.path.join(HERE, "build_cursors.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def over_magenta(px):
    """Composite straight-alpha RGBA over opaque magenta, the way GDI does.

    DrawIconEx into a 32bpp DIB does not carry per-pixel alpha through: it
    composites the cursor onto whatever the DIB already holds and leaves every
    alpha at 255.  So the honest comparison is composite-vs-composite.
    """
    out = []
    for (r, g, b, a) in px:
        af = a / 255.0
        out.append((int(round(255 * (1 - af) + r * af)),
                    int(round(0 * (1 - af) + g * af)),
                    int(round(255 * (1 - af) + b * af)), 255))
    return out


def main():
    m = load_render()
    variants = [("arknights_small", 0.5), ("arknights_medium", 2 ** -0.5),
                ("arknights_large", 1.0)]
    bad = 0
    for stem, gain in variants:
        path = os.path.join(PKG, stem + ".cur")
        print("=" * 96)
        print(os.path.basename(path))
        for size in (32, 48, 64, 96, 128, 256):
            hs, px, W, H = win_draw(path, size)
            if px is None:
                print("  %3dpx  !! LoadImage failed" % size)
                bad += 1
                continue
            ref, want_hs = m.render(gain, size)
            rpx = over_magenta(list(ref.getdata()))
            # Find where GDI actually placed the image.  DrawIconEx puts the
            # icon/cursor's upper-left corner at (x, y) -- it does NOT offset by
            # the hotspot -- so the expected origin is (DRAW_AT, DRAW_AT).  We
            # search a small neighbourhood instead of assuming, and report what won.
            best = None
            for oy in range(max(0, DRAW_AT - 6), DRAW_AT + 7):
                for ox in range(max(0, DRAW_AT - 6), DRAW_AT + 7):
                    if ox < 0 or oy < 0 or ox + size > W or oy + size > H:
                        continue
                    diff = 0
                    worst = 0
                    hard = 0
                    for y in range(size):
                        base = (oy + y) * W + ox
                        for x in range(size):
                            a = px[base + x]
                            b = rpx[y * size + x]
                            if a != b:
                                diff += 1
                                d = max(abs(a[i] - b[i]) for i in range(4))
                                if d > worst:
                                    worst = d
                                if d > 1:
                                    hard += 1
                    # rank by deltas above 1 (true disagreements), then by count
                    key = (hard, diff)
                    if best is None or key < best[0]:
                        best = (key, diff, worst, hard, ox, oy)
            key, diff, worst, hard, fx, fy = best
            placed = "upper-left" if (fx, fy) == (DRAW_AT, DRAW_AT) else \
                     "hotspot" if (fx, fy) == (DRAW_AT - want_hs[0], DRAW_AT - want_hs[1]) else "other"
            print("  %3dpx  hotspot=%-9s (render %-9s)  placement=%s@(%d,%d)  "
                  "exact=%.2f%%  ±1-rounding=%d  disagreements(>1)=%d worst=%d"
                  % (size, hs, want_hs, placed, fx, fy,
                     100.0 * (size * size - diff) / (size * size), diff - hard, hard, worst))
            if tuple(hs) != tuple(want_hs):
                print("      !! Windows hotspot %s != render %s" % (hs, want_hs))
                bad += 1
            if hard:
                print("      !! Windows' composite disagrees in %d px (worst channel delta %d)"
                      % (hard, worst))
                bad += 1
    print()
    print("end-to-end problems: %d" % bad)


main()
