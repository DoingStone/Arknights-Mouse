# -*- coding: utf-8 -*-
"""决策探针：
A) 动画帧如果以 PNG 存储，总共多大？（决定 exe 能否完全自包含）
B) 哪些「鼠标相关参数」可以安全读写并用 SPI_GET* 回读验证？
"""
import ctypes
import ctypes.wintypes as W
import io
import os

PACK = r'G:\ArknightsCursorExtract\CrystalCursorPack'
LARGE = os.path.join(PACK, 'cursors', 'large')
EXTRACTED = os.path.join(PACK, 'extracted')

import importlib.machinery
mod = importlib.machinery.SourceFileLoader(
    'acsize', r'G:\ArknightsCursorExtract\CursorSizeTool\ArknightsCursorSize.pyw'
).load_module()

print('=== A) 动画帧 PNG 化后的体积 ===')
total = 0
ani_roles = ['AppStarting', 'Wait', 'No', 'SizeNS', 'SizeWE',
             'SizeNWSE', 'SizeNESW', 'SizeAll']
for k in ani_roles:
    p = os.path.join(LARGE, 'Arknights_Crystal_%s_large.ani' % k)
    if not os.path.exists(p):
        print('  %-12s 缺失' % k)
        continue
    frames, _d, _r = mod.read_ani_frames(p)
    raw = 0
    for (im, hx, hy) in frames:
        b = io.BytesIO()
        im.convert('RGBA').save(b, 'PNG', optimize=True)
        raw += b.tell()
    total += raw
    print('  %-12s %3d 帧  PNG 合计 %7.1f KB  (原始 %.1f MB)'
          % (k, len(frames), raw / 1024.0,
             os.path.getsize(p) / 1048576.0))
print('  动画 PNG 总计 = %.2f MB' % (total / 1048576.0))

stat = 0
for k in ['Arrow', 'Help', 'Crosshair', 'IBeam', 'NWPen', 'UpArrow',
          'Hand', 'Pin', 'Person']:
    p = os.path.join(EXTRACTED, 'Arknights_Crystal_%s_native96.png' % k)
    if os.path.exists(p):
        stat += os.path.getsize(p)
print('  静态角色 native96 PNG 总计 = %.1f KB' % (stat / 1024.0))
print('  => 全部美术 PNG 化 ≈ %.2f MB' % ((total + stat) / 1048576.0))

print('\n=== B) 鼠标参数 SPI 可读性 ===')
u32 = ctypes.windll.user32
SPI = {
    'MouseTrails':       (0x005E, 'int'),
    'MouseSensitivity':  (0x0070, 'int'),
    'MouseSpeed':        (0x0002, 'int'),
    'MouseThreshold1':   (0x0004, 'int'),
    'MouseThreshold2':   (0x0006, 'int'),
    'DoubleClickSpeed':  (0x001E, 'uint'),
    'WheelScrollLines':  (0x0068, 'uint'),
    'SwapButtons':       (0x0023, 'bool'),
    'SnapToDefaultButton': (0x005F, 'bool'),
    'MouseVanish':       (0x101B, 'bool'),
    'ClickLock':         (0x101F, 'bool'),
    'ActiveWindowTracking': (0x003E, 'bool'),
}
for name, (code, kind) in SPI.items():
    if kind == 'bool':
        v = W.BOOL()
        ok = u32.SystemParametersInfoW(code, 0, ctypes.byref(v), 0)
        print('  %-22s 0x%04X  GET ok=%s value=%s' % (name, code, ok, v.value))
    elif kind == 'int':
        v = ctypes.c_int()
        ok = u32.SystemParametersInfoW(code, 0, ctypes.byref(v), 0)
        print('  %-22s 0x%04X  GET ok=%s value=%s' % (name, code, ok, v.value))
    else:
        v = ctypes.c_uint()
        ok = u32.SystemParametersInfoW(code, 0, ctypes.byref(v), 0)
        print('  %-22s 0x%04X  GET ok=%s value=%s' % (name, code, ok, v.value))

print('\n=== C) 对应注册表值 ===')
import winreg
with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Control Panel\Mouse') as k:
    i = 0
    while True:
        try:
            n, v, t = winreg.EnumValue(k, i)
        except OSError:
            break
        print('  %-26s = %-16r type=%s' % (n, v, t))
        i += 1
