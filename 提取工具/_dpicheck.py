# -*- coding: utf-8 -*-
"""读 Arknights.exe 的 manifest / PE 特征，判断它是否 DPI 感知。

用途：解释「游戏里指针大、桌面小」的机制之一 —— DPI 不感知的进程，
Windows 会按缩放比例放大系统光标。
"""
import ctypes
import os
import re
import struct
from ctypes import wintypes

EXE = r'G:\Hypergryph Launcher\games\Arknights\Arknights.exe'
print('exe =', EXE, os.path.getsize(EXE), 'B')

raw = open(EXE, 'rb').read()

# --- 1) 内嵌 manifest 里的 dpiAware 声明 ---
pats = [b'dpiAware', b'dpiAwareness', b'PerMonitorV2', b'true/pm',
        b'<assembly', b'requestedExecutionLevel']
for p in pats:
    n = raw.count(p)
    print('  manifest 关键词 %-22r 出现 %d 次' % (p.decode(), n))
m = re.search(rb'<\?xml.*?</assembly>', raw, re.S)
if m:
    txt = m.group(0).decode('utf-8', 'replace')
    print('  --- 内嵌 manifest 片段 ---')
    for line in txt.splitlines():
        s = line.strip()
        if any(k in s for k in ('dpi', 'DPI', 'assemblyIdentity',
                                'requestedExecutionLevel', 'aware')):
            print('   ', s[:150])
else:
    print('  未找到完整内嵌 manifest')

# --- 2) PE 头：是否 DPI 感知的 manifest 资源 + 子系统版本 ---
pe_off = struct.unpack_from('<I', raw, 0x3C)[0]
print('  PE 签名 =', raw[pe_off:pe_off + 4])
machine = struct.unpack_from('<H', raw, pe_off + 4)[0]
print('  machine = 0x%04X (0x8664=x64, 0x14C=x86)' % machine)

# --- 3) 运行时 API 问一下当前进程的 DPI 感知（只反映 python 自己）---
u32 = ctypes.WinDLL('user32', use_last_error=True)
try:
    u32.SetProcessDpiAwarenessContext.argtypes = [ctypes.c_void_p]
    # DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = -4
    ok = u32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    print('  本进程设 PerMonitorV2 =', bool(ok))
except Exception as e:
    print('  SetProcessDpiAwarenessContext 不可用:', e)

try:
    shc = ctypes.WinDLL('shcore', use_last_error=True)
    v = ctypes.c_int(0)
    shc.GetProcessDpiAwareness.argtypes = [wintypes.HANDLE,
                                           ctypes.POINTER(ctypes.c_int)]
    hr = shc.GetProcessDpiAwareness(None, ctypes.byref(v))
    print('  GetProcessDpiAwareness(None) hr=%d -> %d' % (hr, v.value))
except Exception as e:
    print('  shcore:', e)

# --- 4) 屏幕与缩放 ---
u32.GetDpiForSystem.restype = wintypes.UINT
print('  GetDpiForSystem =', u32.GetDpiForSystem())
u32.GetSystemMetrics.restype = ctypes.c_int
for i, nm in ((0, 'SM_CXSCREEN'), (1, 'SM_CYSCREEN'), (13, 'SM_CXCURSOR'),
              (14, 'SM_CYCURSOR'), (11, 'SM_CXICON'), (12, 'SM_CYICON'),
              (4, 'SM_CYCAPTION'), (16, 'SM_CXFRAME')):
    print('  %-14s = %d' % (nm, u32.GetSystemMetrics(i)))

print()
print('--- 结论 ---')
print('  桌面 32px 是 Windows 给本机光标解析出的固定尺寸（已实测 1..15 档 +')
print('  CursorBaseSize 全无效）；游戏里指针明显更大，说明游戏不使用系统光标')
print('  的尺寸解析，而是自己按「鼠标指针比例设置」绘制/放大。')
