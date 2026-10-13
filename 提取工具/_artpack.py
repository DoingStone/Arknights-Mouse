# -*- coding: utf-8 -*-
"""把 17 个角色的全部美术帧打成一个自包含的 art.bin。

格式（小端）：
  magic  b'AKPT1\x00\x00\x00'         8 字节
  jlen   uint32                      JSON 索引长度
  jdata  jlen 字节的 UTF-8 JSON
  blobs  依次拼接的 PNG 数据

JSON 索引：
  {
    "roles": {
       "Arrow": {"hot": [28,20], "rate": null,
                 "frames": [[off, len], ...]},
       ...
    }
  }
rate 为 null 表示静态单帧；否则是每帧延时毫秒列表（长度 == 帧数）。
"""
import io
import json
import os
import struct
import sys

PACK = r'G:\ArknightsCursorExtract\CrystalCursorPack'
LARGE = os.path.join(PACK, 'cursors', 'large')
EXTRACTED = os.path.join(PACK, 'extracted')
OUT = sys.argv[1] if len(sys.argv) > 1 else r'G:\ArknightsCursorExtract\_build\art.bin'

sys.path.insert(0, r'G:\ArknightsCursorExtract\CursorSizeTool')
import importlib.machinery
mod = importlib.machinery.SourceFileLoader(
    'acsize', r'G:\ArknightsCursorExtract\CursorSizeTool\ArknightsCursorSize.pyw'
).load_module()

ROLES = [r[0] for r in mod.ROLES]

blobs = []
index = {}
missing = []

for key in ROLES:
    hs = mod._role_hotspot(key)
    ani = os.path.join(LARGE, 'Arknights_Crystal_%s_large.ani' % key)
    cur = os.path.join(LARGE, 'Arknights_Crystal_%s_large.cur' % key)
    png = os.path.join(EXTRACTED, 'Arknights_Crystal_%s_native96.png' % key)

    frames = []
    rate = None
    if os.path.exists(ani):
        fr, _d, r = mod.read_ani_frames(ani)
        frames = [(im, hx, hy) for (im, hx, hy) in fr]
        if r:
            rate = [max(10, int(v * 1000.0 / 60.0)) for v in r]
    elif os.path.exists(png):
        from PIL import Image
        frames = [(Image.open(png).convert('RGBA'), hs[0], hs[1])]
    elif os.path.exists(cur):
        with open(cur, 'rb') as f:
            im, hx, hy = mod.parse_cur_bytes(f.read())
        frames = [(im, hx, hy)]
    else:
        missing.append(key)
        continue

    if not frames:
        missing.append(key)
        continue

    hx, hy = frames[0][1], frames[0][2]
    # 强制统一热点为该角色的规范值（源 ANI 里各帧热点可能略有出入）
    hx, hy = hs[0], hs[1]

    idx = []
    for (im, _a, _b) in frames:
        b = io.BytesIO()
        im.convert('RGBA').save(b, 'PNG', optimize=True)
        data = b.getvalue()
        idx.append([len(blobs), len(data)])
        blobs.append(data)

    if rate and len(rate) != len(frames):
        rate = None
    index[key] = {'hot': [hx, hy], 'rate': rate, 'frames': idx}
    print('  %-12s %3d 帧  hot=(%d,%d)  rate=%s'
          % (key, len(frames), hx, hy,
             'None(静态/默认节拍)' if rate is None else '%d 项' % len(rate)))

if missing:
    print('!! 缺失角色:', missing)

offset = 0
flat = []
for data in blobs:
    flat.append(data)
payload = b''.join(flat)
# 偏移是按拼接后的绝对位置算的，重算一遍
pos = 0
for key, info in index.items():
    for item in info['frames']:
        item[0] = pos
        pos += item[1]

jdata = json.dumps(index, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, 'wb') as f:
    f.write(b'AKPT1\x00\x00\x00')
    f.write(struct.pack('<I', len(jdata)))
    f.write(jdata)
    f.write(payload)

print('\n写出 %s' % OUT)
print('  角色 %d 个 · 帧 %d 个 · 索引 %d B · 载荷 %d B · 合计 %d B (%.2f MB)'
      % (len(index), len(blobs), len(jdata), len(payload),
         os.path.getsize(OUT), os.path.getsize(OUT) / 1048576.0))
