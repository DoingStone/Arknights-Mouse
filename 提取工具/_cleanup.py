# -*- coding: utf-8 -*-
"""清理测试残留进程 + 重新应用 115px 指针。"""
import ctypes
import ctypes.wintypes as wt
import os
import subprocess
import time

u32 = ctypes.WinDLL('user32', use_last_error=True)
k32 = ctypes.WinDLL('kernel32', use_last_error=True)
EXE = r'E:\Qianmory\Desktop\Mouse\明日方舟鼠标.exe'

print('=== 1) 残留进程的窗口 ===')
procs = []
import ctypes.wintypes
out = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq 明日方舟鼠标.exe', '/FO', 'CSV', '/NH'],
                     capture_output=True, text=True, encoding='gbk', errors='replace')
for line in out.stdout.splitlines():
    parts = [p.strip('"') for p in line.split('","')]
    if len(parts) > 1 and parts[0]:
        try:
            procs.append(int(parts[1]))
        except ValueError:
            pass
print('  PIDs: %s' % procs)

res = []


def cb(h, l):
    buf = ctypes.create_unicode_buffer(512)
    u32.GetWindowTextW(h, buf, 512)
    pid = wt.DWORD()
    u32.GetWindowThreadProcessId(h, ctypes.byref(pid))
    if pid.value in procs:
        r = wt.RECT()
        u32.GetWindowRect(h, ctypes.byref(r))
        res.append((pid.value, h, buf.value, bool(u32.IsWindowVisible(h)),
                    (r.left, r.top, r.right, r.bottom)))
    return True


P = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
u32.EnumWindows.argtypes = [P, wt.LPARAM]
u32.EnumWindows(P(cb), 0)
for x in res:
    print('  pid=%-6d hwnd=%-10d vis=%-5s rect=%-24s title=%r'
          % (x[0], x[1], x[3], str(x[4]), x[2]))
if not res:
    print('  （没有窗口 —— 说明 GUI 起来后已退出，或根本没建窗口）')

print('\n=== 2) 结束残留进程 ===')
for pid in procs:
    h = k32.OpenProcess(0x0001, False, pid)   # PROCESS_TERMINATE
    if h:
        k32.TerminateProcess(h, 0)
        k32.CloseHandle(h)
        print('  已结束 pid=%d' % pid)
    else:
        print('  无法打开 pid=%d (err=%d)' % (pid, ctypes.get_last_error()))
time.sleep(2)

print('\n=== 3) 重新应用 1.20× (115px) ===')
time.sleep(1)


class ICONINFO(ctypes.Structure):
    _fields_ = [('fIcon', wt.BOOL), ('xHotspot', wt.DWORD),
                ('yHotspot', wt.DWORD), ('hbmMask', wt.HANDLE),
                ('hbmColor', wt.HANDLE)]


class CURSORINFO(ctypes.Structure):
    _fields_ = [('cbSize', wt.DWORD), ('flags', wt.DWORD),
                ('hCursor', wt.HANDLE), ('ptScreenPos', wt.POINT)]


class BITMAP(ctypes.Structure):
    _fields_ = [('bmType', ctypes.c_long), ('bmWidth', ctypes.c_long),
                ('bmHeight', ctypes.c_long), ('bmWidthBytes', ctypes.c_long),
                ('bmPlanes', wt.WORD), ('bmBitsPixel', wt.WORD),
                ('bmBits', ctypes.c_void_p)]


gdi = ctypes.WinDLL('gdi32', use_last_error=True)
u32.GetCursorInfo.argtypes = [ctypes.POINTER(CURSORINFO)]
u32.GetIconInfo.argtypes = [wt.HANDLE, ctypes.POINTER(ICONINFO)]
gdi.GetObjectW.argtypes = [wt.HANDLE, ctypes.c_int, ctypes.c_void_p]
gdi.DeleteObject.argtypes = [wt.HANDLE]
u32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]


def measure(n=3):
    got = []
    for _ in range(n):
        u32.SetCursorPos(1536, 1036)
        time.sleep(0.10)
        u32.SetCursorPos(1537, 1037)
        time.sleep(0.10)
        ci = CURSORINFO()
        ci.cbSize = ctypes.sizeof(CURSORINFO)
        if not u32.GetCursorInfo(ctypes.byref(ci)) or not ci.hCursor:
            continue
        ii = ICONINFO()
        if not u32.GetIconInfo(ci.hCursor, ctypes.byref(ii)):
            continue
        bm = BITMAP()
        gdi.GetObjectW(ii.hbmColor, ctypes.sizeof(BITMAP), ctypes.byref(bm))
        if ii.hbmColor:
            gdi.DeleteObject(ii.hbmColor)
        if ii.hbmMask:
            gdi.DeleteObject(ii.hbmMask)
        got.append((bm.bmWidth, bm.bmHeight, ii.xHotspot, ii.yHotspot))
        time.sleep(0.15)
    return got


print('  应用前：%s' % measure(2))
p = subprocess.Popen([EXE, '--apply', '1.20'], creationflags=0x08000000)
time.sleep(7)
after = measure(4)
print('  应用后：%s' % after)
ok = bool(after) and all(a[0] == 115 for a in after)
print('  → %s' % ('✓ 115px 已恢复' if ok else '✗ 仍未恢复'))
p.terminate()
time.sleep(1)

print('\n=== 4) 残留检查 ===')
out = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq 明日方舟鼠标.exe', '/FO', 'CSV', '/NH'],
                     capture_output=True, text=True, encoding='gbk', errors='replace')
left = [l for l in out.stdout.splitlines() if l.strip() and '没有' not in l and 'INFO' not in l]
print('  剩余进程行数：%d %s' % (len(left), left if left else '✓'))

print('\n=== 5) 光标方案路径复核 ===')
import winreg
with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Control Panel\Cursors') as k:
    n = winreg.QueryInfoKey(k)[1]
    dirs = set()
    for i in range(n):
        name, data, typ = winreg.EnumValue(k, i)
        if isinstance(data, str) and '\\' in data:
            dirs.add(os.path.dirname(data))
    for d in sorted(dirs):
        print('  %s' % d)
    print('  方案名 = %r' % winreg.QueryValueEx(k, '')[0])
