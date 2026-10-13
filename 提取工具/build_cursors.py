# -*- coding: utf-8 -*-
"""Build installable Windows cursors from the recovered Arknights master.

Two independent art sources, each used where it is exact:

  body   -- the analytic master polygon (96 px pixel-CORNER space), rasterised by
            supersampled scanline coverage at EVERY output size.  No bitmap is
            ever resampled, so the outline keeps a 1-px anti-aliasing ramp at any
            scale.  Against the shipped 96 px tier: alpha RMS 2.58/255, only
            0.22 % of pixels off by more than 24/255.

  shadow -- the measured 96 px shadow field, resampled analytically about the tip
            origin.  The field is a Gaussian of sigma ~ 14.6 px on a 96 px canvas,
            i.e. strongly band-limited, so resampling it is faithful; measured
            recomposite error at 96 px is alpha RMS 1.89/255 with 97.1 % of pixels
            within +-2/255.  (Fitting the shadow analytically as a blurred polygon
            was tried: 8x worse, RMS 15.8/255.)

The game's own three tiers are one master drawn at art scale 1, 1/sqrt(2), 1/2,
so those three ratios become the three size variants.  The composition is
normalised so the tip sits at 1/12 of the canvas in every raster; at the game's
native 96 px canvas that yields exactly the game's own hotspot, (8, 8).
"""
import json
import math
import os
import pickle
import struct

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
EXTRACTED = os.path.join(HERE, "extracted")
OUT = os.path.join(HERE, "package")

# PIL's built-in bitmap font is ASCII-only, so CJK labels come out as
# replacement boxes.  Load a real system CJK face when one is available and
# fall back to the bitmap font otherwise (ASCII-only text still renders).
_FONT_CANDIDATES = [
    (r"C:\Windows\Fonts\msyh.ttc", 13),
    (r"C:\Windows\Fonts\msyhbd.ttc", 13),
    (r"C:\Windows\Fonts\simhei.ttf", 13),
    (r"C:\Windows\Fonts\Deng.ttf", 13),
    (r"C:\Windows\Fonts\simsun.ttc", 13),
]


def cjk_font(size=13):
    """A font that can actually draw Chinese; falls back to the bitmap font."""
    for path, default_size in _FONT_CANDIDATES:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()

with open(os.path.join(EXTRACTED, "_final_model.json"), "r", encoding="utf-8") as fh:
    _FM = json.load(fh)
POLY = [(float(p[0]), float(p[1])) for p in _FM["polygon_96"]]
with open(os.path.join(EXTRACTED, "_layers.pkl"), "rb") as fh:
    S96 = pickle.load(fh)["cursor_large"]["S"]

MASTER = 96.0                      # design canvas
TIP = (8.0, 8.0)                   # tip / hotspot in design space (8/96 = 1/12)
SQ = 2.0 ** -0.5                   # 0.70710678...

# art gain -> (chinese label, folder name, cursor file stem)
VARIANTS = [
    (0.5, u"小", "small", "arknights_small"),
    (SQ,  u"中", "medium", "arknights_medium"),
    (1.0, u"大", "large", "arknights_large"),
]

# rasters embedded in every .cur.  Windows picks the best match for the current
# cursor size / DPI; 32 is the Windows default, 256 the accessibility maximum.
RASTERS = [32, 48, 64, 96, 128, 256]

_tip_vertex = min(range(len(POLY)), key=lambda i: POLY[i][0] + POLY[i][1])


# --------------------------------------------------------------- raster ---
def raster_cov(poly, w, h, ss=8):
    """Supersampled scanline polygon coverage, pixel-CORNER space."""
    cov = [[0.0] * w for _ in range(h)]
    n = len(poly)
    inv = 1.0 / ss
    for y in range(h):
        row = cov[y]
        for sub in range(ss):
            yy = y + (sub + 0.5) * inv
            xs = []
            for i in range(n):
                x1, y1 = poly[i]
                x2, y2 = poly[(i + 1) % n]
                if (y1 > yy) != (y2 > yy):
                    xs.append(x1 + (yy - y1) * (x2 - x1) / (y2 - y1))
            xs.sort()
            for k in range(0, len(xs) - 1, 2):
                a, b = xs[k], xs[k + 1]
                if a < 0.0:
                    a = 0.0
                if b > w:
                    b = float(w)
                if b <= a:
                    continue
                ia, ib = int(a), int(b)
                if ia == ib:
                    row[ia] += (b - a) * inv
                    continue
                row[ia] += (ia + 1 - a) * inv
                for x in range(ia + 1, ib):
                    row[x] += inv
                if ib < w:
                    row[ib] += (b - ib) * inv
    return cov


