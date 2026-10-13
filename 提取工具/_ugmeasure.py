# -*- coding: utf-8 -*-
import os
from collections import deque
from PIL import Image, ImageStat

A = r'C:\Users\22442\.dsh\attachments\v1\objects'
SRC = None
for root, dirs, files in os.walk(A):
    for f in files:
        p = os.path.join(root, f)
        try:
            im = Image.open(p)
        except Exception:
            continue
        if (im.width, im.height) == (1922, 1119):
            SRC = p
            break
print('game screenshot:', SRC)
OUT = r'G:\ArknightsCursorExtract\_diag\gameptr'
os.makedirs(OUT, exist_ok=True)
im = Image.open(SRC).convert('RGB')
im.save(os.path.join(OUT, 'user_game.png'))
print('mean =', [round(v,1) for v in ImageStat.Stat(im).mean])

# The crystal cursor is bright grey/white on a dark background region.
px = im.load(); w, h = im.size
m = bytearray(w*h)
for y in range(h):
    row = y*w
    for x in range(w):
        r, g, b = px[x, y]
        if (r+g+b)//3 >= 120 and max(r,g,b)-min(r,g,b) <= 40:
            m[row+x] = 1
seen = bytearray(w*h); boxes = []
for i in range(w*h):
    if not m[i] or seen[i]: continue
    q = deque([i]); seen[i] = 1; cnt = 0
    x0,y0,x1,y1 = w,h,-1,-1
    while q:
        j = q.popleft(); y,x = divmod(j, w); cnt += 1
        x0=min(x0,x); x1=max(x1,x); y0=min(y0,y); y1=max(y1,y)
        for dy in (-1,0,1):
            yy=y+dy
            if yy<0 or yy>=h: continue
            for dx in (-1,0,1):
                xx=x+dx
                if xx<0 or xx>=w: continue
                k=yy*w+xx
                if m[k] and not seen[k]:
                    seen[k]=1; q.append(k)
    if cnt >= 40: boxes.append((cnt,x0,y0,x1,y1))
boxes.sort(reverse=True)
print('bright neutral blobs>=40px:', len(boxes))
for cnt,x0,y0,x1,y1 in boxes[:20]:
    print('   %3dx%-3d @(%4d,%4d) px=%d' % (x1-x0+1, y1-y0+1, x0, y0, cnt))
if boxes:
    cnt,x0,y0,x1,y1 = boxes[0]
    pad = 60
    box = (max(0,x0-pad), max(0,y0-pad), min(w,x1+pad), min(h,y1+pad))
    sub = im.crop(box); sub.save(os.path.join(OUT,'ug_blob0.png'))
    sub.resize((sub.width*3, sub.height*3), Image.NEAREST).save(os.path.join(OUT,'ug_blob0_3x.png'))
    print('saved ug_blob0*.png  box=', box)
