# -*- coding: utf-8 -*-
"""Dump a Windows .cur / .ico to PNG so it can be inspected visually.

Format facts established from C:\\Windows\\Cursors\\*.cur:
  * ICONDIR (6 bytes) + 16-byte ICONDIRENTRY per image
  * pixel data starts at entryOffset + 40 (no hotspot field before the pixels)
  * the per-image hotspot lives in the ICONDIRENTRY wPlanes / wBitCount WORDs
"""
import os
import struct
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))


def parse(path):
    b = open(path, "rb").read()
    res, typ, n = struct.unpack_from("<HHH", b, 0)
    out = []
    for i in range(n):
        w, h, cc, rsv, hx, hy, sz, off = struct.unpack_from("<BBBBHHII", b, 6 + 16 * i)
        bi = struct.unpack_from("<IiiHHII", b, off)
        W, H = bi[1], bi[2] // 2
        px = b[off + 40: off + 40 + W * H * 4]
        im = Image.new("RGBA", (W, H))
        p = im.load()
        for y in range(H):
            for x in range(W):
                o = ((H - 1 - y) * W + x) * 4
                p[x, y] = (px[o + 2], px[o + 1], px[o], px[o + 3])
        out.append({"size": (W, H), "hotspot": (hx, hy), "img": im})
    return typ, out


def main():
    args = sys.argv[1:]
    outdir = os.path.join(HERE, "_curdump")
    if "-o" in args:
        i = args.index("-o")
        outdir = args[i + 1]
        args = args[:i] + args[i + 2:]
    os.makedirs(outdir, exist_ok=True)
    for path in args:
        if not os.path.exists(path):
            print("missing: %s" % path)
            continue
        typ, imgs = parse(path)
        print("=" * 88)
        print("%s  (type=%d, %d images)" % (os.path.basename(path), typ, len(imgs)))
        for e in imgs:
            print("   %dx%d  hotspot=%s" % (e["size"][0], e["size"][1], e["hotspot"]))
        # composite each image over a neutral mid-grey so alpha shows as brightness
        big = max(imgs, key=lambda e: e["size"][0] * e["size"][1])
        im = big["img"]
        flat = Image.new("RGBA", im.size, (60, 60, 70, 255))
        flat.alpha_composite(im)
        stem = os.path.splitext(os.path.basename(path))[0]
        o1 = os.path.join(outdir, stem + "_%d_flat.png" % im.size[0])
        o2 = os.path.join(outdir, stem + "_%d_alpha.png" % im.size[0])
        flat.convert("RGB").save(o1)
        im.save(o2)
        print("   biggest image %dx%d -> %s" % (im.size[0], im.size[1], o1))
        # also list distinct colours of the opaque region so it can be matched
        p = im.load()
        cols = {}
        for y in range(im.size[1]):
            for x in range(im.size[0]):
                r, g, b, a = p[x, y]
                if a > 200:
                    cols[(r // 32 * 32, g // 32 * 32, b // 32 * 32)] = \
                        cols.get((r // 32 * 32, g // 32 * 32, b // 32 * 32), 0) + 1
        top = sorted(cols.items(), key=lambda kv: -kv[1])[:6]
        print("   opaque colour clusters: %s" % top)


main()
