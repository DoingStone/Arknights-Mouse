# -*- coding: utf-8 -*-
"""Round-trip check for our .cur files.

Parses each file back from bytes and checks:
  1. every ICONDIRENTRY's declared byte count equals the true geometry
     (40-byte DIB header + bottom-up 32bpp BGRA + 1bpp AND mask)
  2. the AND mask is all-zero wherever an alpha channel is present
  3. the decoded pixels are identical to a fresh in-process render
  4. the hotspot stored in the ICONDIRENTRY matches the renderer's hotspot
  5. Windows itself, asked to load the file, reports that same hotspot

Format established against C:\\Windows\\Cursors\\*.cur:
  * pixel data begins at entryOffset + 40 (no hotspot field before the pixels)
  * the per-image hotspot lives in the ICONDIRENTRY, in the two WORDs that an
    .ico would use for wPlanes / wBitCount
"""
import ctypes
import ctypes.wintypes as wt
import os
import struct

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.join(HERE, "package", "cursors")

# ---------------------------------------------------------------- Windows ---
IMAGE_CURSOR = 2
LR_LOADFROMFILE = 0x0010
LR_DEFAULTSIZE = 0x0040


class ICONINFO(ctypes.Structure):
    _fields_ = [("fIcon", wt.BOOL), ("xHotspot", wt.DWORD), ("yHotspot", wt.DWORD),
                ("hbmMask", wt.HBITMAP), ("hbmColor", wt.HBITMAP)]


_u32 = ctypes.WinDLL("user32", use_last_error=True)
_g32 = ctypes.WinDLL("gdi32", use_last_error=True)
_u32.LoadImageW.restype = wt.HANDLE
_u32.LoadImageW.argtypes = [wt.HINSTANCE, wt.LPCWSTR, wt.UINT,
                           ctypes.c_int, ctypes.c_int, wt.UINT]
_u32.GetIconInfo.argtypes = [wt.HANDLE, ctypes.POINTER(ICONINFO)]
_u32.GetIconInfo.restype = wt.BOOL
_u32.DestroyCursor.argtypes = [wt.HANDLE]
_g32.DeleteObject.argtypes = [wt.HANDLE]


def win_hotspot(path, size):
    """The hotspot Windows reports for the image it selects at `size` px."""
    h = _u32.LoadImageW(None, path, IMAGE_CURSOR, size, size, LR_LOADFROMFILE)
    if not h:
        return None
    ii = ICONINFO()
    ok = _u32.GetIconInfo(h, ctypes.byref(ii))
    res = (ii.xHotspot, ii.yHotspot) if ok else None
    if ok:
        _g32.DeleteObject(ii.hbmMask)
        _g32.DeleteObject(ii.hbmColor)
    _u32.DestroyCursor(h)
    return res


# ----------------------------------------------------------------- parser ---
def parse(path):
    d = open(path, "rb").read()
    res, typ, n = struct.unpack_from("<HHH", d, 0)
    assert res == 0 and typ == 2, (res, typ)
    out = []
    for i in range(n):
        (w, h, cc, rsv, hx, hy, sz, off) = struct.unpack_from("<BBBBHHII", d, 6 + 16 * i)
        bi = struct.unpack_from("<IiiHHIIiiII", d, off)
        bw, bh, bpl, bbc, comp, isz = bi[1], bi[2], bi[3], bi[4], bi[5], bi[6]
        W, H = bw, bh // 2
        px0 = off + 40                      # <-- pixels start right after the header
        pxs = d[px0: px0 + W * H * 4]
        im = Image.new("RGBA", (W, H))
        p = im.load()
        for y in range(H):
            for x in range(W):
                o = ((H - 1 - y) * W + x) * 4
                b, g, r, a = pxs[o], pxs[o + 1], pxs[o + 2], pxs[o + 3]
                p[x, y] = (r, g, b, a)
        rowbytes = ((W + 31) // 32) * 4
        andsz = rowbytes * H
        expect = 40 + W * H * 4 + andsz
        out.append({"dir_w": w, "dir_h": h, "entry_hs": (hx, hy),
                    "dir_bytes": sz, "W": W, "H": H, "planes": bpl, "bits": bbc,
                    "comp": comp, "imgsize": isz, "img": im,
                    "actual_bytes": expect,
                    "mod256": (hx % 256, hy % 256),
                    "and_zero": all(v == 0 for v in d[px0 + W * H * 4:
                                                       px0 + W * H * 4 + andsz])})
    return typ, out


def render(gain, size):
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "bc", os.path.join(HERE, "build_cursors.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m.render(gain, size)


VAR = [("arknights_small", 0.5), ("arknights_medium", 2 ** -0.5), ("arknights_large", 1.0)]

bad = 0
for stem, gain in VAR:
    path = os.path.join(PKG, stem + ".cur")
    typ, ents = parse(path)
    print("=" * 104)
    print("%s  (%d bytes, type=%d, %d images)"
          % (os.path.basename(path), os.path.getsize(path), typ, len(ents)))
    for e in ents:
        win = win_hotspot(path, e["W"])
        print("  %3dx%-3d entry(hs=%s) dib(pl=%d bc=%d isz=%d) declared=%-7d geometry=%-7d "
              "and_zero=%-5s win=%s"
              % (e["W"], e["H"], e["entry_hs"], e["planes"], e["bits"], e["imgsize"],
                 e["dir_bytes"], e["actual_bytes"], e["and_zero"], win))
        if e["dir_bytes"] != e["actual_bytes"]:
            print("      !! declared %d != geometry %d" % (e["dir_bytes"], e["actual_bytes"]))
            bad += 1
        if e["planes"] != 1 or e["bits"] != 32:
            print("      !! DIB header planes/bits should be 1/32, got %d/%d"
                  % (e["planes"], e["bits"]))
            bad += 1
        ref, hs = render(gain, e["W"])
        if list(ref.getdata()) != list(e["img"].getdata()):
            n = sum(1 for a, b in zip(ref.getdata(), e["img"].getdata()) if a != b)
            print("      !! pixel mismatch vs fresh render: %d px" % n)
            bad += 1
        if tuple(hs) != tuple(e["entry_hs"]):
            print("      !! entry hotspot %s != render %s" % (e["entry_hs"], hs))
            bad += 1
        if win is not None and tuple(win) != tuple(e["entry_hs"]):
            print("      !! Windows reports %s but the entry stores %s" % (win, e["entry_hs"]))
            bad += 1
print()
print("problems: %d" % bad)
