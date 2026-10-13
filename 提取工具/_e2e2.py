# -*- coding: utf-8 -*-
"""端到端实测 v2 —— 修掉探针点问题。

v1 的教训：SetCursorPos(1536,1036) 落在 Chrome/Electron 窗口上（DSH 自己），
读到的不是桌面光标。必须先用 EnumWindows 找一个「真的没被任何窗口盖住」的
桌面像素（WindowFromPoint 返回 Progman / WorkerW / SysListView32），再量。
"""
import ctypes
import ctypes.wintypes as W
import importlib.machinery
import time

u32 = ctypes.windll.user32
gdi = ctypes.windll.gdi32
u32.SetProcessDPIAware()

TOOL = r'G:\ArknightsCursorExtract\CursorSizeTool\ArknightsCursorSize.pyw'
mod = importlib.machinery.SourceFileLoader('acsize', TOOL).load_module()

DESK_CLASSES = ('Progman', 'WorkerW', 'SysListView32', 'SHELLDLL_DefView',
                'Shell_TrayWnd')


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
    getp = u32.GetParent
    while True:
        p = getp(h)
        if not p:
            break
        h = p
    buf = ctypes.create_unicode_buffer(256)
    u32.GetClassNameW(h, buf, 256)
    return buf.value


def find_desktop_pt():
    """在屏幕上找若干真正暴露的桌面像素点。"""
    w = u32.GetSystemMetrics(0)
    h = u32.GetSystemMetrics(1)
    cands = []
    for y in range(60, h - 120, 40):
        for x in range(10, w - 10, 60):
            c = cls_at((x, y))
            if c in DESK_CLASSES:
                cands.append(((x, y), c))
                if len(cands) >= 5:
                    return cands
    return cands


def measure(pt):
    u32.SetCursorPos(*pt)
    time.sleep(0.30)
    ci = CURSORINFO()
    ci.cbSize = ctypes.sizeof(CURSORINFO)
    if not u32.GetCursorInfo(ctypes.byref(ci)):
        return {'err': 'GetCursorInfo'}
    ii = ICONINFO()
    if not u32.GetIconInfo(ci.hCursor, ctypes.byref(ii)):
        return {'err': 'GetIconInfo'}
    bm = BITMAP()
    ok = gdi.GetObjectW(ii.hbmColor, ctypes.sizeof(BITMAP), ctypes.byref(bm))
    res = {'bitmap': [bm.bmWidth, bm.bmHeight] if ok else None,
           'hotspot': [ii.xHotspot, ii.yHotspot], 'class': cls_at(pt)}
    if ii.hbmColor:
        gdi.DeleteObject(ii.hbmColor)
    if ii.hbmMask:
        gdi.DeleteObject(ii.hbmMask)
    return res


print('=== 找一个真正暴露的桌面像素 ===')
pts = find_desktop_pt()
for p, c in pts:
    print('   ', p, c)
if not pts:
    raise SystemExit('!! 找不到桌面像素（整个屏幕都被窗口盖住）')
PT = pts[0][0]
print('   使用探针点', PT)

print('=== 1. 基线（当前系统光标） ===')
base = measure(PT)
print('   ', base)

eng = mod.Engine()
n = int(round(mod.NATIVE * 1.20))
print('=== 2. build %dpx ===' % n)
t0 = time.time()
eng.build(n)
print('   耗时 %.2fs' % (time.time() - t0))
eng.animate = False

print('=== 3. 装上 Arrow @ %dpx ===' % n)
print('   apply ->', eng.apply('Arrow', 0))
time.sleep(0.6)
after = measure(PT)
print('   ', after)

print()
ok = after.get('bitmap') == [n, n]
print('   ★ 基线 %s  →  应用后 %s   目标 [%d,%d]   =>  %s' %
      (base.get('bitmap'), after.get('bitmap'), n, n,
       '通过 ✔' if ok else '未通过 ✘'))

print('=== 4. 再试 192px，确认尺寸真的可控 ===')
eng2 = mod.Engine()
eng2.build(192)
eng2.animate = False
eng2.apply('Arrow', 0)
time.sleep(0.6)
m192 = measure(PT)
print('   ', m192)
print('   ★ 192px => %s' % ('通过 ✔' if m192.get('bitmap') == [192, 192]
                              else '未通过 ✘'))

print('=== 5. 恢复 ===')
print('   恢复 %d 个角色' % eng2.restore_scheme())
eng.destroy()
eng2.destroy()
time.sleep(0.8)
print('   恢复后 =', measure(PT))
