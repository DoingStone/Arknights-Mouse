# -*- coding: utf-8 -*-
"""Hunt the game's own bundle loader / codec identifiers inside IL2CPP metadata.

global-metadata.dat holds every class/method/field name of the game code as a
contiguous string table, so splitting on NULs gives clean identifiers.  If
Hypergryph wraps asset bundles with a custom codec, the class name is in here.
"""
import re, sys, io

META = r"G:\Hypergryph Launcher\games\Arknights\Arknights_Data\il2cpp_data\Metadata\global-metadata.dat"
raw = open(META, "rb").read()
print("metadata size:", len(raw))

parts = raw.split(b"\0")
strings = []
for p in parts:
    if 3 <= len(p) <= 160:
        try:
            s = p.decode("utf-8")
        except UnicodeDecodeError:
            continue
        if all(32 <= ord(c) < 127 for c in s):
            strings.append(s)
print("printable identifiers:", len(strings), " (unique:", len(set(strings)), ")")

KEYWORDS = [
    "Decrypt", "Encrypt", "Decompress", "Compress", "Cipher", "AES", "Rijndael",
    "Lzham", "LZ4", "Lz4", "Zstd", "ZSTD", "Lzma", "LZMA", "Inflate", "Deflate",
    "Codec", "Obfusc", "UnityFS", "resS", "Bundle", "AssetBundle", "ArchiveStorage",
    "Xor", "XOR", "Stream", "Key", "CRC", "MD5", "SHA", "Hotfix", "Patch",
]

# identifiers that are plainly .NET / Unity framework noise
NOISE = re.compile(
    r"^(System|Microsoft|Mono|UnityEngine|Unity|Newtonsoft|ICSharpCode|Mono\.)"
)

for kw in KEYWORDS:
    hits = [s for s in set(strings) if kw in s]
    interesting = [s for s in hits if not NOISE.match(s)]
    print("=" * 78)
    print("### %-12s total=%d  non-framework=%d" % (kw, len(hits), len(interesting)))
    for s in sorted(interesting, key=len)[:40]:
        print("   ", s)