def lanczos(x, a=3.0):
    if x <= -a or x >= a:
        return 0.0
    if x == 0.0:
        return 1.0
    px = math.pi * x
    return (a * math.sin(px) * math.sin(px / a)) / (px * px)


def shadow_taps(dstn, tip_dst, tip_src, u):
    """Per-destination-index taps into the source grid, as a list of (index, weight)."""
    ue = u if u < 1.0 else 1.0
    rad = 3.0 / ue if u < 1.0 else 3.0
    out = []
    for i in range(dstn):
        # corner-space position of this destination pixel centre, mapped back
        # into the source (design) corner space, then converted to an index.
        s = tip_src + (i + 0.5 - tip_dst) / u - 0.5
        j0 = int(math.floor(s - rad))
        j1 = int(math.ceil(s + rad))
        taps = []
        acc = 0.0
        for j in range(j0, j1 + 1):
            w = lanczos((s - j) * ue, 3.0)
            if w:
                taps.append((j, w))
                acc += w
        if acc:
            taps = [(j, w / acc) for j, w in taps]
        out.append(taps)
    return out


def render(gain, size):
    """Render one variant at one raster size -> (PIL RGBA, (hx, hy))."""
    N = float(size)
    u = gain * N / MASTER                       # art scale, canvas px per design px
    tipx = TIP[0] * N / MASTER                  # tip at 1/12 of the canvas
    tipy = TIP[1] * N / MASTER
    poly = [(tipx + (x - TIP[0]) * u, tipy + (y - TIP[1]) * u) for x, y in POLY]
    body = raster_cov(poly, size, size, ss=8)

    tx = shadow_taps(size, tipx, TIP[0], u)
    ty = shadow_taps(size, tipy, TIP[1], u)

    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    px = out.load()
    for j in range(size):
        tyj = ty[j]
        for i in range(size):
            B = body[j][i]
            if B > 1.0:
                B = 1.0
            if B >= 1.0 and not tyj:
                continue
            Sv = 0.0
            for y, wy in tyj:
                if not (0 <= y < 96):
                    continue
                row = S96[y]
                acc = 0.0
                for x, wx in tx[i]:
                    if 0 <= x < 96:
                        acc += row[x] * wx
                Sv += acc * wy
            if Sv < 0.0:
                Sv = 0.0
            elif Sv > 1.0:
                Sv = 1.0
            A = B + Sv * (1.0 - B)
            if A <= 0.0:
                continue
            gg = B / A
            if gg > 1.0:
                gg = 1.0
            av = int(A * 255.0 + 0.5)
            if av <= 0:
                continue
            gv = int(gg * 255.0 + 0.5)
            px[i, j] = (gv, gv, gv, av)

    # hotspot = the pixel CONTAINING the tip apex.  At the game's native 96 px
    # canvas the apex lands at (8.516, 8.851) -> floor -> (8, 8), which is exactly
    # the hotspot the game itself declares for cursor_large.
    ax = tipx + (POLY[_tip_vertex][0] - TIP[0]) * u
    ay = tipy + (POLY[_tip_vertex][1] - TIP[1]) * u
    hx = max(0, min(size - 1, int(math.floor(ax))))
    hy = max(0, min(size - 1, int(math.floor(ay))))
    return out, (hx, hy)


