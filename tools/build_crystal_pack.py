# -*- coding: utf-8 -*-
"""明日方舟水晶指针 —— 多尺寸可安装指针构建器（生产版）

源：本机已安装的第三方 PRTS Replica v8 96x 方案
    （注册表 HKCU\\Control Panel\\Cursors 的 21 个角色绑定 → .cur / .ani）

产出：三档尺寸（小 / 中 / 大）× 17 个角色，全部为 Windows 原生 .cur / .ani，
      热点取自源文件本身（.ani 的每一帧其实是内嵌的完整 .cur，因此也带热点）。

关键实现要点
------------
1. .cur 容器：ICONDIR 只有 3 个 u16（reserved / type / count）；
   每项 16 字节 <BBBBHHII>；bmp 高度字段 = 2×实际高度；AND 掩码可全零
   （32bpp 直通 alpha 时 Windows 只看 alpha 通道）。
2. .ani 容器：RIFF/ACON，顶层 anih / rate / LIST；LIST 的 **type 字段是 'fram'**，
   子块从 LIST 数据起点 +12 字节开始（8 字节 chunk 头 + 4 字节 type），
   每个子块是 'icon'，其载荷是一整个 .cur 文件。
3. 缩放：源图的完全透明像素全是 (0,0,0,0)，直接对 straight alpha 做 LANCZOS
   会把黑色渗进边缘形成黑边，因此必须 **预乘 alpha** 重采样后再还原。
4. 尺寸语义：档位增益 g（小=0.5，中=1/√2≈0.7071，大=1.0）表示在"96px 参考画布"
   上指针的实际显示大小比例，与游戏内三档 48/64/96 的比例一致。
   画布 N 上：缩放系数 s = g*N/96，热点固定落在 (round(hx*N/96), round(hy*N/96))，
   即指针尖端位置不随档位变化，只有笔身变大变小。
"""
import json, os, struct, subprocess, sys
from PIL import Image

# ------------------------------------------------------------------ 路径与常量
OUT = r"G:\ArknightsCursorExtract\CrystalCursorPack"
SRCDIR = (r"C:\Users\22442\AppData\Local\PRTS\Replica-v8-Windows"
          r"\cursors-34497b84e5b0d7cf")
NATIVE = 96

TIERS = [("small", "小", 0.5, "48px 档（对标游戏 cursor_small）"),
         ("medium", "中", 2.0 ** -0.5, "68px 档（对标游戏 cursor_medium，1/√2）"),
         ("large", "大", 1.0, "96px 档（对标游戏 cursor_large，原始分辨率）")]

ROLE_ORDER = ["Arrow", "Help", "AppStarting", "Wait", "Crosshair", "IBeam",
              "NWPen", "No", "SizeNS", "SizeWE", "SizeNWSE", "SizeNESW",
              "SizeAll", "UpArrow", "Hand", "Pin", "Person"]

STATIC_RASTERS = [32, 48, 64, 96, 128, 256]   # 静态 .cur：覆盖 Windows 全部光标尺寸


# ------------------------------------------------------------------ .cur 读取
def parse_cur_bytes(raw):
    """完整 .cur 字节流 -> (RGBA 图像, hsx, hsy, 光栅尺寸)。取最大光栅。"""
    _r0, rtype, n = struct.unpack_from("<HHH", raw, 0)
    if rtype != 2:
        raise SystemExit("不是指针文件 type=%d" % rtype)
    best = None
    for i in range(n):
        w, h, _nc, _res, hsx, hsy, nb, off = struct.unpack_from("<BBBBHHII", raw, 6 + 16 * i)
        w, h = w or 256, h or 256
        payload = raw[off:off + nb]
        if payload[:4] == b"\x89PNG":
            im = Image.open(__import__("io").BytesIO(payload)).convert("RGBA")
        else:
            _hs, bw, bh = struct.unpack_from("<Iii", payload, 0)
            rw, rh = bw, abs(bh) // 2
            im = Image.frombytes("RGBA", (rw, rh), payload[40:40 + rw * rh * 4],
                                 "raw", "BGRA").transpose(Image.FLIP_TOP_BOTTOM)
        if best is None or w > best[3]:
            best = (im, hsx, hsy, w)
    return best


