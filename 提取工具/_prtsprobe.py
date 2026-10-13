# -*- coding: utf-8 -*-
"""Provenance hunt: is the 'PRTS Replica' cursor pack installed by Arknights itself,
or is it third-party? Scan launcher + game files for the identifying strings."""
import os, sys, re
from pathlib import Path

NEEDLES = [b"PRTS", b"Replica", b"cursors-", b"Replica-v8", b"PRTS-Replica",
           b"settings.ini", b"unavail1"]
ROOTS = [
    r"G:\Hypergryph Launcher",
]

SKIP_EXT = {".ab", ".resS", ".assets", ".bundle", ".dat", ".bmp", ".png", ".jpg",
            ".mp3", ".ogg", ".wav", ".mp4", ".usm", ".dll.pdb"}

def scan(root, max_bytes=64 * 1024 * 1024, max_hits=40):
    print("=" * 78)
    print("ROOT:", root)
    nfiles = 0
    hits = []
    for dp, dn, fn in os.walk(root):
        for f in fn:
            p = os.path.join(dp, f)
            ext = os.path.splitext(f)[1].lower()
            try:
                sz = os.path.getsize(p)
            except OSError:
                continue
            if sz == 0 or sz > max_bytes:
                continue
            nfiles += 1
            try:
                b = Path(p).read_bytes()
            except Exception:
                continue
            found = [n.decode() for n in NEEDLES if n in b]
            if found:
                hits.append((p, sz, found))
                print(f"  HIT {sz:>10} {p}   <- {found}")
                if len(hits) >= max_hits:
                    print("  ... capped")
                    return
    print(f"  scanned files: {nfiles}   hits: {len(hits)}")

for r in ROOTS:
    scan(r)

print()
print("=" * 78)
print("Other copies of the spiky art anywhere obvious:")
try:
    import hashlib
    ref = r"C:\Users\22442\AppData\Local\PRTS\Replica-v8-Windows\cursors-34497b84e5b0d7cf\PRTS-Replica-v8-96x-normal.cur"
    refb = Path(ref).read_bytes()
    h = hashlib.sha256(refb).hexdigest()
    print("  ref sha256:", h, len(refb), "bytes")
    refpx = refb[40 + 3022:40 + 3022 + 64]
    print("  ref pixel head:", refpx[:32].hex())
    # search a few likely dirs for identical bytes / same artist name
    for root in [r"C:\Users\22442\AppData\Local", r"C:\Users\22442\Downloads",
                 r"C:\Users\22442\Desktop", r"C:\Users\22442\Documents"]:
        if not os.path.isdir(root):
            continue
        found = []
        for dp, dn, fn in os.walk(root):
            dn[:] = [d for d in dn if d.lower() not in ("temp", "cache", "microsoft", "packages")]
            for f in fn:
                if not f.lower().endswith((".cur", ".ani", ".ico", ".zip", ".7z", ".rar")):
                    continue
                p = os.path.join(dp, f)
                try:
                    if os.path.getsize(p) == len(refb) and Path(p).read_bytes() == refb:
                        found.append(p)
                except Exception:
                    pass
            if len(found) > 12:
                break
        print(f"  {root}: identical-bytes files = {len(found)}")
        for f in found[:12]:
            print("     ", f)
except Exception as e:
    print("  ref scan failed:", type(e).__name__, e)
