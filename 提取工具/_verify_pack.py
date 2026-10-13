# -*- coding: utf-8 -*-
"""独立验收：重新解析本包产物，验证尺寸/热点/像素一致性/动画完整性。"""
import os, struct, json, sys, hashlib
from PIL import Image

PACK = r"G:\ArknightsCursorExtract\CrystalCursorPack"
SRCDIR = (r"C:\Users\22442\AppData\Local\PRTS\Replica-v8-Windows"
          r"\cursors-34497b84e5b0d7cf")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_crystal_pack import parse_cur_bytes, read_ani

man = json.load(open(os.path.join(PACK, "_manifest.json"), encoding="utf-8"))
reg = json.load(open(os.path.join(PACK, "before-install-backup.json"), encoding="utf-8"))


def rast_n(path, want=96):
    """从 .cur 或 .ani（取第 0 帧）里取出指定尺寸的光栅。"""
    raw = open(path, "rb").read()
    if raw[:4] == b"RIFF":                       # .ani → 取第 0 帧的 .cur
        q = 12
        while q + 8 <= len(raw):
            cid, sz = raw[q:q + 4], struct.unpack_from("<I", raw, q + 4)[0]
            if cid == b"LIST" and raw[q + 8:q + 12] == b"fram":
                p, end = q + 12, q + 8 + sz
                while p + 8 <= end:
                    iid = raw[p:p + 4]
                    isz = struct.unpack_from("<I", raw, p + 4)[0]
                    if iid in (b"icon", b"cur "):
                        raw = raw[p + 8:p + 8 + isz]
                        q = -1
                        break
                    p += 8 + isz + (isz & 1)
                if q == -1:
                    break
            q += 8 + sz + (sz & 1)
    _r, _t, n = struct.unpack_from("<HHH", raw, 0)
    for i in range(n):
        w, h, _c, _s, hsx, hsy, nb, off = struct.unpack_from("<BBBBHHII", raw, 6 + 16 * i)
        if (w or 256) == want:
            pl = raw[off:off + nb]
            if pl[:4] == b"\x89PNG":
                import io
                im = Image.open(io.BytesIO(pl)).convert("RGBA")
            else:
                im = Image.frombytes("RGBA", (want, want), pl[40:40 + want * want * 4],
                                     "raw", "BGRA").transpose(Image.FLIP_TOP_BOTTOM)
            return im, hsx, hsy
    return None, None, None

print("=" * 92)
print("1) 文件计数")
print("=" * 92)
total = 0
for tier in ("small", "medium", "large"):
    d = os.path.join(PACK, "cursors", tier)
    cur = [f for f in os.listdir(d) if f.endswith(".cur")]
    ani = [f for f in os.listdir(d) if f.endswith(".ani")]
    print("  %-7s .cur=%2d  .ani=%2d  合计 %2d" % (tier, len(cur), len(ani), len(cur) + len(ani)))
    total += len(cur) + len(ani)
print("  总计 %d 个指针文件" % total)

print()
print("=" * 92)
print("2) large 档 96px 光栅 vs 源文件（应逐像素完全一致）")
print("=" * 92)
ok_all = True
for role in man["roles"]:
    e = man["tiers"]["large"]["files"].get(role)
    if not e:
        continue
    src = reg[role]
    src = src if os.path.isabs(src) else os.path.join(SRCDIR, src)
    a, hx1, hy1 = rast_n(e["path"], 96)
    b, hx2, hy2 = rast_n(src, 96)
    same = list(a.getdata()) == list(b.getdata())
    hot_ok = (hx1, hy1) == (hx2, hy2)
    good = same and hot_ok and a.size == b.size
    ok_all &= good
    print("  %-12s 尺寸 %s vs %s  像素一致=%-5s  热点 (%d,%d) vs (%d,%d)  %s"
          % (role, a.size, b.size, same, hx1, hy1, hx2, hy2, "OK" if good else "!! 不符"))
print("  → %s" % ("全部通过" if ok_all else "存在不符项"))

print()
print("=" * 92)
print("3) 各档光栅清单 + 热点随尺寸缩放校验")
print("=" * 92)
for tier, zh, gain, _desc in [("small", "小", 0.5, ""), ("medium", "中", 2 ** -0.5, ""),
                              ("large", "大", 1.0, "")]:
    f = man["tiers"][tier]["files"]["Arrow"]
    raw = open(f["path"], "rb").read()
    _r, _t, n = struct.unpack_from("<HHH", raw, 0)
    rows = []
    for i in range(n):
        w, h, _c, _s, hsx, hsy, nb, off = struct.unpack_from("<BBBBHHII", raw, 6 + 16 * i)
        rows.append((w or 256, hsx, hsy))
    rows.sort()
    # 校验热点 = round(28*N/96), round(20*N/96)
    bad = [r for r in rows if (r[1], r[2]) != (round(28 * r[0] / 96.0), round(20 * r[0] / 96.0))]
    print("  档位 %s gain=%.4f  %s" % (zh, gain,
          "  ".join("%d→(%d,%d)" % r for r in rows)))
    print("       热点缩放校验：%s" % ("全部正确" if not bad else "!! 异常 %s" % bad))

print()
print("=" * 92)
print("4) 动画完整性（帧数 / 帧延时 / 首帧热点）")
print("=" * 92)
for role, stem in [("AppStarting", "work"), ("Wait", "busy"), ("No", "unavail1"),
                   ("SizeAll", "move"), ("SizeNS", "sel_1"), ("SizeWE", "sel_2"),
                   ("SizeNWSE", "sel_3"), ("SizeNESW", "sel_4")]:
    srcf = os.path.join(SRCDIR, "PRTS-Replica-v8-96x-%s.ani" % stem)
    sfr, _sa, srate = read_ani(srcf)
    line = []
    for tier in ("small", "medium", "large"):
        fr, _a, rate = read_ani(man["tiers"][tier]["files"][role]["path"])
        line.append("%s:%d帧%s" % (tier, len(fr),
                                   "" if (rate is None) == (srate is None) else "!!"))
    print("  %-12s 源 %d 帧 (rate %s)  →  %s"
          % (role, len(sfr), "有" if srate else "无", "   ".join(line)))

print()
print("=" * 92)
print("5) 各档视觉大小（不透明像素包围盒宽度，应与 gain 成比例）")
print("=" * 92)
for role in ("Arrow", "UpArrow", "NWPen"):
    vals = []
    for tier in ("small", "medium", "large"):
        e = man["tiers"][tier]["files"][role]
        raw = open(e["path"], "rb").read()
        _r, _t, n = struct.unpack_from("<HHH", raw, 0)
        im = None
        for i in range(n):
            w, h, _c, _s, hsx, hsy, nb, off = struct.unpack_from("<BBBBHHII", raw, 6 + 16 * i)
            if (w or 256) == 96:
                pl = raw[off:off + nb]
                im = Image.frombytes("RGBA", (96, 96), pl[40:40 + 96 * 96 * 4],
                                     "raw", "BGRA").transpose(Image.FLIP_TOP_BOTTOM)
                break
        px = im.load()
        xs = [x for y in range(96) for x in range(96) if px[x, y][3] > 40]
        ys = [y for y in range(96) for x in range(96) if px[x, y][3] > 40]
        vals.append((tier, max(xs) - min(xs) + 1, max(ys) - min(ys) + 1))
    print("  %-12s %s" % (role, "   ".join("%s %dx%d" % v for v in vals)))
