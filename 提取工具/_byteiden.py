# -*- coding: utf-8 -*-
"""Byte-level identity proof for the exported pointer textures.

For each of the three pointer Texture2D objects in sharedassets0.assets this
compares the RAW pixel payload stored inside the asset against the bytes of the
PNG we exported.  If they match byte-for-byte (in one row order or the other)
then the export is bit-exact and provably free of any decode/compression loss.

It also prints the decode-relevant Texture2D fields so the format claim
(RGBA32, uncompressed, single mip) rests on the asset's own metadata.
"""
import hashlib
import os
import struct

import UnityPy
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ASSET = r"G:\Hypergryph Launcher\games\Arknights\Arknights_Data\sharedassets0.assets"
EXT = os.path.join(HERE, "extracted")

TARGETS = [(11, "cursor_small"), (7, "cursor_medium"), (13, "cursor_large")]

# Unity's TextureFormat enum values we care about
FMT_NAMES = {1: "Alpha8", 2: "ARGB4444", 3: "RGB24", 4: "RGBA32", 5: "ARGB32",
             7: "RGB565", 10: "DXT1", 12: "DXT5", 25: "ASTC_RGB_8x8",
             47: "ASTC_RGBA_8x8", 48: "ASTC_RGBA_6x6", 63: "ETC_RGB4"}


def px_rows(im):
    w, h = im.size
    p = im.load()
    return [[p[x, y] for x in range(w)] for y in range(h)]


def flatten(rows):
    return b"".join(bytes(v) for row in rows for v in row)


print("asset: %s" % ASSET)
print("size : %d bytes" % os.path.getsize(ASSET))
print()

env = UnityPy.load(ASSET)
objs = [o for o in env.objects if o.type.name == "Texture2D"]
print("Texture2D objects in this file: %d" % len(objs))
print()

for pid, name in TARGETS:
    match = [o for o in objs if o.path_id == pid]
    if not match:
        print("!! path_id %d (%s) not found" % (pid, name))
        continue
    obj = match[0]
    d = obj.read()

    raw = d.image_data
    if hasattr(raw, "image_data"):
        raw = raw.image_data
    raw = bytes(raw)

    w, h, fmt = d.m_Width, d.m_Height, d.m_TextureFormat
    cis = getattr(d, "m_CompleteImageSize", None)
    mips = getattr(d, "m_MipCount", None)
    readable = getattr(d, "m_IsReadable", None)
    srgb = getattr(d, "m_sRGB", None)

    print("=" * 92)
    print("%s   path_id=%d" % (name, pid))
    print("  m_Width x m_Height     : %d x %d" % (w, h))
    print("  m_TextureFormat        : %d (%s)" % (fmt, FMT_NAMES.get(fmt, "?")))
    print("  m_CompleteImageSize    : %s   (w*h*4 = %d)" % (cis, w * h * 4))
    print("  m_MipCount             : %s" % mips)
    print("  m_IsReadable           : %s" % readable)
    print("  m_sRGB                 : %s" % srgb)
    print("  raw payload bytes      : %d" % len(raw))

    png = os.path.join(EXT, name + ".png")
    im = Image.open(png).convert("RGBA")
    rows = px_rows(im)
    top_down = flatten(rows)
    bottom_up = flatten(list(reversed(rows)))

    print("  exported PNG           : %s  %dx%d %s"
          % (os.path.basename(png), im.size[0], im.size[1], im.mode))

    verdict = "NO MATCH"
    if len(raw) == len(top_down):
        if raw == top_down:
            verdict = "IDENTICAL (top-down row order)"
        elif raw == bottom_up:
            verdict = "IDENTICAL (bottom-up row order)"
    elif len(raw) > len(top_down):
        # tolerate a serialization header: look for the pixel block inside
        needle = top_down[:64]
        idx = raw.find(needle)
        if idx < 0:
            idx = raw.find(bottom_up[:64])
            if idx >= 0 and raw[idx:idx + len(bottom_up)] == bottom_up:
                verdict = "IDENTICAL from offset %d (bottom-up)" % idx
        elif raw[idx:idx + len(top_down)] == top_down:
            verdict = "IDENTICAL from offset %d (top-down)" % idx
        if "NO MATCH" == verdict:
            verdict = ("contained? no; payload is %d bytes vs %d expected"
                       % (len(raw), len(top_down)))

    print("  pixel identity         : %s" % verdict)
    print("  sha256 raw payload     : %s" % hashlib.sha256(raw).hexdigest())
    print("  sha256 exported pixels : %s" % hashlib.sha256(top_down).hexdigest())
    print("  sha256 exported (flip) : %s" % hashlib.sha256(bottom_up).hexdigest())
    print()
