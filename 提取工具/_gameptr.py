# -*- coding: utf-8 -*-
"""从已抓取的【游戏窗口截图】中直接量出游戏自绘指针的像素尺寸。

关键前提：游戏把指针画进自己的渲染表面，所以 BitBlt 抓游戏窗口是能抓到指针的
（与系统光标叠加层不同）。
做法：在窗口截图中找【接近白色、且周围有深色背景】的连通块，取最大的那些，
做形态筛选（水晶指针有细长尖刺 + 下方块状体）。
"""
import json
import os
from collections import deque

from PIL import Image

DIAG = r'G:\ArknightsCursorExtract\_diag'
CAND = ['game_window.png', 'game_shot_0.png', 'game_shot_1.png']


def load(name):
    p = os.path.join(DIAG, name)
    if not os.path.exists(p):
        return None, p
    return Image.open(p).convert('RGB'), p


def blobs(im, thresh=170, minpx=25, maxpx=9000, maxblobs=40):
    w, h = im.size
    px = im.load()
    seen = bytearray(w * h)
    out = []
    for y0 in range(h):
        for x0 in range(w):
            i0 = y0 * w + x0
            if seen[i0]:
                continue
            r, g, b = px[x0, y0]
            if not (r >= thresh and g >= thresh and b >= thresh):
                continue
            q = deque([(x0, y0)])
            seen[i0] = 1
            n = 0
            x1 = x2 = x0
            y1 = y2 = y0
            while q:
                x, y = q.popleft()
                n += 1
                if x < x1:
                    x1 = x
                if x > x2:
                    x2 = x
                if y < y1:
                    y1 = y
                if y > y2:
                    y2 = y
                if n > maxpx:
                    break
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    a, c = x + dx, y + dy
                    if 0 <= a < w and 0 <= c < h:
                        j = c * w + a
                        if not seen[j]:
                            rr, gg, bb = px[a, c]
                            if rr >= thresh and gg >= thresh and bb >= thresh:
                                seen[j] = 1
                                q.append((a, c))
            if minpx <= n <= maxpx:
                bw, bh = x2 - x1 + 1, y2 - y1 + 1
                fill = n / float(bw * bh)
                out.append({'n': n, 'box': [x1, y1, bw, bh], 'fill': round(fill, 3),
                            'cx': (x1 + x2) // 2, 'cy': (y1 + y2) // 2})
    out.sort(key=lambda d: -d['n'])
    return out[:maxblobs]


print('=== 在游戏窗口截图里找亮色连通块 ===')
report = {}
for name in CAND:
    im, p = load(name)
    if im is None:
        print('  %-18s 不存在' % name)
        continue
    print()
    print('  --- %s  %dx%d ---' % (name, im.size[0], im.size[1]))
    bl = blobs(im)
    print('      找到 %d 个候选（按像素数降序，前 12 个）:' % len(bl))
    for d in bl[:12]:
        print('        n=%-6d box=%-22s fill=%-6s 中心=(%d,%d)' % (
            d['n'], str(d['box']), d['fill'], d['cx'], d['cy']))
    # 形态筛选：指针候选应当是「宽高都在 20..200」且「不是满块矩形」
    ptr = [d for d in bl
           if 20 <= d['box'][2] <= 220 and 20 <= d['box'][3] <= 220
           and d['fill'] < 0.75]
    print('      形态筛选后（20..220px 且非实心）:')
    for d in ptr[:8]:
        print('        n=%-6d box=%-22s fill=%-6s 中心=(%d,%d)' % (
            d['n'], str(d['box']), d['fill'], d['cx'], d['cy']))
    report[name] = {'size': im.size, 'blobs': bl[:20], 'pointer_like': ptr[:8]}

# 若有候选，裁剪放大以便目视
for name, rec in report.items():
    for k, d in enumerate(rec['pointer_like'][:3]):
        im, _ = load(name)
        x, y, bw, bh = d['box']
        pad = 12
        box = (max(0, x - pad), max(0, y - pad),
               min(im.size[0], x + bw + pad), min(im.size[1], y + bh + pad))
        crop = im.crop(box)
        f = max(1, int(140 / max(1, max(crop.size))))
        big = crop.resize((crop.size[0] * f, crop.size[1] * f), Image.NEAREST)
        outn = 'gameptr_%s_%d_x%d.png' % (name.replace('.png', ''), k, f)
        big.save(os.path.join(DIAG, outn))
        print('  写出 %s  (%dx%d)' % (outn, big.size[0], big.size[1]))

with open(os.path.join(DIAG, 'gameptr_measure.json'), 'w',
          encoding='utf-8') as f:
    json.dump(report, f, ensure_ascii=False, indent=1)
print()
print('写入 _diag\\gameptr_measure.json')