# ----------------------------------------------------------------- .cur ---
def cur_image(im):
    """One BMP/DIB image block of a .cur file (32-bit BGRA + AND mask).

    The block is exactly: 40-byte BITMAPINFOHEADER, then the bottom-up 32bpp
    BGRA XOR bitmap, then the 1bpp AND mask.  Verified against
    C:\\Windows\\Cursors\\*.cur: the ICONDIRENTRY byte count equals
    40 + w*h*4 + andmask for every image, so there is NO hotspot field between
    the header and the pixels.  (The hotspot goes in the ICONDIRENTRY -- see
    write_cur.)
    """
    w, h = im.size
    px = im.load()
    xor = bytearray()
    alpha_used = False
    for y in range(h - 1, -1, -1):                 # DIB is bottom-up
        for x in range(w):
            r, g, b, a = px[x, y]
            if a:
                alpha_used = True
            # Windows stores straight (non-premultiplied) BGRA for 32bpp cursors
            xor += bytes((b, g, r, a))
    rowbytes = ((w + 31) // 32) * 4
    if alpha_used:
        andmask = bytes(rowbytes * h)              # the alpha channel is authoritative
    else:
        andmask = bytearray()
        for y in range(h - 1, -1, -1):
            row = bytearray(rowbytes)
            for x in range(w):
                if px[x, y][3] < 128:
                    row[x >> 3] |= 0x80 >> (x & 7)
            andmask += row
        andmask = bytes(andmask)
    hdr = struct.pack("<IiiHHIIiiII",
                      40, w, h * 2, 1, 32, 0, len(xor) + len(andmask), 0, 0, 0, 0)
    return hdr + bytes(xor) + andmask


def write_cur(path, images):
    """images: list of (PIL RGBA, (hx, hy)).

    Format notes, all established by loading C:\\Windows\\Cursors\\*.cur
    through user32.LoadImage + GetIconInfo:

      * The hotspot of each image is stored in the ICONDIRENTRY, in the two
        WORDs that an .ico would use for wPlanes / wBitCount.  Microsoft's own
        files prove it: aero_move.cur carries planes=45, bitcount=45 and
        Windows reports hotspot (45,45); aero_link.cur carries planes=25,
        bitcount=0 and Windows reports (25,0).  Writing the conventional
        planes=1, bitcount=32 there makes Windows report hotspot (1,32) for
        every raster, so the click point lands nowhere near the arrow tip.
      * GetIconInfo returns the hotspot for whichever image Windows selected,
        so the entry values must be correct per raster, not just for one.
    """
    blobs = [cur_image(im) for im, hs in images]
    n = len(blobs)
    off = 6 + 16 * n
    entries = bytearray()
    for (im, hs), blob in zip(images, blobs):
        w, h = im.size
        entries += struct.pack("<BBBBHHII",
                               w if w < 256 else 0,
                               h if h < 256 else 0,
                               0, 0,
                               int(hs[0]) & 0xFFFF,      # cursor hotspot X
                               int(hs[1]) & 0xFFFF,      # cursor hotspot Y
                               len(blob), off)
        off += len(blob)
    with open(path, "wb") as fh:
        fh.write(struct.pack("<HHH", 0, 2, n))
        fh.write(entries)
        for blob in blobs:
            fh.write(blob)


# ------------------------------------------------------------------ go ---
def main():
    if not os.path.isdir(OUT):
        os.makedirs(OUT)
    curdir = os.path.join(OUT, "cursors")
    if not os.path.isdir(curdir):
        os.makedirs(curdir)

    manifest = {}
    for gain, label, folder, stem in VARIANTS:
        images = []
        hs_map = {}
        for n in RASTERS:
            im, hs = render(gain, n)
            images.append((im, hs))
            hs_map[str(n)] = list(hs)
            print("  %s %3dpx hotspot=%s" % (stem, n, hs))
        p = os.path.join(curdir, stem + ".cur")
        write_cur(p, images)
        manifest[stem] = {"label": label, "gain": gain,
                          "hotspots": hs_map, "bytes": os.path.getsize(p)}
        print("%-22s gain=%.4f  %d bytes" % (stem + ".cur", gain, os.path.getsize(p)))

    with open(os.path.join(OUT, "_manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=2)

    # ---- preview sheet -------------------------------------------------
    # Layout: one column per variant; a two-line caption on top (a real CJK
    # face, so the Chinese labels are legible instead of replacement boxes),
    # then the 96 px checkerboard cell with the hotspot ringed, then a strip
    # of the 32/48/64 rasters that Windows will actually pick from.
    cell = 128
    gap = 14
    head = 46
    strip = 96
    cap = 18
    sheet = Image.new("RGB", (cell * 3 + gap * 4, head + cell + strip + cap),
                      (28, 28, 32))
    dr = ImageDraw.Draw(sheet)
    fnt = cjk_font(13)
    fnt_s = cjk_font(11)
    for col, (gain, label, folder, stem) in enumerate(VARIANTS):
        x0 = gap + col * (cell + gap)
        dr.text((x0, 6), u"变体 %s" % label, fill=(240, 240, 240), font=fnt)
        dr.text((x0, 25), u"art scale %.4f" % gain, fill=(150, 195, 255), font=fnt_s)
        for y in range(cell):
            for x in range(cell):
                v = 190 if ((x // 8) + (y // 8)) % 2 == 0 else 145
                sheet.putpixel((x0 + x, head + y), (v, v, v))
        im, hs = render(gain, 96)
        ox = x0 + (cell - 96) // 2
        oy = head + (cell - 96) // 2
        sheet.paste(im, (ox, oy), im)
        dr.ellipse([ox + hs[0] - 3, oy + hs[1] - 3, ox + hs[0] + 3, oy + hs[1] + 3],
                   outline=(255, 60, 60))
        x = x0
        for n in (32, 48, 64):
            im2, _ = render(gain, n)
            sheet.paste(im2, (x, head + cell + 6), im2)
            x += n + 4
        dr.text((x0, head + cell + 6 + 66), u"红圈 = 热点位置", fill=(255, 120, 120),
                font=fnt_s)
    sp = os.path.join(OUT, "preview_variants.png")
    sheet.save(sp)
    print("wrote %s" % sp)


def verify(size=96, gain=1.0, quiet=False):
    """Compare a render against the shipped extracted PNG (alpha channel)."""
    ref = Image.open(os.path.join(EXTRACTED, "cursor_large.png")).convert("RGBA")
    if size != 96:
        raise SystemExit("verify() only supports the 96 px native tier")
    mine, hs = render(gain, size)
    rp, mp = ref.load(), mine.load()
    se = 0.0
    mx = 0
    over24 = 0
    n = 0
    for y in range(size):
        for x in range(size):
            d = rp[x, y][3] - mp[x, y][3]
            n += 1
            se += d * d
            mx = max(mx, abs(d))
            if abs(d) > 24:
                over24 += 1
    rms = math.sqrt(se / n)
    if not quiet:
        print("verify %dpx gain=%.4f: alpha RMS=%.3f/255  max=%d  px>24=%d/%d (%.2f%%)  hotspot=%s (game says (8,8))"
              % (size, gain, rms, mx, over24, n, 100.0 * over24 / n, hs))
    return rms


def build_custom(gain, sizes, outname=None, outdir=None):
    """Continuous-size mode.

    The in-game CURSOR_SIZE control is a SLIDER, not a fixed ladder, so the user
    may want any art scale rather than the three shipped stops.  Because the
    master is a polygon plus an analytic shadow field, an arbitrary gain costs
    nothing in quality: rasterise again at a different scale.  A .cur can hold at
    most one image per pixel dimension, so the caller supplies the raster list.
    """
    outdir = outdir or OUT
    if not os.path.isdir(outdir):
        os.makedirs(outdir)
    stem = outname or ("arknights_%03d" % int(round(gain * 100)))
    images = []
    hs_map = {}
    for n in sizes:
        im, hs = render(gain, n)
        images.append((im, hs))
        hs_map[str(n)] = list(hs)
        print("  %s %3dpx hotspot=%s" % (stem, n, hs))
    p = os.path.join(outdir, stem + ".cur")
    write_cur(p, images)
    man = os.path.join(outdir, "_" + stem + ".json")
    with open(man, "w", encoding="utf-8") as fh:
        json.dump({"gain": gain, "rasters": list(sizes),
                   "hotspots": hs_map, "bytes": os.path.getsize(p)},
                  fh, ensure_ascii=False, indent=2)
    print("%s  gain=%.4f  %d bytes" % (p, gain, os.path.getsize(p)))
    return p


if __name__ == "__main__":
    import sys
    if "--verify" in sys.argv:
        verify()
    elif "--gain" in sys.argv:
        # python build_cursors.py --gain 1.25 [--sizes 32,48,64,96,128,256]
        g = float(sys.argv[sys.argv.index("--gain") + 1])
        if "--sizes" in sys.argv:
            rast = [int(v) for v in sys.argv[sys.argv.index("--sizes") + 1].split(",")]
        else:
            rast = RASTERS
        nm = None
        if "--name" in sys.argv:
            nm = sys.argv[sys.argv.index("--name") + 1]
        build_custom(g, rast, nm)
    else:
        main()
