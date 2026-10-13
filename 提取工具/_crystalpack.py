# -*- coding: utf-8 -*-
"""Build a portable, multi-resolution Windows cursor scheme from the installed
PRTS Replica v8 96x crystal art.

Source of truth: HKCU\\Control Panel\\Cursors -- the art the user actually sees.
Output: G:\\ArknightsCursorExtract\\CrystalCursorPack\\
   cursors\\  one multi-raster .cur per Windows role
   extracted\\ the untouched native 96x96 PNG per role
   preview.png contact sheet with hotspots marked
   before-install-backup.json  the previous scheme, for one-command rollback
"""
import io, json, os, struct, winreg

from PIL import Image, ImageDraw

PACK = r"G:\ArknightsCursorExtract\CrystalCursorPack"
CURD = os.path.join(PACK, "cursors")
EXD = os.path.join(PACK, "extracted")
NATIVE = 96
RASTERS = [32, 48, 64, 96, 128, 256]
os.makedirs(CURD, exist_ok=True)
os.makedirs(EXD, exist_ok=True)

ROLE_ORDER = ["Arrow", "Help", "AppStarting", "Wait", "Crosshair", "IBeam", "NWPen",
              "No", "SizeNS", "SizeWE", "SizeNWSE", "SizeNESW", "SizeAll", "UpArrow",
              "Hand", "Pin", "Person"]

# ---------------------------------------------------------------- registry
k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Control Panel\Cursors")
roles = {}
plen = winreg.QueryInfoKey(k)[1]
for i in range(plen):
    name, val, _ = winreg.EnumValue(k, i)
    if isinstance(val, str) and val.lower().endswith((".cur", ".ani")):
        roles[name] = os.path.expandvars(val)
before = {}
for i in range(plen):
    name, val, _ = winreg.EnumValue(k, i)
    before[name] = val
winreg.CloseKey(k)
print("registry roles with art: %d" % len(roles))
for r in ROLE_ORDER:
    print("   %-12s %s" % (r, os.path.basename(roles.get(r, "(none)"))))

json.dump(before, open(os.path.join(PACK, "before-install-backup.json"), "w",
                       encoding="utf-8"), indent=2, ensure_ascii=False)


# ---------------------------------------------------------------- parsers
def riff_chunks(buf, start, end):
    p, out = start, []
    while p + 8 <= end:
        cid, sz = buf[p:p + 4], struct.unpack_from("<I", buf, p + 4)[0]
        if p + 8 + sz > end:
            out.append((cid, p + 8, end - (p + 8)))
            break
        out.append((cid, p + 8, sz))
        p += 8 + sz + (sz & 1)
    return out


def dib_to_image(data):
    """data = BITMAPINFOHEADER + XOR + AND  ->  (RGBA image, w, h)"""
    _hs, bw, bh, _pl, _bpp = struct.unpack_from("<IiiHH", data, 0)
    w = bw
    h = abs(bh) // 2 if bh == 2 * w or bh == 2 * abs(bh) // 2 * 2 else abs(bh)
    h = abs(bh) // 2 if abs(bh) % 2 == 0 else abs(bh)
    need = w * h * 4
    xor = data[40:40 + need]
    im = Image.frombytes("RGBA", (w, h), xor, "raw", "BGRA")
    return im.transpose(Image.FLIP_TOP_BOTTOM), w, h, _hs


def parse_cur_bytes(raw):
    """Parse a COMPLETE .cur image (ICONDIR + entries + DIB/PNG) -> (image, hsx, hsy)."""
    _r0, rtype, n = struct.unpack_from("<HHH", raw, 0)
    assert rtype == 2, "not a cursor (type=%d)" % rtype
    best = None
    for i in range(n):
        w, h, _nc, _res, hsx, hsy, nb, off = struct.unpack_from("<BBBBHHII", raw, 6 + 16 * i)
        w, h = w or 256, h or 256
        payload = raw[off:off + nb]
        if payload[:4] == b"\x89PNG":
            im = Image.open(io.BytesIO(payload)).convert("RGBA")
        else:
            im, _w, _h, _hs = dib_to_image(payload)
        if best is None or im.width > best[0].width:
            best = (im, hsx, hsy)
    return best


