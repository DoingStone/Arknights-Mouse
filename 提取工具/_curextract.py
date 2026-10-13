# -*- coding: utf-8 -*-
"""Extract every embedded image from a Windows .cur / .ani file."""
import os, struct, sys

from PIL import Image

OUT = r"G:\ArknightsCursorExtract\_probe_crystal"
os.makedirs(OUT, exist_ok=True)


def read_cur(path):
    raw = open(path, "rb").read()
    if raw[:4] == b"RIFF" and raw[8:12] == b"ACON":
        raise SystemExit("this is an .ani container, not .cur")
    r0, rtype, n = struct.unpack_from("<HHH", raw, 0)
    print("ICONDIR reserved=%d type=%d count=%d size=%d" % (r0, rtype, n, len(raw)))
    out = []
    for i in range(n):
        w, h, ncol, res, hsx, hsy, nbytes, off = struct.unpack_from("<BBBBHHII", raw, 6 + 16 * i)
        w = w or 256
        h = h or 256
        print("  #%d %dx%d hotspot=(%d,%d) bytes=%d off=%d" % (i, w, h, hsx, hsy, nbytes, off))
        out.append((raw[off:off + nbytes], w, h, hsx, hsy, i))
    return out


def decode_dib(data, w, h):
    hs, bw, bh, planes, bpp, comp, isz, xr, yr, used, imp = struct.unpack_from("<IiiHHIIiiII", data, 0)
    print("     BITMAPINFOHEADER size=%d %dx%d planes=%d bpp=%d comp=%d imgSize=%d"
          % (hs, bw, bh, planes, bpp, comp, isz))
    real_h = abs(bh) // 2 if bh == h * 2 else h
    pix = data[hs:hs + w * real_h * 4]
    im = Image.frombytes("RGBA", (w, real_h), pix, "raw", "BGRA")
    return im.transpose(Image.FLIP_TOP_BOTTOM)


path = sys.argv[1] if len(sys.argv) > 1 else (
    r"C:\Users\22442\AppData\Local\PRTS\Replica-v8-Windows"
    r"\cursors-34497b84e5b0d7cf\PRTS-Replica-v8-96x-normal.cur")
for (data, w, h, hsx, hsy, i) in read_cur(path):
    if data[:4] == b"\x89PNG":
        im = Image.open(__import__("io").BytesIO(data)).convert("RGBA")
    else:
        im = decode_dib(data, w, h)
    op = os.path.join(OUT, "img_%02d_%dx%d_hot%d_%d.png" % (i, im.width, im.height, hsx, hsy))
    im.save(op)
    print("   -> %s  alpha_max=%d alpha_min=%d" % (
        op, max(im.getchannel("A").getdata()), min(im.getchannel("A").getdata())))
    # upscale for viewing
    big = im.resize((im.width * 4, im.height * 4), Image.NEAREST)
    bg = Image.new("RGB", big.size, (58, 66, 80))
    bg.paste(big, (0, 0), big)
    bg.save(os.path.join(OUT, "view_%02d.png" % i))
print("dir:", OUT)
