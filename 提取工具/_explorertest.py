# -*- coding: utf-8 -*-
"""最后一条未测路径：改 Accessibility\CursorSize / CursorBaseSize 后【重启 explorer】，
让 shell 重新套用光标方案 —— 若生效，则文件式 .cur/.ani 都能变大且动画保留。
顺序：备份 -> 设 CursorSize=15 -> 重启 explorer -> 量 -> 叠加 CursorBaseSize(DWORD 120) -> 量
      -> 还原注册表 -> 重启 explorer 恢复。
"""
import ctypes
import json
import os
import subprocess
import time
import winreg
from ctypes import wintypes

u32 = ctypes.WinDLL('user32', use_last_error=True)
gdi = ctypes.WinDLL('gdi32', use_last_error=True)

ROOT = r'G:\ArknightsCursorExtract'
OUT = os.path.join(ROOT, '_diag')
REG = r'Control Panel\Cursors'
ACC = r'Software\Microsoft\Accessibility'
DP = (1536, 1036)


class ICONINFO(ctypes.Structure):
    _fields_ = [('fIcon', wintypes.BOOL), ('xHotspot', wintypes.DWORD),
                ('yHotspot', wintypes.DWORD), ('hbmMask', wintypes.HANDLE),
                ('hbmColor', wintypes.HANDLE)]


class CURSORINFO(ctypes.Structure):
    _fields_ = [('cbSize', wintypes.DWORD), ('flags', wintypes.DWORD),
                ('hCursor', wintypes.HANDLE), ('ptScreenPos', wintypes.POINT)]


class BITMAP(ctypes.Structure):
    _fields_ = [('bmType', wintypes.LONG), ('bmWidth', wintypes.LONG),
                ('bmHeight', wintypes.LONG), ('bmWidthBytes', wintypes.LONG),
                ('bmPlanes', wintypes.WORD), ('bmBitsPixel', wintypes.WORD),
                ('bmBits', ctypes.c_void_p)]


class POINT(ctypes.Structure):
    _fields_ = [('x', wintypes.LONG), ('y', wintypes.LONG)]


u32.GetCursorInfo.argtypes = [ctypes.POINTER(CURSORINFO)]
u32.GetCursorInfo.restype = wintypes.BOOL
u32.GetIconInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(ICONINFO)]
u32.GetIconInfo.restype = wintypes.BOOL
gdi.GetObjectW.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p]
gdi.GetObjectW.restype = ctypes.c_int
gdi.DeleteObject.argtypes = [wintypes.HANDLE]
u32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
u32.GetCursorPos.argtypes = [ctypes.POINTER(POINT)]
u32.WindowFromPoint.argtypes = [POINT]
u32.WindowFromPoint.restype = wintypes.HWND
u32.GetClassNameW.argtypes = [wintypes.HWND, ctypes.c_wchar_p, ctypes.c_int]
u32.SystemParametersInfoW.argtypes = [wintypes.UINT, wintypes.UINT,
                                      ctypes.c_void_p, wintypes.UINT]


def ps(cmd, t=90):
    try:
        r = subprocess.run(['powershell', '-NoProfile', '-Command', cmd],
                           capture_output=True, text=True, timeout=t)
        return (r.stdout or '').strip()
    except Exception as e:
        return 'ERR %s' % e


def measure():
    u32.SetCursorPos(DP[0], DP[1])
    time.sleep(0.8)
    p = POINT()
    u32.GetCursorPos(ctypes.byref(p))
    h = u32.WindowFromPoint(p)
    buf = ctypes.create_unicode_buffer(256)
    n = u32.GetClassNameW(h, buf, 256) if h else 0
    ci = CURSORINFO()
    ci.cbSize = ctypes.sizeof(CURSORINFO)
    if not u32.GetCursorInfo(ctypes.byref(ci)) or not ci.hCursor:
        return {'size': None, 'class': buf.value if n else ''}
    ii = ICONINFO()
    if not u32.GetIconInfo(ci.hCursor, ctypes.byref(ii)):
        return {'size': None, 'class': buf.value if n else ''}
    sz = None
    if ii.hbmColor:
        bm = BITMAP()
        if gdi.GetObjectW(ii.hbmColor, ctypes.sizeof(BITMAP), ctypes.byref(bm)):
            sz = [int(bm.bmWidth), int(bm.bmHeight)]
        gdi.DeleteObject(ii.hbmColor)
    if ii.hbmMask:
        gdi.DeleteObject(ii.hbmMask)
    return {'size': sz, 'hotspot': [int(ii.xHotspot), int(ii.yHotspot)],
            'class': buf.value if n else ''}


