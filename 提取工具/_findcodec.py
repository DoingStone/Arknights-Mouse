# -*- coding: utf-8 -*-
"""Find the real block codec by locating a decompressor in shipped binaries.

Reasoning: global-metadata.dat proved the GAME CODE has no LZHAM/LZ4/Zstd
strings, and UnityPlayer.dll proved the ENGINE has no `lzham` strings either.
So scan EVERY other PE we ship or ship alongside: launcher dir, plugins dir,
and any DLL/EXE with a plausible name.  Also inventory the bracket-prefixed
bundle families, since `[uc]` is the suspicious one.
"""
import os, re, collections

GAME = r"G:\Hypergryph Launcher\games\Arknights"
LAUNCH = r"G:\Hypergryph Launcher"

NEEDLES = ["lzham", "LZHAM", "Lzham",
           "lz4", "LZ4", "lz4hc", "LZ4HC",
           "zstd", "ZSTD", "Zstd",
           "lzma", "LZMA", "Lzma",
           "unity3dchina", "UnityCN",
           "AssetBundleEncrypt", "UsesAssetBundleEncryption",
           "ArchiveStorage", "BlockInfoNeedPadding"]

print("=" * 78)
print("[1] every PE under the game dir + launcher dir")
pes = []
for root in (GAME, LAUNCH):
    for dp, dn, fn in os.walk(root):
        # skip the huge StreamingAssets tree (no PEs there) for speed
        if "StreamingAssets" in dp or "PersistentData" in dp:
            continue
        for f in fn:
            if f.lower().endswith((".dll", ".exe", ".so", ".node", ".pyd")):
                fp = os.path.join(dp, f)
                try:
                    sz = os.path.getsize(fp)
                except OSError:
                    continue
                pes.append((sz, fp))
pes.sort(reverse=True)
print("found %d PE-like files" % len(pes))
for sz, fp in pes[:40]:
    print("   %12d  %s" % (sz, fp.replace(GAME, "<GAME>").replace(LAUNCH, "<LAUNCH>")))

print("=" * 78)
print("[2] needle scan (utf-8 + utf-16le) over PEs smaller than 80 MB")
for sz, fp in pes:
    if sz > 80 * 1024 * 1024:
        print("   SKIP (too big) %s" % os.path.basename(fp))
        continue
    try:
        raw = open(fp, "rb").read()
    except OSError:
        continue
    hits = {}
    for n in NEEDLES:
        a = raw.count(n.encode("utf-8"))
        b = raw.count(n.encode("utf-16-le"))
        if a or b:
            hits[n] = (a, b)
    if hits:
        print("   %-52s %s" % (os.path.basename(fp)[:52], hits))

print("=" * 78)
print("[3] bracket-prefixed bundle families under StreamingAssets\\AB\\Windows")
AB = os.path.join(GAME, "Arknights_Data", "StreamingAssets", "AB", "Windows")
fam = collections.Counter()
famsz = collections.Counter()
uc = []
for dp, dn, fn in os.walk(AB):
    for f in fn:
        if not f.endswith(".ab"):
            continue
        m = re.match(r"^(\[[^\]]+\])", f)
        key = m.group(1) if m else "(plain)"
        fam[key] += 1
        try:
            famsz[key] += os.path.getsize(os.path.join(dp, f))
        except OSError:
            pass
        if key == "[uc]":
            uc.append(os.path.join(dp, f))
for k, v in fam.most_common():
    print("   %-10s %6d files  %15d B" % (k, v, famsz[k]))

print("=" * 78)
print("[4] all [uc] bundles (path, size) - these are the suspicious family")
for fp in sorted(uc):
    print("   %10d  %s" % (os.path.getsize(fp), fp.replace(AB + "\\", "")))
