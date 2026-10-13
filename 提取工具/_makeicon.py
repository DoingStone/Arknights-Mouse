# -*- coding: utf-8 -*-
"""从水晶指针美术生成 exe 图标 app.ico（多尺寸）。"""
import os
import sys

from PIL import Image

SRC = r'E:\Qianmory\Desktop\Mouse\源码\arkmouse'
sys.path.insert(0, SRC)
import artpack  # noqa: E402

OUT = r'E:\Qianmory\Desktop\Mouse\构建\app.ico'
os.makedirs(os.path.dirname(OUT), exist_ok=True)

pk = artpack.load(os.path.join(SRC, 'art.bin'))
im, hx, hy = pk.frames('Arrow')[0]
im = im.convert('RGBA')

# 裁到内容 + 一点边距，做成方形画布
bbox = im.split()[3].getbbox()
art = im.crop(bbox)
w, h = art.size
side = max(w, h)
pad = int(side * 0.10)
canvas = Image.new('RGBA', (side + 2 * pad, side + 2 * pad), (0, 0, 0, 0))
# 让指针尖端落在中心，视觉更自然
canvas.paste(art, (pad + (side - w) // 2, pad + (side - h) // 2), art)

sizes = [16, 24, 32, 48, 64, 128, 256]
canvas.save(OUT, format='ICO', sizes=[(s, s) for s in sizes])
print('wrote', OUT, os.path.getsize(OUT), 'B  from', os.path.basename('Arrow'),
      'bbox', bbox, 'canvas', canvas.size)
