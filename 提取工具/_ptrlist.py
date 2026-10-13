# -*- coding: utf-8 -*-
"""List + export every Texture2D / Sprite whose name smells like a pointer."""
import os, re, sys, io

import UnityPy

GAME = r"G:\Hypergryph Launcher\games\Arknights\Arknights_Data"
OUT = r"G:\ArknightsCursorExtract\_probe_pointer"
os.makedirs(OUT, exist_ok=True)

PAT = re.compile(r"pointer|cursor|arrow|mouse|hand|click|aim|select", re.I)

files = []
for root, dirs, fs in os.walk(GAME):
    for f in fs:
        if f.lower().endswith(".assets"):
            files.append(os.path.join(root, f))
files.sort()
print("assets files: %d" % len(files))

for path in files:
    try:
        env = UnityPy.load(path)
    except Exception as ex:
        print("[skip] %s : %s" % (os.path.basename(path), ex))
        continue
    t2d, spr = [], []
    for obj in env.objects:
        try:
            tn = obj.type.name
        except Exception:
            continue
        if tn == "Texture2D":
            try:
                d = obj.read()
                t2d.append((obj.path_id, d.m_Name, d.m_Width, d.m_Height,
                            int(d.m_TextureFormat)))
            except Exception:
                pass
        elif tn == "Sprite":
            try:
                d = obj.read()
                spr.append((obj.path_id, d.m_Name))
            except Exception:
                pass
    hits_t = [t for t in t2d if PAT.search(t[1] or "")]
    hits_s = [s for s in spr if PAT.search(s[1] or "")]
    print("\n=== %s : Texture2D=%d Sprite=%d ===" % (path, len(t2d), len(spr)))
    for h in hits_t:
        print("   TEX  path=%-7d %-34s %4dx%-4d fmt=%d" % h)
    for h in hits_s:
        print("   SPR  path=%-7d %s" % h)
    for (pid, nm, w, hh, fmt) in hits_t:
        try:
            obj = next(o for o in env.objects if o.path_id == pid)
            img = obj.read().image
            safe = re.sub(r"[^A-Za-z0-9_.-]", "_", nm)
            op = os.path.join(OUT, "%s__%s.png" % (os.path.basename(path)[:24], safe))
            img.save(op)
            print("        -> %s" % op)
        except Exception as ex:
            print("        !! export failed %s: %s" % (nm, ex))
