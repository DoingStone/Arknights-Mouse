# -*- coding: utf-8 -*-
"""Shape-match every game Texture2D against the crystal cursor's alpha silhouette.

The crystal pointer has a unique outline.  If ANY texture in the game is that
same artwork (at any scale), normalised-mask IoU will catch it.
"""
import os, math

import UnityPy
from PIL import Image

GAME = r"G:\Hypergryph Launcher\games\Arknights\Arknights_Data"
CRYSTAL = r"G:\ArknightsCursorExtract\_probe_crystal\img_00_96x96_hot28_20.png"
N = 48


def norm_mask(im, thresh=110):
    """Return NxN binary tuple (1/0) of the alpha silhouette, aspect-preserved."""
    a = im.convert("RGBA").getchannel("A")
    bb = a.point(lambda v: 255 if v > thresh else 0).getbbox()
    if not bb:
        return None, 0
    a = a.crop(bb)
    w, h = a.size
    s = max(w, h)
    sq = Image.new("L", (s, s), 0)
    sq.paste(a, ((s - w) // 2, (s - h) // 2))
    sq = sq.resize((N, N), Image.BILINEAR)
    px = list(sq.getdata())
    return tuple(1 if v > 127 else 0 for v in px), sum(1 for v in px if v > 127) / float(N * N)


def iou(a, b):
    inter = sum(1 for x, y in zip(a, b) if x and y)
    uni = sum(1 for x, y in zip(a, b) if x or y)
    return inter / float(uni) if uni else 0.0


ref, ref_fill = norm_mask(Image.open(CRYSTAL))
print("crystal ref: fill=%.3f" % ref_fill)
print("crystal ref ASCII:")
for r in range(N):
    print("   " + "".join("#" if ref[r * N + c] else "." for c in range(N)))

cands = []
for fn in sorted(os.listdir(GAME)):
    if not fn.endswith(".assets"):
        continue
    env = UnityPy.load(os.path.join(GAME, fn))
    for obj in env.objects:
        if obj.type.name != "Texture2D":
            continue
        try:
            d = obj.read()
            im = d.image
            if im is None:
                continue
            im = im.convert("RGBA")
            m, fill = norm_mask(im)
            if m is None:
                continue
            if fill < 0.10 or fill > 0.90:
                continue
            s = iou(ref, m)
            cands.append((s, fn, obj.path_id, str(getattr(d, "m_Name", "?")),
                          im.width, im.height, fill))
        except Exception:
            pass

cands.sort(reverse=True)
print("\ntop 25 silhouette matches across ALL game textures:")
for s, fn, pid, nm, w, h, fill in cands[:25]:
    print("   IoU=%.3f  %-26s pid=%-8d %4dx%-4d fill=%.2f  %s" % (s, fn, pid, w, h, fill, nm))
print("\ncandidates considered: %d" % len(cands))
