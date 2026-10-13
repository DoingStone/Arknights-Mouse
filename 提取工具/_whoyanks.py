# -*- coding: utf-8 -*-
"""定位「鼠标被拽回左上角」的真凶。

cursorwin.desktop_cursor_size() 内部会 SetCursorPos —— 这是测量用的
（必须先钉到真桌面窗口，否则 GetCursorInfo 读到的是悬停窗口的光标）。
但它算出来的「桌面点」如果落到 (0,0)，就会把鼠标拽到左上角。
"""
import ctypes
import ctypes.wintypes as wt
import os
import sys
import time

APP = r'E:\Qianmory\Desktop\Mouse'
sys.path.insert(0, os.path.join(APP, '源码', 'arkmouse'))
import cursorwin as cw  # noqa: E402

u32 = ctypes.windll.user32
u32.GetCursorPos.argtypes = [ctypes.c_void_p]
u32.GetWindowRect.argtypes = [wt.HWND, ctypes.c_void_p]
u32.FindWindowW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p]
u32.FindWindowW.restype = wt.HWND


class POINT(ctypes.Structure):
    _fields_ = [('x', ctypes.c_long), ('y', ctypes.c_long)]


def pos():
    p = POINT()
    u32.GetCursorPos(ctypes.byref(p))
    return p.x, p.y


print('=== 1) 每个桌面类窗口的矩形 + 会算出哪个点 ===')
for cls in cw.DESKTOP_CLASSES:
    h = u32.FindWindowW(cls, None)
    if not h:
        print('  %-16s 不存在' % cls)
        continue
    r = wt.RECT()
    if not u32.GetWindowRect(h, ctypes.byref(r)):
        print('  %-16s GetWindowRect 失败' % cls)
        continue
    w, hh = r.right - r.left, r.bottom - r.top
    pts = [(int(r.left + w * fx), int(r.top + hh * fy))
           for fx, fy in ((0.55, 0.45), (0.35, 0.65), (0.75, 0.80))]
    print('  %-16s hwnd=%-10d rect=(%d,%d)-(%d,%d) %dx%d  候选点=%s'
          % (cls, h, r.left, r.top, r.right, r.bottom, w, hh, pts))

print('\n=== 2) find_desktop_point() 实际返回 ===')
pt = cw.find_desktop_point()
print('  返回 = %s' % (pt,))
if pt:
    print('  %s' % ('⚠️  这是左上角！会把鼠标拽过去' if pt[0] < 50 and pt[1] < 50
                    else '位置正常'))

print('\n=== 3) 实测：调用 desktop_cursor_size() 前后鼠标位置 ===')
before = pos()
print('  调用前 = %s' % (before,))
t0 = time.time()
res = cw.desktop_cursor_size(jiggle=False)
dt = time.time() - t0
after = pos()
print('  调用后 = %s   （耗时 %.2fs）' % (after, dt))
print('  桌面光标 = %s' % (res,))
moved = abs(after[0] - before[0]) + abs(after[1] - before[1])
print('  鼠标位移 = %d px  ⇒ %s'
      % (moved, '⚠️  测量会移动鼠标！' if moved > 3 else '未移动'))

print('\n=== 4) 代码里所有 SetCursorPos 的调用点 ===')
src = os.path.join(APP, '源码', 'arkmouse')
for fn in sorted(os.listdir(src)):
    if not fn.endswith(('.py', '.pyw')):
        continue
    p = os.path.join(src, fn)
    for i, ln in enumerate(open(p, encoding='utf-8', errors='replace'), 1):
        if 'SetCursorPos' in ln:
            print('  %s:%d  %s' % (fn, i, ln.strip()))
for fn in sorted(os.listdir(os.path.join(APP, '提取工具'))):
    if not fn.endswith('.py'):
        continue
    p = os.path.join(APP, '提取工具', fn)
    try:
        for i, ln in enumerate(open(p, encoding='utf-8', errors='replace'), 1):
            if 'SetCursorPos' in ln:
                print('  提取工具/%s:%d  %s' % (fn, i, ln.strip()))
    except Exception:
        pass

print('\n=== 5) 谁在定时调用它 ===')
for fn in ('main.pyw', 'guard.py'):
    p = os.path.join(src, fn)
    for i, ln in enumerate(open(p, encoding='utf-8', errors='replace'), 1):
        s = ln.strip()
        if ('desktop_cursor_size' in s or '_tick' in s or 'after(' in s
                or 'refresh_now' in s):
            print('  %s:%d  %s' % (fn, i, s))
