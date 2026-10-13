# -*- coding: utf-8 -*-
"""把 PRTS 的帧式效果美术导进本工程的 art.bin 格式（fx.bin）。

出处（PRTS 参考工程，逐条可核验）：
  E:\\Qianmory\\下载\\QuarkDownload\\_prts_build\\extract\\PRTS-Replica-v8-96x-<phase>.cur
  帧序与命名规则见 _prts_build\\motion\\src\\Runtime.cs:
    FileFor      427-444    hand_*/grab_*/idle_* 都是 .cur，一帧一个文件
    DragFrame   1115-1137   grab_enter_0000..0011 / grab_begin_0000..0011 / grab_loop_0000
                             松手后 grab_end_0000..0040 / grab_return_0000..0011
    IdleFrame    379-386    idle_enter_frame_000..029 @60fps
                             idle_frame_0000..0341 @15fps（342 帧循环）

产物：源码\\arkmouse\\fx.bin（与 art.bin 同格式，用 artpack.ArtPack 直接读）
  {"roles": {"grab_enter": {"hot":[x,y], "rate":null, "frames":[[off,len],...]}, ...}}

用法：
  python import_prts_fx.py              # 导全部：点击 535 帧 + 拖动 79 + 待机 372
  python import_prts_fx.py --any        # 缺帧不报错，能收多少收多少
"""
import io
import json
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PIL import Image

import build_crystal_pack as B

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = r'E:\Qianmory\下载\QuarkDownload\_prts_build\extract'
PREFIX = 'PRTS-Replica-v8-96x-'
OUT = os.path.join(ROOT, '源码', 'arkmouse', 'fx.bin')

NATIVE = 96

# 角色名 -> (文件名模式, 帧数, 缺帧是否致命)
GRAB = [
    ('grab_enter',  'grab_enter_%04d',  12),
    ('grab_begin',  'grab_begin_%04d',  12),
    ('grab_end',    'grab_end_%04d',    41),
    ('grab_return', 'grab_return_%04d', 12),
]
GRAB_EXTRA = [('grab_loop', 'grab_loop_%04d', 2)]

# 只收 .cur 的那两族。PRTS 的退出过渡（enter_exit_* / idle_exit_*）是 .ani，
# 一个文件里装着多帧；按“一文件一帧”收进来只会拿到每段的第 0 帧，是错的。
# 本工程退出待机时直接回到 Arrow 常态，不走过渡（见 prtsfx.py 段注释）。
IDLE = [
    ('idle_enter_frame', 'idle_enter_frame_%03d', 30),
    ('idle_frame',       'idle_frame_%04d',       342),
]

# 点击挤压。PRTS 只给这 5 个角色烘了 hand_* 原帧（normal=Arrow、helpsel=Help、
# link=Hand、pin=Pin、person=Person），其余角色 PRTS 自己也没有点击动画。
CLICK = [
    ('hand_normal',  'hand_normal_%03d',  107),
    ('hand_helpsel', 'hand_helpsel_%03d', 107),
    ('hand_link',    'hand_link_%03d',    107),
    ('hand_pin',     'hand_pin_%03d',     107),
    ('hand_person',  'hand_person_%03d',  107),
]


def one(rel):
    p = os.path.join(SRC, PREFIX + rel + '.cur')
    if not os.path.exists(p):
        return None, p
    art, hx, hy = B.raster_of(p, NATIVE)
    return (art.convert('RGBA'), (int(hx), int(hy))), p


def collect(families, only_shape=False):
    """返回 (角色 -> [(Image, hx, hy)...]), 报告行列表。"""
    out = {}
    report = []
    for role, pat, n in families:
        frames = []
        hot = None
        missing = []
        for i in range(n):
            got, path = one(pat % i)
            if got is None:
                missing.append(i)
                continue
            im, h = got
            if hot is None:
                hot = h
            elif h != hot:
                raise SystemExit('%s 第 %d 帧热点不一致：%s vs %s' % (role, i, h, hot))
            frames.append((im, h[0], h[1]))
        if missing and not only_shape:
            raise SystemExit('%s 缺 %d 帧（%s…）' % (role, len(missing), missing[:5]))
        if not frames:
            raise SystemExit('%s 一帧都没取到' % role)
        out[role] = frames
        report.append('  %-18s %3d 帧  热点=%s' % (role, len(frames), hot))
    return out, report


def write_pack(roles, path):
    """按 artpack 的格式写：magic + jlen + json + 依次拼接的 PNG。"""
    blobs = []
    index = {'roles': {}}
    off = 0
    for role in sorted(roles):
        frames = roles[role]
        hx, hy = frames[0][1], frames[0][2]
        entries = []
        for (im, _x, _y) in frames:
            b = io.BytesIO()
            im.convert('RGBA').save(b, 'PNG', optimize=True)
            data = b.getvalue()
            blobs.append(data)
            entries.append([off, len(data)])
            off += len(data)
        index['roles'][role] = {'hot': [hx, hy], 'rate': None, 'frames': entries}
    jdata = json.dumps(index, separators=(',', ':')).encode('utf-8')
    body = b''.join(blobs)
    with open(path, 'wb') as f:
        f.write(B.ART_MAGIC if hasattr(B, 'ART_MAGIC') else b'AKPT1\x00\x00\x00')
        f.write(struct.pack('<I', len(jdata)))
        f.write(jdata)
        f.write(body)
    return 12 + len(jdata) + len(body)


def main():
    argv = sys.argv[1:]
    only_shape = ('--any' in argv)

    if not os.path.isdir(SRC):
        print('找不到 PRTS extract 目录：%s' % SRC)
        return 2

    roles = {}
    for title, fams in (('拖动爪子帧族', GRAB + GRAB_EXTRA),
                        ('点击挤压帧族', CLICK),
                        ('待机帧族', IDLE)):
        print('导入%s…' % title)
        got, rep = collect(fams, only_shape)
        roles.update(got)
        print('\n'.join(rep))

    size = write_pack(roles, OUT)
    nfr = sum(len(v) for v in roles.values())
    print('写出 %s：%d 个角色 / %d 帧 / %.2f MB'
          % (OUT, len(roles), nfr, size / 1048576.0))
    return 0


if __name__ == '__main__':
    sys.exit(main())
