# -*- coding: utf-8 -*-
"""Why does [uc]pc.ab block 0 hang while block 5 decodes instantly?

Sweep dict_size_log2 for the big blocks with a short hard timeout each, so the
decode cost profile is mapped instead of assumed.
"""
import os, struct, subprocess, sys, time

BUNDLE = (r"G:\Hypergryph Launcher\games\Arknights\Arknights_Data"
          r"\StreamingAssets\AB\Windows\ui\[uc]pc.ab")
WORK = r"G:\ArknightsCursorExtract\_blk\_dslsweep"
PY310 = r"G:\ArknightsCursorExtract\_lzham\py310\python.exe"
os.makedirs(WORK, exist_ok=True)
import lz4.block

raw = open(BUNDLE, "rb").read()
p = 12


def cstr(buf, pp):
    e = buf.index(b"\x00", pp)
    return buf[pp:e].decode(), e + 1


_, p = cstr(raw, p)
_, p = cstr(raw, p)
p += 8
cbi, ubi, flags = struct.unpack_from(">III", raw, p)
p += 12
qi = (p + 15) & ~15
bi = lz4.block.decompress(raw[qi:qi + cbi], uncompressed_size=ubi)

q = 16
nb = struct.unpack_from(">i", bi, q)[0]
q += 4
blocks = []
for _ in range(nb):
    blocks.append(struct.unpack_from(">IIH", bi, q))
    q += 10
nn = struct.unpack_from(">i", bi, q)[0]
q += 4
nodes = []
for _ in range(nn):
    off, sz, nfl = struct.unpack_from(">qqI", bi, q)
    q += 20
    e = bi.index(b"\x00", q)                     # NUL-terminated, NO alignment
    nodes.append((off, sz, nfl, bi[q:e].decode()))
    q = e + 1
print("blocks =", blocks)
print("nodes  =", nodes)
print("consumed %d of %d blocks-info bytes" % (q, len(bi)))

dstart = (qi + cbi + 15) & ~15
off = dstart
for i, (us, cs, fl) in enumerate(blocks):
    open(os.path.join(WORK, "b%d.bin" % i), "wb").write(raw[off:off + cs])
    off += cs

HELPER = os.path.join(WORK, "_lz2.py")
open(HELPER, "w", encoding="utf-8").write('''import sys, time
import lzham
src, want, dsl, outp = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
flt = {"compute_adler32_during_decomp": 0}
if dsl:
    flt["dict_size_log2"] = dsl
d = open(src, "rb").read()
t = time.time()
try:
    out = lzham.decompress(d, want, flt)
    print("    dsl=%-3d OK got=%-8d t=%.2fs" % (dsl, len(out), time.time() - t))
    open(outp, "wb").write(out)
except Exception as ex:
    print("    dsl=%-3d FAIL t=%.2fs %s" % (dsl, time.time() - t, str(ex)[:90]))
''')

BLK = int(sys.argv[1]) if len(sys.argv) > 1 else 0
us, cs, fl = blocks[BLK]
srcp = os.path.join(WORK, "b%d.bin" % BLK)
print("\nsweeping dict_size_log2 for blk%d (usize=%d csize=%d)" % (BLK, us, cs))
for dsl in (0, 20, 21, 22, 23, 24, 25, 26, 27):
    outp = os.path.join(WORK, "b%d_dsl%d.out" % (BLK, dsl))
    if os.path.exists(outp) and os.path.getsize(outp) == us:
        print("    dsl=%-3d cached" % dsl)
        continue
    try:
        r = subprocess.run([PY310, HELPER, srcp, str(us), str(dsl), outp],
                           capture_output=True, text=True, timeout=45)
        print((r.stdout or r.stderr).rstrip()[:300])
    except subprocess.TimeoutExpired:
        print("    dsl=%-3d TIMEOUT after 45s" % dsl)
    sys.stdout.flush()
