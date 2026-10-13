# -*- coding: utf-8 -*-
"""Two questions, answered from bytes and from Windows itself:

Q1  For a .cur image, does the pixel data start at entryOffset + biSize (40),
    or are there 4 extra "hotspot" bytes between the BITMAPINFOHEADER and the
    XOR bitmap?  Answered arithmetically: compare the entry's declared byte
    count against 40 + xor + and  and against 44 + xor + and.

Q2  Does Windows read the cursor hotspot from the ICONDIRENTRY wPlanes /
    wBitCount fields?  Answered by loading real Microsoft cursors and
    comparing what Windows reports against what the file declares.
"""
import ctypes
import ctypes.wintypes as wt
import glob
import os
import struct

IMAGE_CURSOR = 2
LR_LOADFROMFILE = 0x0010
LR_DEFAULTSIZE = 0x0040
DI_NORMAL = 0x0003
DIB_RGB_COLORS = 0


class ICONINFO(ctypes.Structure):
    _fields_ = [("fIcon", wt.BOOL), ("xHotspot", wt.DWORD),
                ("yHotspot", wt.DWORD), ("hbmMask", wt.HBITMAP),
                ("hbmColor", wt.HBITMAP)]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", wt.DWORD), ("biWidth", ctypes.c_long),
                ("biHeight", ctypes.c_long), ("biPlanes", wt.WORD),
                ("biBitCount", wt.WORD), ("biCompression", wt.DWORD),
                ("biSizeImage", wt.DWORD), ("biXPelsPerMeter", ctypes.c_long),
                ("biYPelsPerMeter", ctypes.c_long), ("biClrUsed", wt.DWORD),
                ("biClrImportant", wt.DWORD)]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER),
                ("bmiColors", wt.DWORD * 3)]


