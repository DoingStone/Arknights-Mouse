# -*- coding: utf-8 -*-
"""Survey the PRTS Replica pack: sizes, extensions, embedded image geometry."""
import os, struct, collections

ROOT = r"C:\Users\22442\AppData\Local\PRTS\Replica-v8-Windows\cursors-34497b84e5b0d7cf"

by_ext = collections.Counter()
by_size = collections.Counter()
files = []
for fn in os.listdir(ROOT):
    p = os.path.join(ROOT, fn)
    if not os.path.isfile(p):
        continue
    sz = os.path.getsize(p)
    ext = os.path.splitext(fn)[1].lower()
    by_ext[ext] += 1
    by_size[(ext, sz)] += 1
    files.append((fn, sz, ext))

print("total files:", len(files))
print("\n[ext counts]")
for e, c in by_ext.most_common():
    print("   %-6s %d" % (e, c))

print("\n[distinct (ext,size) groups]")
for (e, sz), c in sorted(by_size.items(), key=lambda kv: -kv[1]):
    print("   %-6s %10d B  x%d" % (e, sz, c))


def probe_cur(path):
    raw = open(path, "rb").read()
    if raw[:4] == b"RIFF" and raw[8:12] == b"ACON":
        return "ANI"
    if raw[:4] == b"\x89PNG":
        return "PNG?"
    r0, rtype, n = struct.unpack_from("<HHH", raw, 0)
    geo = []
    for i in range(n):
        w, h, ncol, res, hsx, hsy, nbytes, off = struct.unpack_from("<BBBBHHII", raw, 6 + 16 * i)
        geo.append("%dx%d@(%d,%d)" % (w or 256, h or 256, hsx, hsy))
    return "cur n=%d %s" % (n, ",".join(geo))


print("\n[probe one file per distinct (ext,size) group]")
seen = set()
for fn, sz, ext in sorted(files):
    key = (ext, sz)
    if key in seen:
        continue
    seen.add(key)
    try:
        info = probe_cur(os.path.join(ROOT, fn))
    except Exception as ex:
        info = "ERR %s" % ex
    print("   %-58s %10d  %s" % (fn[:58], sz, info))
