# -*- coding: utf-8 -*-
"""实测【游戏自绘指针】在屏幕上的像素尺寸。

要点：游戏把指针画进自己的渲染表面，所以对游戏窗口做位图抓取是能抓到指针的
（系统光标叠加层抓不到，但游戏自绘的可以）。
步骤：找「明日方舟」窗口 -> 记住前台窗口 -> 把游戏提到前台 -> 把鼠标移到窗口内
一个安全点 -> 抓窗口位图 -> 在鼠标点附近找亮色水晶形状 -> 量包围盒 -> 还原前台。
"""
import ctypes
import json
import os
import time
from collections import deque
from ctypes import wintypes

from PIL import Image, ImageGrab

u32 = ctypes.WinDLL('user32', use_last_error=True)

u32.EnumWindows.argtypes = [ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND,
                                               wintypes.LPARAM),
                            wintypes.LPARAM]
u32.GetWindowTextW.argtypes = [wintypes.HWND, ctypes.c_wchar_p, ctypes.c_int]
u32.GetClassNameW.argtypes = [wintypes.HWND, ctypes.c_wchar_p, ctypes.c_int]
u32.IsWindowVisible.argtypes = [wintypes.HWND]
u32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
u32.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
u32.GetWindowThreadProcessId.argtypes = [wintypes.HWND,
                                         ctypes.POINTER(wintypes.DWORD)]
u32.GetForegroundWindow.restype = wintypes.HWND
u32.SetForegroundWindow.argtypes = [wintypes.HWND]
u32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
u32.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
u32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
u32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int,
                             ctypes.c_int, ctypes.c_int, ctypes.c_int,
                             wintypes.UINT]

HWND_TOP = 0
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_SHOWWINDOW = 0x0040
SW_RESTORE = 9

DIAG = r'G:\ArknightsCursorExtract\_diag'


def find_game():
    hits = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def cb(h, _l):
        if not u32.IsWindowVisible(h):
            return True
        b = ctypes.create_unicode_buffer(512)
        u32.GetWindowTextW(h, b, 512)
        t = b.value
        c = ctypes.create_unicode_buffer(256)
        u32.GetClassNameW(h, c, 256)
        if '明日方舟' in t or 'Arknights' in t or c.value.startswith('UnityWnd'):
            r = wintypes.RECT()
            u32.GetWindowRect(h, ctypes.byref(r))
            pid = wintypes.DWORD()
            u32.GetWindowThreadProcessId(h, ctypes.byref(pid))
            hits.append({'hwnd': int(h), 'title': t, 'cls': c.value,
                         'rect': [r.left, r.top, r.right, r.bottom],
                         'pid': int(pid.value)})
        return True

    u32.EnumWindows(cb, 0)
    return hits


print('=== 找游戏窗口 ===')
g = find_game()
for d in g:
    print('  hwnd=%(hwnd)d pid=%(pid)d cls=%(cls)s rect=%(rect)s  title=%(title)s'
          % d)
if not g:
    print('  没有找到游戏窗口 —— 游戏当前未运行。跳过实测。')
    raise SystemExit(0)

win = g[0]
hwnd = wintypes.HWND(win['hwnd'])
prev_fg = u32.GetForegroundWindow()
print('  原前台 hwnd =', int(prev_fg) if prev_fg else 0)

cr = wintypes.RECT()
u32.GetClientRect(hwnd, ctypes.byref(cr))
print('  客户区 = %dx%d' % (cr.right, cr.bottom))
wr = wintypes.RECT()
u32.GetWindowRect(hwnd, ctypes.byref(wr))
print('  窗口 = (%d,%d)-(%d,%d)' % (wr.left, wr.top, wr.right, wr.bottom))

# 客户区 -> 屏幕；挑一个靠左上的安全点
pt = wintypes.POINT(220, 200)
u32.ClientToScreen(hwnd, ctypes.byref(pt))
print('  目标屏幕点 =', (pt.x, pt.y))

