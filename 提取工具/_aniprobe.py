# -*- coding: utf-8 -*-
"""Probe .ani frame geometry + hunt for a higher-resolution pack variant."""
import os, struct, collections

ROOT = r"C:\Users\22442\AppData\Local\PRTS\Replica-v8-Windows\cursors-34497b84e5b0d7cf"


def riff_chunks(buf, start, end):
    p = start
    out = []
    while p + 8 <= end:
        cid = buf[p:p + 4]
        sz = struct.unpack_from("<I", buf, p + 4)[0]
        out.append((cid, p + 8, sz))
        p += 8 + sz + (sz & 1)
    return out


def cur_geo(data):
    """data = a .cur image payload (BMP or PNG)"""
    if data[:4] == b"\x89PNG":
        w, h = struct.unpack_from(">II", data, 16)
        return ("PNG", w, h, 0, 0)
    hs, bw, bh, planes, bpp = struct.unpack_from("<IiiHH", data, 0)
    return ("BMP", bw, abs(bh) // 2 if bh > 0 else abs(bh), bpp, hs)


def probe_ani(path):
    raw = open(path, "rb").read()
    assert raw[:4] == b"RIFF" and raw[8:12] == b"ACON", "not an ANI"
    top = riff_chunks(raw, 12, len(raw))
    fmt = [c for c in top if c[0] == b"fmt "]
    fram = [c for c in top if c[0] == b"fram"]
    rate = [c for c in top if c[0] == b"rate"]
    seq = [c for c in top if c[0] == b"seq "]
    info = "fmt=%s frames=%d rate=%d seq=%d" % (
        fmt[0][2] if fmt else "-", len(fram), rate[0][2] if rate else 0, seq[0][2] if seq else 0)
    geos = collections.Counter()
    nimg = 0
    for _, off, sz in fram[:6]:
        for cid, coff, csz in riff_chunks(raw, off, off + sz):
            if cid in (b"icon", b"cur "):
                g = cur_geo(raw[coff:coff + csz])
                geos[(g[0], g[1], g[2])] += 1
                nimg += 1
    return info, geos, nimg


for name in ("PRTS-Replica-v8-96x-idle.ani", "PRTS-Replica-v8-96x-helpsel_press.ani",
             "PRTS-Replica-v8-96x-busy.ani", "PRTS-Replica-v8-96x-move.ani"):
    p = os.path.join(ROOT, name)
    try:
        info, geos, nimg = probe_ani(p)
        print("%-42s %s" % (name.replace("PRTS-Replica-v8-96x-", ""), info))
        print("    probe frames=6 images=%d  geo=%s" % (nimg, dict(geos)))
    except Exception as ex:
        print("%-42s ERR %s" % (name, ex))

# ---- full frame-size census across ALL anis (cheap: walk fram chunks only, take first img each)
print("\n[frame geo census over all .ani]")
agg = collections.Counter()
for fn in sorted(os.listdir(ROOT)):
    if not fn.lower().endswith(".ani"):
        continue
    path = os.path.join(ROOT, fn)
    try:
        raw = open(path, "rb").read()
        top = riff_chunks(raw, 12, len(raw))
        got = None
        for cid, off, sz in top:
            if cid != b"fram":
                continue
            for iid, ioff, isz in riff_chunks(raw, off, off + sz):
                if iid in (b"icon", b"cur "):
                    got = cur_geo(raw[ioff:ioff + isz])
                    break
            if got:
                break
        agg[got] += 1 if got else 0
    except Exception as ex:
        agg[("ERR", str(ex)[:40], 0)] += 1
for k, v in agg.most_common(20):
    print("   %-46s x%d" % (str(k), v))

print("\n[InstallerWebCache hunt]")
cache = r"C:\Users\22442\AppData\Local\PRTS"
hits = 0
for dp, dn, fns in os.walk(cache):
    for fn in fns:
        low = fn.lower()
        if low.endswith((".cur", ".ani", ".zip", ".7z", ".exe", ".msi", ".json", ".ini", ".xml")):
            p = os.path.join(dp, fn)
            try:
                sz = os.path.getsize(p)
            except OSError:
                continue
            print("   %10d  %s" % (sz, p.replace(cache, "...")))
            hits += 1
            if hits > 60:
                print("   ... (truncated)")
                break
    if hits > 60:
        break
print("   cache entries listed:", hits)
