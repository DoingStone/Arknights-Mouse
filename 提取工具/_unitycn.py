# -*- coding: utf-8 -*-
"""Load the PC UI bundle with UnityPy, whose UnityCN support handles 0x200 encryption."""
import os, sys, json

BUNDLE = sys.argv[1] if len(sys.argv) > 1 else \
    r"G:\Hypergryph Launcher\games\Arknights\Arknights_Data\StreamingAssets\AB\Windows\ui\[uc]pc.ab"

import UnityPy
print("UnityPy", getattr(UnityPy, "__version__", "?"))
print("has UnityCN helper:", os.path.exists(os.path.join(os.path.dirname(UnityPy.__file__), "helpers", "UnityCN.py")))

try:
    env = UnityPy.load(BUNDLE)
except Exception as e:
    import traceback; traceback.print_exc()
    raise SystemExit(1)

print("objects:", len(env.objects))
print("container keys:", len(getattr(env, "container", {}) or {}))

kinds = {}
rows = []
for o in env.objects:
    try:
        t = o.type.name
    except Exception:
        t = str(getattr(o, "type", "?"))
    kinds[t] = kinds.get(t, 0) + 1
    nm = None
    try:
        d = o.read()
        nm = getattr(d, "m_Name", None) or getattr(d, "name", None)
    except Exception as e:
        nm = "<read failed: %s>" % type(e).__name__
    rows.append((t, nm, o.path_id))

print()
print("=" * 78)
print("type histogram:")
for k, v in sorted(kinds.items(), key=lambda kv: -kv[1]):
    print("  %-22s %d" % (k, v))

print()
print("=" * 78)
print("ALL OBJECTS:")
for t, nm, pid in rows:
    print("  %-20s path_id=%-10s %s" % (t, pid, nm))

print()
print("=" * 78)
print("container:")
for k, v in (getattr(env, "container", {}) or {}).items():
    print("  %-60s -> %s" % (k, getattr(v, "path_id", v)))

print()
print("=" * 78)
print("names containing cursor/arrow/mouse/pointer:")
for t, nm, pid in rows:
    if nm and any(w in str(nm).lower() for w in ("cursor", "arrow", "mouse", "pointer", "pc")):
        print("  %-20s path_id=%-10s %s" % (t, pid, nm))
