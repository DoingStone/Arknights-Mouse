# -*- coding: utf-8 -*-
"""终局：清空陈旧错误日志 → 起 exe GUI → 正确点开「鼠标参数」页签截图 → 收尾。"""
import ctypes
import ctypes.wintypes as wt
import os
import subprocess
import time

u32 = ctypes.WinDLL('user32', use_last_error=True)
k32 = ctypes.WinDLL('kernel32', use_last_error=True)
gdi = ctypes.WinDLL('gdi32', use_last_error=True)
EXE = r'E:\Qianmory\Desktop\Mouse\明日方舟鼠标.exe'
TOP = r'E:\Qianmory\Desktop\Mouse'
OUT = r'G:\ArknightsCursorExtract\_diag\newgui'
LOG = os.path.join(TOP, '错误日志.txt')
os.makedirs(OUT, exist_ok=True)


def pids_of():
    out = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq 明日方舟鼠标.exe',
                          '/FO', 'CSV', '/NH'], capture_output=True, text=True,
                         encoding='gbk', errors='replace')
    got = []
    for line in out.stdout.splitlines():
        parts = [p.strip('"') for p in line.split('","')]
        if len(parts) > 1 and parts[0]:
            try:
                got.append(int(parts[1]))
            except ValueError:
                pass
    return got


print('=== 0) 结束所有残留 + 清空日志 ===')
for pid in set(pids_of()):
    h = k32.OpenProcess(0x0001, False, pid)
    if h:
        k32.TerminateProcess(h, 0)
        k32.CloseHandle(h)
        print('  结束 pid=%d' % pid)
time.sleep(2)
if os.path.isfile(LOG):
    try:
        os.remove(LOG)
        print('  已删除陈旧错误日志（里面是旧 exe 的 KeyError 记录）')
    except OSError as e:
        print('  删除失败：%s' % e)

print('\n=== 1) 起 exe GUI ===')
p = subprocess.Popen([EXE], creationflags=0x08000000)
P = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
u32.EnumWindows.argtypes = [P, wt.LPARM if False else wt.LPARAM]

win = []
for i in range(25):
    time.sleep(1.0)
    ids = set(pids_of())
    win = []

    def cb(h, l):
        buf = ctypes.create_unicode_buffer(512)
        u32.GetWindowTextW(h, buf, 512)
        pid = wt.DWORD()
        u32.GetWindowThreadProcessId(h, ctypes.byref(pid))
        if pid.value in ids and '·' in buf.value and u32.IsWindowVisible(h):
            r = wt.RECT()
            u32.GetWindowRect(h, ctypes.byref(r))
            win.append((pid.value, h, buf.value, (r.left, r.top, r.right, r.bottom)))
        return True
    u32.EnumWindows(P(cb), 0)
    if win:
        break
print('  窗口：%s' % win)
if not win:
    raise SystemExit('没找到窗口')

pid, hwnd, title, (L, T, R, B) = win[0]
print('  pid=%d hwnd=%d rect=%s' % (pid, hwnd, (L, T, R, B)))


class BMIH(ctypes.Structure):
    _fields_ = [('biSize', wt.DWORD), ('biWidth', ctypes.c_long),
                ('biHeight', ctypes.c_long), ('biPlanes', wt.WORD),
                ('biBitCount', wt.WORD), ('biCompression', wt.DWORD),
                ('biSizeImage', wt.DWORD), ('biXPelsPerMeter', ctypes.c_long),
                ('biYPelsPerMeter', ctypes.c_long), ('biClrUsed', wt.DWORD),
                ('biClrImportant', wt.DWORD)]


def grab(path):
    r = wt.RECT()
    u32.GetWindowRect(hwnd, ctypes.byref(r))
    w, h = r.right - r.left, r.bottom - r.top
    dc = u32.GetWindowDC(hwnd)
    mdc = gdi.CreateCompatibleDC(dc)
    bmp = gdi.CreateCompatibleBitmap(dc, w, h)
    gdi.SelectObject(mdc, bmp)
    u32.PrintWindow(hwnd, mdc, 0x00000002)
    bi = BMIH()
    bi.biSize = ctypes.sizeof(BMIH)
    bi.biWidth = w
    bi.biHeight = -h
    bi.biPlanes = 1
    bi.biBitCount = 32
    buf = ctypes.create_string_buffer(w * h * 4)
    gdi.GetDIBits(mdc, bmp, 0, h, buf, ctypes.byref(bi), 0)
    gdi.DeleteObject(bmp)
    gdi.DeleteDC(mdc)
    u32.ReleaseDC(hwnd, dc)
    from PIL import Image
    Image.frombytes('RGBA', (w, h), buf.raw, 'raw', 'BGRA').save(path)
    return w, h


u32.SetForegroundWindow(hwnd)
time.sleep(0.8)
print('\n=== 2) 点「鼠标参数」页签 ===')
TAB2 = (L + 163, T + 60)
u32.SetCursorPos(*TAB2)
time.sleep(0.4)
u32.mouse_event(0x0002, 0, 0, 0, 0)
u32.mouse_event(0x0004, 0, 0, 0, 0)
time.sleep(1.5)
w, h = grab(os.path.join(OUT, 'exe_tab2.png'))
print('  截图 -> exe_tab2.png (%dx%d)' % (w, h))

print('\n=== 3) 点回「指针大小」页签再截一张 ===')
u32.SetCursorPos(L + 70, T + 60)
time.sleep(0.4)
u32.mouse_event(0x0002, 0, 0, 0, 0)
u32.mouse_event(0x0004, 0, 0, 0, 0)
time.sleep(1.2)
w, h = grab(os.path.join(OUT, 'exe_tab1.png'))
print('  截图 -> exe_tab1.png (%dx%d)' % (w, h))

print('\n=== 4) 结束进程 ===')
for x in set(pids_of()):
    hh = k32.OpenProcess(0x0001, False, x)
    if hh:
        k32.TerminateProcess(hh, 0)
        k32.CloseHandle(hh)
        print('  结束 pid=%d' % x)
time.sleep(2)
print('  剩余：%s' % pids_of())

print('\n=== 5) 错误日志 ===')
if os.path.isfile(LOG):
    txt = open(LOG, encoding='utf-8', errors='replace').read().strip()
    print('  长度 %d' % len(txt))
    print(txt[-2500:] if txt else '  ✓ 空')
else:
    print('  ✓ 不存在 —— 修复后的 exe 全程零异常')
