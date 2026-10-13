# -*- coding: utf-8 -*-
import importlib, os
for m in ("zstandard", "pyzstd", "zstd", "lz4", "brotli", "lzma", "bz2"):
    try:
        importlib.import_module(m)
        print("HAVE", m)
    except Exception as e:
        print("MISS", m, type(e).__name__)
p = r"G:\ArknightsCursorExtract\_lzham\py310\Lib\site-packages\lzham"
print("--- lzham pkg files:", os.listdir(p))
for f in ("__init__.py", "decompress.py", "compress.py"):
    fp = os.path.join(p, f)
    if os.path.exists(fp):
        print("=" * 30, f, os.path.getsize(fp))
        print(open(fp, encoding="utf-8", errors="replace").read()[:4000])
