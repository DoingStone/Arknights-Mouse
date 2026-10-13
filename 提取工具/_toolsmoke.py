# -*- coding: utf-8 -*-
"""在无界面模式下冒烟测试 ArknightsCursorSize.pyw 的 Engine：
  1) 导入 .pyw 模块
  2) build(128) -> 检查角色数、热点、动画节拍
  3) apply_all() -> 桌面实测位图尺寸
  4) 逐尺寸扫 32/64/96/144/192/256 -> 桌面实测
  5) 结束后恢复原始光标
"""
import ctypes
import importlib.machinery
import importlib.util
import json
import os
import time
import winreg
from ctypes import wintypes

from PIL import Image

TOOL = r'G:\ArknightsCursorExtract\CursorSizeTool\ArknightsCursorSize.pyw'
OUT = r'G:\ArknightsCursorExtract\_diag'

loader = importlib.machinery.SourceFileLoader('acsize', TOOL)
spec = importlib.util.spec_from_loader('acsize', loader)
mod = importlib.util.module_from_spec(spec)
loader.exec_module(mod)
print('模块已导入：', TOOL)

u32 = mod.u32
gdi = mod.gdi

u32.GetCursorInfo.argtypes = [ctypes.POINTER(ctypes.c_byte * 24)]
u32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]


class CURSORINFO(ctypes.Structure):
    _fields_ = [('cbSize', wintypes.DWORD), ('flags', wintypes.DWORD),
                ('hCursor', wintypes.HANDLE), ('ptScreenPos', wintypes.POINT)]


class ICONINFO(ctypes.Structure):
    _fields_ = [('fIcon', wintypes.BOOL), ('xHotspot', wintypes.DWORD),
                ('yHotspot', wintypes.DWORD), ('hbmMask', wintypes.HANDLE),
                ('hbmColor', wintypes.HANDLE)]


class BITMAP(ctypes.Structure):
    _fields_ = [('bmType', wintypes.LONG), ('bmWidth', wintypes.LONG),
                ('bmHeight', wintypes.LONG), ('bmWidthBytes', wintypes.LONG),
                ('bmPlanes', wintypes.WORD), ('bmBitsPixel', wintypes.WORD),
                ('bmBits', ctypes.c_void_p)]


u32.GetCursorInfo.argtypes = [ctypes.POINTER(CURSORINFO)]
u32.GetCursorInfo.restype = wintypes.BOOL
u32.GetIconInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(ICONINFO)]
u32.GetIconInfo.restype = wintypes.BOOL
gdi.GetObjectW.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p]
gdi.GetObjectW.restype = ctypes.c_int
gdi.DeleteObject.argtypes = [wintypes.HANDLE]
u32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
u32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
u32.WindowFromPoint.argtypes = [wintypes.POINT]
u32.WindowFromPoint.restype = wintypes.HWND
u32.GetClassNameW.argtypes = [wintypes.HWND, ctypes.c_wchar_p, ctypes.c_int]

DP = (1536, 1036)


def desk():
    u32.SetCursorPos(DP[0], DP[1])
    time.sleep(0.65)
    p = wintypes.POINT()
    u32.GetCursorPos(ctypes.byref(p))
    h = u32.WindowFromPoint(p)
    b = ctypes.create_unicode_buffer(256)
    n = u32.GetClassNameW(h, b, 256) if h else 0
    ci = CURSORINFO()
    ci.cbSize = ctypes.sizeof(CURSORINFO)
    if not u32.GetCursorInfo(ctypes.byref(ci)) or not ci.hCursor:
        return None, None, b.value if n else ''
    ii = ICONINFO()
    if not u32.GetIconInfo(ci.hCursor, ctypes.byref(ii)):
        return None, None, b.value if n else ''
    sz = None
    if ii.hbmColor:
        bm = BITMAP()
        if gdi.GetObjectW(ii.hbmColor, ctypes.sizeof(BITMAP), ctypes.byref(bm)):
            sz = (int(bm.bmWidth), int(bm.bmHeight))
        gdi.DeleteObject(ii.hbmColor)
    if ii.hbmMask:
        gdi.DeleteObject(ii.hbmMask)
    return sz, (int(ii.xHotspot), int(ii.yHotspot)), (b.value if n else '')


