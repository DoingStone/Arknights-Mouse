# -*- coding: utf-8 -*-
"""Find which codec the shipped binaries actually contain.

Key question: block flag 4 is Unity's LZHAM slot, but is there any LZHAM
(or other) decompressor in this build?  Search UTF-8 AND UTF-16LE, and
print a CONTROL string that we KNOW exists (PCCursorRuntimeConfig) so a
zero result can be distinguished from a broken scan.
"""
import os, re, collections

TARGETS = [
    (r"G:\Hypergryph Launcher\games\Arknights\UnityPlayer.dll", "UnityPlayer.dll"),
    (r"G:\Hypergryph Launcher\games\Arknights\GameAssembly.dll", "GameAssembly.dll"),
    (r"G:\Hypergryph Launcher\games\Arknights\Arknights_Data\il2cpp_data\Metadata\global-metadata.dat", "global-metadata.dat"),
    (r"G:\Hypergryph Launcher\games\Arknights\Arknights_Data\globalgamemanagers", "globalgamemanagers"),
]

NEEDLES = [
    # controls - these MUST be found
    b"PCCursorRuntimeConfig", b"Torappu", b"cursor_small",
    # codec names
    b"lzham", b"LZHAM", b"Lzham", b"zstd", b"ZSTD", b"Zstd", b"zstandard", b"Zstandard",
    b"lz4", b"LZ4", b"lzma", b"LZMA",
    # assetbundle machinery
    b"CompressionType", b"ArchiveStorage", b"UnityCN", b"unity3dchina",
    b"AssetBundleDecrypt", b"Decrypt", b"encrypt", b"kArchiveLZHAM",
    b"BundleFile", b"AssetBundle", b"Decompress", b"decompress",
    b"BlockInfoNeedPadding", b"UsesAssetBundleEncryption",
]


def find_all(hay, needle):
    out = []
    s = 0
    while True:
        i = hay.find(needle, s)
        if i < 0:
            break
        out.append(i)
        s = i + 1
        if len(out) > 400:
            break
    return out


for path, label in TARGETS:
    if not os.path.exists(path):
        print("%-22s MISSING" % label); continue
    raw = open(path, "rb").read()
    print("=" * 78)
    print("%s  (%d bytes)" % (label, len(raw)))
    for nd in NEEDLES:
        n8 = find_all(raw, nd)
        try:
            n16 = find_all(raw, nd.decode().encode("utf-16-le"))
        except Exception:
            n16 = []
        if not n8 and not n16:
            continue
        ctxs = []
        for i in n8[:2]:
            seg = raw[max(0, i - 28):i + len(nd) + 34]
            txt = "".join(chr(c) if 32 <= c < 127 else "." for c in seg)
            ctxs.append(txt)
        print("  %-30s utf8=%-5d utf16=%-5d" % (nd.decode(), len(n8), len(n16)))
        for c in ctxs:
            print("      | %s" % c)
