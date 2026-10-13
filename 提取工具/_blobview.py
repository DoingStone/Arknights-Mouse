# -*- coding: utf-8 -*-
"""核对三张截图的尺寸，并放大查看 screen_full 里那个 50x48 亮块。"""
import os

from PIL import Image

DIAG = r'G:\ArknightsCursorExtract\_diag'
OUT = os.path.join(DIAG, 'gameptr')

for n in ('game_shot_0.png', 'game_shot_1.png', 'screen_full.png',
          'game_window.png', 'gamewin_thumb.png'):
    p = os.path.join(DIAG, n)
    if os.path.exists(p):
        im = Image.open(p)
        print('%-20s %sx%s mode=%s' % (n, im.width, im.height, im.mode))

# 亮块在 screen_full 的坐标（原图尺度）
full = Image.open(os.path.join(DIAG, 'screen_full.png')).convert('RGB')
print()
print('screen_full size =', full.size)
bx0, by0, bx1, by1 = 310 + 876 * 2, 172 + 320 * 2, 310 + 901 * 2, 172 + 344 * 2
print('亮块原图坐标 = (%d,%d)-(%d,%d)  %dx%d'
      % (bx0, by0, bx1, by1, bx1 - bx0, by1 - by0))
pad = 60
box = (max(0, bx0 - pad), max(0, by0 - pad),
       min(full.width, bx1 + pad), min(full.height, by1 + pad))
crop = full.crop(box)
crop.save(os.path.join(OUT, 'blob_ctx.png'))
crop.resize((crop.width * 3, crop.height * 3), Image.NEAREST).save(
    os.path.join(OUT, 'blob_ctx_3x.png'))
tight = full.crop((bx0 - 8, by0 - 8, bx1 + 8, by1 + 8))
tight.resize((tight.width * 6, tight.height * 6), Image.NEAREST).save(
    os.path.join(OUT, 'blob_tight_6x.png'))
print('已存 blob_ctx.png / blob_ctx_3x.png / blob_tight_6x.png')

# 顺便量一下整窗缩略图里的亮块分布，看看是不是我在别的窗口上
print()
print('--- 全屏亮中性像素分布（每 200px 一格，看亮块集中在哪）---')
sm = full.resize((full.width // 8, full.height // 8), Image.BILINEAR)
px = sm.load()
gw, gh = sm.size
grid = {}
for y in range(gh):
    for x in range(gw):
        r, g, b = px[x, y]
        if (r + g + b) // 3 > 165 and max(r, g, b) - min(r, g, b) <= 34:
            k = (x * 8 // 200, y * 8 // 200)
            grid[k] = grid.get(k, 0) + 1
for k in sorted(grid, key=lambda k: -grid[k])[:14]:
    print('  格(%4d,%4d)~(%4d,%4d)  %d px'
          % (k[0] * 200, k[1] * 200, k[0] * 200 + 199, k[1] * 200 + 199,
             grid[k]))
