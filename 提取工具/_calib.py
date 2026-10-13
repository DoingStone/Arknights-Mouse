# -*- coding: utf-8 -*-
"""把游戏内实际指针 vs 工具在 0.75 比例（72px）下的渲染并排对比。"""
import os, sys
from PIL import Image, ImageDraw

TOOL = r'G:\ArknightsCursorExtract\CursorSizeTool\ArknightsCursorSize.pyw'
NAT = r'G:\ArknightsCursorExtract\CrystalCursorPack\extracted\Arknights_Crystal_Arrow_native96.png'
OUT = r'G:\ArknightsCursorExtract\_diag\gameptr'
import importlib.machinery
mod = importlib.machinery.SourceFileLoader('acsize', TOOL).load_module()

nat = Image.open(NAT).convert('RGBA')
game = Image.open(os.path.join(OUT, 'user_game.png')).convert('RGB')

# 游戏内指针区域（含阴影留白）
gsub = game.crop((328, 326, 328+197, 326+206))

SCALES = [0.50, 0.75, 1.00, 1.50]
tiles = []
for s in SCALES:
    size = int(round(96 * s))
    im = mod.premul_resize(nat, size)
    tiles.append((s, size, im))

# 画布：每格 200x210，深色背景
BG = (34, 36, 40)
CELL_W, CELL_H = 200, 210
sheet = Image.new('RGB', (CELL_W * (len(SCALES)+1), CELL_H + 26), BG)
d = ImageDraw.Draw(sheet)

def paste_cell(idx, img, label, hot=None):
    cell = Image.new('RGB', (CELL_W, CELL_H), BG)
    cw, ch = cell.size
    img = img.convert('RGBA')
    ox = (cw - img.width)//2
    oy = (ch - img.height)//2
    cell.paste(img, (ox, oy), img)
    cd = ImageDraw.Draw(cell)
    if hot:
        hx = ox + hot[0]; hy = oy + hot[1]
        cd.line([(hx-7, hy), (hx+7, hy)], fill=(255, 60, 60), width=1)
        cd.line([(hx, hy-7), (hx, hy+7)], fill=(255, 60, 60), width=1)
    sheet.paste(cell, (idx*CELL_W, 26))
    d.text((idx*CELL_W + 8, 8), label, fill=(255, 230, 120))

paste_cell(0, gsub, u'game (0.75 on screen)')
for i, (s, size, im) in enumerate(tiles):
    paste_cell(i+1, im, u'tool scale=%.2f -> %dpx' % (s, size),
               hot=(28*size//96, 20*size//96))

p = os.path.join(OUT, 'calibration.png')
sheet.save(p)
print('wrote', p, sheet.size)
