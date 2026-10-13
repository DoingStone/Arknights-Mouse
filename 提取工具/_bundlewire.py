# -*- coding: utf-8 -*-
"""Diagnose why UnityFS blocks-info won't LZ4-decompress.

Key insight to test: flags 0x243 = 0x200 | 0x40 | 0x03.
  bit 0x200 = kArchiveBlockInfoNeedPaddingAtStart
  bit 0x40  = kArchiveBlocksAndDirectoryInfoCombined
  bit 0x80  = kArchiveBlocksInfoAtTheEnd
So 0x40 is NOT 'at end'. This dumps the real bytes so the layout can be read
off the wire instead of inferred, and tests plain LZ4 at several offsets.
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

G = r"G:\Hypergryph Launcher\games\Arknights"
AB = os.path.join(G, "Arknights_Data", "StreamingAssets", "AB", "Windows")

CANDIDATES = [
    os.path.join(AB, "ui", "[uc]pc.ab"),
    os.path.join(AB, "ui", "[uc]home.ab"),
    os.path.join(AB, "ui", "roguelike.ab"),
    os.path.join(AB, "ui", "skin_groups.ab"),
    os.path.join(AB, "arts", "[pack]common.ab"),
    os.path.join(AB, "activity", "[uc]actfun.ab"),
    os.path.join(AB, "graphics", "common.ab"),
]


def hexdump(b, base=0, n=192, width=16):
    for i in range(0, min(n, len(b)), width):
        chunk = b[i:i + width]
        hx = " ".join("%02X" % c for c in chunk)
        asc = "".join(chr(c) if 32 <= c < 127 else "." for c in chunk)
        print("  %06X  %-*s  %s" % (base + i, width * 3, hx, asc))


def cstr(b, o):
    e = b.index(b"\x00", o)
    return b[o:e].decode("utf-8", "replace"), e + 1


def header(path):
    raw = open(path, "rb").read()
    if raw[:8] != b"UnityFS\x00":
        return None, raw
    o = 12
    uv, o = cstr(raw, o)
    ur, o = cstr(raw, o)
    total = struct.unpack_from(">q", raw, o)[0]; o += 8
    cbis = struct.unpack_from(">I", raw, o)[0]; o += 4
    ubis = struct.unpack_from(">I", raw, o)[0]; o += 4
    flags = struct.unpack_from(">I", raw, o)[0]; o += 4
    return dict(uv=uv, ur=ur, total=total, cbis=cbis, ubis=ubis,
                flags=flags, hdr_end=o, raw=raw), raw


print("=" * 78)
print("PART 1 — does UnityPy load ANY bundle?")
print("=" * 78)
import UnityPy
for p in CANDIDATES:
    if not os.path.exists(p):
        print("  MISSING  %s" % os.path.basename(p))
        continue
    try:
        env = UnityPy.load(p)
        nobj = 0
        for _ in env.objects:
            nobj += 1
        print("  OK       %-28s objects=%d" % (os.path.basename(p), nobj))
    except Exception as e:
        print("  FAIL     %-28s %s: %s" % (os.path.basename(p),
                                          type(e).__name__, str(e)[:70]))

print()
print("=" * 78)
print("PART 2 — raw wire bytes of the failing bundle")
print("=" * 78)
p = CANDIDATES[0]
h, raw = header(p)
print("file      : %s" % p)
print("flags     : 0x%06X  (0x200 pad@start=%s  0x40 combined=%s  0x80 atEnd=%s)"
      % (h["flags"], bool(h["flags"] & 0x200), bool(h["flags"] & 0x40),
         bool(h["flags"] & 0x80)))
print("hdr_end   : %d   cbis=%d ubis=%d" % (h["hdr_end"], h["cbis"], h["ubis"]))
print("\nfirst 192 bytes:")
hexdump(raw, 0, 192)

print("\nlast 192 bytes:")
hexdump(raw, len(raw) - 192, 192)

bi_off = h["hdr_end"]
bi = raw[bi_off:bi_off + h["cbis"]]
print("\nblocks-info candidate @ %d, %d bytes; head:" % (bi_off, len(bi)))
hexdump(bi, bi_off, 64)
print("sha/hex head: %s" % bi[:16].hex())

print("\n--- try LZ4 at several offsets / sizes ---")
for off in (bi_off, bi_off + 4, bi_off + 8, bi_off + 16):
    for sz in (h["cbis"], h["cbis"] - 4, h["cbis"] - 8, h["cbis"] - 16):
        if sz <= 0:
            continue
        try:
            d = lz4.block.decompress(raw[off:off + sz],
                                     uncompressed_size=h["ubis"])
            print("  OK  off=%d size=%d -> %d bytes" % (off, sz, len(d)))
        except Exception as e:
            pass
print("  (only OK lines shown)")

print("\n--- try raw (uncompressed) blocks-info ---")
for off in (bi_off, bi_off + 4):
    d = raw[off:off + h["ubis"]]
    print("  off=%d first 32: %s" % (off, d[:32].hex()))
    if len(d) >= 20:
        nb = struct.unpack_from(">I", d, 16)[0]
        print("     interpreted blocksInfoCount = %d" % nb)
