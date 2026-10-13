# -*- coding: utf-8 -*-
"""最终定标确认：把 96px 原生美术按 1.20 比例合成到游戏背景上，
与游戏截图并排 + 50% 叠加，肉眼判定是否完全重合。"""
import os, importlib.machinery
from PIL import Image, ImageDraw

TOOL = r'G:\ArknightsCursorExtract\CursorSizeTool\ArknightsCursorSize.pyw'
NAT  = r'G:\ArknightsCursorExtract\CrystalCursorPack\extracted\Arknights_Crystal_Arrow_native96.png'
OUT  = r'G:\ArknightsCursorExtract\_diag\gameptr'
mod = importlib.machinery.SourceFileLoader('acsize', TOOL).load_module()
nat = Image.open(NAT).convert('RGBA')
game = Image.open(os.path.join(OUT, 'user_game.png')).convert('RGB')

GX, GY, GW2, GH2 = 328, 326, 197, 206
gsub = game.crop((GX, GY, GX+GW2, GY+GH2))
# 实测最佳偏移（scale=1.20）：ox=37, oy=48 相对裁剪左上
OX, OY, SCALE = 37, 48, 1.20

def render_on(size, canvas, ox, oy, a_scale=1.0, bg=(27, 27, 27)):
    im = mod.premul_resize(nat, size)
    if a_scale != 1.0:
        a = im.getchannel('A').point(lambda v: min(255, int(v * a_scale)))
        im.putalpha(a)
    c = Image.new('RGB', canvas, bg)
    c.paste(im, (ox, oy), im)
    return c

size = int(round(96 * SCALE))
print('scale=%.2f -> %dpx' % (SCALE, size))

# 面板 1: 游戏原图  2: 工具 1.20 合成  3: 叠加 50%
rows = []
g1 = gsub
g2 = render_on(size, (GW2, GH2), OX, OY)
g3 = Image.blend(g1.convert('RGB'), g2, 0.5)
pad = 12
ZW, ZH = 20, 30
sheet = Image.new('RGB', ((GW2*3 + pad*4), GH2 + pad*2 + ZH), (24, 25, 28))
d = ImageDraw.Draw(sheet)
for i, (img, lab) in enumerate([(g1, u'game screenshot (1:1)'),
                                (g2, u'tool scale=1.20 -> 115px'),
                                (g3, u'overlay 50%')]):
    x = pad + i * (GW2 + pad)
    sheet.paste(img, (x, ZH + pad))
    d.text((x + 2, 9), lab, fill=(255, 220, 110))
p = os.path.join(OUT, 'calib_final.png')
sheet.save(p)
print('wrote', p, sheet.size)

# 4x 放大版，便于看边缘
big = sheet.resize((sheet.width*2, sheet.height*2), Image.NEAREST)
big.save(os.path.join(OUT, 'calib_final_2x.png'))
print('wrote calib_final_2x.png', big.size)
