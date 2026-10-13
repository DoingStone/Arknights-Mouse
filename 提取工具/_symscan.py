# -*- coding: utf-8 -*-
"""Does the engine even carry an LZHAM decompressor?

If Arknights ships LZHAM-compressed bundles, the engine MUST contain a decoder.
If 'lzham' appears nowhere in UnityPlayer.dll / GameAssembly.dll / global-metadata.dat,
then block flag 4 is almost certainly NOT LZHAM and my earlier reading of the flag
semantics is wrong.
"""
import os, re

TARGETS = [
    (r"G:\Hypergryph Launcher\games\Arknights\UnityPlayer.dll", "Arknights UnityPlayer"),
    (r"G:\Hypergryph Launcher\games\Arknights\GameAssembly.dll", "Arknights GameAssembly"),
    (r"G:\Hypergryph Launcher\games\Arknights\Arknights_Data\il2cpp_data\Metadata\global-metadata.dat", "global-metadata"),
    (r"G:\Hypergryph Launcher\games\Arknights\Arknights_Data\globalgamemanagers", "globalgamemanagers"),
]

NEEDLES = [b"lzham", b"LZHAM", b"lz4", b"LZ4", b"lzma", b"LZMA", b"Lz4", b"blockCompression",
           b"CompressionType", b"DecompressLzham", b"lzham_decompress"]

for path, label in TARGETS:
    if not os.path.exists(path):
        print("MISSING", path)
        continue
    with open(path, "rb") as f:
        b = f.read()
    print("=" * 78)
    print("%s\n  %s\n  %d bytes" % (label, path, len(b)))
    hits = {}
    for n in NEEDLES:
        c = b.count(n)
        if c:
            hits[n.decode("ascii", "replace")] = c
    print("  hits:", hits if hits else "(none)")
    for n in (b"lzham", b"LZHAM"):
        i = b.find(n)
        while i != -1:
            ctx = b[max(0, i - 48):i + 64]
            printable = "".join(chr(c) if 32 <= c < 127 else "." for c in ctx)
            print("    @%-9d %s" % (i, printable))
            i = b.find(n, i + 1)
            if i > 0 and b.count(n) > 8:
                break
