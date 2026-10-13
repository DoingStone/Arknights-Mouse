# -*- coding: utf-8 -*-
"""内容级动画验证：不看 HCURSOR 句柄值（会被 GDI 复用），而是把当前光标
用 DrawIconEx 画到 DIB 上，对像素做哈希，看随时间是否变化。
"""
import ctypes
import hashlib
import importlib.machinery
import importlib.util
import os
import time
from ctypes import wintypes

TOOL = r'G:\ArknightsCursorExtract\CursorSizeTool\ArknightsCursorSize.pyw'
loader = importlib.machinery.SourceFileLoader('acsize', TOOL)
spec = importlib.util.spec_from_loader('acsize', loader)
mod = importlib.util.module_from_spec(spec)
loader.exec_module(mod)

u32, gdi = mod.u32, mod.gdi


class CURSORINFO(ctypes.Structure):
    _fields_ = [('cbSize', wintypes.DWORD), ('flags', wintypes.DWORD),
                ('hCursor', wintypes.HANDLE), ('ptScreenPos', wintypes.POINT)]


class BMIH(ctypes.Structure):
    _fields_ = [('biSize', wintypes.DWORD), ('biWidth', wintypes.LONG),
                ('biHeight', wintypes.LONG), ('biPlanes', wintypes.WORD),
                ('biBitCount', wintypes.WORD), ('biCompression', wintypes.DWORD),
                ('biSizeImage', wintypes.DWORD), ('biXPelsPerMeter', wintypes.LONG),
                ('biYPelsPerMeter', wintypes.LONG), ('biClrUsed', wintypes.DWORD),
                ('biClrImportant', wintypes.DWORD)]


u32.GetCursorInfo.argtypes = [ctypes.POINTER(CURSORINFO)]
u32.GetCursorInfo.restype = wintypes.BOOL
u32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
u32.DrawIconEx.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int,
                           wintypes.HANDLE, ctypes.c_int, ctypes.c_int,
                           wintypes.UINT, wintypes.HANDLE, wintypes.UINT]
u32.DrawIconEx.restype = wintypes.BOOL
gdi.CreateDIBSection.argtypes = [wintypes.HDC, ctypes.c_void_p, wintypes.UINT,
                                 ctypes.POINTER(ctypes.c_void_p),
                                 wintypes.HANDLE, wintypes.DWORD]
gdi.CreateDIBSection.restype = wintypes.HBITMAP
gdi.CreateCompatibleDC.argtypes = [wintypes.HDC]
gdi.CreateCompatibleDC.restype = wintypes.HDC
gdi.SelectObject.argtypes = [wintypes.HDC, wintypes.HANDLE]
gdi.SelectObject.restype = wintypes.HANDLE
gdi.DeleteObject.argtypes = [wintypes.HANDLE]
gdi.DeleteDC.argtypes = [wintypes.HDC]

N = 128
DP = (1536, 1036)


def cur_hash():
    """把当前光标画到黑底 DIB 上，返回像素哈希。"""
    ci = CURSORINFO()
    ci.cbSize = ctypes.sizeof(CURSORINFO)
    if not u32.GetCursorInfo(ctypes.byref(ci)) or not ci.hCursor:
        return None, None
    bi = BMIH()
    bi.biSize = ctypes.sizeof(BMIH)
    bi.biWidth = N
    bi.biHeight = -N
    bi.biPlanes = 1
    bi.biBitCount = 32
    bits = ctypes.c_void_p()
    hbm = gdi.CreateDIBSection(None, ctypes.byref(bi), 0, ctypes.byref(bits),
                               None, 0)
    ctypes.memset(bits, 0, N * N * 4)
    hdc = gdi.CreateCompatibleDC(None)
    old = gdi.SelectObject(hdc, hbm)
    u32.DrawIconEx(hdc, 0, 0, ci.hCursor, N, N, 0, None, 0x0003)
    gdi.SelectObject(hdc, old)
    buf = (ctypes.c_ubyte * (N * N * 4)).from_address(bits.value)
    data = bytes(buf)
    gdi.DeleteDC(hdc)
    gdi.DeleteObject(hbm)
    return hashlib.md5(data).hexdigest()[:12], int(ci.hCursor)


import subprocess


def ps(c):
    try:
        r = subprocess.run(['powershell', '-NoProfile', '-Command', c],
                           capture_output=True, text=True, timeout=60)
        return (r.stdout or '').strip()
    except Exception:
        return ''


info = ps("Get-CimInstance Win32_Process -Filter \"Name='PRTS-Motion-96.exe'\""
          "|Select-Object ProcessId,ExecutablePath|ConvertTo-Json -Compress")
import json
prts = {}
try:
    d = json.loads(info)
    prts = d[0] if isinstance(d, list) else d
except Exception:
    pass
if prts.get('ProcessId'):
    ps("Stop-Process -Id %d -Force" % prts['ProcessId'])
    time.sleep(2.0)
    print('PRTS-Motion 已停')

print()
print('=== A) 静态：ani=False 时抖动检测（应当只有 1 种内容）===')
e = mod.Engine()
e.animate = False
e.build(128)
e.apply_all()
u32.SetCursorPos(*DP)
sigs = {}
for _ in range(12):
    time.sleep(0.08)
    u32.SetCursorPos(*DP)
    h, hc = cur_hash()
    sigs[h] = sigs.get(h, 0) + 1
print('  12 次采样，不同内容数 =', len(sigs), list(sigs.items())[:4])

print()
print('=== B) 动画：start_anim() 后采样（应当出现多种内容）===')
e.start_anim()
sigs2 = {}
seq = []
t0 = time.time()
while time.time() - t0 < 3.0:
    u32.SetCursorPos(*DP)
    time.sleep(0.05)
    h, hc = cur_hash()
    sigs2[h] = sigs2.get(h, 0) + 1
    seq.append(h)
print('  3 秒采样 %d 次，不同内容数 = %d' % (len(seq), len(sigs2)))
print('  前 24 次序列 =', seq[:24])
e.stop_anim()

print()
print('=== C) 单角色验证：只动画 Wait（忙）===')
e2 = mod.Engine()
e2.build(128, only=['Wait'])
e2.apply_all()
e2.anim_idx['Wait'] = 0
e2.start_anim()
sigs3 = {}
t0 = time.time()
while time.time() - t0 < 2.0:
    u32.SetCursorPos(*DP)
    time.sleep(0.04)
    h, _ = cur_hash()
    sigs3[h] = sigs3.get(h, 0) + 1
print('  Wait 单角色：不同内容数 =', len(sigs3), '（帧数 72）')
e2.stop_anim()

print()
print('=== D) 恢复 ===')
e3 = mod.Engine()
print('  恢复角色数 =', e3.restore_scheme())
time.sleep(0.6)

if prts.get('ExecutablePath'):
    ps('Start-Process -FilePath "%s" -ArgumentList \'"%s"\'' % (
        prts['ExecutablePath'],
        r'C:\Users\22442\AppData\Local\PRTS\Replica-v8-Windows\cursors-34497b84e5b0d7cf'))
    time.sleep(1.5)
    print('  PRTS 进程数 =', ps("(Get-Process -Name 'PRTS-Motion-96' "
                               "-ErrorAction SilentlyContinue|Measure-Object).Count"))
