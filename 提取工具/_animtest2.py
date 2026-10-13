# -*- coding: utf-8 -*-
"""把动画帧绑到桌面箭头槽位上，直接验证动画循环是否真的在驱动桌面光标。

之前 _animtest.py 的 B/C 段是方法错误：采样点在桌面，桌面槽位是 Arrow（静态，
只有 1 帧），而 Wait/AppStarting 只在应用请求时才出现。所以「不同内容数=1」
是【正确行为】，不是 bug。
本测试把 Wait 的 72 帧装进 Arrow(OCR_NORMAL=32512) 槽位，再采样桌面。
"""
import ctypes
import hashlib
import importlib.machinery
import importlib.util
import json
import os
import subprocess
import time
from ctypes import wintypes

TOOL = r'G:\ArknightsCursorExtract\CursorSizeTool\ArknightsCursorSize.pyw'
loader = importlib.machinery.SourceFileLoader('acsize', TOOL)
spec = importlib.util.spec_from_loader('acsize', loader)
mod = importlib.util.module_from_spec(spec)
loader.exec_module(mod)

u32, gdi = mod.u32, mod.gdi

OCR_NORMAL = 32512


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
    ci = CURSORINFO()
    ci.cbSize = ctypes.sizeof(CURSORINFO)
    if not u32.GetCursorInfo(ctypes.byref(ci)) or not ci.hCursor:
        return None
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
    return hashlib.md5(data).hexdigest()[:12]


def ps(c):
    try:
        r = subprocess.run(['powershell', '-NoProfile', '-Command', c],
                           capture_output=True, text=True, timeout=60)
        return (r.stdout or '').strip()
    except Exception:
        return ''


info = ps("Get-CimInstance Win32_Process -Filter \"Name='PRTS-Motion-96.exe'\""
          "|Select-Object ProcessId,ExecutablePath|ConvertTo-Json -Compress")
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

# --- 把 Wait 的 72 帧装进 Arrow 槽位 ---
orig_rf = mod.role_frames
wait_frames = orig_rf('Wait')
print('Wait 帧数 =', len(wait_frames))
mod.role_frames = lambda k: wait_frames if k == 'Arrow' else orig_rf(k)
mod.ROLES = [('Arrow', 'Arrow', OCR_NORMAL, (28, 20))]

print()
print('=== A) 静态对照（animate=False）：应当只有 1 种内容 ===')
e = mod.Engine()
e.animate = False
e.build(128, only=['Arrow'])
print('  构造帧数 =', len(e.masters['Arrow']))
e.apply_all()
u32.SetCursorPos(*DP)
sigs = {}
for _ in range(14):
    time.sleep(0.08)
    u32.SetCursorPos(*DP)
    sigs[cur_hash()] = sigs.get(cur_hash(), 0) + 1
print('  14 次采样，不同内容数 =', len(sigs), '(期望 1)')

print()
print('=== B) 动画（start_anim, 25ms/帧）：应当出现多种内容 ===')
e.anim_rates['Arrow'] = 25
e.start_anim()
sigs2, seq = {}, []
t0 = time.time()
while time.time() - t0 < 3.0:
    u32.SetCursorPos(*DP)
    time.sleep(0.045)
    h = cur_hash()
    sigs2[h] = sigs2.get(h, 0) + 1
    seq.append(h)
e.stop_anim()
print('  3 秒采样 %d 次，不同内容数 = %d (期望 > 5)' % (len(seq), len(sigs2)))
print('  前 30 次序列 =', seq[:30])
print('  动画索引推进到 =', e.anim_idx.get('Arrow'))

print()
print('=== C) 停表验证：stop_anim 后应恢复静态 ===')
time.sleep(0.6)
sigs3 = {}
for _ in range(10):
    time.sleep(0.08)
    u32.SetCursorPos(*DP)
    sigs3[cur_hash()] = sigs3.get(cur_hash(), 0) + 1
print('  10 次采样，不同内容数 =', len(sigs3), '(期望 1)')

print()
print('=== D) 节拍检测复核（原 ROLES 下各动画角色的 ms）===')
mod.role_frames = orig_rf
mod.ROLES = [('Wait', 'Wait', 32514, (48, 48)), ('No', 'No', 32648, (28, 20)),
             ('SizeAll', 'SizeAll', 32646, (48, 48)),
             ('AppStarting', 'AppStarting', 32650, (28, 20))]
e4 = mod.Engine()
e4.build(64)
for k, v in e4.anim_rates.items():
    print('   %-12s %s ms' % (k, v))
print('  源 .ani 的 dispRate/rate 值（帧延时以 1/60 秒为单位）:')
for k in ('Wait', 'No', 'SizeAll', 'AppStarting'):
    p = os.path.join(mod.LARGE, 'Arknights_Crystal_%s_large.ani' % k)
    if os.path.exists(p):
        _f, disp, rates = orig_rf and mod.read_ani_frames(p)
        print('     %-12s dispRate=%s rate=%s' % (
            k, disp, ('%d 项 均值%.2f' % (len(rates), sum(rates) / len(rates)))
            if rates else None))

print()
print('=== E) 恢复 ===')
for x in (e, e4):
    try:
        x.destroy()
    except Exception:
        pass
e5 = mod.Engine()
print('  恢复角色数 =', e5.restore_scheme())
time.sleep(0.5)

if prts.get('ExecutablePath'):
    ps('Start-Process -FilePath "%s" -ArgumentList \'"%s"\'' % (
        prts['ExecutablePath'],
        r'C:\Users\22442\AppData\Local\PRTS\Replica-v8-Windows\cursors-34497b84e5b0d7cf'))
    time.sleep(1.5)
    print('  PRTS 进程数 =', ps("(Get-Process -Name 'PRTS-Motion-96' "
                               "-ErrorAction SilentlyContinue|Measure-Object).Count"))
