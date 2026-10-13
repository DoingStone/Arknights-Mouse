# -*- coding: utf-8 -*-
"""Show raw bytes around the ANI LIST/type/icon boundary to pin the payload layout."""
import struct

SRC = (r"C:\Users\22442\AppData\Local\PRTS\Replica-v8-Windows"
       r"\cursors-34497b84e5b0d7cf\PRTS-Replica-v8-96x-work.ani")
raw = open(SRC, "rb").read()


def hx(a, b, tag):
    print("%-22s [%d:%d]" % (tag, a, b))
    for o in range(a, b, 16):
        seg = raw[o:o + 16]
        print("   %6d  %-47s %s" % (o, " ".join("%02x" % c for c in seg),
                                    "".join(chr(c) if 32 <= c < 127 else "." for c in seg)))


hx(348, 400, "LIST hdr + type + icon#0")
print()
# icon#0 chunk id sits at 364, its data at 372
d = raw[372:372 + 38078]
print("icon#0 data[0:48] =", d[:48].hex())
print("  as <Iii   ->", struct.unpack_from("<Iii", d, 0))
print("  as <IHHII ->", struct.unpack_from("<IHHII", d, 0))
print()
for shift in range(0, 12):
    hs, bw, bh = struct.unpack_from("<Iii", d, shift)
    if hs == 40 and bw == 96 and abs(bh) == 192:
        print("  ** BITMAPINFOHEADER found at data offset %d" % shift)
print()
hx(372, 420, "icon#0 data head")
