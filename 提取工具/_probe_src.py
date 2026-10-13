# -*- coding: utf-8 -*-
"""普查 17 个源文件里每个 .cur 的各档光栅尺寸与热点，找出非 96px 的特例。"""
import os, struct, json

SRCDIR = (r"C:\Users\22442\AppData\Local\PRTS\Replica-v8-Windows"
          r"\cursors-34497b84e5b0d7cf")
PACK = r"G:\ArknightsCursorExtract\CrystalCursorPack"

reg = json.load(open(os.path.join(PACK, "before-install-backup.json"), encoding="utf-8"))
roles = ["Arrow", "Help", "AppStarting", "Wait", "Crosshair", "IBeam", "NWPen", "No",
         "SizeNS", "SizeWE", "SizeNWSE", "SizeNESW", "SizeAll", "UpArrow", "Hand",
         "Pin", "Person"]

def cur_rasters(path):
    raw = open(path, "rb").read()
    if raw[:4] == b"RIFF":
        return None, len(raw)
    r, t, n = struct.unpack_from("<HHH", raw, 0)
    out = []
    for i in range(n):
        w, h, nc, res, hsx, hsy, nb, off = struct.unpack_from("<BBBBHHII", raw, 6 + 16 * i)
        d = raw[off:off + nb]
        if d[:4] == b"\x89PNG":
            out.append((w or 256, h or 256, hsx, hsy, nb, "PNG"))
        else:
            _hs, bw, bh = struct.unpack_from("<Iii", d, 0)
            out.append((bw, abs(bh) // 2, hsx, hsy, nb, "DIB"))
    return out, len(raw)

def ani_rasters(path):
    raw = open(path, "rb").read()
    q, frames, hs = 12, 0, None
    while q + 8 <= len(raw):
        cid = raw[q:q + 4]
        sz = struct.unpack_from("<I", raw, q + 4)[0]
        if cid == b"LIST" and raw[q + 8:q + 12] == b"fram":
            p, end = q + 12, q + 8 + sz
            while p + 8 <= end:
                iid = raw[p:p + 4]
                isz = struct.unpack_from("<I", raw, p + 4)[0]
                if iid in (b"icon", b"cur "):
                    frames += 1
                    if hs is None:
                        rs, _ = cur_rasters_bytes(raw[p + 8:p + 8 + isz])
                        hs = rs
                p += 8 + isz + (isz & 1)
        q += 8 + sz + (sz & 1)
    return frames, hs, len(raw)

def cur_rasters_bytes(raw):
    r, t, n = struct.unpack_from("<HHH", raw, 0)
    out = []
    for i in range(n):
        w, h, nc, res, hsx, hsy, nb, off = struct.unpack_from("<BBBBHHII", raw, 6 + 16 * i)
        d = raw[off:off + nb]
        _hs, bw, bh = struct.unpack_from("<Iii", d, 0)
        out.append((bw, abs(bh) // 2, hsx, hsy, nb))
    return out, len(raw)

print("%-12s %-9s %-9s %s" % ("角色", "文件", "字节", "光栅(尺寸/热点)"))
print("-" * 100)
special = []
for role in roles:
    v = reg.get(role)
    if not v:
        continue
    p = v if os.path.isabs(v) else os.path.join(SRCDIR, v)
    name = os.path.basename(p)
    if p.lower().endswith(".ani"):
        nf, rs, sz = ani_rasters(p)
        desc = "ani %d 帧, 帧内 %s" % (nf, rs)
        dims = [r[0] for r in (rs or [])]
        print("%-12s %-9s %9d %s" % (role, name.replace("PRTS-Replica-v8-96x-", ""), sz, desc))
        if rs and rs[0][0] != 96:
            special.append((role, name, rs))
    else:
        rs, sz = cur_rasters(p)
        # 只显示光栅尺寸集合与最大光栅的热点
        dims = sorted(set(r[0] for r in rs))
        big = max(rs, key=lambda r: r[0])
        print("%-12s %-9s %9d 光栅 %s  最大 %dx%d hot=(%d,%d)"
              % (role, name.replace("PRTS-Replica-v8-96x-", ""), sz, dims,
                 big[0], big[1], big[2], big[3]))
        if 96 not in dims:
            special.append((role, name, rs))

print()
print("=" * 78)
if special:
    print("!! 不含 96px 光栅的源文件（会被放大）：")
    for role, name, rs in special:
        print("   %-12s %-46s %s" % (role, name, rs))
else:
    print("全部源文件都含 96px 光栅。")
