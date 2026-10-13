# -*- coding: utf-8 -*-
"""判定用户截图的像素比例：用标题栏高度做标尺（SM_CYCAPTION=29 @125% DPI，23 @100%）。"""
import os
from PIL import Image
OUT = r'G:\ArknightsCursorExtract\_diag\gameptr'
im = Image.open(os.path.join(OUT, 'user_game.png')).convert('RGB')
w, h = im.size
px = im.load()
print('screenshot =', (w, h))

# 逐行统计：标题栏是浅色（含文字），客户区顶部是深色
print('row  meanL  dark_frac(<90)')
for y in range(0, 60):
    s = 0; dark = 0
    for x in range(0, w, 4):
        r, g, b = px[x, y]
        L = (r + g + b) // 3
        s += L
        if L < 90: dark += 1
    n = len(range(0, w, 4))
    print('%3d  %6.1f  %.3f' % (y, s/float(n), dark/float(n)))
