# -*- coding: utf-8 -*-
"""Try every plausible decompressor on a real data block.

Block flag is uniformly 4 in this client. UnityPy maps 4 -> LZHAM (removed by
Unity) and raises. But the raw head of block 0 looks like a valid LZ4 block
token stream, so test the hypothesis that flag 4 here means:
  (a) plain LZ4 (LZ4HC output is a valid LZ4 block stream), or
  (b) LZ4 with a frame header, or
  (c) LZMA/raw-deflate, or
  (d) zstd.
We accept whichever yields exactly the declared uncompressed size.
"""
import os
import struct
import sys
import zlib

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import lz4.block
import lz4.frame

G = r"G:\Hypergryph Launcher\games\Arknights"
AB = os.path.join(G, "Arknights_Data", "StreamingAssets", "AB", "Windows")


def align16(n):
    return (n + 15) & ~15


def cstr(b, o):
    e = b.index(b"\x00", o)
    return b[o:e].decode("utf-8", "replace"), e + 1


def blocks_of(path):
    raw = open(path, "rb").read()
    o = 12
    uv, o = cstr(raw, o)
    ur, o = cstr(raw, o)
    o += 8                                  # total
    cbis = struct.unpack_from(">I", raw, o)[0]; o += 4
    ubis = struct.unpack_from(">I", raw, o)[0]; o += 4
    flags = struct.unpack_from(">I", raw, o)[0]; o += 4
    o = align16(o)
    bi = lz4.block.decompress(raw[o:o + cbis], uncompressed_size=ubis)
    p = 16
    nblk = struct.unpack_from(">I", bi, p)[0]; p += 4
    blks = []
    for _ in range(nblk):
        usz, csz, bfl = struct.unpack_from(">IIH", bi, p); p += 10
        blks.append((usz, csz, bfl))
    nnode = struct.unpack_from(">I", bi, p)[0]; p += 4
    for _ in range(nnode):
        p += 16
        p += 1 if False else 0
        p += 4
        e = bi.index(b"\x00", p)
        p = e + 1
    dstart = o + cbis
    if flags & 0x200:
        dstart = align16(dstart)
    return raw, blks, dstart


def try_all(blob, usize, tag):
    out = []
    # 1. plain LZ4 block
    try:
        d = lz4.block.decompress(blob, uncompressed_size=usize)
        out.append(("lz4.block(exact)", len(d), "EXACT" if len(d) == usize else "len!="))
    except Exception as e:
        out.append(("lz4.block(exact)", 0, str(e)[:45]))
    # 2. LZ4 with lexicographic-free guess: no size hint
    try:
        d = lz4.block.decompress(blob)
        out.append(("lz4.block(auto)", len(d), "EXACT" if len(d) == usize else "len!="))
    except Exception as e:
        out.append(("lz4.block(auto)", 0, str(e)[:45]))
    # 3. LZ4 frame
    try:
        d = lz4.frame.decompress(blob)
        out.append(("lz4.frame", len(d), "EXACT" if len(d) == usize else "len!="))
    except Exception as e:
        out.append(("lz4.frame", 0, str(e)[:45]))
    # 4. skip a small header then LZ4
    for skip in (1, 2, 4, 8, 16):
        if len(blob) <= skip + 16:
            continue
        try:
            d = lz4.block.decompress(blob[skip:], uncompressed_size=usize)
            out.append(("skip%d+lz4" % skip, len(d),
                        "EXACT" if len(d) == usize else "len!="))
            break
        except Exception:
            pass
    # 5. raw deflate / zlib / gzip
    for nm, fn in (("zlib", zlib.decompress),
                   ("raw-deflate", lambda b: zlib.decompress(b, -15)),
                   ("gzip", lambda b: zlib.decompress(b, 16 + 15))):
        try:
            d = fn(blob)
            out.append((nm, len(d), "EXACT" if len(d) == usize else "len!="))
        except Exception:
            pass
    # 6. lzma
    try:
        import lzma
        for nm, fn in (("lzma", lzma.decompress),
                       ("lzma-raw", lambda b: lzma.decompress(
                           b, format=lzma.FORMAT_ALONE)),
                       ("lzma-rawf", lambda b: lzma.decompress(
                           b, format=lzma.FORMAT_RAW,
                           filters=[{"id": lzma.FILTER_LZMA1,
                                     "preset": 9}]))):
            try:
                d = fn(blob)
                out.append((nm, len(d), "EXACT" if len(d) == usize else "len!="))
            except Exception:
                pass
    except Exception:
        pass
    # 7. zstd / brotli if present
    for mod, nm in (("zstandard", "zstd"), ("zstd", "zstd"), ("brotli", "brotli")):
        try:
            m = __import__(mod)
            d = (m.decompress(blob) if mod == "brotli" else m.ZstdDecompressor().decompress(blob))
            out.append((nm, len(d), "EXACT" if len(d) == usize else "len!="))
        except Exception:
            pass
    print("  [%s] usize=%d csize=%d" % (tag, usize, len(blob)))
    print("      head: %s" % blob[:24].hex())
    ok = False
    for nm, ln, note in out:
        mark = ""
        if note == "EXACT":
            mark = "   <<<< EXACT MATCH"
            ok = True
        print("      %-20s -> %-9d %s%s" % (nm, ln, note, mark))
    if not ok:
        print("      (no decompressor produced the declared size)")
    return ok


if __name__ == "__main__":
    targets = sys.argv[1:] or [
        os.path.join(AB, "ui", "zonemap_misc.ab"),      # 1 block, small
        os.path.join(AB, "ui", "[uc]pc.ab"),            # 6 blocks, PC bundle
    ]
    for t in targets:
        print("=" * 78)
        print(t)
        raw, blks, dstart = blocks_of(t)
        print("blocks=%d data@%d" % (len(blks), dstart))
        cur = dstart
        for i, (usz, csz, bfl) in enumerate(blks[:3]):
            try_all(raw[cur:cur + csz], usz, "blk%d flag=%d" % (i, bfl))
            cur += csz
        print()
