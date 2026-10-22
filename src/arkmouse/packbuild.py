# -*- coding: utf-8 -*-
"""缺指针文件时，从内嵌的 art.bin 现场重建一套 .cur / .ani。

## 为什么需要这个模块

exe 只内嵌 art.bin / fx.bin（见 build/build_exe.py），**不带 cursors/ 目录**。
于是「只拿到 exe」的人（Release 单下附件、或从旧版仓库里翻出来的 exe）
点「安装指针」就会撞上「没有找到指针目录」，然后什么也做不了 —— 报错弹窗
看起来像程序坏了，其实只是少了几个文件。

而 art.bin 里本来就存着全部原生 96px 美术（17 个角色、543 帧、热点齐全），
指针文件完全是从它派生的：按档位增益 gain 重摆一遍、再按 .cur/.ani 的
二进制格式写出去即可。实测一档 17 个文件约 3 秒、22.9 MB，产物与仓库里
那份等价 —— 17/17 语义一致（帧像素 + 有效节拍逐帧相同），其中 15 个
**逐字节相同**；只有 AppStarting / Wait 这两个 .ani 的容器差了 296 字节
（仓库那份是早期工具写的，多出一点填充，解出来的帧完全一样）。
可用 tools/_verify_packbuild.py 复算。

所以这里的策略是「能生成就不报错」：找不到目录就先造一套，再造不出来
才提示用户。

## 与仓库里那份的关系

生成器只负责**从 art.bin 重算**，不读旧文件。因此它天然是幂等的：
同一份 art.bin + 同一个 gain，永远得到同一串字节。仓库里的
cursors/cursors/<档>/ 是同一个算法 + 同一份 art.bin 的产物，两者互为校验。

## 注意

- 画布与热点语义见 cursorwin.PACK_TIERS 的注释：gain 是「指针在 96px
  参考画布上占多大」，和程序里的 scale 是同一个量。
- 静态角色写 .cur（6 档光栅），动画角色写 .ani（画布固定 96px，帧数由
  art.bin 决定）。这一点必须和 install.ps1 / guard 找文件的方式一致：
  先找 .cur，找不到再找 .ani。
"""
import os
import struct

from PIL import Image

import artpack
import cursorwin as cw

NATIVE = 96

STATIC_RASTERS = (32, 48, 64, 96, 128, 256)
"""静态角色 .cur 里放的 6 档光栅。

和仓库里那份完全相同。32 是 Windows 加载文件式光标时唯一会用到的一档
（见 说明.md「Windows 把光标钉死在 32px」），后面几档留给别的尺寸路径。
"""

ANIH_BPP = 32
ANIH_PLANES = 1
ANIH_DISP_RATE = 1
"""没有 rate 块时的默认节拍，单位 jiffy（1/60 秒）。

`anih` 的第 8 个字是 iDispRate、第 9 个是 bfAttributes。bfAttributes 的
最低位（AF_ICON）决定 iDispRate 的单位：置 1 时是 jiffy，置 0 时是内部
速率表的下标。本包的 .ani 全部按 jiffy + AF_ICON 写，和系统自带的光标
动画一致。
"""
ANIH_ATTRS = 1

JIFFY_MS = 1000.0 / 60.0
"""一个 jiffy 的毫秒数（16.667）。"""


def ms_to_jiffies(rate_ms):
    """毫秒 -> jiffy。

    art.bin 里存的是**毫秒**（`artpack.rates_ms`，直接喂给运行期的
    `tick_anim` 用），而 .ani 的 rate 块和 iDispRate 都是 **jiffy**。
    不换算就会写出「16 jiffy ≈ 267ms 一帧」的龟速动画 —— 实测原素材
    是 16ms/帧（= 1 jiffy），换算后正好对上仓库里那份。
    """
    out = []
    for v in (rate_ms or []):
        try:
            n = int(round(float(v) / JIFFY_MS))
        except (TypeError, ValueError):
            n = ANIH_DISP_RATE
        out.append(max(1, n))
    return out or None


