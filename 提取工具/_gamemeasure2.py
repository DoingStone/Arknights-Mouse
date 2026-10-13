# -*- coding: utf-8 -*-
"""再分析 game_shot_0/1：先判断游戏画面是否被 BitBlt 抓到（还是全黑），
再降低阈值找游戏自绘的白色水晶指针，量它的大小。
"""
import os
from collections import deque

from PIL import Image, ImageStat

DIAG = r'G:\ArknightsCursorExtract\_diag'
OUT = os.path.join(DIAG, 'gameptr')
WIN = (310, 172, 2248, 1299)   # 游戏窗口矩形

for n in ('game_shot_0.png', 'game_shot_1.png'):
    p = os.path.join(DIAG, n)
    if not os.path.exists(p):
        continue
    im = Image.open(p).convert('RGB')
    crop = im.crop(WIN)
    st = ImageStat.Stat(crop)
    ex = crop.getextrema()
    print('=== %s  窗口 %dx%d ===' % (n, crop.width, crop.height))
    print('  mean RGB =', [round(v, 1) for v in st.mean])
    print('  通道极值 =', ex)
    px = crop.load()
    w, h = crop.size
    # 直方图：亮度分布
    hist = [0] * 8
    for y in range(0, h, 2):
        for x in range(0, w, 2):
            r, g, b = px[x, y]
            hist[((r + g + b) // 3) // 32] += 1
    tot = sum(hist) or 1
    print('  亮度直方图(每32一档) =',
          ['%.2f%%' % (v * 100.0 / tot) for v in hist])
    # 亮且中性
    for thr in (200, 165, 140, 110):
        m = bytearray(w * h)
        n_px = 0
        for y in range(h):
            row = y * w
            for x in range(w):
                r, g, b = px[x, y]
                if (r + g + b) // 3 >= thr and max(r, g, b) - min(r, g, b) <= 40:
                    m[row + x] = 1
                    n_px += 1
        print('  thr=%3d -> 亮中性 %d px (%.3f%%)'
              % (thr, n_px, n_px * 100.0 / (w * h)))
        if thr != 140 or n_px == 0:
            continue
        # 连通块
        seen = bytearray(w * h)
        boxes = []
        for i in range(w * h):
            if not m[i] or seen[i]:
                continue
            q = deque([i])
            seen[i] = 1
            cnt = 0
            x0, y0, x1, y1 = w, h, -1, -1
            while q:
                j = q.popleft()
                y, x = divmod(j, w)
                cnt += 1
                x0 = min(x0, x)
                x1 = max(x1, x)
                y0 = min(y0, y)
                y1 = max(y1, y)
                for dy in (-1, 0, 1):
                    yy = y + dy
                    if yy < 0 or yy >= h:
                        continue
                    for dx in (-1, 0, 1):
                        xx = x + dx
                        if xx < 0 or xx >= w:
                            continue
                        k = yy * w + xx
                        if m[k] and not seen[k]:
                            seen[k] = 1
                            q.append(k)
            if cnt >= 60:
                boxes.append((cnt, x0, y0, x1, y1))
        boxes.sort(reverse=True)
        print('    thr=140 连通块>=60px 共 %d 个，前 15：' % len(boxes))
        for cnt, x0, y0, x1, y1 in boxes[:15]:
            print('      %dx%d @(%d,%d) px=%d  屏幕@(%d,%d)'
                  % (x1 - x0 + 1, y1 - y0 + 1, x0, y0, cnt,
                     WIN[0] + x0, WIN[1] + y0))
        if boxes:
            cnt, x0, y0, x1, y1 = boxes[0]
            pad = 40
            box = (max(0, x0 - pad), max(0, y0 - pad),
                   min(w, x1 + pad), min(h, y1 + pad))
            sub = crop.crop(box)
            tag = n.replace('.png', '') + '_bigblob'
            sub.save(os.path.join(OUT, tag + '.png'))
            sub.resize((sub.width * 3, sub.height * 3), Image.NEAREST).save(
                os.path.join(OUT, tag + '_3x.png'))
            print('    已存 %s.png / _3x.png' % tag)
    print()

# 附：把 game_window.png 顶部缩略看一眼（先前结论：那是 DSH 界面）
p = os.path.join(DIAG, 'game_window.png')
if os.path.exists(p):
    im = Image.open(p).convert('RGB')
    im.resize((im.width // 3, im.height // 3), Image.LANCZOS).save(
        os.path.join(OUT, 'gw_thumb.png'))
    st = ImageStat.Stat(im)
    print('game_window.png %dx%d mean=%s' % (im.width, im.height,
                                             [round(v, 1) for v in st.mean]))
