# -*- coding: utf-8 -*-
"""Provenance push: (A) PC-ish bundle names, (B) .idx structure + cursor/mouse hits,
(C) MonoScript/MonoBehaviour census for cursor-class configs across all *.assets.
"""
import glob
import os
import re
import struct
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

G = r"G:\Hypergryph Launcher\games\Arknights"
DATA = os.path.join(G, "Arknights_Data")
AB = os.path.join(DATA, "StreamingAssets", "AB", "Windows")
IDX = os.path.join(AB, "074c396967a291d157f01a3e40c79119.idx")

print("=" * 78)
print("### A. bundle filenames that look PC / mouse / cursor / pointer")
seen = []
for root, _d, files in os.walk(AB):
    for f in files:
        if not f.lower().endswith(".ab"):
            continue
        stem = f[:-3]
        if (stem.lower() in ("pc", "[uc]pc", "[pack]pc")
                or re.search(r"mouse|cursor|pointer", f, re.I)):
            seen.append(os.path.relpath(os.path.join(root, f), AB))
print("count: %d" % len(seen))
for s in sorted(seen):
    print("   %s" % s)

print()
print("=" * 78)
print("### B. .idx inspection")
raw = open(IDX, "rb").read()
print("size      : %d" % len(raw))
print("head hex  : %s" % raw[:64].hex())
print("head ascii: %s" % repr(raw[:128]))
for k in (b"cursor", b"Cursor", b"pointer", b"Pointer", b"mouse", b"Mouse",
          b"[uc]pc.ab", b"PCCursor"):
    print("  %-12s hits=%d" % (k.decode(), raw.count(k)))

def ctx(needle, before=90, after=140, maxhits=40, label=None):
    print("\n--- context for %s ---" % (label or needle))
    n = 0
    start = 0
    while True:
        i = raw.find(needle, start)
        if i < 0:
            break
        n += 1
        if n > maxhits:
            print("    ... more suppressed")
            break
        lo = max(0, i - before)
        seg = raw[lo:i + after]
        print("    @%-9d %s" % (i, repr(seg)))
        start = i + 1

ctx(b"cursor", maxhits=12)
ctx(b"[uc]pc.ab", before=200, after=220, maxhits=4)
ctx(b"PCCursor", before=60, after=120, maxhits=8)

print()
print("=" * 78)
print("### C. cursor-class census across all *.assets (raw MonoBehaviour header parse)")
try:
    import UnityPy
except Exception as e:  # pragma: no cover
    print("UnityPy unavailable: %s" % e)
    raise SystemExit(0)

assets = sorted(glob.glob(os.path.join(DATA, "*.assets")))
print("assets files: %d" % len(assets))
all_cursor_classes = {}
for p in assets:
    try:
        env = UnityPy.load(p)
    except Exception as e:
        print("  %-28s LOAD FAIL %s" % (os.path.basename(p), str(e)[:60]))
        continue
    scripts = {}
    mbs = []
    for o in env.objects:
        if o.type.name == "MonoScript":
            try:
                d = o.read()
                scripts[o.path_id] = (getattr(d, "m_ClassName", None)
                                      or getattr(d, "m_Name", None) or "?")
            except Exception:
                scripts[o.path_id] = "?"
        elif o.type.name == "MonoBehaviour":
            mbs.append(o)
    hits = []
    for o in mbs:
        try:
            r = o.get_raw_data()
            if isinstance(r, memoryview):
                r = r.tobytes()
            if len(r) < 36:
                continue
            fid, pid = struct.unpack_from("<iq", r, 16)
            nm_len = struct.unpack_from("<i", r, 28)[0]
            nm = r[32:32 + nm_len].decode("utf-8", "replace") if 0 < nm_len < 200 else ""
            cls = scripts.get(pid, "file%d:%d" % (fid, pid))
            if re.search(r"cursor", cls, re.I) or re.search(r"cursor", nm, re.I):
                hits.append((o.path_id, cls, nm, len(r)))
        except Exception:
            pass
    if hits:
        print("  %s : %d cursor-ish MonoBehaviour" % (os.path.basename(p), len(hits)))
        for pid_, cls, nm, ln in hits:
            print("      path_id=%-6d script=%-42s m_Name=%-26s raw=%d" % (pid_, cls, nm, ln))
    for cls in scripts.values():
        if re.search(r"cursor", cls, re.I):
            all_cursor_classes[cls] = all_cursor_classes.get(cls, 0) + 1
print("\n  distinct MonoScript classes matching cursor:")
for k, v in sorted(all_cursor_classes.items()):
    print("    %-52s x%d" % (k, v))
