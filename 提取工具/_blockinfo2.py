# -*- coding: utf-8 -*-
"""Correct UnityFS block parse (with the 16-byte alignment UnityPy applies).

UnityPy's read_fs order, version >= 2021.3.2 (this client is 2021.3.39f1, so
ArchiveFlags, not ArchiveFlagsOld):
    read_long  size
    read_u_int compressedSize   (cbis)
    read_u_int uncompressedSize (ubis)
    read_u_int dataflags
    [UsesAssetBundleEncryption 0x1400 -> decryptor]
    if version >= 7: reader.align_stream(16)      <-- THE STEP I MISSED
    start = reader.Position
    if BlocksInfoAtTheEnd (0x80): read from (len - cbis)
    else: read cbis bytes here
    decompress with dataflags
...then, if BlockInfoNeedPaddingAtStart (0x200): reader.align_stream(16)
...then the data blocks are read and each decompressed with ITS OWN flags.
"""
import os
import struct
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import lz4.block

MASK = 0x3F
COMP = {0: "none", 1: "LZMA", 2: "LZ4", 3: "LZ4HC", 4: "LZHAM(custom?)"}


def decomp(flag, data, usize, tag=""):
    ct = flag & MASK
    if ct == 0:
        return data, "stored"
    if ct in (2, 3):
        try:
            return lz4.block.decompress(data, uncompressed_size=usize), "lz4"
        except Exception as e:
            return None, "LZ4FAIL:%s" % str(e)[:50]
    return None, "UNSUPPORTED comp=%d" % ct


def cstr(b, o):
    e = b.index(b"\x00", o)
    return b[o:e].decode("utf-8", "replace"), e + 1


def align16(n):
    return (n + 15) & ~15


def parse(path):
    raw = open(path, "rb").read()
    print("=" * 78)
    print("file    : %s" % path)
    print("bytes   : %d" % len(raw))
    if raw[:8] != b"UnityFS\x00":
        print("not UnityFS")
        return None

    o = 12                                  # skip signature + version (BE u32)
    uv, o = cstr(raw, o)
    ur, o = cstr(raw, o)
    total = struct.unpack_from(">q", raw, o)[0]; o += 8
    cbis = struct.unpack_from(">I", raw, o)[0]; o += 4
    ubis = struct.unpack_from(">I", raw, o)[0]; o += 4
    flags = struct.unpack_from(">I", raw, o)[0]; o += 4
    print("unity   : %s / %s   total=%d %s" % (uv, ur, total,
          "match" if total == len(raw) else "MISMATCH"))
    print("flags   : 0x%06X  comp=%s combined=%s atEnd=%s padAtStart=%s enc=%s"
          % (flags, COMP.get(flags & MASK),
             bool(flags & 0x40), bool(flags & 0x80), bool(flags & 0x200),
             bool(flags & 0x1400)))

    # ---- the alignment UnityPy performs for version >= 7 ----
    o_unaligned = o
    o = align16(o)
    print("blocks-info offset: unaligned=%d -> aligned=%d (+%d)"
          % (o_unaligned, o, o - o_unaligned))

    bi_c = raw[o:o + cbis]
    bi, how = decomp(flags, bi_c, ubis)
    print("blocks-info: %d -> %d bytes (%s)" % (cbis, len(bi) if bi else 0, how))
    if bi is None:
        print("  head: %s" % bi_c[:24].hex())
        return None

    p = 0
    print("  hash  : %s" % bi[p:p + 16].hex()); p += 16
    nblk = struct.unpack_from(">I", bi, p)[0]; p += 4
    blocks = []
    for i in range(nblk):
        usz, csz, bfl = struct.unpack_from(">IIH", bi, p); p += 10
        blocks.append((usz, csz, bfl))
    print("  blocks: %d" % nblk)
    for i, (usz, csz, bfl) in enumerate(blocks[:20]):
        print("    blk %2d usize=%-9d csize=%-9d flags=0x%04X comp=%d(%s) enc=%s"
              % (i, usz, csz, bfl, bfl & MASK, COMP.get(bfl & MASK, "?"),
                 bool(bfl & 0x100)))
    if nblk > 20:
        print("    ... %d more" % (nblk - 20))
    nnode = struct.unpack_from(">I", bi, p)[0]; p += 4
    print("  nodes : %d" % nnode)
    nodes = []
    for _ in range(nnode):
        off, sz = struct.unpack_from(">qq", bi, p); p += 16
        nfl = struct.unpack_from(">I", bi, p)[0]; p += 4
        nm, p = cstr(bi, p)
        nodes.append((nm, sz, off, nfl))
    for nm, sz, off, nfl in nodes:
        print("    %-56s size=%-9d off=%-9d flags=0x%08X" % (nm, sz, off, nfl))

    # ---- data area ----
    dstart = o + cbis
    if flags & 0x200:               # BlockInfoNeedPaddingAtStart
        a = align16(dstart)
        print("  data area: %d -> aligned %d (+%d)" % (dstart, a, a - dstart))
        dstart = a
    cursor = dstart
    print("\n  --- trying each block ---")
    for i, (usz, csz, bfl) in enumerate(blocks):
        blob = raw[cursor:cursor + csz]
        data, how = decomp(bfl, blob, usz)
        print("    blk %2d @%-9d %-8d -> %-8s  %s"
              % (i, cursor, csz, (len(data) if data else 0), how))
        if data is None:
            print("        raw head: %s" % blob[:20].hex())
            break
        cursor += csz
    return dict(raw=raw, blocks=blocks, nodes=nodes, flags=flags,
                bi=bi, bi_off=o, data_off=dstart)


if __name__ == "__main__":
    G = r"G:\Hypergryph Launcher\games\Arknights"
    AB = os.path.join(G, "Arknights_Data", "StreamingAssets", "AB", "Windows")
    targets = sys.argv[1:] or [
        os.path.join(AB, "ui", "[uc]pc.ab"),
        os.path.join(AB, "ui", "zonemap_misc.ab"),
    ]
    for t in targets:
        try:
            parse(t)
        except Exception:
            import traceback
            traceback.print_exc()
        print()
