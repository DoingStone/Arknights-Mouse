# -*- coding: utf-8 -*-
"""Diagnose the flag-4 data-block format.

Facts already established:
  * blocks-info decompresses fine with plain LZ4 (header flag = 3 LZ4HC).
  * every DATA block declares flag 4, which UnityPy maps to LZHAM.
  * blocks are contiguous with zero padding: [uc]pc.ab 192 + 353929 == 354121.
  * no stock decompressor (lz4 block/frame, zlib, deflate, gzip, lzma, zstd,
    brotli) reproduces the declared uncompressed size.

So the question is what the bytes actually ARE. Diagnostics below:
  [1] entropy + byte histogram  -> compressed vs structured vs encrypted
  [2] repeating-key detection   -> XOR / permutation obfuscation
  [3] manual LZ4 trace          -> where does a genuine LZ4 stream diverge?
  [4] LZ4 at every start offset -> is the stream merely offset by a few bytes?
  [5] look for a plausible plaintext prefix (serialized-file header) after
      each candidate transform
"""
import os
import math
import struct
import sys
from collections import Counter

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import lz4.block

G = r"G:\Hypergryph Launcher\games\Arknights"
AB = os.path.join(G, "Arknights_Data", "StreamingAssets", "AB", "Windows")


def align16(n):
    return (n + 15) & ~15


def cstr(b, o):
    e = b.index(b"\x00", o)
    return b[o:e].decode("utf-8", "replace"), e + 1


def load_blocks(path):
    raw = open(path, "rb").read()
    o = 12
    _uv, o = cstr(raw, o)
    _ur, o = cstr(raw, o)
    o += 8
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
    dstart = o + cbis
    if flags & 0x200:
        dstart = align16(dstart)
    out = []
    cur = dstart
    for usz, csz, bfl in blks:
        out.append((usz, raw[cur:cur + csz], bfl))
        cur += csz
    return raw, out, dstart


def entropy(b):
    if not b:
        return 0.0
    c = Counter(b)
    n = len(b)
    return -sum((v / n) * math.log2(v / n) for v in c.values())


def rep_key_periods(b, topn=6):
    """For each candidate key length k, count positions where b[i]==b[i+k]."""
    res = []
    for k in range(1, 65):
        same = sum(1 for i in range(len(b) - k) if b[i] == b[i + k])
        res.append((same / (len(b) - k), k))
    res.sort(reverse=True)
    return res[:topn]


def lz4_trace(b, limit=40):
    """Manual LZ4 block decode with a trace; returns (out, ok, why)."""
    out = bytearray()
    i = 0
    step = 0
    try:
        while i < len(b):
            tok = b[i]; i += 1
            ll = tok >> 4
            if ll == 15:
                while True:
                    x = b[i]; i += 1
                    ll += x
                    if x != 255:
                        break
            out += b[i:i + ll]
            i += ll
            if i >= len(b):
                break
            off = b[i] | (b[i + 1] << 8)
            i += 2
            ml = tok & 0x0F
            if ml == 15:
                while True:
                    x = b[i]; i += 1
                    ml += x
                    if x != 255:
                        break
            ml += 4
            if off == 0 or off > len(out):
                return bytes(out), False, ("bad offset %d at in=%d out=%d"
                                           % (off, i, len(out)))
            start = len(out) - off
            for j in range(ml):
                out.append(out[start + j])
            step += 1
            if step <= limit and (step <= 8 or step % 8 == 0):
                print("        tok#%-3d tok=0x%02X lit=%-4d off=%-6d match=%-4d out=%d"
                      % (step, tok, ll, off, ml, len(out)))
            if step > 200000:
                return bytes(out), False, "runaway"
    except IndexError:
        return bytes(out), False, "ran off the end at in=%d" % i
    return bytes(out), True, "consumed all input"


for tag, path in (("zonemap_misc.ab", os.path.join(AB, "ui", "zonemap_misc.ab")),
                  ("[uc]pc.ab blk0", os.path.join(AB, "ui", "[uc]pc.ab"))):
    print("=" * 78)
    print("### %s" % tag)
    _raw, blocks, dstart = load_blocks(path)
    usz, blob, bfl = blocks[0]
    print("declared usize=%d  actual csize=%d  ratio=%.3f  flag=%d"
          % (usz, len(blob), len(blob) / usz, bfl))
    print("head : %s" % blob[:48].hex())
    print("tail : %s" % blob[-16:].hex())

    print("\n[1] entropy = %.4f bits/byte  (8.0 = incompressible)" % entropy(blob))
    hist = Counter(blob).most_common(12)
    print("    top bytes: %s" % ", ".join("0x%02X:%d" % (k, v) for k, v in hist))
    zero = blob.count(0)
    print("    0x00 share = %.2f%%   distinct bytes = %d/256"
          % (100.0 * zero / len(blob), len(set(blob))))

    print("\n[2] repeating-period check (higher = more likely key length)")
    for frac, k in rep_key_periods(blob):
        print("    k=%-3d identical-bytes ratio %.4f" % (k, frac))

    print("\n[3] manual LZ4 trace from offset 0")
    out, ok, why = lz4_trace(blob)
    print("    -> out=%d bytes  ok=%s  why=%s" % (len(out), ok, why))
    print("    first 48 out: %s" % out[:48].hex())
    print("    ascii       : %s" % repr(out[:48]))

    print("\n[4] LZ4 with every start offset 0..40")
    hits = []
    for sk in range(0, 41):
        try:
            d = lz4.block.decompress(blob[sk:], uncompressed_size=usz)
            hits.append((sk, len(d)))
        except Exception:
            pass
    print("    successes: %s" % (hits if hits else "none"))

    print("\n[5] does any transform expose a serialized-file header "
          "(8+ leading zero bytes)?")
    cands = {"raw": blob, "rev": blob[::-1]}
    for k in (1, 2, 3, 4, 8, 16):
        cands["xor-k%d" % k] = bytes(
            blob[i] ^ blob[i % k] for i in range(len(blob))) if False else None
    for nm, b in cands.items():
        if b is None:
            continue
        lead = 0
        for x in b:
            if x == 0:
                lead += 1
            else:
                break
        print("    %-10s leading zeros = %d" % (nm, lead))
    # how many long zero runs exist anywhere?
    runs = max((len(s) for s in blob.split(b"\x00" * 4)), default=0)
    print("    longest 0x00-run (>=4) span = %d bytes" % runs)
    print()
