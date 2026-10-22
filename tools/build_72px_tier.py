# -*- coding: utf-8 -*-
"""从现成的 large 档派生「0.75× / 72px」档。

背景
----
`指针\\cursors` 原本只有 小/中/大 三档（gain 0.50 / 0.7071 / 1.00）。
程序里 `scale=0.75` 时现场渲染的是 96×0.75 = **72px** 的指针，但注册进
Windows 方案的却一直是 `large` 档（96px 观感）—— 登记的和实际显示的不是一回事。

本脚本补出 72px 档：`指针\\cursors\\p72\\Arknights_Crystal_<Role>_p72.cur|.ani`。

为什么不用 G: 里的原始素材
--------------------------
`build_crystal_pack.py` 的源是本机已安装的 PRTS Replica v8，那个目录已经不在了
（`C:\\Users\\...\\PRTS\\Replica-v8-Windows` 不存在）。但没关系：

  large 档的 gain = 1.0，所以它 **96px 画布上的那块图就是原生素材本身**
  （place() 里 s = 1.0、m = 96，resize_rgba 尺寸相同直接 copy，不重采样），
  热点也等于原生热点（hx = round(hsx*96/96) = hsx）。

所以拿 large 档的 96px 光栅当母版，再用同一套 place()/cur_blob()/write_ani()
按 gain 0.75 重新摆放，得到的等价于「直接拿原生素材跑一遍 0.75 档」。

档位语义（与 build_crystal_pack.py 一致）
----------------------------------------
视觉大小 = gain × 96px。gain 0.75 → 72px，正是程序 scale 0.75 的观感。
.ani 画布恒为 96（art = gain×96 = 72px）；.cur 画布取 STATIC_RASTERS，
每张画布上 art = gain×N。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_crystal_pack as B          # noqa: E402  复用生产版写入器

PACK = r'E:\Qianmory\Desktop\Mouse\指针\cursors'
SRC_TIER = 'large'
DST_TIER = 'p72'
GAIN = 0.75
SUFFIX = 'p72'


def main():
    src = os.path.join(PACK, SRC_TIER)
    dst = os.path.join(PACK, DST_TIER)
    os.makedirs(dst, exist_ok=True)

    print('源档位 : %s  (gain 1.0 → 96px 画布上的图就是原生素材)' % src)
    print('目标档 : %s  gain=%.2f  → 视觉 %dpx' % (dst, GAIN, int(round(GAIN * B.NATIVE))))
    print('')

    total = 0
    for role in B.ROLE_ORDER:
        sfile = None
        for ext in ('.cur', '.ani'):
            p = os.path.join(src, 'Arknights_Crystal_%s_%s%s' % (role, SRC_TIER, ext))
            if os.path.isfile(p):
                sfile, sext = p, ext
                break
        if not sfile:
            print('  跳过 %-12s（large 档无此角色）' % role)
            continue

        if sext == '.cur':
            art, hx, hy = B.raster_of(sfile, B.NATIVE)
            rasters = [B.place(art, GAIN, N, hx, hy) for N in B.STATIC_RASTERS]
            out = os.path.join(dst, 'Arknights_Crystal_%s_%s.cur' % (role, SUFFIX))
            nb = B.write_cur(out, rasters)
            print('  %-12s CUR  %2d 张光栅 %s  热点=(%d,%d)  %d B'
                  % (role, len(rasters), B.STATIC_RASTERS, hx, hy, nb))
        else:
            frames_raw, anih, rate = B.read_ani(sfile)
            # read_ani 的每帧是 (RGBA, hsx, hsy, 光栅宽) —— 第 4 位只是尺寸，丢掉
            frames = [B.place(im, GAIN, B.NATIVE, fx, fy) for (im, fx, fy, _w) in frames_raw]
            out = os.path.join(dst, 'Arknights_Crystal_%s_%s.ani' % (role, SUFFIX))
            nb = B.write_ani(out, frames, anih, rate)
            print('  %-12s ANI  %2d 帧 画布 %d  热点=(%d,%d)  %d B'
                  % (role, len(frames), B.NATIVE, frames_raw[0][1], frames_raw[0][2], nb))
        total += nb

    n = len(os.listdir(dst))
    print('')
    print('写出 %d 个文件，共 %.2f MB' % (n, total / 1048576.0))
    if n != len(B.ROLE_ORDER):
        raise SystemExit('角色数不对：%d != %d' % (n, len(B.ROLE_ORDER)))


if __name__ == '__main__':
    main()