# ------------------------------------------------------------------ 图像处理
def resize_rgba(im, size):
    """预乘 alpha 的 LANCZOS 缩放（避免黑边）。"""
    if im.size == (size, size):
        return im.copy()
    w, h = im.size
    s = im.load()
    pm = Image.new('RGB', (w, h))
    al = Image.new('L', (w, h))
    p, a = pm.load(), al.load()
    for y in range(h):
        for x in range(w):
            r, g, b, av = s[x, y]
            f = av / 255.0
            p[x, y] = (int(r * f + 0.5), int(g * f + 0.5), int(b * f + 0.5))
            a[x, y] = av
    ps = pm.resize((size, size), Image.LANCZOS)
    as_ = al.resize((size, size), Image.LANCZOS)
    out = Image.new('RGBA', (size, size))
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
    hx = int(round(hsx * canvas / float(NATIVE)))
    hy = int(round(hsy * canvas / float(NATIVE)))
    ax, ay = int(round(hx - hsx * s)), int(round(hy - hsy * s))
    out = Image.new('RGBA', (canvas, canvas), (0, 0, 0, 0))
    # 手动合成，容忍越界（裁剪）；alpha_composite 不接受负偏移
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
    hdr = struct.pack('<IiiHHIIiiII', 40, w, h * 2, 1, 32, 0,
                      len(xor), 0, 0, 0, 0)
    return hdr + bytes(xor) + bytes(need)


def cur_blob(images):
    """把若干 (图像, hsx, hsy) 光栅打包成一整个 .cur 字节流（含 ICONDIR）。"""
    blobs = [cur_image(im, hx, hy) for im, hx, hy in images]
    n = len(blobs)
    out = bytearray(struct.pack('<HHH', 0, 2, n))
    off = 6 + 16 * n
    for (im, hx, hy), blob in zip(images, blobs):
        w, h = im.size
        out += struct.pack('<BBBBHHII', w if w < 256 else 0,
                           h if h < 256 else 0, 0, 0, hx, hy,
                           len(blob), off)
        off += len(blob)
    for b in blobs:
        out += b
    return bytes(out)


def write_cur(path, images):
    blob = cur_blob(images)
    with open(path, 'wb') as f:
        f.write(blob)
    return len(blob)


def write_ani(path, frames, rate_ms):
    """frames = [(RGBA, hsx, hsy)]；每帧封装成一个完整 .cur（与源文件一致）。

    rate_ms 是**毫秒**（art.bin 的口径），这里换算成 jiffy 再写进 rate 块：
    两处单位不同是这个模块最容易写错的地方，见 ms_to_jiffies()。

    节拍的两种写法：整体同一个节拍时，Windows 与仓库里那份的做法都是把
    它折进 anih.iDispRate、**不写 rate 块**；只有逐帧不同才写 rate 块。
    两种写法的播放效果完全一样，但跟着仓库那样做能让重新生成的目录与
    仓库里的那份逐字节相同 —— 维护者跑完生成器 `git status` 才是干净的。
    """
    body = b''
    for (im, hx, hy) in frames:
        cb = cur_blob([(im, hx, hy)])        # icon 载荷 = 一整份 .cur
        body += b'icon' + struct.pack('<I', len(cb)) + cb
        if len(cb) & 1:
            body += b'\x00'
    list_data = b'fram' + body
    nf = len(frames)
    rate = ms_to_jiffies(rate_ms)
    if rate is None:
        per_frame = [ANIH_DISP_RATE] * nf
    else:
        per_frame = list(rate[:nf]) + [rate[-1]] * max(0, nf - len(rate))
    uniform = len(set(per_frame)) == 1
    disp = per_frame[0] if uniform else ANIH_DISP_RATE
    a = struct.pack('<9I', 36, nf, nf, 0, 0, ANIH_BPP, ANIH_PLANES,
                    disp, ANIH_ATTRS)
    chunks = b'anih' + struct.pack('<I', len(a)) + a
    if not uniform:
        rdat = struct.pack('<%dI' % nf, *per_frame)
        chunks += b'rate' + struct.pack('<I', len(rdat)) + rdat
    chunks += b'LIST' + struct.pack('<I', len(list_data)) + list_data
    riff = b'ACON' + chunks
    blob = b'RIFF' + struct.pack('<I', len(riff)) + riff
    with open(path, 'wb') as f:
        f.write(blob)
    return len(blob)


# ------------------------------------------------------------------ 对外
def tier_dir(root, tier_key):
    """某一档在磁盘上的目录：<指针根>/cursors/<档名>/。"""
    return os.path.join(root, 'cursors', tier_key)


def file_name(role_key, tier_key, animated):
    return 'Arknights_Crystal_%s_%s%s' % (
        role_key, tier_key, '.ani' if animated else '.cur')


def have_tier(root, tier_key):
    """这一档是不是 17 个角色全齐了（缺一个就当没有，避免半套方案）。"""
    d = tier_dir(root, tier_key)
    for r in cw.ROLES:
        key = r[0]
        animated = key in cw.ANIMATED
        p = os.path.join(d, file_name(key, tier_key, animated))
        if not os.path.isfile(p):
            return False
    return True