def read_cur(path):
    raw = open(path, "rb").read()
    if raw[:4] == b"RIFF" and raw[8:12] == b"ACON":
        raise SystemExit("不是 .cur（这是 .ani）：%s" % path)
    return parse_cur_bytes(raw)


# ------------------------------------------------------------------ .ani 读取
def read_ani(path):
    """返回 (frames=[(RGBA,hsx,hsy)], anih 字段元组, rate 列表或 None)。"""
    raw = open(path, "rb").read()
    assert raw[:4] == b"RIFF" and raw[8:12] == b"ACON", path
    anih, rate, frames = None, None, []
    q = 12
    while q + 8 <= len(raw):
        cid = raw[q:q + 4]
        sz = struct.unpack_from("<I", raw, q + 4)[0]
        data = q + 8
        if cid == b"anih":
            anih = struct.unpack_from("<9I", raw, data)
        elif cid == b"rate":
            rate = list(struct.unpack_from("<%dI" % (sz // 4), raw, data))
        elif cid == b"LIST":
            if raw[data:data + 4] != b"fram":
                raise SystemExit("LIST type 不是 fram：%r" % raw[data:data + 4])
            p, end = data + 4, q + 8 + sz       # 子块从 type 之后开始
            while p + 8 <= end:
                iid = raw[p:p + 4]
                isz = struct.unpack_from("<I", raw, p + 4)[0]
                if iid in (b"icon", b"cur "):
                    frames.append(parse_cur_bytes(raw[p + 8:p + 8 + isz]))
                p += 8 + isz + (isz & 1)
        q += 8 + sz + (sz & 1)
    return frames, anih, rate


# ------------------------------------------------------------------ 图像处理
def resize_rgba(im, size):
    """预乘 alpha 的 LANCZOS 缩放（避免黑边）。"""
    if im.size == (size, size):
        return im.copy()
    w, h = im.size
    s = im.load()
    pm = Image.new("RGB", (w, h))
    al = Image.new("L", (w, h))
    p, a = pm.load(), al.load()
    for y in range(h):
        for x in range(w):
            r, g, b, av = s[x, y]
            f = av / 255.0
            p[x, y] = (int(r * f + 0.5), int(g * f + 0.5), int(b * f + 0.5))
            a[x, y] = av
    ps = pm.resize((size, size), Image.LANCZOS)
    as_ = al.resize((size, size), Image.LANCZOS)
    out = Image.new("RGBA", (size, size))
    o, sp, ap = out.load(), ps.load(), as_.load()
    for y in range(size):
        for x in range(size):
            av = ap[x, y]
            if av == 0:
                continue
            f = 255.0 / av
            r, g, b = sp[x, y]
            o[x, y] = (min(255, int(r * f + 0.5)), min(255, int(g * f + 0.5)),
                       min(255, int(b * f + 0.5)), av)
    return out


def place(art, gain, canvas, hsx, hsy):
    """把 96px 源图按档位增益缩放到 canvas 画布上，热点位置不随档位改变。"""
    s = gain * canvas / float(NATIVE)
    m = max(1, int(round(NATIVE * s)))
    scaled = resize_rgba(art, m)
    hx, hy = int(round(hsx * canvas / float(NATIVE))), int(round(hsy * canvas / float(NATIVE)))
    ax, ay = int(round(hx - hsx * s)), int(round(hy - hsy * s))
    out = Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))
    # 手动合成，容忍越界（裁剪），不使用 alpha_composite 以免负偏移报错
    op, sp = out.load(), scaled.load()
    for y in range(m):
        ty = ay + y
        if ty < 0 or ty >= canvas:
            continue
        for x in range(m):
            tx = ax + x
            if tx < 0 or tx >= canvas:
                continue
            op[tx, ty] = sp[x, y]
    return out, hx, hy


# ------------------------------------------------------------------ .cur 写入
def cur_image(im, hsx, hsy):
    w, h = im.size
    px = im.load()
    xor = bytearray()
    for y in range(h - 1, -1, -1):          # bottom-up
        row = bytearray()
        for x in range(w):
            r, g, b, a = px[x, y]
            row += bytes((b, g, r, a))       # BGRA，straight alpha
        xor += row
    need = ((w + 31) // 32) * 4 * h          # 1bpp AND 掩码，行按 4 字节对齐
    hdr = struct.pack("<IiiHHIIiiII", 40, w, h * 2, 1, 32, 0,
                      len(xor), 0, 0, 0, 0)
    return hdr + bytes(xor) + bytes(need)


def cur_blob(images):
    """把若干 (图像, hsx, hsy) 光栅打包成一整个 .cur 字节流（含 ICONDIR）。"""
    blobs = [cur_image(im, hx, hy) for im, hx, hy in images]
    n = len(blobs)
    out = bytearray(struct.pack("<HHH", 0, 2, n))
    off = 6 + 16 * n
    for (im, hx, hy), blob in zip(images, blobs):
        w, h = im.size
        out += struct.pack("<BBBBHHII", w if w < 256 else 0, h if h < 256 else 0,
                           0, 0, hx, hy, len(blob), off)
        off += len(blob)
    for b in blobs:
        out += b
    return bytes(out)


def write_cur(path, images):
    blob = cur_blob(images)
    open(path, "wb").write(blob)
    return len(blob)


# ------------------------------------------------------------------ .ani 写入
def write_ani(path, frames, anih, rate):
    """frames = [(RGBA,hsx,hsy)]；每帧封装成一个完整 .cur（与源文件格式一致）。"""
    body = b""
    for (im, hx, hy) in frames:
        cb = cur_blob([(im, hx, hy)])        # icon 载荷 = 一整份 .cur
        body += b"icon" + struct.pack("<I", len(cb)) + cb
        if len(cb) & 1:
            body += b"\x00"
    list_data = b"fram" + body
    chunks = b""
    _cb_size, _nf, _ns, _w, _h, bpp, planes, disp, attrs = anih[:9]
    nf = len(frames)
    a = struct.pack("<9I", 36, nf, nf, 0, 0, bpp, planes, disp, attrs)
    chunks += b"anih" + struct.pack("<I", len(a)) + a
    if rate is not None:
        rt = rate[:nf] + [rate[-1]] * max(0, nf - len(rate))
        rdat = struct.pack("<%dI" % nf, *rt)
        chunks += b"rate" + struct.pack("<I", len(rdat)) + rdat
    chunks += b"LIST" + struct.pack("<I", len(list_data)) + list_data
    riff = b"ACON" + chunks
    blob = b"RIFF" + struct.pack("<I", len(riff)) + riff
    open(path, "wb").write(blob)
    return len(blob)


def raster_of(path, want=96):
    """从 .cur 或 .ani（取第 0 帧）里取出指定尺寸的光栅，返回 (RGBA, hsx, hsy)。"""
    raw = open(path, "rb").read()
    if raw[:4] == b"RIFF":
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
                return Image.open(io.BytesIO(pl)).convert("RGBA"), hsx, hsy
            return Image.frombytes("RGBA", (want, want), pl[40:40 + want * want * 4],
                                   "raw", "BGRA").transpose(Image.FLIP_TOP_BOTTOM), hsx, hsy
    raise SystemExit("在 %s 里找不到 %dpx 光栅" % (path, want))


# ------------------------------------------------------------------ 主流程
def main():
    reg = json.load(open(os.path.join(OUT, "before-install-backup.json"), encoding="utf-8"))
    roles = reg["current"] if "current" in reg else reg
    # 取注册表里每个角色当前绑定的文件
    binding = {}
    for r in ROLE_ORDER:
        v = roles.get(r)
        if v:
            binding[r] = v if os.path.isabs(v) else os.path.join(SRCDIR, v)

    print("源目录: %s" % SRCDIR)
    print("角色绑定: %d" % len(binding))
    manifest = {"source_dir": SRCDIR, "tiers": {}, "roles": ROLE_ORDER}

    for tier, zh, gain, desc in TIERS:
        tdir = os.path.join(OUT, "cursors", tier)
        edir = os.path.join(OUT, "extracted", tier)
        os.makedirs(tdir, exist_ok=True)
        os.makedirs(edir, exist_ok=True)
        print("\n=== 档位 %s (%s)  gain=%.4f  %s ===" % (zh, tier, gain, desc))
        tinfo = {"gain": gain, "zh": zh, "desc": desc, "files": {}}
        nbytes_tot = 0
        for role in ROLE_ORDER:
            src = binding.get(role)
            if not src or not os.path.exists(src):
                print("  跳过 %-12s（无源）" % role)
                continue
            if src.lower().endswith(".ani"):
                frames, anih, rate = read_ani(src)
                out_frames = []
                for (im, hx, hy, _fw) in frames:
                    im96 = im if im.width == NATIVE else resize_rgba(im, NATIVE)
                    pim, phx, phy = place(im96, gain, NATIVE, hx, hy)
                    out_frames.append((pim, phx, phy))
                outp = os.path.join(tdir, "Arknights_Crystal_%s_%s.ani" % (role, tier))
                nb = write_ani(outp, out_frames, anih, rate)
                # 导出第 0 帧 PNG 作为交付图
                out_frames[0][0].save(os.path.join(edir, "Arknights_Crystal_%s_%s_f000.png"
                                                   % (role, tier)))
                kind = "ani(%d 帧, %d×%d)" % (len(frames), NATIVE, NATIVE)
            else:
                art, hx, hy, _fw = read_cur(src)
                art = art if art.width == NATIVE else resize_rgba(art, NATIVE)
                rasters = [place(art, gain, N, hx, hy) for N in STATIC_RASTERS]
                outp = os.path.join(tdir, "Arknights_Crystal_%s_%s.cur" % (role, tier))
                nb = write_cur(outp, rasters)
                art.save(os.path.join(edir, "Arknights_Crystal_%s_%s_native96.png"
                                      % (role, tier)))
                kind = "cur(%s)" % "+".join(str(n) for n in STATIC_RASTERS)
            nbytes_tot += nb
            tinfo["files"][role] = {"path": outp, "bytes": nb, "kind": kind,
                                    "hotspot_96": [int(round(hx * (96 / float(NATIVE)))),
                                                   int(round(hy * (96 / float(NATIVE))))]}
            print("  %-12s %-46s %9d B  %s" % (role, os.path.basename(outp), nb, kind))
        tinfo["total_bytes"] = nbytes_tot
        manifest["tiers"][tier] = tinfo

    # 预览图：三档各一张，17 个角色（一律取 96 光栅，避免裁到大光栅的局部）
    for tier, zh, gain, desc in TIERS:
        cell = 96
        cols = 6
        rows = (len(ROLE_ORDER) + cols - 1) // cols
        pad = 26
        sheet = Image.new("RGB", (cols * (cell + 8) + 8, rows * (cell + pad) + pad + 8),
                          (24, 26, 32))
        from PIL import ImageDraw
        dr = ImageDraw.Draw(sheet)
        for i, role in enumerate(ROLE_ORDER):
            f = manifest["tiers"][tier]["files"].get(role)
            if not f:
                continue
            im, hx, hy = raster_of(f["path"], 96)
            cx = 8 + (i % cols) * (cell + 8)
            cy = 8 + (i // cols) * (cell + pad)
            bg = Image.new("RGBA", (cell, cell), (58, 66, 80, 255))
            bg.alpha_composite(im.convert("RGBA"), (0, 0))
            sheet.paste(bg.convert("RGB"), (cx, cy))
            dr.line([(cx + hx - 5, cy + hy), (cx + hx + 5, cy + hy)], fill=(230, 60, 60), width=1)
            dr.line([(cx + hx, cy + hy - 5), (cx + hx, cy + hy + 5)], fill=(230, 60, 60), width=1)
            dr.text((cx, cy + cell + 3), "%s  hot=%d,%d" % (role, hx, hy),
                    fill=(200, 200, 208))
        dr.text((8, 4), "档位 %s  gain=%.4f  %s" % (zh, gain, desc), fill=(255, 210, 90))
        sheet.save(os.path.join(OUT, "preview_%s.png" % tier))
        print("写出 preview_%s.png" % tier)

    json.dump(manifest, open(os.path.join(OUT, "_manifest.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    tot = sum(manifest["tiers"][t]["total_bytes"] for t in manifest["tiers"])
    print("\n清单已写入 _manifest.json")
    print("指针文件总量: %.1f MB" % (tot / 1048576.0))


if __name__ == "__main__":
    main()
