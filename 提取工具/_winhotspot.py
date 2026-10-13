# -*- coding: utf-8 -*-
"""Ask Windows itself what hotspot it reads out of a .cur, and compare that
against what is stored in the file's bytes.

Background: for CUR files the ICONDIRENTRY is byte-identical in layout to an
ICO entry, where wPlanes/wBitCount mean planes/bit depth.  Several sources
claim that for cursors those two WORDs instead carry the hotspot.  Our writer
sets planes=1, bitcount=32 there, and Windows reported hotspot=(1,32) -- which
is exactly those two values.  This script settles it by probing real Microsoft
cursors (whose entries carry planes=0, bitcount=0) and our own files.
"""
import ctypes
import ctypes.wintypes as wt
import glob
import os
import struct
import sys

IMAGE_CURSOR = 2
LR_LOADFROMFILE = 0x0010
LR_DEFAULTSIZE = 0x0040


class ICONINFO(ctypes.Structure):
    _fields_ = [("fIcon", wt.BOOL),
                ("xHotspot", wt.DWORD),
                ("yHotspot", wt.DWORD),
                ("hbmMask", wt.HBITMAP),
                ("hbmColor", wt.HBITMAP)]


user32 = ctypes.WinDLL("user32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
user32.LoadImageW.restype = wt.HANDLE
user32.LoadImageW.argtypes = [wt.HINSTANCE, wt.LPCWSTR, wt.UINT,
                              ctypes.c_int, ctypes.c_int, wt.UINT]
user32.GetIconInfo.argtypes = [wt.HANDLE, ctypes.POINTER(ICONINFO)]
user32.GetIconInfo.restype = wt.BOOL
user32.DestroyCursor.argtypes = [wt.HANDLE]
gdi32.DeleteObject.argtypes = [wt.HANDLE]


def win_hotspot(path, cx=0, cy=0):
    """What the OS says after actually loading the file."""
    h = user32.LoadImageW(None, path, IMAGE_CURSOR, cx, cy,
                          LR_LOADFROMFILE | (0 if (cx or cy) else LR_DEFAULTSIZE))
    if not h:
        return None, "LoadImage failed err=%d" % ctypes.get_last_error()
    ii = ICONINFO()
    ok = user32.GetIconInfo(h, ctypes.byref(ii))
    res = (ii.xHotspot, ii.yHotspot) if ok else None
    if ok:
        gdi32.DeleteObject(ii.hbmMask)
        gdi32.DeleteObject(ii.hbmColor)
    user32.DestroyCursor(h)
    return res, "" if ok else "GetIconInfo failed"


def file_facts(path):
    """What is actually inside the file."""
    b = open(path, "rb").read()
    reserved, itype, count = struct.unpack_from("<HHH", b, 0)
    out = []
    for i in range(count):
        o = 6 + i * 16
        w, h, colorcount, res, planes, bitcount, nbytes, off = \
            struct.unpack_from("<BBBBHHII", b, o)
        dx, dy = struct.unpack_from("<ii", b, off + 40)
        real_h = (w or 256, h or 256)
        out.append(dict(entry=(w, h), planes=planes, bitcount=bitcount,
                        first_px=(dx & 0xFFFF, dy & 0xFFFF), real=real_h,
                        off=off, nbytes=nbytes))
    return reserved, itype, count, out


def report(path, label):
    if not os.path.exists(path):
        print("  [%s] missing" % label)
        return
    reserved, itype, count, entries = file_facts(path)
    print("  %s" % label)
    print("    file      : reserved=%d type=%d images=%d" % (reserved, itype, count))
    for e in entries:
        print("      %4dx%-4d entry(hs_x=%d hs_y=%d)  first two pixels=%s"
              % (e["real"][0], e["real"][1], e["planes"], e["bitcount"], e["first_px"]))
    for (cx, cy) in ((0, 0), (32, 32), (48, 48), (96, 96)):
        hs, err = win_hotspot(path, cx, cy)
        tag = "default" if (cx == 0) else "%dx%d" % (cx, cy)
        print("    Windows loads %-8s -> hotspot=%s %s" % (tag, hs, err))


def main():
    print("=" * 72)
    print("REAL MICROSOFT CURSORS (ground truth for the format)")
    print("=" * 72)
    for p in sorted(glob.glob(r"C:\Windows\Cursors\*.cur")):
        n = os.path.basename(p).lower()
        if n in ("aero_arrow.cur", "aero_pen.cur", "aero_text.cur",
                 "aero_link.cur", "aero_cross.cur", "aero_move.cur"):
            report(p, n)
    print()
    print("=" * 72)
    print("OUR PACKAGE")
    print("=" * 72)
    here = os.path.dirname(os.path.abspath(__file__))
    for n in ("small", "medium", "large"):
        p = os.path.join(here, "package", "cursors", "arknights_%s.cur" % n)
        report(p, "arknights_%s.cur" % n)


if __name__ == "__main__":
    main()
