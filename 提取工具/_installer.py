# -*- coding: utf-8 -*-
"""Recover the PRTS installer's own web app from the WebView2 cache.

The cache referenced /install-bridge.js, /grab-cursor.js, /mesh-renderer.js,
/pet.js, /spine-canvas.js served from https://prts.local/.  Those scripts know
how the cursor pack is built and whether other sizes (256x) exist.
"""
import os, re, collections

CACHE = r"C:\Users\22442\AppData\Local\PRTS\InstallerWebCache"
OUT = r"G:\ArknightsCursorExtract\_installer"
os.makedirs(OUT, exist_ok=True)

NEEDLES = [b"install-bridge", b"grab-cursor", b"mesh-renderer", b"spine-canvas",
           b"pet.js", b"prts.local", b"256", b"96x", b"size"]

hits = []
for dp, dn, fns in os.walk(CACHE):
    for fn in fns:
        p = os.path.join(dp, fn)
        try:
            if os.path.getsize(p) > 30 * 1024 * 1024:
                continue
            b = open(p, "rb").read()
        except OSError:
            continue
        score = sum(1 for n in NEEDLES if n in b)
        if score >= 2:
            hits.append((score, len(b), p, b))

hits.sort(reverse=True)
print("candidate cache entries: %d" % len(hits))
for score, sz, p, b in hits[:20]:
    print("   score=%-3d %9d B  %s" % (score, sz, p.replace(CACHE, "...")))

print("\n[extracting JS / HTML text from the top entries]")
written = 0
for score, sz, p, b in hits[:12]:
    # pull readable JS/CSS/HTML runs
    runs = re.findall(rb"[\x09\x0a\x0d\x20-\x7e]{200,200000}", b)
    runs.sort(key=len, reverse=True)
    if not runs:
        continue
    best = runs[0]
    if b"function" not in best and b"<" not in best:
        continue
    name = "cache_%02d_%d.js" % (written, sz)
    op = os.path.join(OUT, name)
    open(op, "wb").write(best)
    print("   wrote %-28s %8d B   head=%r" % (name, len(best), best[:70]))
    written += 1

print("\nwritten:", written)
print("\n[all distinct text filenames referenced in the cache]")
refs = collections.Counter()
pat = re.compile(rb"[\w\-/\.]{3,60}\.(js|html|css|json|wasm|png|webp)", re.I)
for dp, dn, fns in os.walk(CACHE):
    for fn in fns:
        p = os.path.join(dp, fn)
        try:
            if os.path.getsize(p) > 30 * 1024 * 1024:
                continue
            b = open(p, "rb").read()
        except OSError:
            continue
        for m in pat.findall(b) or []:
            pass
        for m in pat.finditer(b):
            refs[m.group(0).decode("ascii", "replace").lower()] += 1
for r, c in refs.most_common(45):
    print("   x%-4d %s" % (c, r))