# 提到前台并挪到原位置（不改变大小/位置）
u32.ShowWindow(hwnd, SW_RESTORE)
u32.SetWindowPos(hwnd, wintypes.HWND(HWND_TOP), 0, 0, 0, 0,
                 SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)
u32.SetForegroundWindow(hwnd)
time.sleep(1.2)

u32.SetCursorPos(pt.x, pt.y)
time.sleep(1.0)
u32.SetCursorPos(pt.x + 1, pt.y)
time.sleep(0.8)

wr2 = wintypes.RECT()
u32.GetWindowRect(hwnd, ctypes.byref(wr2))
rect = (wr2.left, wr2.top, wr2.right, wr2.bottom)
im = ImageGrab.grab(bbox=rect, all_screens=True).convert('RGB')
print('  抓到窗口位图 =', im.size)
im.save(os.path.join(DIAG, 'game_live_full.png'))

# 鼠标在窗口内的本地坐标
mx, my = pt.x - wr2.left, pt.y - wr2.top
print('  鼠标在窗口内坐标 =', (mx, my))

# 在鼠标点附近找亮色连通块
w, h = im.size
px = im.load()
R = 190
x0, y0 = max(0, mx - R), max(0, my - R)
x1, y1 = min(w, mx + R), min(h, my + R)
seen = set()
best = []
for yy in range(y0, y1):
    for xx in range(x0, x1):
        if (xx, yy) in seen:
            continue
        r, gg, b = px[xx, yy]
        if not (r > 150 and gg > 150 and b > 150):
            continue
        q = deque([(xx, yy)])
        seen.add((xx, yy))
        n = 0
        bx1 = bx2 = xx
        by1 = by2 = yy
        while q:
            a, c = q.popleft()
            n += 1
            bx1 = min(bx1, a)
            bx2 = max(bx2, a)
            by1 = min(by1, c)
            by2 = max(by2, c)
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                u, v = a + dx, c + dy
                if x0 <= u < x1 and y0 <= v < y1 and (u, v) not in seen:
                    rr, g2, b2 = px[u, v]
                    if rr > 150 and g2 > 150 and b2 > 150:
                        seen.add((u, v))
                        q.append((u, v))
        bw, bh = bx2 - bx1 + 1, by2 - by1 + 1
        if n >= 15:
            best.append({'n': n, 'box': [bx1, by1, bw, bh],
                         'fill': round(n / float(bw * bh), 3),
                         'dist': round(((bx1 + bx2) / 2.0 - mx) ** 2 +
                                       ((by1 + by2) / 2.0 - my) ** 2, 1)})
best.sort(key=lambda d: d['dist'])
print()
print('=== 鼠标点附近的亮色块（按距鼠标距离排序，前 8）===')
for d in best[:8]:
    print('  n=%-6d box=%-24s fill=%-6s 距鼠标^2=%.1f' % (
        d['n'], str(d['box']), d['fill'], d['dist']))

# 裁剪放大
for i, d in enumerate(best[:3]):
    bx, by, bw, bh = d['box']
    pad = 14
    box = (max(0, bx - pad), max(0, by - pad),
           min(w, bx + bw + pad), min(h, by + bh + pad))
    crop = im.crop(box)
    f = max(2, int(200 / max(1, max(crop.size))))
    big = crop.resize((crop.size[0] * f, crop.size[1] * f), Image.NEAREST)
    out = os.path.join(DIAG, 'gamelive_ptr_%d_x%d.png' % (i, f))
    big.save(out)
    print('  写出 %s (%dx%d)' % (os.path.basename(out), big.size[0], big.size[1]))

# 还原前台
if prev_fg:
    u32.SetForegroundWindow(prev_fg)

with open(os.path.join(DIAG, 'game_cursor_measured.json'), 'w',
          encoding='utf-8') as f:
    json.dump({'window': win, 'client': [cr.right, cr.bottom],
               'mouse_local': [mx, my], 'blobs': best[:10]},
              f, ensure_ascii=False, indent=1)
print()
print('写入 _diag\\game_cursor_measured.json；前台已还原')