# --- 停 PRTS，避免干扰 ---
import subprocess


def ps(c):
    try:
        r = subprocess.run(['powershell', '-NoProfile', '-Command', c],
                           capture_output=True, text=True, timeout=60)
        return (r.stdout or '').strip()
    except Exception as e:
        return 'ERR %s' % e


info = ps("Get-CimInstance Win32_Process -Filter \"Name='PRTS-Motion-96.exe'\" "
          "| Select-Object ProcessId,ExecutablePath | ConvertTo-Json -Compress")
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
print('=== 1) build(128) 结构检查 ===')
e = mod.Engine()
e.animate = False
keys = e.build(128)
print('  构造成功角色数 =', len(keys), '/', len(mod.ROLES))
print('  ', ', '.join(keys))
missing = [r[0] for r in mod.ROLES if r[0] not in keys]
print('  缺失 =', missing or '无')
anim = {k: v for k, v in e.anim_rates.items() if v}
print('  动画节拍(ms) =', anim)
print('  帧数 =', {k: len(v) for k, v in list(e.masters.items())
                  if len(v) > 1})
print('  热点(128px) =', {k: v[0] for k, v in list(e.hotspots.items())[:5]})

print()
print('=== 2) apply_all() -> 桌面实测 ===')
n = e.apply_all()
print('  已应用 =', n)
sz, hs, cls = desk()
print('  桌面位图 =', sz, ' 热点 =', hs, ' [%s]' % cls)

print()
print('=== 3) 逐尺寸扫描（桌面实测）===')
rows = []
for want in (32, 48, 64, 96, 144, 192, 256, 320, 384):
    e.build(want)
    e.apply_all()
    time.sleep(0.4)
    sz, hs, cls = desk()
    exp = (int(round(28 * want / 96.0)), int(round(20 * want / 96.0)))
    ok = (sz == (want, want)) and (hs == exp)
    rows.append({'want': want, 'desktop': sz, 'hotspot': hs,
                 'expected_hotspot': list(exp), 'ok': bool(ok)})
    print('  请求 %-4d -> 桌面 %-12s 热点 %-12s 期望 %-12s %s' % (
        want, str(sz), str(hs), str(exp), '✓' if ok else '✗'))

print()
print('=== 4) 动画引擎（忙 72 帧）===')
e.build(128)
e.animate = True
e.apply_all()
e.start_anim()
seen = set()
t0 = time.time()
while time.time() - t0 < 2.5:
    u32.SetCursorPos(DP[0], DP[1])
    time.sleep(0.06)
    ci = CURSORINFO()
    ci.cbSize = ctypes.sizeof(CURSORINFO)
    if u32.GetCursorInfo(ctypes.byref(ci)) and ci.hCursor:
        seen.add(int(ci.hCursor))
print('  2.5 秒内观察到的不同 HCURSOR 句柄数 =', len(seen), '(>1 说明动画在跑)')
e.stop_anim()

print()
print('=== 5) 恢复 ===')
e2 = mod.Engine()
print('  恢复角色数 =', e2.restore_scheme())
time.sleep(0.6)
print('  桌面 =', desk())

if prts.get('ExecutablePath'):
    ps('Start-Process -FilePath "%s" -ArgumentList \'"%s"\'' % (
        prts['ExecutablePath'],
        r'C:\Users\22442\AppData\Local\PRTS\Replica-v8-Windows\cursors-34497b84e5b0d7cf'))
    time.sleep(2.0)
    print('  PRTS 进程数 =', ps("(Get-Process -Name 'PRTS-Motion-96' "
                               "-ErrorAction SilentlyContinue | Measure-Object).Count"))

with open(os.path.join(OUT, 'tool_smoke.json'), 'w', encoding='utf-8') as f:
    json.dump({'roles': keys, 'anim_ms': anim, 'scan': rows}, f,
              ensure_ascii=False, indent=1)
print('  写入 _diag\\tool_smoke.json')
