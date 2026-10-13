# -*- coding: utf-8 -*-
"""Calibrate the LZHAM decoder, then decode ui\\[uc]pc.ab fully.

Why it mattered: block 5 (36,876 B out) decoded fine, but block 0 (131,072 B out)
timed out at 45 s.  If LZHAM is merely slow, a long timeout on all six blocks
yields the CAB node AND the uncompressed .resS stream -- the latter holds the
raw Texture2D pixel data, i.e. the cursor art itself.
"""
import os, struct, subprocess, sys, time

BUNDLE = (r"G:\Hypergryph Launcher\games\Arknights\Arknights_Data"
          r"\StreamingAssets\AB\Windows\ui\[uc]pc.ab")
WORK = r"G:\ArknightsCursorExtract\_blk\_cab2"
PY310 = r"G:\ArknightsCursorExtract\_lzham\py310\python.exe"
TIMEOUT = int(sys.argv[1]) if len(sys.argv) > 1 else 5400
os.makedirs(WORK, exist_ok=True)
import lz4.block

raw = open(BUNDLE, "rb").read()
assert raw[:7] == b"UnityFS"


def cstr(buf, pp):
    e = buf.index(b"\x00", pp)
    return buf[pp:e].decode("utf-8", "replace"), e + 1


p = 12
player, p = cstr(raw, p)
engine, p = cstr(raw, p)
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
    e = bi.index(b"\x00", q)                # NUL-terminated, NO alignment padding
    nodes.append((off, sz, nfl, bi[q:e].decode("utf-8", "replace")))
    q = e + 1
dstart = (qi + cbi + 15) & ~15
print("engine=%s cbi=%d ubi=%d flags=0x%x dstart=%d" % (engine, cbi, ubi, flags, dstart))
print("blocks =", blocks)
print("nodes  =", nodes)
print("blocks-info consumed %d/%d" % (q, len(bi)))

off = dstart
for i, (us, cs, fl) in enumerate(blocks):
    open(os.path.join(WORK, "b%d.bin" % i), "wb").write(raw[off:off + cs])
    off += cs
print("block payloads written to", WORK)

HELPER = os.path.join(WORK, "_lz3.py")
open(HELPER, "w", encoding="utf-8").write('''import sys, time
import lzham
src, want, outp = sys.argv[1], int(sys.argv[2]), sys.argv[3]
d = open(src, "rb").read()
t = time.time()
try:
    out = lzham.decompress(d, want, {"compute_adler32_during_decomp": 0})
    dt = time.time() - t
    print("  OK got=%-8d t=%.1fs  (%.2f MB/s out)" % (len(out), dt, len(out)/dt/1e6 if dt else 0))
    open(outp, "wb").write(out)
except Exception as ex:
    print("  FAIL t=%.1fs %s: %s" % (time.time()-t, type(ex).__name__, str(ex)[:200]))
''')

# ---- calibration: re-decode block 5 (known good) with timing ----
if len(sys.argv) > 2 and sys.argv[2] == "cal":
    us, cs, fl = blocks[5]
    print("\n[calibration] block5 usize=%d csize=%d" % (us, cs))
    r = subprocess.run([PY310, HELPER, os.path.join(WORK, "b5.bin"), str(us),
                        os.path.join(WORK, "b5.out")], capture_output=True, text=True,
                       timeout=1200)
    print(r.stdout or r.stderr)

