# -*- coding: utf-8 -*-
"""在游戏窗口截图里定位指针（用户截图里它在左上区域），裁出来目视 + 量尺寸。"""
import os

from PIL import Image

DIAG = r'G:\ArknightsCursorExtract\_diag'
p = os.path.join(DIAG, 'game_window.png')
im = Image.open(p).convert('RGB')
print('game_window.png =', im.size)

# 用户截图里指针在窗口内容左上 ~ (215,205)/(1041x621) -> 按窗口尺寸缩放
W, H = im.size
regions = [(0.10, 0.20, 0.35, 0.48), (0.0, 0.0, 0.5, 0.5), (0.6, 0.4, 0.9, 0.7)]
for i, (a, b, c, d) in enumerate(regions):
    box = (int(W * a), int(H * b), int(W * c), int(H * d))
    crop = im.crop(box)
    f = 2 if max(crop.size) < 900 else 1
    if f > 1:
        crop = crop.resize((crop.size[0] * f, crop.size[1] * f), Image.NEAREST)
    out = os.path.join(DIAG, 'gamewin_region_%d.png' % i)
    crop.save(out)
    print('  写出 %s  box=%s -> %s' % (os.path.basename(out), str(box),
                                     str(crop.size)))

# 全图缩略以便总览
th = im.copy()
th.thumbnail((1000, 1000))
th.save(os.path.join(DIAG, 'gamewin_thumb.png'))
print('  写出 gamewin_thumb.png', th.size)
