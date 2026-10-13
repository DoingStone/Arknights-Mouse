# -*- coding: utf-8 -*-
"""启动 CursorSizeTool 的 GUI，等待渲染后截取窗口，然后关闭。
用于实机验证界面可用（不改任何系统设置 —— 不点「应用」）。"""
import ctypes
import ctypes.wintypes as wintypes
import os
import subprocess
import sys
import time

sys.coinit_flags = 2
from ctypes import wintypes as W

u32 = ctypes.windll.user32
u32.SetProcessDPIAware()

TOOL = r'G:\ArknightsCursorExtract\CursorSizeTool\ArknightsCursorSize.pyw'
OUT = r'G:\ArknightsCursorExtract\_diag'
PYW = os.path.join(os.path.dirname(sys.executable), 'pythonw.exe')
if not os.path.exists(PYW):
    PYW = sys.executable

os.makedirs(OUT, exist_ok=True)

# 先记录当前系统光标方案名，验证 GUI 不会偷改设置
import winreg
try:
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Control Panel\Cursors') as k:
        before = winreg.QueryValueEx(k, '')[0]
except Exception as e:
    before = 'ERR %s' % e
print('before scheme:', repr(before))

p = subprocess.Popen([PYW, TOOL])
print('launched pid', p.pid)

# 等待窗口出现
hwnd = 0
title = ''
for _ in range(60):
    time.sleep(0.25)
    found = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, W.HWND, W.LPARAM)
    def cb(h, l):
        if not u32.IsWindowVisible(h):
            return True
        n = u32.GetWindowTextLengthW(h)
        if n <= 0:
            return True
        buf = ctypes.create_unicode_buffer(n + 1)
        u32.GetWindowTextW(h, buf, n + 1)
        pid = W.DWORD()
        u32.GetWindowThreadProcessId(h, ctypes.byref(pid))
        if pid.value == p.pid:
            found.append((h, buf.value))
        return True

    u32.EnumWindows(cb, 0)
    if found:
        hwnd, title = found[0]
        break

print('hwnd=%s title=%r' % (hwnd, title))
if not hwnd:
    print('!! 没有找到窗口')
    p.terminate()
    raise SystemExit(1)

time.sleep(1.5)   # 让 tkinter 画完

# 抓窗口
from PIL import ImageGrab
r = W.RECT()
u32.GetWindowRect(hwnd, ctypes.byref(r))
x0, y0, x1, y1 = r.left, r.top, r.right, r.bottom
print('rect', (x0, y0, x1, y1), 'size', (x1 - x0, y1 - y0))
img = ImageGrab.grab(bbox=(x0, y0, x1, y1), all_screens=True)
dst = os.path.join(OUT, 'gui_shot.png')
img.save(dst)
print('wrote', dst, img.size)

# 读取窗口里的所有文本控件内容（确认标签渲染正确）
# 用 tkinter 自己导不出来；这里改用截图目视 + 打印进程是否还活着
alive = p.poll() is None
print('process alive:', alive)
if not alive:
    print('!! 进程已退出，returncode =', p.returncode)

# 关闭 GUI（正常关闭，不触碰设置）
u32.PostMessageW(hwnd, 0x0010, 0, 0)   # WM_CLOSE
time.sleep(1.5)
if p.poll() is None:
    print('窗口未关，强制结束')
    p.terminate()
    time.sleep(0.5)
print('exit code:', p.poll())

# 复核方案名没被改
try:
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Control Panel\Cursors') as k:
        after = winreg.QueryValueEx(k, '')[0]
except Exception as e:
    after = 'ERR %s' % e
print('after  scheme:', repr(after))
print('scheme unchanged:', before == after)