def read_cur(path):
    raw = open(path, "rb").read()
    if raw[:4] == b"RIFF" and raw[8:12] == b"ACON":
        raise SystemExit("not a .cur")
    return parse_cur_bytes(raw)


def read_ani_frame0(path):
    """Return (image, hsx, hsy) of the first ANI frame.

    ANI layout (verified by hexdump of PRTS-Replica-v8-96x-work.ani):
        RIFF <size> ACON | anih@12 | rate@56 | LIST@352 type='fram'
    Each LIST child is an `icon` chunk whose payload is a COMPLETE .cur file
    (ICONDIR + entry table + BITMAPINFOHEADER), so hotspots ARE present.
    Children begin 12 bytes past the LIST tag: 8 header + 4 type field.
    """
    raw = open(path, "rb").read()
    assert raw[:4] == b"RIFF" and raw[8:12] == b"ACON", "not an .ani: %s" % path
    for cid, off, sz in riff_chunks(raw, 12, len(raw)):
        if cid != b"LIST":
            continue
        if raw[off:off + 4] != b"fram":          # off points AT the 4-byte type
            continue
        p, end = off + 4, off + sz               # skip the type field
        while p + 8 <= end:
            iid = raw[p:p + 4]
            isz = struct.unpack_from("<I", raw, p + 4)[0]
            if iid in (b"icon", b"cur "):
                d = raw[p + 8:p + 8 + isz]
                if d[:4] == b"\x89PNG":
                    return Image.open(io.BytesIO(d)).convert("RGBA"), 0, 0
                return parse_cur_bytes(d)        # complete .cur: hotspot included
            p += 8 + isz + (isz & 1)
    raise SystemExit("no frame in %s" % path)


# ---------------------------------------------------------------- cursor writer
def resize_rgba(im, size):
    """LANCZOS resize with PREMULTIPLIED alpha.

    All fully-transparent pixels in this art are exactly (0,0,0,0).  Resampling
    straight alpha therefore drags black into every edge, producing a dark halo
    around the crystal.  Multiplying RGB by alpha first, resampling, then
    un-premultiplying keeps the edge colour correct.
    """
    if im.size == (size, size):
        return im.copy()
    w, h = im.size
    src = im.load()
    pm = Image.new("RGB", (w, h))
    al = Image.new("L", (w, h))
    pmp, alp = pm.load(), al.load()
    for y in range(h):
        for x in range(w):
            r, g, b, a = src[x, y]
            f = a / 255.0
            pmp[x, y] = (int(r * f + 0.5), int(g * f + 0.5), int(b * f + 0.5))
            alp[x, y] = a
    pms = pm.resize((size, size), Image.LANCZOS)
    als = al.resize((size, size), Image.LANCZOS)
    out = Image.new("RGBA", (size, size))
    op, sp, ap = out.load(), pms.load(), als.load()
    for y in range(size):
        for x in range(size):
            a = ap[x, y]
            if a == 0:
                op[x, y] = (0, 0, 0, 0)
                continue
            f = 255.0 / a
            r, g, b = sp[x, y]
            op[x, y] = (min(255, int(r * f + 0.5)), min(255, int(g * f + 0.5)),
                        min(255, int(b * f + 0.5)), a)
    return out


