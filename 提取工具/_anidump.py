# -*- coding: utf-8 -*-
"""Proper RIFF/ANI walk + hash-dedupe of the whole PRTS pack."""
import os, struct, collections, hashlib

ROOT = r"C:\Users\22442\AppData\Local\PRTS\Replica-v8-Windows\cursors-34497b84e5b0d7cf"


def chunks(buf, start, end):
    p = start
    out = []
    while p + 8 <= end:
        cid = buf[p:p + 4]
        sz = struct.unpack_from("<I", buf, p + 4)[0]
        if p + 8 + sz > end:
            out.append((cid, p + 8, end - (p + 8), "TRUNC"))
            break
        out.append((cid, p + 8, sz, ""))
        p += 8 + sz + (sz & 1)
    return out


raw = open(os.path.join(ROOT, "PRTS-Replica-v8-96x-idle.ani"), "rb").read()
print("idle.ani size=%d head=%r" % (len(raw), raw[:4]))
print(" riff size field=%d  form=%r" % (struct.unpack_from("<I", raw, 4)[0], raw[8:12]))
top = chunks(raw, 12, len(raw))
print("\n[top-level chunks]  n=%d" % len(top))
for cid, off, sz, flag in top[:20]:
    print("   %-6r off=%-10d size=%-10d %s" % (cid, off, sz, flag))

# descend into the first non-fram container if fram is absent
for cid, off, sz, flag in top:
    if cid == b"fram":
        break
else:
    print("\n[no top-level 'fram' -> descending one level into each chunk]")
    for cid, off, sz, flag in top:
        if sz < 8:
            continue
        sub = chunks(raw, off, off + sz)
        ids = [c[0] for c in sub[:8]]
        print("   inside %-6r : %d subchunks, first ids=%s" % (cid, len(sub), ids))
        if any(i in (b"icon", b"cur ") for i in ids):
            for s_cid, s_off, s_sz, s_flag in sub[:4]:
                if s_cid in (b"icon", b"cur "):
                    d = raw[s_off:s_off + s_sz]
                    if d[:4] == b"\x89PNG":
                        w, h = struct.unpack_from(">II", d, 16)
                        print("      %r PNG %dx%d  (%d B)" % (s_cid, w, h, s_sz))
                    else:
                        hs, bw, bh, pl, bpp = struct.unpack_from("<IiiHH", d, 0)
                        print("      %r BMP %dx%d bpp=%d hdr=%d (%d B)" % (s_cid, bw, abs(bh) // 2, bpp, hs, s_sz))
            break

# ---------- dedupe census ----------
print("\n[hash census of all .cur/.ani]")
h = collections.Counter()
sz_of = {}
for fn in sorted(os.listdir(ROOT)):
    p = os.path.join(ROOT, fn)
    if not os.path.isfile(p) or not fn.lower().endswith((".cur", ".ani")):
        continue
    d = hashlib.md5(open(p, "rb").read()).hexdigest()
    h[d] += 1
    sz_of[d] = os.path.getsize(p)
print("   files=%d  distinct(md5)=%d" % (sum(h.values()), len(h)))
top_n = h.most_common(12)
for d, c in top_n:
    print("   %s  x%-5d %8d B" % (d, c, sz_of[d]))

# how many DISTINCT 96x96 cursor images (by payload hash, ignoring name)
imgs = collections.Counter()
for fn in sorted(os.listdir(ROOT)):
    if not fn.lower().endswith(".cur"):
        continue
    p = os.path.join(ROOT, fn)
    r = open(p, "rb").read()
    imgs[hashlib.md5(r[22:]).hexdigest()] += 1
print("\n   distinct .cur IMAGE payloads = %d" % len(imgs))
