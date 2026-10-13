# -*- coding: utf-8 -*-
"""Extract a bundle block payload, then try PARTIAL LZHAM decodes on py310.

Partial decode matters: block 0 is 131072 B of output and a full decode exceeded
300 s.  The first few KB of the CAB node is the serialized-file header + object
table, which is all I need to list what lives inside ui\\[uc]pc.ab.
"""
import os, struct, subprocess, sys, time

BUNDLE = (r"G:\Hypergryph Launcher\games\Arknights\Arknights_Data"
          r"\StreamingAssets\AB\Windows\ui\[uc]pc.ab")
WORK = r"G:\ArknightsCursorExtract\_blk\_part"
PY310 = r"G:\ArknightsCursorExtract\_lzham\py310\python.exe"
os.makedirs(WORK, exist_ok=True)

import lz4.block

raw = open(BUNDLE, "rb").read()
assert raw[:7] == b"UnityFS", raw[:16]


def cstr(buf, p):
    e = buf.index(b"\x00", p)
    return buf[p:e].decode("utf-8", "replace"), e + 1


p = 8
fmt = struct.unpack_from(">i", raw, p)[0]
p += 4
player, p = cstr(raw, p)
engine, p = cstr(raw, p)
size = struct.unpack_from(">q", raw, p)[0]
p += 8
cbi, ubi, flags = struct.unpack_from(">III", raw, p)
p += 12
header_end = p
qi = (p + 15) & ~15
bi = lz4.block.decompress(raw[qi:qi + cbi], uncompressed_size=ubi)
assert len(bi) == ubi
q = 16
nb = struct.unpack_from(">i", bi, q)[0]
q += 4
blocks = []
for _ in range(nb):
    us, cs, fl = struct.unpack_from(">IIH", bi, q)
    blocks.append((us, cs, fl))
    q += 10
nn = struct.unpack_from(">i", bi, q)[0]
q += 4
nodes = []
for _ in range(nn):
    off, sz, nfl = struct.unpack_from(">qqI", bi, q)
    q += 20
    nl = struct.unpack_from(">i", bi, q)[0]
    q += 4
    nm = bi[q:q + nl].rstrip(b"\x00").decode("utf-8", "replace")
    q += nl
    nodes.append((off, sz, nfl, nm))
dstart = (qi + cbi + 15) & ~15

print("fmt=%d player=%s engine=%s size=%d" % (fmt, player, engine, size))
print("cbi=%d ubi=%d flags=0x%x header_end=%d qi=%d dstart=%d" % (cbi, ubi, flags, header_end, qi, dstart))
print("blocks:", blocks)
print("nodes :", nodes)

off = dstart
for i, (us, cs, fl) in enumerate(blocks):
    payload = raw[off:off + cs]
    assert len(payload) == cs, "block %d short" % i
    fp = os.path.join(WORK, "b%d.bin" % i)
    open(fp, "wb").write(payload) if False else open(fp, "wb").write(payload)
    print("  blk%d usize=%-8d csize=%-8d flag=%d -> %s" % (i, us, cs, fl, fp))
    off += cs
print("end of blocks = %d   file = %d   (equal: %s)" % (off, len(raw), off == len(raw)))

HELPER = os.path.join(WORK, "_lzpart.py")
open(HELPER, "w", encoding="utf-8").write('''# -*- coding: utf-8 -*-
import sys, time, os
import lzham
d = open(sys.argv[1], "rb").read()
want = int(sys.argv[2])
outp = sys.argv[3]
t = time.time()
try:
    out = lzham.decompress(d, want, {"compute_adler32_during_decomp": 0})
    dt = time.time() - t
    print("  want=%-8d OK   got=%-8d t=%.2fs" % (want, len(out), dt))
    open(outp, "wb").write(out)
    sys.exit(0)
except Exception as ex:
    dt = time.time() - t
    print("  want=%-8d FAIL t=%.2fs  %s: %s" % (want, dt, type(ex).__name__, str(ex)[:160]))
    # the C layer may still have filled the buffer; probe partial file if any
    sys.exit(1)
''')

BI = int(sys.argv[1]) if len(sys.argv) > 1 else 0
us, cs, fl = blocks[BI]
srcp = os.path.join(WORK, "b%d.bin" % BI)
for want in (4096, 16384, 65536, us):
    outp = os.path.join(WORK, "b%d_%d.out" % (BI, want))
    print("blk%d partial decode want=%d ..." % (BI, want))
    t0 = time.time()
    try:
        r = subprocess.run([PY310, HELPER, srcp, str(want), outp],
                           capture_output=True, text=True, timeout=600)
        print(r.stdout.rstrip() or r.stderr.rstrip()[:300])
        if os.path.exists(outp):
            print("    -> wrote %d bytes in %.1fs" % (os.path.getsize(outp), time.time() - t0))
    except subprocess.TimeoutExpired:
        print("  want=%-8d TIMEOUT after 600s" % want)
        break
print("done")
