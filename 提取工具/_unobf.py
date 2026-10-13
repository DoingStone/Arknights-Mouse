# -*- coding: utf-8 -*-
"""Brute-force the data-block obfuscation.

Facts already proven for ui\[uc]pc.ab:
  header_end=50, version=8 (Unity 2021.3.39f1), flags=0x243
    0x03  = LZ4HC  (blocks-info container)
    0x40  = kArchiveBlocksAndDirectoryInfoCombined
    0x200 = BlockInfoNeedPaddingAtStart  (=> blocks-info at 64, data at 192)
  blocks-info: 6 blocks + 2 nodes, consumed 203/203
  data start 192 + sum(csize 353929) == 354121 == file size   (exact)
  sum(usize) == 692236 == node0(189068) + node1(503168)       (exact)
  all 6 block flags == 4  -> Unity calls that LZHAM, but NO lzham symbol
     exists in UnityPlayer.dll / GameAssembly.dll,
  and plain LZ4 / LZMA / zlib / brotli all refuse.
"""
import struct, lz4.block

P = r"G:\Hypergryph Launcher\games\Arknights\Arknights_Data\StreamingAssets\AB\Windows\ui\[uc]pc.ab"
D = open(P, "rb").read()

BI = lz4.block.decompress(D[64:64 + 119], uncompressed_size=203)
q = 16
n, = struct.unpack_from(">I", BI, q); q += 4
B = []
for _ in range(n):
    u, c, f = struct.unpack_from(">IIH", BI, q); q += 10
    B.append((u, c, f))

DATA = 192
blk = []
pos = DATA
for (u, c, f) in B:
    blk.append(D[pos:pos + c])
    pos += c

print("data start=%d  sum(csize)=%d  file=%d  (192+%d=%d)"
      % (DATA, sum(c for _, c, _ in B), len(D), sum(c for _, c, _ in B), DATA + sum(c for _, c, _ in B)))
print()


def try_lz4(buf, u):
    if len(buf) != u:
        # lz4.block needs the exact slice; allow longer buffers, it stops when done
        pass
    try:
        r = lz4.block.decompress(buf, uncompressed_size=u)
        if len(r) == u:
            return r
    except Exception:
        pass
    return None


TRANSFORMS = []
TRANSFORMS.append(("xor_%02x", lambda b, k: bytes(x ^ k for x in b), range(256)))
TRANSFORMS.append(("nibswap", lambda b, k: bytes(((x >> 4) | ((x & 0xF) << 4)) for x in b), [0]))
TRANSFORMS.append(("bitrev", lambda b, k: bytes(int('{:08b}'.format(x)[::-1], 2) for x in b), [0]))
TRANSFORMS.append(("not", lambda b, k: bytes(x ^ 0xFF for x in b), [0]))
TRANSFORMS.append(("nibxorF", lambda b, k: bytes(((x ^ 0xF) if False else x) for x in b), [0]))
# nibble-swap of the 0-F index space (UnityCN-ish): each byte -> table[hi]|table[lo]
TRANSFORMS.append(("add_%02x", lambda b, k: bytes((x + k) & 0xFF for x in b),
                   [0, 1, 0x10, 0x11, 0x20, 0x33, 0x40, 0x55, 0x7F, 0x80, 0xAA, 0xCC, 0xFE, 0xFF]))

hits = []
for i, ch in enumerate(blk):
    u = B[i][0]
    found = []
    # 0) as-is and with leading skips
    for skip in range(0, 33):
        if try_lz4(ch[skip:], u):
            found.append("asis skip=%d" % skip); break
    if not found:
        for name, fn, keys in TRANSFORMS:
            for k in keys:
                t = fn(ch, k)
                for skip in (0, 1, 2, 4, 8, 16):
                    if try_lz4(t[skip:], u):
                        found.append("%s k=%s skip=%d" % (name, hex(k), skip)); break
                if found:
                    break
            if found:
                break
    print("blk%d u=%-7d c=%-7d flag=%d -> %s" % (i, u, B[i][1], B[i][2],
                                                found[0] if found else "NO TRANSFORM WORKED"))
    if found:
        hits.append((i, found[0]))

print()
print("=" * 70)
if hits:
    print("SUCCESS:", hits)
else:
    print("No byte-wise transform unlocks these blocks.")

# Diagnostic: entropy + where the LZ4 token stream first goes invalid
import math, collections
for i, ch in enumerate(blk):
    cnt = collections.Counter(ch)
    ent = -sum((v / len(ch)) * math.log2(v / len(ch)) for v in cnt.values())
    top = cnt.most_common(6)
    print("blk%d entropy=%.3f  top=%s" % (i, ent, [(hex(k), v) for k, v in top]))
