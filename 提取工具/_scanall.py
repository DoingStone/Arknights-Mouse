# -*- coding: utf-8 -*-
"""Scan EVERY Unity asset file in the client for pointer-like Texture2D names."""
import os, glob, UnityPy
D = r"G:\Hypergryph Launcher\games\Arknights\Arknights_Data"
files = sorted(glob.glob(os.path.join(D, "*.assets"))) 
KW = ("cursor", "pointer", "arrow")
hits = []
for f in files:
    try:
        env = UnityPy.load(f)
        for o in env.objects:
            if o.type.name != "Texture2D":
                continue
            try:
                d = o.read()
            except Exception:
                continue
            nm = getattr(d, "m_Name", "") or ""
            if any(k in nm.lower() for k in KW):
                hits.append((os.path.basename(f), o.path_id, nm,
                             d.m_Width, d.m_Height, d.m_TextureFormat))
    except Exception as e:
        print("  !! %s -> %s" % (os.path.basename(f), str(e)[:70]))
print("asset files scanned: %d" % len(files))
print("%-28s %-9s %-42s %-10s %s" % ("file", "path_id", "name", "size", "fmt"))
for h in hits:
    print("%-28s %-9d %-42s %-10s %d" % (h[0], h[1], h[2][:42], "%dx%d" % (h[3], h[4]), h[5]))
print("\ntotal pointer-named Texture2D found: %d" % len(hits))
