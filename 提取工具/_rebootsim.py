# -*- coding: utf-8 -*-
"""模拟重启：先恢复成 32px（模拟开机时 Windows 的初始状态），
再一字不差地执行注册表里的自启命令，看光标是否自动变成 115px。"""
import ctypes
import ctypes.wintypes as W
import os
import subprocess
import time
import winreg

u32 = ctypes.windll.user32
gdi = ctypes.windll.gdi32
u32.SetProcessDPIAware()

DESK = ('Progman', 'WorkerW', 'SysListView32', 'SHELLDLL_DefView', 'Shell_TrayWnd')
TOOL = r'G:\ArknightsCursorExtract\CursorSizeTool\ArknightsCursorSize.pyw'


class ICONINFO(ctypes.Structure):
    _fields_ = [('fIcon', W.BOOL), ('xHotspot', W.DWORD), ('yHotspot', W.DWORD),
                ('hbmMask', W.HANDLE), ('hbmColor', W.HANDLE)]


class CURSORINFO(ctypes.Structure):
    _fields_ = [('cbSize', W.DWORD), ('flags', W.DWORD), ('hCursor', W.HANDLE),
                ('ptScreenPos', W.POINT)]


class BITMAP(ctypes.Structure):
    _fields_ = [('bmType', ctypes.c_long), ('bmWidth', ctypes.c_long),
                ('bmHeight', ctypes.c_long), ('bmWidthBytes', ctypes.c_long),
                ('bmPlanes', ctypes.c_ushort), ('bmBitsPixel', ctypes.c_ushort),
                ('bmBits', ctypes.c_void_p)]


u32.GetCursorInfo.argtypes = [ctypes.POINTER(CURSORINFO)]
u32.GetIconInfo.argtypes = [W.HANDLE, ctypes.POINTER(ICONINFO)]
gdi.GetObjectW.argtypes = [W.HANDLE, ctypes.c_int, ctypes.c_void_p]
gdi.DeleteObject.argtypes = [W.HANDLE]


def cls_at(pt):
    h = u32.WindowFromPoint(W.POINT(*pt))
    if not h:
        return None
    while True:
        p = u32.GetParent(h)
        if not p:
            break
        h = p
    b = ctypes.create_unicode_buffer(256)
    u32.GetClassNameW(h, b, 256)
    return b.value


def find_pt():
    w, h = u32.GetSystemMetrics(0), u32.GetSystemMetrics(1)
    for y in range(60, h - 200, 40):
        for x in range(6, w - 6, 60):
            if cls_at((x, y)) in DESK:
                return (x, y)
    return None


PT = find_pt()
print('探针点 =', PT, cls_at(PT))


def read_size(settle=0.7):
    u32.SetCursorPos(PT[0] + 7, PT[1] + 7)
    time.sleep(settle)
    u32.SetCursorPos(*PT)
    time.sleep(settle)
    ci = CURSORINFO()
    ci.cbSize = ctypes.sizeof(CURSORINFO)
    if not u32.GetCursorInfo(ctypes.byref(ci)):
        return None
    ii = ICONINFO()
    if not u32.GetIconInfo(ci.hCursor, ctypes.byref(ii)):
        return None
    bm = BITMAP()
    ok = gdi.GetObjectW(ii.hbmColor, ctypes.sizeof(BITMAP), ctypes.byref(bm))
    r = (bm.bmWidth, bm.bmHeight) if ok else None
    if ii.hbmColor:
        gdi.DeleteObject(ii.hbmColor)
    if ii.hbmMask:
        gdi.DeleteObject(ii.hbmMask)
    return r


print('\n=== 1. 清场：杀掉所有本工具的常驻进程 ===')
r = subprocess.run(
    ['powershell', '-NoProfile', '-Command',
     "Get-CimInstance Win32_Process -Filter \"Name='pythonw.exe'\" | "
     "Where-Object { $_.CommandLine -like '*ArknightsCursorSize*' } | "
     "ForEach-Object { Stop-Process -Id $_.ProcessId -Force; $_.ProcessId }"],
    capture_output=True, text=True)
print('   已杀 pid:', r.stdout.split() or '(无)')
time.sleep(1.0)

print('\n=== 2. 恢复原始光标（模拟刚开机：32px）===')
subprocess.run([r'C:\Users\22442\AppData\Local\Programs\Python\Python311\python.exe',
                TOOL, '--restore'], capture_output=True, timeout=180)
time.sleep(2.0)
base = read_size()
print('   当前桌面 =', base)

print('\n=== 3. 读取注册表里的自启命令并原样执行 ===')
with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                    r'Software\Microsoft\Windows\CurrentVersion\Run') as k:
    cmd, _ = winreg.QueryValueEx(k, 'ArknightsCursorSize')
print('   命令 =', cmd)
# Windows 启动项是直接 CreateProcess 这条命令行，这里照做
p = subprocess.Popen(cmd, shell=False)
print('   已启动 pid =', p.pid)

print('\n=== 4. 等待并采样（模拟开机后用户看桌面）===')
for i in range(8):
    time.sleep(2.0)
    s = read_size(settle=0.4)
    print('   t=%4.1fs  %s' % ((i + 1) * 2, s))

final = read_size()
print('\n=== 5. 结论 ===')
print('   开机前 =', base)
print('   自启后 =', final)
ok = final == (115, 115)
print('   ★ 开机自动恢复 115px  =>  %s' % ('通过 ✔' if ok else '未通过 ✘'))
print('   常驻进程存活 =', p.poll() is None, '(动画线程)')
