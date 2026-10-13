# -*- coding: utf-8 -*-
"""从全屏截图里找出游戏自绘的指针，量出它在屏幕上的真实像素尺寸。

原理：全屏抓图含应用自己画进 framebuffer 的内容，但不含系统光标叠加层。
所以这里找到的指针 = 游戏自己画的；找不到 = 游戏用的是系统光标。
"""
import os
import sys
from collections import deque

from PIL import Image

DIAG = r'G:\ArknightsCursorExtract\_diag'
OUT = os.path.join(DIAG, 'gameptr')
ART = r'G:\ArknightsCursorExtract\CrystalCursorPack\extracted'
GAME_ART = r'G:\ArknightsCursorExtract\extracted'

# 游戏窗口矩形（先前实测）
WIN = (310, 172, 2248, 1299)


def load_art():
    """返回 [(名字, RGBA 图)] —— 候选指针美术。"""
    cands = []
    for name in ('Arrow', 'Pin', 'Person', 'Help'):
        p = os.path.join(ART, 'Arknights_Crystal_%s_native96.png' % name)
        if os.path.exists(p):
            cands.append(('crystal_' + name, Image.open(p).convert('RGBA')))
    for name in ('cursor_large', 'cursor_medium', 'cursor_small'):
        p = os.path.join(GAME_ART, name + '.png')
        if os.path.exists(p):
            cands.append(('game_' + name, Image.open(p).convert('RGBA')))
    return cands


def bright_mask(im, thr=165, neutral=34):
    """亮且接近中性色的像素（排除黄色球体与彩色 UI）。"""
    w, h = im.size
    px = im.load()
    m = bytearray(w * h)
    for y in range(h):
        row = y * w
        for x in range(w):
            r, g, b = px[x, y][:3]
            if (r + g + b) // 3 < thr:
                continue
            if max(r, g, b) - min(r, g, b) > neutral:
                continue
            m[row + x] = 1
    return m


def components(mask, w, h, minpx=180, maxpx=40000):
    """连通块（8 邻域）→ [(x0,y0,x1,y1,n)]"""
    seen = bytearray(w * h)
    out = []
    for i in range(w * h):
        if not mask[i] or seen[i]:
            continue
        q = deque([i])
        seen[i] = 1
        n = 0
        x0, y0, x1, y1 = w, h, -1, -1
        while q:
            j = q.popleft()
            y, x = divmod(j, w)
            n += 1
            if x < x0:
                x0 = x
            if x > x1:
                x1 = x
            if y < y0:
                y0 = y
            if y > y1:
                y1 = y
            for dy in (-1, 0, 1):
                yy = y + dy
                if yy < 0 or yy >= h:
                    continue
                for dx in (-1, 0, 1):
                    xx = x + dx
                    if xx < 0 or xx >= w:
                        continue
                    k = yy * w + xx
                    if mask[k] and not seen[k]:
                        seen[k] = 1
                        q.append(k)
        if minpx <= n <= maxpx:
            out.append((x0, y0, x1, y1, n))
    return out


def sil(art, w, h):
    """把美术的 alpha 轮廓归一化成 w×h 的 0/1 掩码（保持长宽比，居中）。"""
    a = art.getchannel('A')
    aw, ah = a.size
    # 先裁到不透明包围盒
    bb = a.getbbox()
    if bb:
        a = a.crop(bb)
        aw, ah = a.size
    k = min(w / float(aw), h / float(ah))
    nw, nh = max(1, int(round(aw * k))), max(1, int(round(ah * k)))
    a = a.resize((nw, nh), Image.LANCZOS)
    out = [0] * (w * h)
    ox, oy = (w - nw) // 2, (h - nh) // 2
    ap = a.load()
    for y in range(nh):
        row = (y + oy) * w + ox
        for x in range(nw):
            if ap[x, y] >= 128:
                out[row + x] = 1
    return out


def iou(a, b):
    inter = union = 0
    for i in range(len(a)):
        if a[i] or b[i]:
            union += 1
            if a[i] and b[i]:
                inter += 1
    return inter / float(union) if union else 0.0


def main():
    shots = [os.path.join(DIAG, n) for n in ('game_shot_0.png', 'game_shot_1.png',
                                             'screen_full.png')]
    shots = [p for p in shots if os.path.exists(p)]
    arts = load_art()
    print('候选美术:', [n for n, _ in arts])
    print('截图:', [os.path.basename(p) for p in shots])
    if not os.path.isdir(OUT):
        os.makedirs(OUT)

    for sp in shots:
        full = Image.open(sp).convert('RGB')
        W, H = full.size
        x0, y0, x1, y1 = WIN
        x0, y0 = max(0, x0), max(0, y0)
        x1, y1 = min(W, x1), min(H, y1)
        crop = full.crop((x0, y0, x1, y1))
        # 2 倍降采样加速
        small = crop.resize((crop.width // 2, crop.height // 2), Image.BILINEAR)
        w, h = small.size
        print()
        print('=== %s  窗口裁剪 %dx%d -> 分析 %dx%d ==='
              % (os.path.basename(sp), crop.width, crop.height, w, h))
        thr = 165
        m = bright_mask(small, thr)
        comps = components(m, w, h)
        comps.sort(key=lambda c: -(c[4]))
        print('  亮中性连通块 %d 个（前 12）:' % len(comps))
        for c in comps[:12]:
            bw, bh = c[2] - c[0] + 1, c[3] - c[1] + 1
            print('    box=(%d,%d)-(%d,%d) %dx%d px=%d'
                  % (c[0], c[1], c[2], c[3], bw, bh, c[4]))
        if not comps:
            print('  -> 没有亮块；提高/降低阈值再试')
            continue
        # 对最大的若干块做形状匹配
        best = []
        for c in comps[:200]:
            bw, bh = c[2] - c[0] + 1, c[3] - c[1] + 1
            if bw < 8 or bh < 8:
                continue
            sub = [0] * (bw * bh)
            for y in range(bh):
                srcrow = (c[1] + y) * w + c[0]
                for x in range(bw):
                    sub[y * bw + x] = m[srcrow + x]
            for name, art in arts:
                s = sil(art, bw, bh)
                v = iou(s, sub)
                if v > 0.60:
                    best.append((v, name, c, bw, bh))
        best.sort(key=lambda t: -t[0])
        print('  形状匹配 IoU>0.60 的命中 %d 个:' % len(best))
        for v, name, c, bw, bh in best[:10]:
            # 屏幕坐标（原图尺度）
            print('    IoU=%.3f  %s  box=(%d,%d) %dx%d  -> 屏幕 %dx%d @ (%d,%d)'
                  % (v, name, c[0], c[1], bw, bh, bw * 2, bh * 2,
                     x0 + c[0] * 2, y0 + c[1] * 2))
            tag = '%s_%s_%d_%d' % (os.path.basename(sp)[:12], name, c[0], c[1])
            box = (x0 + c[0] * 2 - 12, y0 + c[1] * 2 - 12,
                   x0 + (c[2] + 1) * 2 + 12, y0 + (c[3] + 1) * 2 + 12)
            box = (max(0, box[0]), max(0, box[1]),
                   min(W, box[2]), min(H, box[3]))
            full.crop(box).save(os.path.join(OUT, tag + '.png'))
        # 也存一张整窗缩略图供目视
        if sp.endswith('game_shot_0.png'):
            crop.resize((crop.width // 4, crop.height // 4),
                        Image.LANCZOS).save(os.path.join(OUT, 'window_thumb.png'))
            print('  已存 window_thumb.png')


if __name__ == '__main__':
    sys.exit(main() or 0)
