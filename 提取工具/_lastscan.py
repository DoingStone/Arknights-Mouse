# -*- coding: utf-8 -*-
"""Last-chance sweep for ANY cursor art shipped or hot-updated by the game.

A hot-update bundle in PersistentData could OVERRIDE StreamingAssets.  If any
archive anywhere references a cursor texture name other than cursor_small /
cursor_medium / cursor_large, this finds it.
"""
import os, re, collections

GAME = r"G:\Hypergryph Launcher\games\Arknights"
NEEDLE = re.compile(
    rb"cursor[_\-]?(small|medium|large|big|xl|hd)|"
    rb"(small|medium|large)[_\-]?cursor|"
    rb"PCCursorRuntimeConfig|PCCursorHelper|nc_cursor|img_cursor\b", re.I)

print("[1] every file named like a pc/cursor bundle, game-wide")
hits = []
for dp, dn, fns in os.walk(GAME):
    for fn in fns:
        low = fn.lower()
        if low.endswith(".ab") and ("pc" == low[:-3] or low.startswith("[uc]pc") or "cursor" in low):
            p = os.path.join(dp, fn)
            try:
                hits.append((os.path.getsize(p), p.replace(GAME, "...")))
            except OSError:
                pass
for sz, p in sorted(hits):
    print("   %12d  %s" % (sz, p))
print("   total:", len(hits))

print("\n[2] PersistentData hot-update ui/ bundle names (newest first)")
pd = os.path.join(GAME, "Arknights_Data", "PersistentData")
if os.path.isdir(pd):
    rows = []
    for dp, dn, fns in os.walk(pd):
        for fn in fns:
            p = os.path.join(dp, fn)
            try:
                rows.append((os.path.getmtime(p), os.path.getsize(p), p.replace(GAME, "...")))
            except OSError:
                pass
    rows.sort(reverse=True)
    print("   total files in PersistentData:", len(rows))
    for mt, sz, p in rows[:25]:
        import datetime
        print("   %s %12d  %s" % (datetime.datetime.fromtimestamp(mt).strftime("%Y-%m-%d %H:%M"), sz, p))
else:
    print("   (no PersistentData dir)")

print("\n[3] binary-grep the whole install for cursor-texture names (first 60 hits)")
found = collections.Counter()
scanned = 0
for dp, dn, fns in os.walk(GAME):
    for fn in fns:
        p = os.path.join(dp, fn)
        try:
            sz = os.path.getsize(p)
            if sz > 300 * 1024 * 1024:
                continue
            b = open(p, "rb").read()
        except OSError:
            continue
        scanned += 1
        for m in NEEDLE.finditer(b):
            key = (p.replace(GAME, "..."), m.group(0).decode("ascii", "replace").lower())
            found[key] += 1
print("   files scanned:", scanned, "  distinct (file,needle):", len(found))
bysum = collections.Counter()
for (p, n), c in found.items():
    bysum[n] += c
print("   needle totals:", dict(bysum))
print("\n   per-file breakdown (needle != generic 'img_cursor'):")
for (p, n), c in sorted(found.items(), key=lambda kv: -kv[1]):
    if n == "img_cursor":
        continue
    print("      x%-4d %-26s %s" % (c, n, p))
