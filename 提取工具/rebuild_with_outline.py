# -*- coding: utf-8 -*-
"""给「浅底看不见」的角色补暗描边，并重打 art.bin 与四档 .cur/.ani。

为什么需要这个脚本
------------------
根因（实测，不是审美）：本包拖拽族 SizeAll / SizeNS / SizeWE / SizeNWSE /
SizeNESW 以及 Crosshair / Wait / IBeam 的美术是**纯近白色细线** —— 实心像素
（alpha≥200）最小亮度 117–183、暗像素占比 0.0%，整幅图连一个暗像素都没有。
在 Windows 常见的浅色背景（≈243）上最大对比只有 1.79–2.52，**没有任何一个
像素达到 WCAG 3.0**，所以日常拖动窗口时系统取用的 SizeAll 实际上看不见。
对照 Arrow：它自带 2.6% 的暗描边（min=20），最大对比 11.32，一直很清楚。

修法与程序侧完全一致：用「膨胀 alpha − 原 alpha」取形状外沿一圈环带，作为
描边色合成到原图**下层**；原图不透明像素逐一还原，因此已可见的角色像素级
零变化。程序侧 `cursorwin.frames_with_outline()` 做同一件事（内存光标），
本脚本把它固化到**磁盘上的 .cur/.ani 与 art.bin**（注册表方案指向的就是这些
文件，守护只比尺寸、不会因为美术变化而重下发，所以必须重新生成文件）。

用法： python 提取工具\\rebuild_with_outline.py
"""
import io
import json
import os
import shutil
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, '源码'))
sys.path.insert(0, HERE)

from PIL import Image, ImageChops, ImageFilter          # noqa: E402
from arkmouse import artpack, cursorwin as cw           # noqa: E402
import build_crystal_pack as B                          # noqa: E402

ART = os.path.join(ROOT, '源码', 'arkmouse', 'art.bin')
PACK = os.path.join(ROOT, '指针', 'cursors')
TIERS = [('small', 0.50, 'small'), ('medium', 2.0 ** -0.5, 'medium'),
         ('p72', 0.75, 'p72'), ('large', 1.00, 'large')]
ROLES = list(B.ROLE_ORDER)


def _load_source_ani():
    """源 .ani 的 anih / rate，用于**原样搬运**到重打出来的 .ani。

    踩过的坑：旧版这里把 anih 的 dispRate 写死成 1，rate 又误传了 art.bin 里的
    **毫秒**值（`pk.rates_ms()`），结果 No 的 dispRate 4→1（快 4 倍），
    AppStarting / Wait 的 rate 1→16（慢 16 倍）。两边帧数一致，整块照搬才精确。
    """
    p = os.path.join(B.OUT, 'before-install-backup.json')
    reg = json.load(open(p, encoding='utf-8'))
    roles = reg['current'] if 'current' in reg else reg
    out = {}
    for r in ROLES:
        v = roles.get(r)
        if not v:
            continue
        sp = v if os.path.isabs(v) else os.path.join(B.SRCDIR, v)
        if sp.lower().endswith('.ani') and os.path.exists(sp):
            _frames, anih, rate = B.read_ani(sp)
            out[r] = (anih, rate)
    return out


SRC_ANI = _load_source_ani()


def rebuild_artbin(frames_by_role, hotspot_by_role, rate_by_role, path):
    """按 _artpack.py 的格式重写 art.bin（magic + jlen + json + png 拼接）。"""
    blobs, index = [], {}
    for key in ROLES:
        frames = frames_by_role.get(key)
        if not frames:
            continue
        hx, hy = hotspot_by_role[key]
        idx = []
        for (im, _a, _b) in frames:
            b = io.BytesIO()
            im.convert('RGBA').save(b, 'PNG', optimize=True)
            data = b.getvalue()
            idx.append([0, len(data)])
            blobs.append(data)
        rate = rate_by_role.get(key)
        if rate and len(rate) != len(frames):
            rate = None
        index[key] = {'hot': [hx, hy], 'rate': rate, 'frames': idx}
    payload = b''.join(blobs)
    pos = 0
    for info in index.values():
        for item in info['frames']:
            item[0] = pos
            pos += item[1]
    jdata = json.dumps(index, ensure_ascii=False,
                       separators=(',', ':')).encode('utf-8')
    with open(path, 'wb') as f:
        f.write(b'AKPT1\x00\x00\x00')
        f.write(struct.pack('<I', len(jdata)))
        f.write(jdata)
        f.write(payload)
    return len(index), len(blobs), len(jdata), len(payload), os.path.getsize(path)


