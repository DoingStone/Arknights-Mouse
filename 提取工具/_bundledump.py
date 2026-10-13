# -*- coding: utf-8 -*-
"""Dump the full object inventory of one Unity asset bundle / assets file.

Purpose: find pointer art that does NOT live in the *.assets files.
Lists every object's type + name, and flags anything cursor/pointer shaped.
"""
import os
import sys

import UnityPy

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

TEXFMT = {1: "Alpha8", 2: "ARGB4444", 3: "RGB24", 4: "RGBA32", 5: "ARGB32",
          7: "RGB565", 10: "DXT1", 12: "DXT5", 25: "ASTC_RGB_8x8",
          47: "ASTC_RGBA_8x8", 48: "ASTC_RGBA_6x6", 63: "ETC_RGB4"}

path = sys.argv[1]
name_filter = sys.argv[2].lower() if len(sys.argv) > 2 else None

print("=" * 78)
print("file: %s" % path)
print("bytes: %d" % os.path.getsize(path))
head = open(path, "rb").read(32)
print("head : %r" % head[:24])

env = UnityPy.load(path)

counts = {}
for o in env.objects:
    counts[o.type.name] = counts.get(o.type.name, 0) + 1
print("\nobject types (%d objects):" % len(env.objects))
for t in sorted(counts, key=lambda k: -counts[k]):
    print("  %-24s %d" % (t, counts[t]))

print("\n--- all objects with a readable name ---")
hits = []
for o in env.objects:
    try:
        d = o.read_typetree() if o.type.name not in ("Texture2D", "Sprite") else None
    except Exception:
        d = None
    nm = ""
    try:
        if o.type.name == "Texture2D":
            d = o.read()
            nm = getattr(d, "m_Name", "") or ""
            extra = "%dx%d fmt=%s" % (d.m_Width, d.m_Height,
                                      TEXFMT.get(d.m_TextureFormat, d.m_TextureFormat))
        else:
            nm = (d or {}).get("m_Name", "") if isinstance(d, dict) else ""
            if not nm:
                dd = o.read()
                nm = getattr(dd, "m_Name", "") or ""
            extra = ""
    except Exception as e:
        nm, extra = "", "err=%s" % str(e)[:30]
    if nm or extra:
        print("  %-20s path_id=%-8d %-42s %s" % (o.type.name, o.path_id, nm, extra))
    if nm and any(k in nm.lower() for k in ("cursor", "pointer", "arrow")):
        hits.append((o.type.name, o.path_id, nm, extra))

print("\n--- cursor/pointer/arrow named objects: %d ---" % len(hits))
for t, pid, nm, extra in hits:
    print("  %-20s path_id=%-8d %-42s %s" % (t, pid, nm, extra))

if name_filter:
    print("\n--- objects whose name contains %r ---" % name_filter)
    for o in env.objects:
        try:
            d = o.read()
            nm = getattr(d, "m_Name", "") or ""
        except Exception:
            continue
        if name_filter in nm.lower():
            print("  %-20s path_id=%-8d %s" % (o.type.name, o.path_id, nm))
