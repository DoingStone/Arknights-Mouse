# -*- coding: utf-8 -*-
"""Manually parse a UnityFS bundle: header, compressed-blocks-info, block list,
and the internal directory (file names), WITHOUT UnityPy's high-level loader.

Why: ui\\[uc]pc.ab fails inside UnityPy at BundleFile.py:523 while
decompressing a *data block* (traceback frame line 175), i.e. its block-info
reads fine but some block's flag word is not a plain LZ4/LZ4HC code.
This prints the raw truth instead of guessing.
"""
import io
import lzma
import os
import struct
import sys
import zlib

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

try:
    import lz4.block
except Exception:
    lz4 = None

MASK = 0x3F
COMP = {0: "none", 1: "LZMA", 2: "LZ4", 3: "LZ4HC", 4: "LZHAM", 5: "?"}


def read_cstr(b, o):
    e = b.index(b"\x00", o)
    return b[o:e].decode("utf-8", "replace"), e + 1


def decomp(flag, data, usize):
    ct = flag & MASK
    if ct == 0:
        return data
    if ct in (2, 3):
        if lz4 is None:
            raise RuntimeError("lz4 module missing")
        try:
            return lz4.block.decompress(data, uncompressed_size=usize)
        except Exception as e:
            return ("__LZ4_FAIL__: %s" % e).encode()
    if ct == 1:
        try:
            d = lzma.LZMADecompressor()
            return d.decompress(data)
        except Exception as e:
            return ("__LZMA_FAIL__: %s" % e).encode()
    if ct == 4:
        return b"__LZHAM_NOT_SHIPPED__"
    return b"__UNKNOWN_COMP__"


def parse(path, verbose=True):
    raw = open(path, "rb").read()
    if raw[:8] != b"UnityFS\x00":
        print("not a UnityFS bundle")
        return None
    o = 8
    ver = struct.unpack_from(">I", raw, o)[0]
    o += 4
    unity_ver, o = read_cstr(raw, o)
    unity_rev, o = read_cstr(raw, o)
    total, o = struct.unpack_from(">q", raw, o)[0], o + 8
    cbis, o = struct.unpack_from(">I", raw, o)[0], o + 4
    ubis, o = struct.unpack_from(">I", raw, o)[0], o + 4
    flags, o = struct.unpack_from(">I", raw, o)[0], o + 4
    if verbose:
        print("file           : %s" % path)
        print("bytes          : %d" % len(raw))
        print("ver            : %d" % ver)
        print("unityVer/Rev   : %s / %s" % (unity_ver, unity_rev))
        print("total          : %d (file=%d, %s)"
              % (total, len(raw), "match" if total == len(raw) else "MISMATCH"))
        print("cbis/ubis      : %d / %d" % (cbis, ubis))
        print("flags          : 0x%08X  compType=%d(%s) blockInfoAtEnd=%s pad=%s"
              % (flags, flags & MASK, COMP.get(flags & MASK, "?"),
                 bool(flags & 0x40), bool(flags & 0x80)))

    # ---- blocks info ----
    bi_off = o
    bi_raw = raw[bi_off:bi_off + cbis]
    bi = decomp(flags, bi_raw, ubis)
    ok = not bi.startswith(b"__")
    if verbose:
        print("\nblocksInfo@%d  %d -> %d bytes  %s"
              % (bi_off, cbis, len(bi), "OK" if ok else bi[:60].decode("latin1")))
    if not ok:
        return None
    p = 0
    hash16 = bi[p:p + 16]
    p += 16
    nblk, p = struct.unpack_from(">I", bi, p)[0], p + 4
    blocks = []
    for _ in range(nblk):
        usz, csz, bfl = struct.unpack_from(">IIH", bi, p)
        p += 10
        blocks.append((usz, csz, bfl))
    if verbose:
        print("blockInfoHash  : %s" % hash16.hex())
        print("blocks         : %d" % nblk)
        for i, (usz, csz, bfl) in enumerate(blocks):
            print("   blk %2d  usize=%-10d csize=%-10d flags=0x%04X  comp=%d(%s)"
                  " enc=0x100:%s"
                  % (i, usz, csz, bfl, bfl & MASK, COMP.get(bfl & MASK, "?"),
                     bool(bfl & 0x100)))
    nnode, p = struct.unpack_from(">I", bi, p)[0], p + 4
    nodes = []
    for _ in range(nnode):
        off, sz = struct.unpack_from(">qq", bi, p)
        p += 16
        nfl, p = struct.unpack_from(">I", bi, p)[0], p + 4
        nm, p = read_cstr(bi, p)
        nodes.append((off, sz, nfl, nm))
    if verbose:
        print("nodes          : %d" % nnode)
        shown = nodes if nnode <= 60 else nodes[:60]
        for off, sz, nfl, nm in shown:
            print("   %-60s  size=%-10d off=%-10d flags=0x%08X" % (nm, sz, off, nfl))
        if nnode > 60:
            print("   ... (%d more)" % (nnode - 60))
    return dict(blocks=blocks, nodes=nodes, flags=flags, raw=raw,
                bi_off=bi_off, bi_len=cbis, bi=bi, hdr_end=o)


if __name__ == "__main__":
    targets = sys.argv[1:]
    if not targets:
        g = r"G:\Hypergryph Launcher\games\Arknights"
        targets = [os.path.join(g, "Arknights_Data", "StreamingAssets", "AB",
                                "Windows", "ui", "[uc]pc.ab"),
                   os.path.join(g, "Arknights_Data", "StreamingAssets", "AB",
                                "Windows", "ui", "[uc]home.ab")]
    for t in targets:
        print("=" * 78)
        try:
            parse(t)
        except Exception as e:
            import traceback
            traceback.print_exc()
        print()
