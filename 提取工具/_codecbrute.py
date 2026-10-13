# -*- coding: utf-8 -*-
"""Brute-force the inner block codec for the StreamingAssets .ab bundles.

Container facts already PROVEN (do not re-derive):
  * UnityFS, version 8, engine 2021.3.39f1, file 354121 B for ui/[uc]pc.ab
  * blocks-info: LZ4 (flags & 0x3F == 3) at offset 64, decodes to 203 B
  * 6 blocks, every block flag == 4, sizes (usize, csize):
      (131072,42602) (131072,62388) (131072,85812) (131072,70942)
      (131072,71559) (36876,20626)
  * sum(csize) = 353929 and 192 + 353929 = 354121 == file size  -> EXACT
  * sum(usize) = 692236 == 189068 + 503168 == CAB node + .resS -> EXACT
So the codec must map 353929 -> 692236 bytes.

Every candidate is tried at inner offsets 0..64 with a hard per-attempt cap,
because a wrong-parameter LZHAM stream can loop forever.
"""
import bz2, gzip, lzma, os, struct, subprocess, sys, zlib

BUNDLE = (r"G:\Hypergryph Launcher\games\Arknights\Arknights_Data"
          r"\StreamingAssets\AB\Windows\ui\[uc]pc.ab")
PY310 = r"G:\ArknightsCursorExtract\_lzham\py310\python.exe"
WORK = r"G:\ArknightsCursorExtract\_blk\_brute"
os.makedirs(WORK, exist_ok=True)

raw = open(BUNDLE, "rb").read()
D = 192
BLOCKS = [(131072, 42602, 4), (131072, 62388, 4), (131072, 85812, 4),
          (131072, 70942, 4), (131072, 71559, 4), (36876, 20626, 4)]

chunks, pos = [], D
for (u, c, f) in BLOCKS:
    chunks.append(raw[pos:pos + c])
    pos += c
print("chunks parsed: %d, consumed %d..%d (file %d)"
      % (len(chunks), D, pos, len(raw)))

# sanity: entropy of block 5
import collections, math
def entropy(b):
    h = collections.Counter(b)
    n = len(b)
    return -sum((v / n) * math.log2(v / n) for v in h.values())
print("block entropies:", ["%.3f" % entropy(c) for c in chunks])

TARGET = [b[0] for b in BLOCKS]   # per-block uncompressed sizes

# ---------------------------------------------------------------- pure-python
def try_zlib(d, want):
    for wbits in (15, -15, 47):
        try:
            o = zlib.decompressobj(wbits)
            r = o.decompress(d) + o.flush()
            if len(r) == want:
                return r
        except Exception:
            pass
    return None

def try_gzip(d, want):
    try:
        r = gzip.decompress(d)
        return r if len(r) == want else None
    except Exception:
        return None

def try_lzma(d, want):
    for fmt in (lzma.FORMAT_ALONE, lzma.FORMAT_XZ, lzma.FORMAT_RAW):
        for off in (0, 1, 4, 5, 8, 9, 13):
            try:
                if fmt == lzma.FORMAT_RAW:
                    dec = lzma.LZMADecompressor(
                        format=fmt,
                        filters=[{"id": lzma.FILTER_LZMA1, "dict_size": 1 << 23,
                                  "lc": 3, "lp": 0, "pb": 2}])
                else:
                    dec = lzma.LZMADecompressor(format=fmt)
                r = dec.decompress(d[off:])
                if len(r) == want:
                    return r
            except Exception:
                pass
    return None

def try_bz2(d, want):
    try:
        r = bz2.decompress(d)
        return r if len(r) == want else None
    except Exception:
        return None

def try_brotli(d, want):
    try:
        import brotli
        r = brotli.decompress(d)
        return r if len(r) == want else None
    except Exception:
        return None

def try_lz4(d, want):
    import lz4.block, lz4.frame
    out = []
    try:
        out.append(("lz4.block+sizeprefix",
                    lz4.block.decompress(d, uncompressed_size=want)))
    except Exception:
        pass
    try:
        out.append(("lz4.block.nosize", lz4.block.decompress(d)))
    except Exception:
        pass
    try:
        r = lz4.frame.decompress(d)
        if isinstance(r, bytes):
            out.append(("lz4.frame", r))
    except Exception:
        pass
    for nm, r in out:
        if r is not None and len(r) == want:
            return nm, r
    return None, None

