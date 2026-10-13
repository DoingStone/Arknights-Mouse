# -*- coding: utf-8 -*-
"""Decode the two LZHAM blocks that make up ui\\[uc]pc.ab's CAB node, then list
its contents.  Generous timeout: the engine's LZHAM streams are slow to decode
with pylzham (block5 took seconds, 131072-byte blocks take much longer).
"""
import os, struct, subprocess, sys, time

BUNDLE = (r"G:\Hypergryph Launcher\games\Arknights\Arknights_Data"
          r"\StreamingAssets\AB\Windows\ui\[uc]pc.ab")
WORK = r"G:\ArknightsCursorExtract\_blk\_cab"
PY310 = r"G:\ArknightsCursorExtract\_lzham\py310\python.exe"
TIMEOUT = int(sys.argv[1]) if len(sys.argv) > 1 else 1800
os.makedirs(WORK, exist_ok=True)

import lz4.block

raw = open(BUNDLE, "rb").read()
assert raw[:7] == b"UnityFS"


def cstr(buf, p):
    e = buf.index(b"\x00", p)
    return buf[p:e].decode("utf-8", "replace"), e + 1


p = 12
player, p = cstr(raw, p)
engine, p = cstr(raw, p)
p += 8                                    # int64 size
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
    nl = struct.unpack_from(">i", bi, q)[0]
    q += 4
    nm = bi[q:q + nl].rstrip(b"\x00").decode("utf-8", "replace")
    q = (q + nl + 3) & ~3          # read_aligned_string: align AFTER the bytes
    nodes.append((off, sz, nfl, nm))
dstart = (qi + cbi + 15) & ~15
print("engine=%s blocks=%s" % (engine, blocks))
print("nodes =%s" % (nodes,))

HELPER = os.path.join(WORK, "_lz1.py")
open(HELPER, "w", encoding="utf-8").write(
    'import sys, time\nimport lzham\n'
    'd = open(sys.argv[1], "rb").read()\nwant = int(sys.argv[2])\n'
    't = time.time()\n'
    'out = lzham.decompress(d, want, {"compute_adler32_during_decomp": 0})\n'
    'print("  want=%-8d OK got=%-8d t=%.1fs" % (want, len(out), time.time() - t))\n'
    'open(sys.argv[3], "wb").write(out)\n')

off = dstart
need = nodes[0][1]                        # CAB node size = 189068
cum = 0
blobs = []
for i, (us, cs, fl) in enumerate(blocks):
    payload = raw[off:off + cs]
    off += cs
    cum += us
    if cum - us >= need:                  # this block lies entirely past the node
        break
    srcp = os.path.join(WORK, "b%d.bin" % i)
    open(srcp, "wb").write(payload)
    outp = os.path.join(WORK, "b%d.out" % i)
    if os.path.exists(outp) and os.path.getsize(outp) == us:
        print("blk%d cached (%d B)" % (i, us))
    else:
        print("blk%d usize=%d csize=%d cflag=%d  decoding (timeout %ds)..." % (i, us, cs, fl, TIMEOUT))
        sys.stdout.flush()
        t0 = time.time()
        try:
            r = subprocess.run([PY310, HELPER, srcp, str(us), outp],
                               capture_output=True, text=True, timeout=TIMEOUT)
            print((r.stdout or r.stderr).rstrip()[:400])
        except subprocess.TimeoutExpired:
            print("  TIMEOUT after %ds" % TIMEOUT)
            break
        print("  elapsed %.1fs" % (time.time() - t0))
        sys.stdout.flush()
    if not (os.path.exists(outp) and os.path.getsize(outp) == us):
        print("  !! blk%d not available" % i)
        break
    blobs.append(open(outp, "rb").read())

if blobs:
    blob = b"".join(blobs)
    cab = blob[:need]
    cp = os.path.join(WORK, "CAB_dec.bin")
    open(cp, "wb").write(cab)
    print("\nCAB written: %s  (%d B)" % (cp, len(cab)))
    hdr = struct.unpack_from(">IIIII", cab, 0)
    print("serialized header (meta/file/ver/dataoff/endian?) =", hdr)
    meta, fsize, ver, doff = struct.unpack_from(">iiii", cab, 0)
    ver = struct.unpack_from(">i", cab, 8)[0]
    print("  metadata=%-6d fileSize=%-8d version=%-4d dataOffset=%d" % (meta, fsize, ver, doff))
    if meta > 0:
        up = cab[doff:doff + 200]
        print("  unityVersion=%r" % up.split(b"\x00")[0][:40])
    # object table
    tp = doff + meta
    nn2 = struct.unpack_from(">i", cab, tp)[0]
    tp += 4
    names = []
    for _ in range(max(0, min(nn2, 4000))):
        try:
            al = struct.unpack_from(">i", cab, tp)[0]
            tp += 4 + al
            tp = (tp + 3) & ~3
            tidx = struct.unpack_from(">i", cab, tp)[0]
            tp += 4
            pid = struct.unpack_from(">q", cab, tp)[0]
            tp += 8
            names.append((pid, tidx, al))
        except Exception:
            break
    print("  objects: %d  first 40 (pathid,typeidx,nlen):" % nn2)
    for pid, tidx, al in names[:40]:
        print("     pid=%-10d type=%-5d namelen=%d" % (pid, tidx, al))
    # pull printable strings from the metadata region
    import re
    meta_blob = cab[doff:doff + meta]
    strs = re.findall(rb"[\x20-\x7e]{4,80}", meta_blob)
    keep = [s.decode() for s in strs
            if any(k in s.lower() for k in (b"cursor", b"pc", b"texture", b"sprite", b"assets", b"cab-"))]
    print("\n  interesting strings in metadata (%d):" % len(keep))
    for s in keep[:120]:
        print("     ", s)
    print("\n  total printable strings in metadata:", len(strs))
    for s in strs[:60]:
        print("     ", s.decode()[:90])
else:
    print("no blocks decoded")