def main():
    pk = artpack.load(ART)
    print('读入 %s' % ART)

    # ---- 1) 取出 96px 原生帧，按判据补描边 -------------------------------
    frames_by_role, hotspot_by_role, rate_by_role = {}, {}, {}
    fixed, kept = [], []
    for key in ROLES:
        frames = pk.frames(key)
        if not frames:
            print('  跳过 %-12s（art.bin 里没有）' % key)
            continue
        im0 = frames[0][0]
        if cw.needs_outline(im0):
            frames = [(cw.add_outline(im), hx, hy) for (im, hx, hy) in frames]
            fixed.append(key)
            tag = '补描边'
        else:
            kept.append(key)
            tag = '保持原样'
        hotspot_by_role[key] = list(pk.hotspot(key))
        # art.bin 存的是**毫秒**（引擎 `cursorwin.py:756` 取平均当每帧节拍）。
        # 源 .ani 没有 rate 数组时 `rates_ms()` 返回 None，引擎会退回写死的
        # 20ms —— 对 dispRate=4 的 No 来说就是 3.3 倍速。这里按源 dispRate
        # （jiffies，1/60 s）补出真实毫秒，别让写死的默认值生效。
        _rate = pk.rates_ms(key)
        _src = SRC_ANI.get(key)
        if not _rate and _src:
            _rate = [int(round(_src[0][7] * 1000.0 / 60.0))] * len(frames)
        rate_by_role[key] = _rate
        frames_by_role[key] = frames
        print('  %-12s %-8s %3d 帧  实心最小亮度=%3d'
              % (key, tag, len(frames), cw._solid_min_luma(im0)))
    print('\n  补描边 %d 个：%s' % (len(fixed), ' '.join(fixed)))
    print('  未改动 %d 个：%s\n' % (len(kept), ' '.join(kept)))

    # ---- 2) 重写 art.bin --------------------------------------------------
    bak = ART + '.bak_before_outline'
    if not os.path.exists(bak):
        shutil.copy2(ART, bak)
        print('已备份 %s' % bak)
    n_role, n_frame, jlen, plen, size = rebuild_artbin(
        frames_by_role, hotspot_by_role, rate_by_role, ART)
    print('写出 %s  角色 %d · 帧 %d · 索引 %d B · 载荷 %d B · 合计 %d B (%.2f MB)\n'
          % (ART, n_role, n_frame, jlen, plen, size, size / 1048576.0))

    # ---- 3) 重打四档 .cur / .ani -----------------------------------------
    total = 0
    for tier, gain, suffix in TIERS:
        dst = os.path.join(PACK, tier)
        os.makedirs(dst, exist_ok=True)
        n = 0
        for key in ROLES:
            frames = frames_by_role.get(key)
            if not frames:
                continue
            hx, hy = hotspot_by_role[key]
            src96 = frames[0][0]
            animated = len(frames) > 1
            if animated:
                # 每帧按档位摆到 96 画布上
                out_frames = [B.place(im, gain, B.NATIVE, hx, hy)[0]
                              for (im, _a, _b) in frames]
                # anih = (cbSize, nFrames, nSteps, w, h, bpp, planes, dispRate, flags)
                # dispRate 与 rate 一律照搬源 .ani：write_ani 只会把
                # nFrames/nSteps 换成实际帧数，其余字段原样写出。
                _src = SRC_ANI.get(key)
                if _src:
                    anih, rate = _src[0][:9], _src[1]
                else:
                    anih, rate = (36, 0, 0, 0, 0, 32, 1, 1, 1), None
                p = os.path.join(dst, 'Arknights_Crystal_%s_%s.ani' % (key, suffix))
                nb = B.write_ani(p, [(im, hx, hy) for im in out_frames], anih, rate)
                print('  %-6s %-12s ANI %3d 帧  %8d B' % (tier, key, len(out_frames), nb))
            else:
                # 每档画布不同，热点必须跟着画布一起缩放：place() 返回
                # (图, 该画布下的 hotx, hoty)，必须用它返回的热点，不能用 96 档的
                # 原始热点 —— 否则 32px 光栅也会写 hot=(28,20)，Windows 直接读
                # 这些 .cur 时（方案被系统重新加载）指针尖会偏掉。
                placed = [B.place(src96, gain, N, hx, hy) for N in B.STATIC_RASTERS]
                p = os.path.join(dst, 'Arknights_Crystal_%s_%s.cur' % (key, suffix))
                nb = B.write_cur(p, list(placed))
                print('  %-6s %-12s CUR %2d 光栅 %8d B  96px热点=(%d,%d)'
                      % (tier, key, len(placed), nb, hx, hy))
            total += nb
            n += 1
        print('  -> %s : %d 个文件\n' % (tier, n))
    print('四档共写出 %.2f MB' % (total / 1048576.0))


if __name__ == '__main__':
    main()
