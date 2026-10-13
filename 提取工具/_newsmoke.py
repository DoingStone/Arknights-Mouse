# -*- coding: utf-8 -*-
"""新工程 E:\Qianmory\Desktop\Mouse\源码\arkmouse 的冒烟测试。"""
import os
import sys
import time

SRC = r'E:\Qianmory\Desktop\Mouse\源码\arkmouse'
sys.path.insert(0, SRC)

import artpack          # noqa: E402
import cursorwin as cw  # noqa: E402
import mousep           # noqa: E402
import paths            # noqa: E402
import store            # noqa: E402

print('=== 路径 ===')
print('  APP_DIR   =', paths.APP_DIR)
print('  BUNDLE_DIR=', paths.BUNDLE_DIR)
print('  find_art  =', paths.find_art())
print('  find_pack =', paths.find_pack())
print('  STATE     =', paths.STATE)
print('  frozen    =', paths.is_frozen())

print('=== art.bin ===')
pk = artpack.load(paths.find_art())
print('  角色数 =', len(pk.roles))
for k in cw.ROLE_NAMES:
    print('  %-12s hot=%-10s frames=%-4d rate=%s' % (
        k, pk.hotspot(k), pk.frame_count(k),
        ('有 %d 项' % len(pk.rates_ms(k))) if pk.rates_ms(k) else '无'))

print('=== 帧解码 ===')
for k in ('Arrow', 'Wait', 'SizeAll'):
    fr = pk.frames(k)
    im, hx, hy = fr[0]
    print('  %-12s 帧数=%-4d 第0帧=%s hot=(%d,%d)' % (k, len(fr), im.size, hx, hy))

print('=== 桌面 ===')
print('  桌面点     =', cw.find_desktop_point())
print('  当前指针   =', cw.desktop_cursor_size())

print('=== Engine.build ===')
eng = cw.Engine()
t0 = time.time()
eng.build(115, pk)
print('  构造完成 %.2fs  角色数=%d  热点样本=%s'
      % (time.time() - t0, len(eng.masters), list(eng.hotspots.items())[:2]))
eng.destroy()
print('  destroy ok')

print('=== 鼠标参数 ===')
for k, v in mousep.get_all().items():
    print('  %-14s %s' % (k, v))

print('=== store ===')
print('  自启命令 =', store.app_command(1.20))
print('  Run 项   =', store.get_autostart())
d = store.load()
print('  设置     =', d)
print('OK')
