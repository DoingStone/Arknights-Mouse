# -*- coding: utf-8 -*-
"""量游戏窗口内指针的绘制尺寸（快速版）：
把鼠标钉进客户区 -> 截取鼠标周围 260x260 -> 多次采样求中值背景 -> 提取亮像素包围盒。
游戏自绘的白色水晶在深色背景上极易分割，直接量包围盒即可。
"""
import ctypes
import json
import os
import time
from ctypes import wintypes

from PIL import Image, ImageChops, ImageDraw, ImageGrab

u32 = ctypes.WinDLL('user32', use_last_error=True)

ROOT = r'G:\ArknightsCursorExtract'
OUT = os.path.join(ROOT, '_diag')
os.makedirs(OUT, exist_ok=True)

u32.EnumWindows.argtypes = [ctypes.c_void_p, wintypes.LPARAM]
u32.GetWindowTextW.argtypes = [wintypes.HWND, ctypes.c_wchar_p, ctypes.c_int]
u32.IsWindowVisible.argtypes = [wintypes.HWND]
u32.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
u32.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
u32.SetForegroundWindow.argtypes = [wintypes.HWND]
u32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
u32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
u32.GetWindowThreadProcessId.argtypes = [wintypes.HWND,
                                         ctypes.POINTER(wintypes.DWORD)]
u32.GetClassNameW.argtypes = [wintypes.HWND, ctypes.c_wchar_p, ctypes.c_int]


def find_windows(substr):
    res = []
    CB = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def cb(h, l):
        if not u32.IsWindowVisible(h):
            return True
        b = ctypes.create_unicode_buffer(512)
        u32.GetWindowTextW(h, b, 512)
        if substr in b.value:
            pid = wintypes.DWORD()
            u32.GetWindowThreadProcessId(h, ctypes.byref(pid))
            res.append((h, b.value, pid.value))
        return True

    u32.EnumWindows(CB(cb), 0)
    return res


def client_box(hwnd):
    cr = wintypes.RECT()
    u32.GetClientRect(hwnd, ctypes.byref(cr))
    tl = wintypes.POINT(0, 0)
    u32.ClientToScreen(hwnd, ctypes.byref(tl))
    return ((tl.x, tl.y, tl.x + cr.right, tl.y + cr.bottom),
            (cr.right, cr.bottom))


wins = find_windows('明日方舟')
print('=== 明日方舟 窗口 ===')
for h, t, p in wins:
    cb_, sz = client_box(h)
    print('  hwnd=%d title=%r pid=%d 客户区=%s 尺寸=%s' % (h, t, p, cb_, sz))
if not wins:
    print('  游戏未运行 —— 跳过实测；先给出机制结论')
    raise SystemExit(0)

hwnd = wins[0][0]
box, csize = client_box(hwnd)
u32.ShowWindow(hwnd, 9)
u32.SetForegroundWindow(hwnd)
time.sleep(2.5)
print('  客户区 =', box, csize)

# 鼠标停在客户区中部偏左（截图里游戏内指针大致出现在偏左上位置）
P = (box[0] + int(csize[0] * 0.22), box[1] + int(csize[1] * 0.40))
D = (1536, 1036)
R = 150
crop_box = (P[0] - R, P[1] - R, P[0] + R, P[1] + R)

print()
print('=== 采两张：指针在 P(游戏客户区) / 指针在桌面 ===')
u32.SetCursorPos(P[0], P[1])
time.sleep(2.0)
A = ImageGrab.grab(bbox=crop_box).convert('RGB')
A.save(os.path.join(OUT, 'game_ptr_A.png'))

u32.SetCursorPos(D[0], D[1])
time.sleep(2.0)
B = ImageGrab.grab(bbox=crop_box).convert('RGB')
B.save(os.path.join(OUT, 'game_ptr_B.png'))

diff = ImageChops.difference(A, B).convert('L')
dp = diff.load()
w, h = diff.size
pts = [(x, y) for y in range(h) for x in range(w) if dp[x, y] > 45]
print('  差异像素(>45) =', len(pts), '/', w * h)
if pts:
    x0 = min(p[0] for p in pts)
    x1 = max(p[0] for p in pts)
    y0 = min(p[1] for p in pts)
    y1 = max(p[1] for p in pts)
    print('  差异包围盒(局部) =', (x0, y0, x1, y1), '尺寸 =', (x1 - x0 + 1, y1 - y0 + 1))
diff.point(lambda v: min(255, v * 4)).save(os.path.join(OUT, 'game_ptr_diff.png'))

# 亮像素分割（游戏内指针是白色，背景是深蓝灰）
ap = A.load()
bright = [(x, y) for y in range(h) for x in range(w)
          if ap[x, y][0] > 150 and ap[x, y][1] > 150 and ap[x, y][2] > 150]
print('  亮像素(>150) =', len(bright))
if bright:
    x0 = min(p[0] for p in bright)
    x1 = max(p[0] for p in bright)
    y0 = min(p[1] for p in bright)
    y1 = max(p[1] for p in bright)
    print('  亮像素包围盒(局部) =', (x0, y0, x1, y1),
          '尺寸 =', (x1 - x0 + 1, y1 - y0 + 1))

# 并排放大取证
grid = Image.new('RGB', (w * 2 * 2 + 20, h * 2 + 30), (20, 20, 24))
grid.paste(A.resize((w * 2, h * 2), Image.NEAREST), (5, 25))
grid.paste(B.resize((w * 2, h * 2), Image.NEAREST), (w * 2 + 15, 25))
d = ImageDraw.Draw(grid)
d.text((6, 6), 'A: mouse inside game client', fill=(255, 220, 120))
d.text((w * 2 + 16, 6), 'B: mouse on desktop', fill=(255, 220, 120))
grid.save(os.path.join(OUT, 'game_ptr_AB.png'))
print('  已写 game_ptr_A.png / game_ptr_B.png / game_ptr_diff.png / game_ptr_AB.png')

res = {'client_box': box, 'client_size': list(csize),
       'ptr_screen': list(P), 'radius': R}
if pts:
    res['diff_bbox'] = [x0, y0, x1, y1]
    res['diff_size'] = [x1 - x0 + 1, y1 - y0 + 1]
if bright:
    res['bright_bbox'] = [x0b for x0b in (min(p[0] for p in bright),
                                          min(p[1] for p in bright),
                                          max(p[0] for p in bright),
                                          max(p[1] for p in bright))]
with open(os.path.join(OUT, 'game_cursor_measure.json'), 'w',
          encoding='utf-8') as f:
    json.dump(res, f, ensure_ascii=False, indent=1)
print('  已写 game_cursor_measure.json')
