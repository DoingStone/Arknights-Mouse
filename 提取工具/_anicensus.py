# -*- coding: utf-8 -*-
"""Census the embedded image sizes inside every .ani in the PRTS pack.

ANI layout is: RIFF 'ACON' / 'anih' / 'rate' / LIST('fram') -> 'icon'|'cur ' chunks.
If any frame is bigger than 96x96 there IS a higher-resolution source.
"""
import os, struct, collections

ROOT = r"C:\Users\22442\AppData\Local\PRTS\Replica-v8-Windows\cursors-34497b84e5b0d7cf"


def chunks(buf, start, end):
    p = start
    out = []
    while p + 8 <= end:
        cid = buf[p:p + 4]
        sz = struct.unpack_from("<I", buf, p + 4)[0]
        if p + 8 + sz > end:
            out.append((cid, p + 8, end - (p + 8)))
            break
        out.append((cid, p + 8, sz))
        p += 8 + sz + (sz & 1)
    return out


def geo(data):
    if data[:4] == b"\x89PNG":
        w, h = struct.unpack_from(">II", data, 16)
        return ("PNG", w, h, 0)
    if len(data) < 16:
        return ("SHORT", len(data), 0, 0)
    hs, bw, bh, pl, bpp = struct.unpack_from("<IiiHH", data, 0)
    h = abs(bh) // 2 if bh == (bw and abs(bh)) and bh == 2 * (abs(bh) // 2) else abs(bh)
    return ("BMP", bw, h, bpp)


def ani_frames(path):
    raw = open(path, "rb").read()
    if raw[:4] != b"RIFF" or raw[8:12] != b"ACON":
        return None
    top = chunks(raw, 12, len(raw))
    frames = []
    for cid, off, sz in top:
        if cid != b"LIST":
            continue
        for sid, soff, ssz in chunks(raw, off, off + sz):
            if sid != b"fram":
                continue
            for iid, ioff, isz in chunks(raw, soff, soff + ssz):
                if iid in (b"icon", b"cur "):
                    frames.append(geo(raw[ioff:ioff + isz]))
    return frames


agg = collections.Counter()
per_file = {}
for fn in sorted(os.listdir(ROOT)):
    if not fn.lower().endswith(".ani"):
        continue
    try:
        fr = ani_frames(os.path.join(ROOT, fn))
    except Exception as ex:
        agg[("ERR", str(ex)[:40], 0, 0)] += 1
        continue
    if fr is None:
        agg[("NOTANI", 0, 0, 0)] += 1
        continue
    c = collections.Counter(fr)
    per_file[fn] = (len(fr), c)
    for k, v in c.items():
        agg[k] += v

print("[all .ani frame image geometries]")
for k, v in agg.most_common(30):
    print("   %-40s x%d" % (str(k), v))

print("\n[sample: frame count + geo per ani, first 12]")
for fn, (n, c) in list(per_file.items())[:12]:
    print("   %-46s frames=%-4d %s" % (fn.replace("PRTS-Replica-v8-96x-", ""), n, dict(c)))

print("\nlargest image found anywhere in the pack:")
best = []
for k, v in agg.items():
    if k[0] in ("BMP", "PNG") and isinstance(k[1], int):
        best.append((k[1] * k[2], k, v))
best.sort(reverse=True)
for a, k, v in best[:10]:
    print("   %s px=%d  count=%d" % (k, a, v))

# also: is there a 256x variant folder anywhere?
print("\n[any other Replica version folder]")
base = r"C:\Users\22442\AppData\Local\PRTS"
for dp, dn, fns in os.walk(base):
    for d in dn:
        if "replica" in d.lower() or "cursor" in d.lower() or "96" in d or "256" in d:
            print("   dir:", os.path.join(dp, d))
