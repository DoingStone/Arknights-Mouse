# -*- coding: utf-8 -*-
"""Correct flag decode + test blocks-info at the RIGHT offset.

flags = 0x243:
  0x003 & 0x3F  = 3        -> LZ4HC compression
  0x040        = set      -> BlocksAndDirectoryInfoCombined
  0x080        = CLEAR    -> blocks info right AFTER HEADER (not at end!)
  0x200        = set      -> UsesAssetBundleEncryption (UnityCN)

Earlier attempts looked at `len - cbi` because 0x40 was misread as "at end".
Here we scan the bytes right after the header.
"""
import os, sys, struct

def parse_header(data):
    p = data.index(b"\0") + 1
    version, = struct.unpack_from(">I", data, p); p += 4
    e = data.index(b"\0", p); unity_ver = data[p:e].decode(); p = e + 1
    e = data.index(b"\0", p); unity_rev = data[p:e].decode(); p = e + 1
    size, = struct.unpack_from(">q", data, p); p += 8
    cbi, = struct.unpack_from(">I", data, p); p += 4
    ubi, = struct.unpack_from(">I", data, p); p += 4
    flags, = struct.unpack_from(">I", data, p); p += 4
    return dict(sig="UnityFS", version=version, unity_ver=unity_ver, unity_rev=unity_rev,
                size=size, cbi=cbi, ubi=ubi, flags=flags, header_end=p)

import lz4.block

def try_at(data, off, cbi, ubi):
    chunk = data[off:off + cbi]
    if len(chunk) < cbi:
        return None
    for label, fn in (
        ("lz4-exact", lambda c: lz4.block.decompress(c, uncompressed_size=ubi)),
        ("lz4-skip4", lambda c: lz4.block.decompress(c[4:], uncompressed_size=ubi)),
    ):
        try:
            r = fn(chunk)
            if len(r) == ubi:
                return label, r
        except Exception:
            pass
    return None

BUNDLES = sys.argv[1:] or [
    r"G:\Hypergryph Launcher\games\Arknights\Arknights_Data\StreamingAssets\AB\Windows\ui\[uc]pc.ab",
    r"G:\Hypergryph Launcher\games\Arknights\Arknights_Data\StreamingAssets\AB\Windows\ui\roguelike.ab",
    r"G:\Hypergryph Launcher\games\Arknights\Arknights_Data\StreamingAssets\AB\Windows\ui\zonemap_misc.ab",
]

for b in BUNDLES:
    print("=" * 78)
    print(b)
    data = open(b, "rb").read()
    h = parse_header(data)
    print("  version=%d unity=%s %s  size=%d" % (h["version"], h["unity_ver"], h["unity_rev"], h["size"]))
    print("  cbi=%d ubi=%d flags=0x%X" % (h["cbi"], h["ubi"], h["flags"]))
    f = h["flags"]
    print("  compression=%d  combined=%-5s atEnd=%-5s encryption=0x%X"
          % (f & 0x3F, bool(f & 0x40), bool(f & 0x80), f & 0x300))

    base = (h["header_end"] + 15) & ~15
    print("  header_end=%d  aligned=%d" % (h["header_end"], base))

    found = False
    # scan a generous window right after the header
    for off in range(h["header_end"], min(len(data) - h["cbi"], h["header_end"] + 128)):
        got = try_at(data, off, h["cbi"], h["ubi"])
        if got:
            label, bi = got
            print("  *** blocks info decoded at offset %d via %s (delta from aligned = %+d)"
                  % (off, label, off - base))
            q = 0
            if f & 0x80 and len(bi) >= 16:
                q += 16  # uncompressed data hash
            elif len(bi) >= 16:
                q += 16
            n, = struct.unpack_from(">I", bi, q); q += 4
            print("      BLOCKS: %d" % n)
            for i in range(n):
                u, c, bfl = struct.unpack_from(">IIH", bi, q); q += 10
                print("        blk%-2d usize=%-9d csize=%-9d flag=%d (0x%X)" % (i, u, c, bfl & 0x3F, bfl))
            nn, = struct.unpack_from(">I", bi, q); q += 4
            print("      NODES: %d" % nn)
            for i in range(nn):
                o, s, fl2 = struct.unpack_from(">qqI", bi, q); q += 20
                e = bi.index(b"\0", q)
                path = bi[q:e].decode("utf-8", "replace"); q = e + 1
                print("        n%-3d off=%-9d size=%-9d flags=%-3d %s" % (i, o, s, fl2, path))
            print("      consumed %d / %d" % (q, len(bi)))
            os.makedirs(r"G:\ArknightsCursorExtract\_blk", exist_ok=True)
            open(r"G:\ArknightsCursorExtract\_blk\bi_%s.bin" % os.path.basename(b).replace("[", "").replace("]", ""), "wb").write(bi)
            found = True
            break
    if not found:
        print("  !! no LZ4 blocks info found in the window -> likely UnityCN-encrypted")
        print("     head@aligned: %s" % data[base:base + 48].hex())
