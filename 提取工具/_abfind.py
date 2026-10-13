# -*- coding: utf-8 -*-
"""Locate the blocks info for real, by brute force + UnityPy cross-check.

Earlier attempt aligned forward from (len - cbi_size) and ran past EOF, so the
slice was truncated. Here we scan every offset in the tail for an LZ4 block
that decompresses to exactly the declared uncompressed size.
"""
import os, sys, struct

BUNDLE = sys.argv[1] if len(sys.argv) > 1 else \
    r"G:\Hypergryph Launcher\games\Arknights\Arknights_Data\StreamingAssets\AB\Windows\ui\[uc]pc.ab"

data = open(BUNDLE, "rb").read()
print("bundle:", BUNDLE)
print("len:", len(data))

# re-read the header to get the declared sizes
p = data.index(b"\0") + 1
version, = struct.unpack_from(">I", data, p); p += 4
zv = data.index(b"\0", p); p = zv + 1
zr = data.index(b"\0", p); p = zr + 1
size, = struct.unpack_from(">q", data, p); p += 8
cbi, = struct.unpack_from(">I", data, p); p += 4
ubi, = struct.unpack_from(">I", data, p); p += 4
flags, = struct.unpack_from(">I", data, p); p += 4
print("version=%d cbi=%d ubi=%d flags=0x%X" % (version, cbi, ubi, flags))
print("naive blocksInfoAtEnd offset = len - cbi =", len(data) - cbi)

import lz4.block

found = []
lo = max(0, len(data) - cbi - 200)
for off in range(lo, len(data)):
    chunk = data[off:off + cbi]
    if len(chunk) < cbi:
        break
    try:
        r = lz4.block.decompress(chunk, uncompressed_size=ubi)
        if len(r) == ubi:
            found.append((off, r))
            print("  !! LZ4 OK at offset %d (delta from naive = %+d)" % (off, off - (len(data) - cbi)))
    except Exception:
        pass

print("lz4 candidates:", len(found))
if found:
    off, bi = found[0]
    q = 16 if flags & 0x80 else 0
    n, = struct.unpack_from(">I", bi, q); q += 4
    print("blocks: %d" % n)
    for i in range(n):
        u, c, bf = struct.unpack_from(">IIH", bi, q); q += 10
        print("  blk%-2d usize=%-8d csize=%-8d flags=%d 0x%04X" % (i, u, c, bf & 0x3F, bf))
    nn, = struct.unpack_from(">I", bi, q); q += 4
    print("NODES: %d" % nn)
    for i in range(nn):
        o, s, f = struct.unpack_from(">qqI", bi, q); q += 20
        e = bi.index(b"\0", q)
        path = bi[q:e].decode("utf-8", "replace"); q = e + 1
        print("  n%-3d off=%-9d size=%-9d flags=%-4d %s" % (i, o, s, f, path))
    print("consumed %d / %d" % (q, len(bi)))
    open(r"G:\ArknightsCursorExtract\_blk\blocksinfo.bin", "wb").write(bi)

print()
print("=" * 78)
print("UnityPy cross-check")
try:
    import UnityPy
    from UnityPy.streams import EndianBinaryReader
    from UnityPy.files import BundleFile
    r = EndianBinaryReader(open(BUNDLE, "rb").read())
    bf = BundleFile(r)
    print("unity_version:", getattr(bf, "unity_version", None))
    print("flags:", hex(getattr(bf, "flags", 0)))
    files = getattr(bf, "files", None)
    if files:
        print("bundle contains %d file(s):" % len(files))
        for f in files:
            nm = getattr(f, "name", None) or getattr(f, "path", "?")
            print("   ", nm)
    else:
        print("no .files attr; attrs:", [a for a in dir(bf) if not a.startswith("_")])
except Exception as e:
    import traceback; traceback.print_exc()