def try_zstd(d, want):
    try:
        import zstandard
        return zstandard.ZstdDecompressor().decompress(d, max_output_size=want)
    except Exception:
        pass
    try:
        import zstd
        return zstd.decompress(d)
    except Exception:
        return None

PURE = [("zlib", try_zlib), ("gzip", try_gzip), ("lzma", try_lzma),
        ("bz2", try_bz2), ("brotli", try_brotli), ("zstd", try_zstd)]

print("=" * 78)
print("PHASE 1 - pure-python codecs, inner offsets 0..64")
found = None
for ci, ch in enumerate(chunks):
    want = TARGET[ci]
    for off in range(0, 65):
        d = ch[off:]
        for nm, fn in PURE:
            try:
                r = fn(d, want)
            except Exception:
                r = None
            if r is not None and len(r) == want:
                print("!! HIT block %d %s at inner offset %d" % (ci, nm, off))
                found = (ci, nm, off)
                break
        if found:
            break
    if found:
        break
    # LZ4 needs separate handling (it raises instead of returning None)
    for off in range(0, 65):
        nm, r = try_lz4(ch[off:], want)
        if r is not None:
            print("!! HIT block %d %s at inner offset %d" % (ci, nm, off))
            found = (ci, nm, off)
            break
    if found:
        break
    print("  block %d: no pure-python codec matched (offsets 0..64)" % ci)
if not found:
    print("PHASE 1: nothing")

# ---------------------------------------------------------------- LZHAM
HELPER = r'''# -*- coding: utf-8 -*-
import sys, lzham
d = open(sys.argv[1], "rb").read()
want = int(sys.argv[2])
off  = int(sys.argv[3])
dsl  = int(sys.argv[4])
flt  = {"dict_size_log2": dsl} if dsl else None
for tag, mk in (("func", lambda: lzham.decompress(d[off:], want, flt)),
                ("cls",  lambda: lzham.LZHAMDecompressor(flt).decompress(d[off:], want))):
    try:
        out = mk()
        print("OK %s off=%d dsl=%s len=%d want=%d match=%s"
              % (tag, off, dsl, len(out), want, len(out) == want))
        if len(out) == want:
            open(sys.argv[1] + ".out", "wb").write(out)
            sys.exit(0)
    except Exception as ex:
        print("FAIL %s off=%d dsl=%s %s: %s" % (tag, off, dsl, type(ex).__name__, ex))
sys.exit(1)
'''
hp = os.path.join(WORK, "_lz_probe.py")
open(hp, "w", encoding="utf-8").write(HELPER)

print("=" * 78)
print("PHASE 2 - LZHAM parameter sweep (block 5 first: smallest)")
bp = os.path.join(WORK, "b5.bin")
open(bp, "wb").write(chunks[5])
lz_ok = False
for off in (0, 1, 2, 4, 8):
    for dsl in (0, 20, 21, 22, 23, 24, 25, 26):
        try:
            r = subprocess.run([PY310, hp, bp, str(TARGET[5]), str(off), str(dsl)],
                               capture_output=True, text=True, timeout=45)
            o = r.stdout.strip()
            ok = "OK " in o
            print("   off=%-2d dsl=%-2d rc=%d %s" % (off, dsl, r.returncode,
                                                     o.replace("\n", " | ")[:160]))
            if ok:
                lz_ok = True
                break
        except subprocess.TimeoutExpired:
            print("   off=%-2d dsl=%-2d TIMEOUT (loops forever -> not this param set)"
                  % (off, dsl))
    if lz_ok:
        break
if not lz_ok:
    print("PHASE 2: no LZHAM parameter set decoded the block")

print("=" * 78)
print("RESULT:", found if found else ("LZHAM ok" if lz_ok else "NO CODEC FOUND"))

# ---------------------------------------------------------------- structure
print("=" * 78)
print("block 0 first 64 bytes:", chunks[0][:64].hex())
print("block 5 first 64 bytes:", chunks[5][:64].hex())
print("block 4 first 64 bytes:", chunks[4][:64].hex())
print("tail of block 5 (last 32):", chunks[5][-32:].hex())