def getv(path, name):
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as k:
            return winreg.QueryValueEx(k, name)
    except OSError:
        return (None, None)


def setv(path, name, val, typ):
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path, 0,
                        winreg.KEY_SET_VALUE) as k:
        winreg.SetValueEx(k, name, 0, typ, val)


def bounce_explorer(tag):
    print('  [%s] 结束 explorer…' % tag)
    ps("Get-Process explorer -ErrorAction SilentlyContinue | Stop-Process -Force")
    time.sleep(4.0)
    n = ps("(Get-Process explorer -ErrorAction SilentlyContinue | Measure-Object).Count")
    print('  [%s] explorer 进程数 = %s' % (tag, n))
    if n.strip() in ('', '0'):
        print('  [%s] 未自启，手动启动' % tag)
        ps("Start-Process explorer.exe")
        time.sleep(6.0)
        print('  [%s] 启动后 explorer = %s' % (
            tag, ps("(Get-Process explorer -ErrorAction SilentlyContinue | Measure-Object).Count")))
    time.sleep(3.0)


rep = {}
orig_cs = getv(ACC, 'CursorSize')
orig_cbs = getv(REG, 'CursorBaseSize')
orig_arrow = getv(REG, 'Arrow')
rep['orig'] = {'CursorSize': orig_cs, 'CursorBaseSize': orig_cbs,
               'Arrow': orig_arrow}
print('原始 CursorSize =', orig_cs, ' CursorBaseSize =', orig_cbs)
print('原始 Arrow =', orig_arrow[0])
print('基线 =', measure())
rep['baseline'] = measure()

print()
print('=== 1) CursorSize = 15（最大档）-> 重启 explorer ===')
setv(ACC, 'CursorSize', 15, winreg.REG_DWORD)
bounce_explorer('step1')
m = measure()
print('  结果 =', m)
rep['cursor_size15'] = m

print()
print('=== 2) 叠加 CursorBaseSize = 120 (DWORD) -> 重启 explorer ===')
setv(REG, 'CursorBaseSize', 120, winreg.REG_DWORD)
bounce_explorer('step2')
m = measure()
print('  结果 =', m)
rep['plus_base120'] = m

print()
print('=== 3) 叠加 CursorBaseSize = 200 (DWORD) -> 重启 explorer ===')
setv(REG, 'CursorBaseSize', 200, winreg.REG_DWORD)
bounce_explorer('step3')
m = measure()
print('  结果 =', m)
rep['plus_base200'] = m

print()
print('=== 4) 用 SPI_SETCURSORS 强制重载（不重启 explorer）===')
u32.SystemParametersInfoW(0x0057, 0, None, 0x01 | 0x02)
time.sleep(2.0)
m = measure()
print('  结果 =', m)
rep['spi_setcursors'] = m

print()
print('=== 还原 ===')
setv(ACC, 'CursorSize', orig_cs[0], orig_cs[1])
setv(REG, 'CursorBaseSize', orig_cbs[0], orig_cbs[1])
u32.SystemParametersInfoW(0x0057, 0, None, 0x01 | 0x02)
time.sleep(1.5)
print('  CursorSize =', getv(ACC, 'CursorSize'))
print('  CursorBaseSize =', getv(REG, 'CursorBaseSize'))
print('  当前 =', measure())

with open(os.path.join(OUT, 'explorertest.json'), 'w', encoding='utf-8') as f:
    json.dump(rep, f, ensure_ascii=False, indent=1)
print('写入 _diag\\explorertest.json')
