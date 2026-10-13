# -*- coding: utf-8 -*-
"""最终验收：走工具的真实 --apply 路径，把 1.20x(115px) 装上，
在真实桌面点上逐尺寸采样确认，然后保持安装状态。"""
import ctypes
import ctypes.wintypes as W
import subprocess
import sys
import time

u32 = ctypes.windll.user32
gdi = ctypes.windll.gdi32
u32.SetProcessDPIAware()

TOOL = r'G:\ArknightsCursorExtract\CursorSizeTool\ArknightsCursorSize.pyw'
PYW = r'C:\Users\22442\AppData\Local\Programs\Python\Python311\pythonw.exe'
DESK = ('Progman', 'WorkerW', 'SysListView32', 'SHELLDLL_DefView', 'Shell_TrayWnd')


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
print('探针点 =', PT, cls_at(PT), '\n')


def measure(samples=4, gap=0.45):
    u32.SetCursorPos(PT[0] + 7, PT[1] + 7)
    time.sleep(gap)
    u32.SetCursorPos(*PT)
    time.sleep(gap)
    out = []
    for _ in range(samples):
        ci = CURSORINFO()
        ci.cbSize = ctypes.sizeof(CURSORINFO)
        if not u32.GetCursorInfo(ctypes.byref(ci)):
            out.append(None)
            continue
        ii = ICONINFO()
        if not u32.GetIconInfo(ci.hCursor, ctypes.byref(ii)):
            out.append(None)
            continue
        bm = BITMAP()
        ok = gdi.GetObjectW(ii.hbmColor, ctypes.sizeof(BITMAP),
                            ctypes.byref(bm))
        out.append(((bm.bmWidth, bm.bmHeight) if ok else None,
                    (ii.xHotspot, ii.yHotspot)))
        if ii.hbmColor:
            gdi.DeleteObject(ii.hbmColor)
        if ii.hbmMask:
            gdi.DeleteObject(ii.hbmMask)
        time.sleep(gap)
    return out


print('=== 基线 ===')
before = measure()
for s in before:
    print('   ', s)

print('\n=== 走工具真实入口：--apply 1.20（含动画常驻）===')
# 先确保动画开关状态已知：读 state.json
import json, os
st = os.path.join(os.path.dirname(TOOL), 'state.json')
print('   state.json =', open(st, encoding='utf-8').read().strip()
      if os.path.exists(st) else '(无)')

p = subprocess.Popen([PYW, TOOL, '--apply', '1.20'],
                     stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
time.sleep(6)
# 工具在动画模式下会常驻；采样几次
after = measure()
for s in after:
    print('   ', s)

ok = all(a[0] == (115, 115) for a in after if a)
print('\n   ★ 目标 115x115   实测 %s   =>  %s' %
      ([a[0] for a in after if a], '通过 ✔' if ok else '未通过 ✘'))

# 顺手确认热点比例：115px 时 Arrow 热点应为 round(28*115/96), round(20*115/96) = (34,24)
hs = [a[1] for a in after if a]
print('   ★ 热点 %s   期望 (34, 24)  =>  %s' %
      (hs, '通过 ✔' if all(h == (34, 24) for h in hs) else '未通过 ✘'))

print('\n=== 保持安装状态（工具常驻管理中，不杀进程）===')
print('   --apply 进程 pid =', p.pid, ' alive =', p.poll() is None)