blobs = []
for i, (us, cs, fl) in enumerate(blocks):
    outp = os.path.join(WORK, "b%d.out" % i)
    if os.path.exists(outp) and os.path.getsize(outp) == us:
        print("blk%d cached (%d B)" % (i, us))
        blobs.append(open(outp, "rb").read())
        continue
    print("blk%d usize=%-8d csize=%-8d  decoding (timeout %ds) ..." % (i, us, cs, TIMEOUT))
    sys.stdout.flush()
    t0 = time.time()
    try:
        r = subprocess.run([PY310, HELPER, os.path.join(WORK, "b%d.bin" % i), str(us), outp],
                           capture_output=True, text=True, timeout=TIMEOUT)
        print((r.stdout or r.stderr).rstrip()[:300])
    except subprocess.TimeoutExpired:
        print("  TIMEOUT after %ds -- abandoning" % TIMEOUT)
        blobs = None
        break
    print("  wall %.1fs" % (time.time() - t0))
    sys.stdout.flush()
    if not (os.path.exists(outp) and os.path.getsize(outp) == us):
        print("  !! blk%d unavailable" % i)
        blobs = None
        break
    blobs.append(open(outp, "rb").read())

if not blobs:
    print("\nDECODE INCOMPLETE")
    sys.exit(2)

blob = b"".join(blobs)
print("\ntotal decompressed = %d  (nodes sum = %d)" % (len(blob), sum(n[1] for n in nodes)))
for off, sz, nfl, nm in nodes:
    seg = blob[off:off + sz]
    fp = os.path.join(WORK, nm.replace("/", "_"))
    open(fp, "wb").write(seg)
    print("  wrote %-52s %8d B" % (fp, len(seg)))

cab = blob[nodes[0][0]:nodes[0][0] + nodes[0][1]]
print("\n=== CAB serialized-file header ===")
meta, fsize, ver, doff = struct.unpack_from(">iiii", cab, 0)
print("  metadataSize=%d fileSize=%d version=%d dataOffset=%d" % (meta, fsize, ver, doff))
up, q2 = cstr(cab, doff)
plat = struct.unpack_from(">i", cab, q2)[0]
q2 += 4
ett = cab[q2]
q2 += 1
print("  unityVersion=%r targetPlatform=%d enableTypeTree=%d" % (up, plat, ett))
nclass = struct.unpack_from(">i", cab, q2)[0]
q2 += 4
print("  classCount=%d" % nclass)
names = {}
for _ in range(nclass):
    cid = struct.unpack_from(">i", cab, q2)[0]
    q2 += 4
    if ver >= 16:
        q2 += 1
    if ver >= 17:
        q2 += 2
    if ver >= 13:
        q2 += 2
    if ver >= 16:
        q2 += 1
    if ver >= 15:
        q2 = (q2 + 3) & ~3
    cnt = struct.unpack_from(">i", cab, q2)[0]
    q2 += 4
    q2 += cnt
    names[cid] = names.get(cid, 0) + 1
print("  class ids present:", sorted(names.items()))
nobj = struct.unpack_from(">i", cab, q2)[0]
q2 += 4
print("  objectCount=%d" % nobj)
objs = []
for _ in range(nobj):
    q2 = (q2 + 3) & ~3
    pid = struct.unpack_from(">q", cab, q2)[0]
    q2 += 8
    bs = struct.unpack_from(">I", cab, q2)[0]
    q2 += 4
    q2 = (q2 + 3) & ~3
    bsz = struct.unpack_from(">I", cab, q2)[0]
    q2 += 4
    tid = struct.unpack_from(">i", cab, q2)[0]
    q2 += 4
    objs.append((pid, bs, bsz, tid))
print("  first 40 objects (pathID, dataOffset, size, classID):")
for o in objs[:40]:
    print("     pid=%-10d off=%-8d size=%-8d class=%d" % o)

import re
print("\n=== printable strings in CAB (cursor/texture related first) ===")
strs = re.findall(rb"[\x20-\x7e]{4,90}", cab)
key = [s.decode() for s in strs
       if any(k in s.lower() for k in (b"cursor", b"texture", b"sprite", b"png", b"asset",
                                       b"pixelmap", b"tier", b"setting", b"ui/", b"pc"))]
for s in key[:150]:
    print("   ", s)
print("\n   total strings: %d ; keyword hits: %d" % (len(strs), len(key)))
print("   first 80 strings overall:")
for s in strs[:80]:
    print("     ", s.decode()[:88])
