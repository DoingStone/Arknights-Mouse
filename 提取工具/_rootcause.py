# -*- coding: utf-8 -*-
"""根因判定：为什么 Windows 光标尺寸设置无效？
假设：PRTS-Motion-96.exe 在持续把光标以 base=32 重新 SetSystemCursor，压掉了系统的尺寸缩放。
步骤：
 A) 记录 PRTS 进程状态
 B) 杀掉 PRTS -> 设 CursorSize=15 -> SPI_SETCURSORS -> 量桌面光标
 C) 仍无效则试 CursorBaseSize(DWORD) 大值
 D) 仍无效则重启 explorer（已知的系统级生效路径）
最后还原设置并按原命令行重启 PRTS。
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
os.makedirs(OUT, exist_ok=True)
REG = r'Control Panel\Cursors'
ACC = r'Software\Microsoft\Accessibility'
DO_EXPLORER = os.environ.get('CURSOR_TEST_EXPLORER') == '1'


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
gdi.DeleteObject.restype = wintypes.BOOL
u32.SystemParametersInfoW.argtypes = [wintypes.UINT, wintypes.UINT,
                                      ctypes.c_void_p, wintypes.UINT]
u32.SystemParametersInfoW.restype = wintypes.BOOL
u32.WindowFromPoint.argtypes = [POINT]
u32.WindowFromPoint.restype = wintypes.HWND
u32.GetClassNameW.argtypes = [wintypes.HWND, ctypes.c_wchar_p, ctypes.c_int]
u32.GetClassNameW.restype = ctypes.c_int
u32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
u32.GetCursorPos.argtypes = [ctypes.POINTER(POINT)]

DP = (1536, 1036)


def measure(pt=DP):
    u32.SetCursorPos(pt[0], pt[1])
    time.sleep(0.6)
    p = POINT()
    u32.GetCursorPos(ctypes.byref(p))
    h = u32.WindowFromPoint(p)
    buf = ctypes.create_unicode_buffer(256)
    n = u32.GetClassNameW(h, buf, 256) if h else 0
    cls = buf.value if n else ''
    ci = CURSORINFO()
    ci.cbSize = ctypes.sizeof(CURSORINFO)
    if not u32.GetCursorInfo(ctypes.byref(ci)) or not ci.hCursor:
        return {'bitmap': None, 'class': cls}
    ii = ICONINFO()
    if not u32.GetIconInfo(ci.hCursor, ctypes.byref(ii)):
        return {'bitmap': None, 'class': cls}
    sz = None
    if ii.hbmColor:
        bm = BITMAP()
        if gdi.GetObjectW(ii.hbmColor, ctypes.sizeof(BITMAP), ctypes.byref(bm)):
            sz = [int(bm.bmWidth), int(bm.bmHeight)]
        gdi.DeleteObject(ii.hbmColor)
    if ii.hbmMask:
        gdi.DeleteObject(ii.hbmMask)
    return {'bitmap': sz, 'hotspot': [int(ii.xHotspot), int(ii.yHotspot)],
            'class': cls}


def getval(path, name):
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as k:
            return winreg.QueryValueEx(k, name)
    except OSError:
        return (None, None)


def setval(path, name, val, typ):
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path, 0,
                        winreg.KEY_SET_VALUE) as k:
        winreg.SetValueEx(k, name, 0, typ, val)


def refresh():
    r = ctypes.c_ulong()
    u32.SendMessageTimeoutW(0xFFFF, 0x001A, 0, REG, 0x0002, 2000, ctypes.byref(r))
    u32.SystemParametersInfoW(0x0057, 0, None, 0x01 | 0x02)
    time.sleep(1.5)


def ps(cmd):
    try:
        r = subprocess.run(['powershell', '-NoProfile', '-Command', cmd],
                           capture_output=True, text=True, timeout=60)
        return (r.stdout or '').strip()
    except Exception as e:
        return 'ERR %s' % e


rep = {}
print('=== A) PRTS-Motion 进程状态 ===')
info = ps("Get-CimInstance Win32_Process -Filter \"Name='PRTS-Motion-96.exe'\" "
          "| Select-Object ProcessId,Name,ExecutablePath,CommandLine "
          "| ConvertTo-Json -Compress")
print(' ', info)
rep['prts_before'] = info
try:
    prts = json.loads(info) if info.startswith('{') else (json.loads(info)[0] if info.startswith('[') else {})
except Exception:
    prts = {}
if isinstance(prts, list):
    prts = prts[0] if prts else {}

print()
print('=== 基线 ===')
orig_cs = getval(ACC, 'CursorSize')
orig_cbs = getval(REG, 'CursorBaseSize')
print('  CursorSize =', orig_cs, ' CursorBaseSize =', orig_cbs)
base = measure()
print('  桌面光标 =', base)
rep['baseline'] = base

print()
print('=== B) 杀掉 PRTS -> CursorSize=15 -> 刷新 ===')
if prts.get('ProcessId'):
    print(' ', ps("Stop-Process -Id %d -Force" % prts['ProcessId']))
    time.sleep(2.0)
else:
    print('  PRTS 未运行')
alive = ps("Get-Process -Name 'PRTS-Motion-96' -ErrorAction SilentlyContinue | Measure-Object | Select-Object -Expand Count")
print('  剩余 PRTS 进程数 =', alive)
setval(ACC, 'CursorSize', 15, winreg.REG_DWORD)
refresh()
m = measure()
print('  CursorSize=15 -> 桌面光标 =', m)
rep['B_after_kill_prts'] = m

print()
print('=== C) 叠加 CursorBaseSize(DWORD 大值) ===')
rows_c = []
for v in (96, 192, 256):
    setval(REG, 'CursorBaseSize', v, winreg.REG_DWORD)
    refresh()
    m = measure()
    rows_c.append({'CursorBaseSize': v, 'result': m})
    print('  CursorBaseSize=%d -> %s' % (v, m))
rep['C_base_size'] = rows_c

if DO_EXPLORER:
    print()
    print('=== D) 重启 explorer（系统级生效路径）===')
    print(' ', ps("Stop-Process -Name explorer -Force -ErrorAction SilentlyContinue"))
    time.sleep(4.0)
    n = ps("(Get-Process -Name explorer -ErrorAction SilentlyContinue | Measure-Object).Count")
    print('  explorer 进程数 =', n)
    if n.strip() == '0':
        print(' ', ps("Start-Process explorer.exe"))
        time.sleep(5.0)
        print('  重启后 explorer =',
              ps("(Get-Process -Name explorer -ErrorAction SilentlyContinue | Measure-Object).Count"))
    refresh()
    m = measure()
    print('  重启 explorer 后 ->', m)
    rep['D_explorer'] = m
else:
    print()
    print('=== D) 跳过 explorer 重启（设 CURSOR_TEST_EXPLORER=1 启用）===')
    rep['D_explorer'] = 'skipped'

print()
print('=== 还原 ===')
setval(ACC, 'CursorSize', orig_cs[0], orig_cs[1])
setval(REG, 'CursorBaseSize', orig_cbs[0], orig_cbs[1])
refresh()
print('  CursorSize =', getval(ACC, 'CursorSize'))
print('  CursorBaseSize =', getval(REG, 'CursorBaseSize'))

if prts.get('ExecutablePath'):
    cmd = prts.get('CommandLine') or ('"%s"' % prts['ExecutablePath'])
    print('  重启 PRTS:', cmd)
    print(' ', ps('Start-Process -FilePath "%s" -ArgumentList \'%s\'' % (
        prts['ExecutablePath'],
        (prts.get('CommandLine') or '').replace(prts['ExecutablePath'], '').strip().strip('"'))))
    time.sleep(2.0)
    print('  PRTS 进程数 =',
          ps("(Get-Process -Name 'PRTS-Motion-96' -ErrorAction SilentlyContinue | Measure-Object).Count"))

print('  最终桌面光标 =', measure())

with open(os.path.join(OUT, 'rootcause.json'), 'w', encoding='utf-8') as f:
    json.dump(rep, f, ensure_ascii=False, indent=1)
print('  写入 _diag\\rootcause.json')
