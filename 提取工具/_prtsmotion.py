# -*- coding: utf-8 -*-
import os, re, struct
from PIL import Image

OUT = r'G:\ArknightsCursorExtract\_diag\gameptr'
im = Image.open(os.path.join(OUT, 'user_game.png')).convert('RGB')
px = im.load()
# 水晶指针所在区域（cand_a）
X0, Y0 = 328, 326
sub = im.crop((X0, Y0, X0+197, Y0+206))
sp = sub.load()
print('=== 游戏内指针 bbox（多阈值）===')
for thr in (60, 90, 120, 150, 180):
    x0, y0, x1, y1, n = 999, 999, -1, -1, 0
    for y in range(sub.height):
        for x in range(sub.width):
            r, g, b = sp[x, y]
            if (r+g+b)//3 >= thr and max(r,g,b)-min(r,g,b) <= 45:
                n += 1
                x0=min(x0,x); x1=max(x1,x); y0=min(y0,y); y1=max(y1,y)
    if x1 >= 0:
        print('  thr=%3d -> %3dx%-3d  px=%d' % (thr, x1-x0+1, y1-y0+1, n))

print()
print('=== PRTS-Motion-96.exe 可解字符串（含 size/app 相关）===')
exe = r'C:\Users\22442\AppData\Local\PRTS\Replica-v8-Windows\PRTS-Motion-96.exe'
raw = open(exe, 'rb').read()
# ASCII
asc = re.findall(rb'[\x20-\x7e]{5,}', raw)
# UTF-16LE
u16 = re.findall(rb'(?:[\x20-\x7e]\x00){5,}', raw)
keys = ('size', 'Size', 'cursor', 'Cursor', 'app', 'App', 'window', 'Window',
        'scale', 'Scale', 'game', 'Arknights', 'reapply', 'base', 'dpi', 'DPI',
        'CreateIcon', 'SetSystemCursor', 'LoadCursor', 'reg', 'Reg', 'ini', 'json')
seen = set()
hits = []
for b in list(asc) + [x.replace(b'\x00', b'') for x in u16]:
    try:
        s = b.decode('ascii', 'ignore')
    except Exception:
        continue
    if len(s) < 5 or s in seen:
        continue
    if any(k in s for k in keys):
        seen.add(s)
        hits.append(s)
for s in sorted(hits)[:70]:
    print('  ', s)
print('  total hits =', len(hits))
