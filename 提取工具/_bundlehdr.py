# -*- coding: utf-8 -*-
"""Scan UnityFS bundle headers: compression type, sizes, and which bundles
contain cursor/pointer-named assets.

Motivation: the *.assets files are only a fraction of the client.  The PC-specific
bundle ui\\[uc]pc.ab refuses to load with UnityPy ("Custom compression or
unimplemented LZHAM").  This maps how widespread that is, before attempting
any extraction.
"""
import os
import re
import struct
import sys
from collections import Counter

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

GAME = r"G:\Hypergryph Launcher\games\Arknights"

COMP = {0: "none", 1: "LZMA", 2: "LZ4", 3: "LZ4HC", 4: "LZHAM"}


def bundle_header(path):
    """Return dict with version / unityVer / flags / compression, or None."""
    with open(path, "rb") as f:
        b = f.read(256)
    if b[:8] != b"UnityFS\x00":
        return None
    o = 8
    ver = struct.unpack_from(">I", b, o)[0]
    o += 4
    for _ in range(2):                     # unityVersion, unityRevision
        e = b.index(b"\x00", o)
        o = e + 1
    total = struct.unpack_from(">q", b, o)[0]
    o += 8
    cbis = struct.unpack_from(">I", b, o)[0]
    o += 4
    ubis = struct.unpack_from(">I", b, o)[0]
    o += 4
    flags = struct.unpack_from(">I", b, o)[0]
    o += 4
    return dict(ver=ver, total=total, flags=flags,
                comp=COMP.get(flags & 0x3F, "?%d" % (flags & 0x3F)),
                block_info_at_end=bool(flags & 0x40),
                padding=bool(flags & 0x80),
                cbis=cbis, ubis=ubis, hdr_end=o)


roots = [os.path.join(GAME, "Arknights_Data", "StreamingAssets", "AB"),
         os.path.join(GAME, "PersistentData", "Bundles")]

comps = Counter()
bad = []
all_ab = []
for root in roots:
    if not os.path.isdir(root):
        continue
    for dirpath, _dirs, files in os.walk(root):
        for f in files:
            if f.lower().endswith((".ab", ".bin", ".bundle")):
                all_ab.append(os.path.join(dirpath, f))

print("bundle-ish files found: %d" % len(all_ab))

by_comp = {}
for p in all_ab:
    try:
        h = bundle_header(p)
    except Exception as e:
        comps["read-error"] += 1
        continue
    if h is None:
        comps["not-UnityFS"] += 1
        continue
    comps[h["comp"]] += 1
    by_comp.setdefault(h["comp"], []).append((p, h))

print("\ncompression distribution across bundles:")
for c, n in comps.most_common():
    print("  %-14s %d" % (c, n))

for c in ("LZHAM", "none"):
    if c in by_comp:
        lst = by_comp[c]
        print("\n%s bundles: %d, examples:" % (c, len(lst)))
        for p, h in lst[:15]:
            print("   %8d B  flags=0x%04X  %s" % (os.path.getsize(p), h["flags"],
                                                  p[len(GAME) + 1:]))

if "LZ4" in by_comp:
    print("\nLZ4 example headers:")
    for p, h in by_comp["LZ4"][:5]:
        print("   flags=0x%04X ver=%d total=%d  %s"
              % (h["flags"], h["ver"], h["total"], p[len(GAME) + 1:]))