user32 = ctypes.WinDLL("user32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
user32.LoadImageW.restype = wt.HANDLE
user32.LoadImageW.argtypes = [wt.HINSTANCE, wt.LPCWSTR, wt.UINT,
                              ctypes.c_int, ctypes.c_int, wt.UINT]
user32.GetIconInfo.argtypes = [wt.HANDLE, ctypes.POINTER(ICONINFO)]
user32.GetIconInfo.restype = wt.BOOL
user32.DestroyCursor.argtypes = [wt.HANDLE]
user32.DrawIconEx.argtypes = [wt.HDC, ctypes.c_int, ctypes.c_int, wt.HANDLE,
                              ctypes.c_int, ctypes.c_int, wt.UINT, wt.HANDLE,
                              wt.UINT]
user32.DrawIconEx.restype = wt.BOOL
gdi32.CreateCompatibleDC.argtypes = [wt.HDC]
gdi32.CreateCompatibleDC.restype = wt.HDC
gdi32.CreateDIBSection.argtypes = [wt.HDC, ctypes.POINTER(BITMAPINFO), wt.UINT,
                                   ctypes.POINTER(ctypes.c_void_p), wt.HANDLE,
                                   wt.DWORD]
gdi32.CreateDIBSection.restype = wt.HBITMAP
gdi32.SelectObject.argtypes = [wt.HDC, wt.HANDLE]
gdi32.SelectObject.restype = wt.HANDLE
gdi32.DeleteObject.argtypes = [wt.HANDLE]
gdi32.DeleteDC.argtypes = [wt.HDC]


def entries(path):
    b = open(path, "rb").read()
    reserved, itype, count = struct.unpack_from("<HHH", b, 0)
    out = []
    for i in range(count):
        o = 6 + i * 16
        w, h, cc, rsv, planes, bitcount, nbytes, off = \
            struct.unpack_from("<BBBBHHII", b, o)
        bi = struct.unpack_from("<IiiHHIIiiII", b, off)
        out.append(dict(file=b, name=os.path.basename(path), W=(w or 256),
                        H=(h or 256), planes=planes, bitcount=bitcount,
                        nbytes=nbytes, off=off, biSize=bi[0], biW=bi[1],
                        biH=bi[2], biBits=bi[4], biImg=bi[6],
                        trailing=struct.unpack_from("<hh", b, off + 40)))
    return reserved, itype, count, out


def q1(path):
    """Where does the pixel data start?"""
    print("=" * 74)
    print("Q1  pixel-data start offset  -- %s" % os.path.basename(path))
    print("=" * 74)
    _, _, _, es = entries(path)
    for e in es:
        w, h = e["W"], e["H"]
        xor = w * h * 4
        andm = ((w + 31) // 32) * 4 * h
        print("  %4dx%-4d declared=%-8d  off=%-8d" % (w, h, e["nbytes"], e["off"]))
        print("            40 + xor + and = %-8d   %s"
              % (40 + xor + andm, "MATCH" if e["nbytes"] == 40 + xor + andm else ""))
        print("            44 + xor + and = %-8d   %s"
              % (44 + xor + andm, "MATCH" if e["nbytes"] == 44 + xor + andm else ""))
        print("            biSize=%d biW=%d biH=%d bits=%d biSizeImage=%d trailing(hs)=%s"
              % (e["biSize"], e["biW"], e["biH"], e["biBits"], e["biImg"], e["trailing"]))


def q2(path):
    """Does Windows take the hotspot from the ICONDIRENTRY planes/bitcount?"""
    _, _, _, es = entries(path)
    print("  %-22s entry(planes,bitcount) per image   Windows reports" %
          os.path.basename(path))
    for e in es:
        print("    %4dx%-4d  planes=%-4d bitcount=%-4d" % (e["W"], e["H"], e["planes"], e["bitcount"]), end="")
        hs = win_hotspot(path, e["W"], e["H"])
        print("   -> hotspot=%s" % (hs,))
    return es


def win_hotspot(path, cx=0, cy=0):
    flags = LR_LOADFROMFILE | (0 if (cx or cy) else LR_DEFAULTSIZE)
    h = user32.LoadImageW(None, path, IMAGE_CURSOR, cx, cy, flags)
    if not h:
        return "LOAD FAILED"
    ii = ICONINFO()
    if not user32.GetIconInfo(h, ctypes.byref(ii)):
        user32.DestroyCursor(h)
        return "GetIconInfo FAILED"
    res = (ii.xHotspot, ii.yHotspot)
    gdi32.DeleteObject(ii.hbmMask)
    gdi32.DeleteObject(ii.hbmColor)
    user32.DestroyCursor(h)
    return res


def draw_cursor(path, cx, cy, w, h):
    """Ask Windows to draw the cursor into a 32bpp top-down DIB; return BGRA bytes."""
    cur = user32.LoadImageW(None, path, IMAGE_CURSOR, cx, cy, LR_LOADFROMFILE)
    if not cur:
        return None, "LoadImage failed err=%d" % ctypes.get_last_error()
    hdc_screen = user32.GetDC(None)
    hdc = gdi32.CreateCompatibleDC(hdc_screen)
    bi = BITMAPINFO()
    ctypes.memset(ctypes.byref(bi), 0, ctypes.sizeof(bi))
    bi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bi.bmiHeader.biWidth = w
    bi.bmiHeader.biHeight = -h          # negative -> top-down rows
    bi.bmiHeader.biPlanes = 1
    bi.bmiHeader.biBitCount = 32
    bi.bmiHeader.biCompression = 0      # BI_RGB
    bits = ctypes.c_void_p()
    hbm = gdi32.CreateDIBSection(hdc, ctypes.byref(bi), DIB_RGB_COLORS,
                                 ctypes.byref(bits), None, 0)
    old = gdi32.SelectObject(hdc, hbm)
    ok = user32.DrawIconEx(hdc, 0, 0, cur, cx, cy, 0, None, DI_NORMAL)
    buf = ctypes.string_at(bits, w * h * 4)
    gdi32.SelectObject(hdc, old)
    gdi32.DeleteObject(hbm)
    gdi32.DeleteDC(hdc)
    user32.ReleaseDC(None, hdc_screen)
    user32.DestroyCursor(cur)
    if not ok:
        return None, "DrawIconEx failed err=%d" % ctypes.get_last_error()
    return buf, ""


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    print("#" * 74)
    print("# PART 1 -- how Microsoft lays out a .cur image")
    print("#" * 74)
    for n in ("aero_arrow.cur", "aero_move.cur", "aero_link.cur"):
        q1(os.path.join(r"C:\Windows\Cursors", n))
        print()

    print("#" * 74)
    print("# PART 2 -- where does Windows take the hotspot from?")
    print("#" * 74)
    for n in ("aero_arrow.cur", "aero_move.cur", "aero_link.cur", "aero_pen.cur"):
        q2(os.path.join(r"C:\Windows\Cursors", n))
        print()
    print("  -- our package --")
    for n in ("small", "medium", "large"):
        q2(os.path.join(here, "package", "cursors", "arknights_%s.cur" % n))
        print()

    print("#" * 74)
    print("# PART 3 -- what pixels does Windows actually draw? (ours, 32px)")
    print("#" * 74)
    p = os.path.join(here, "package", "cursors", "arknights_small.cur")
    buf, err = draw_cursor(p, 32, 32, 32, 32)
    if buf is None:
        print("  %s" % err)
    else:
        print("  non-transparent pixels: %d / 1024" %
              sum(1 for i in range(3, len(buf), 4) if buf[i] > 8))
        for y in range(0, 32):
            row = "".join("#" if buf[(y * 32 + x) * 4 + 3] > 128 else
                          ("+" if buf[(y * 32 + x) * 4 + 3] > 8 else ".")
                          for x in range(32))
            print("   %2d %s" % (y, row))


if __name__ == "__main__":
    main()