def cur_image(im, hsx, hsy):
    w, h = im.size
    px = im.load()
    xor = bytearray()
    for y in range(h - 1, -1, -1):
        row = bytearray()
        for x in range(w):
            r, g, b, a = px[x, y]
            row += bytes((b, g, r, a))
        xor += row
    andmask = bytes((w + 31) // 32 * 4 * h)
    hdr = struct.pack("<IiiHHIIiiII", 40, w, h * 2, 1, 32, 0,
                      len(xor) + len(andmask), 0, 0, 0, 0)
    return hdr + bytes(xor) + andmask


def write_cur(path, images):
    """images = [(PIL RGBA, hsx, hsy), ...]"""
    blobs = [cur_image(im, hx, hy) for im, hx, hy in images]
    n = len(blobs)
    out = bytearray(struct.pack("<HHH", 0, 2, n))
    off = 6 + 16 * n
    for (im, hx, hy), blob in zip(images, blobs):
        w, h = im.size
        out += struct.pack("<BBBBHHII", w if w < 256 else 0, h if h < 256 else 0,
                           0, 0, hx, hy, len(blob), off)
        off += len(blob)
    for blob in blobs:
        out += blob
    open(path, "wb").write(bytes(out))
    return len(out)


def scaled_hotspot(hx, hy, size):
    return (min(size - 1, max(0, int(round(hx * size / float(NATIVE))))),
            min(size - 1, max(0, int(round(hy * size / float(NATIVE))))))


# ---------------------------------------------------------------- build
manifest = []
preview_cells = []
for role in ROLE_ORDER:
    src = roles.get(role)
    if not src or not os.path.exists(src):
        print("SKIP %-12s (no source)" % role)
        continue
    ext = os.path.splitext(src)[1].lower()
    note = ""
    if ext == ".cur":
        art, hsx, hsy = read_cur(src)
        note = "native hotspot from .cur"
    else:
        art, hsx, hsy = read_ani_frame0(src)
        note = "native hotspot from ANI frame 0 (frames are embedded .cur files)"

    art = art.convert("RGBA")
    if art.width != NATIVE:
        art = resize_rgba(art, NATIVE)

    png = os.path.join(EXD, "Arknights_Crystal_%s_native96.png" % role)
    art.save(png)

    rasters = []
    for size in RASTERS:
        if size == NATIVE:
            im = art.copy()                       # pixel-exact, no resampling
        else:
            im = resize_rgba(art, size)
        hx, hy = scaled_hotspot(hsx, hsy, size)
        rasters.append((im, hx, hy))

    out = os.path.join(CURD, "Arknights_Crystal_%s.cur" % role)
    nbytes = write_cur(out, rasters)
    hs96 = scaled_hotspot(hsx, hsy, NATIVE)
    manifest.append({"role": role, "source": src, "output": out, "bytes": nbytes,
                     "native_hotspot_96": list(hs96), "rasters": RASTERS, "note": note})
    print("%-12s -> %-34s %7d B  hs96=%s   %s" % (role, os.path.basename(out), nbytes, hs96, note))
    preview_cells.append((role, art, hs96))

json.dump(manifest, open(os.path.join(PACK, "_manifest.json"), "w", encoding="utf-8"),
          indent=2, ensure_ascii=False)

# ---------------------------------------------------------------- preview
CELL, COLS = 128, 6
rows = (len(preview_cells) + COLS - 1) // COLS
sheet = Image.new("RGB", (COLS * (CELL + 8), rows * (CELL + 26)), (22, 24, 28))
dr = ImageDraw.Draw(sheet)
for i, (role, art, hs) in enumerate(preview_cells):
    cx, cy = (i % COLS) * (CELL + 8), (i // COLS) * (CELL + 26)
    bg = Image.new("RGB", (CELL, CELL), (58, 66, 80))
    th = art.resize((CELL, CELL), Image.LANCZOS)
    bg.paste(th, (0, 0), th)
    d2 = ImageDraw.Draw(bg)
    hx, hy = hs[0] * CELL // NATIVE, hs[1] * CELL // NATIVE
    d2.line([(hx - 7, hy), (hx + 7, hy)], fill=(255, 60, 60), width=1)
    d2.line([(hx, hy - 7), (hx, hy + 7)], fill=(255, 60, 60), width=1)
    sheet.paste(bg, (cx, cy))
    dr.text((cx + 2, cy + CELL + 3), "%s  hs96=%d,%d" % (role, hs[0], hs[1]), fill=(200, 200, 208))
sheet.save(os.path.join(PACK, "preview.png"))
print("\nwrote preview.png  (%d roles)" % len(preview_cells))
print("pack root:", PACK)