def build_tier(art_path, root, tier_key, gain, progress=None):
    """从 art.bin 重建一整档，返回写出的文件数。

    progress: 可选回调 progress(已完成角色数, 总角色数, 角色名)，用来驱动
    一个进度条 —— 一档约 3 秒，不给反馈的话界面会像卡死。
    """
    pk = artpack.load(art_path)
    d = tier_dir(root, tier_key)
    os.makedirs(d, exist_ok=True)
    total = len(cw.ROLES)
    done = 0
    for r in cw.ROLES:
        key = r[0]
        frames = pk.frames(key)
        if not frames:
            raise RuntimeError('art.bin 里没有 %s 的帧，无法生成指针' % key)
        animated = key in cw.ANIMATED
        path = os.path.join(d, file_name(key, tier_key, animated))
        if animated:
            scaled = [place(im, gain, NATIVE, hx, hy)
                      for (im, hx, hy) in frames]
            write_ani(path, scaled, pk.rates_ms(key))
        else:
            art, hx, hy = frames[0]
            rasters = [place(art, gain, n, hx, hy) for n in STATIC_RASTERS]
            write_cur(path, rasters)
        done += 1
        if progress is not None:
            try:
                progress(done, total, key)
            except Exception:
                pass
    return done


def build_tier_for_scale(art_path, root, scale, progress=None):
    """按当前 scale 挑最近的一档来生成，返回 (档位元组, 文件数)。

    和 guard.scheme_tier() 的选择口径一致：先找增益最接近、且 17 个角色
    全齐的档；都不齐就按距离取第一个（然后现场补出来）。
    """
    tier = cw.pack_tiers_for(scale)[0]
    n = build_tier(art_path, root, tier[0], tier[1], progress=progress)
    return tier, n


# ------------------------------------------------------- 登记成 Windows 方案
def scheme_paths(root, tier_key):
    """某一档的 17 条路径，顺序固定为 cursorwin.ROLES。缺文件返回 None。"""
    d = tier_dir(root, tier_key)
    out = []
    for r in cw.ROLES:
        key = r[0]
        hit = None
        for ext in ('.cur', '.ani'):
            p = os.path.join(d, 'Arknights_Crystal_%s_%s%s'
                             % (key, tier_key, ext))
            if os.path.isfile(p):
                hit = p
                break
        if hit is None:
            return None
        out.append(hit)
    return out


def register(root, tier_key):
    """把某一档登记进「鼠标属性 → 指针 → 方案」，返回 (方案名, 路径列表)。

    和 cursors/install.ps1 的 Install-Tier 逐字段对齐（那边是与其它皮肤
    比对出来的基准格式）：

      · 17 个槽位写 REG_EXPAND_SZ，值是该角色的绝对路径（先 .cur 后 .ani）；
      · (default) 写 REG_SZ 方案名，Scheme Source 写 DWORD 1；
      · Schemes 下新增「方案名 → 17 条绝对路径、**纯逗号**分隔、顺序固定」，
        类型 REG_EXPAND_SZ。这一条才是让方案出现在「鼠标属性」下拉框里的
        东西：只写槽位不写它，系统只会把当前指针换掉，方案列表里看不到。

    顺手摘掉本包别的档位残留的 Schemes 条目：守护会按当前 scale 把方案认
    回来，留着旧档只会让用户点了又被改回去。

    不广播（不调 SystemParametersInfo）：写方案条目本来就不改当前外观，
    广播反而会把用户正在用的内存级指针冲掉。
    """
    import winreg
    tier = next((t for t in cw.PACK_TIERS if t[0] == tier_key), None)
    if tier is None:
        raise RuntimeError('未知档位：%s' % tier_key)
    found = scheme_paths(root, tier_key)
    if found is None:
        raise RuntimeError('第 %s 档的 17 个角色不齐，没法登记方案' % tier_key)
    name = cw.scheme_display_name(tier)
    blob = ','.join(found)
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, cw.REG_CURSORS_PATH,
                            0, winreg.KEY_SET_VALUE) as k:
        for r, p in zip(cw.ROLES, found):
            winreg.SetValueEx(k, r[0], 0, winreg.REG_EXPAND_SZ, p)
        winreg.SetValueEx(k, '', 0, winreg.REG_SZ, name)
        winreg.SetValueEx(k, 'Scheme Source', 0, winreg.REG_DWORD, 1)
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, cw.REG_SCHEMES_PATH,
                            0, winreg.KEY_SET_VALUE) as k:
        winreg.SetValueEx(k, name, 0, winreg.REG_EXPAND_SZ, blob)
        for other in cw.PACK_TIERS:
            if other[0] == tier_key:
                continue
            try:
                winreg.DeleteValue(k, cw.scheme_display_name(other))
            except OSError:
                pass
    return name, found
