# -*- coding: utf-8 -*-
"""最终验收：走 GUI 的真实代码路径（App.do_apply），全程 1:1 量桌面活光标。"""
import ctypes
import ctypes.wintypes as W
import importlib.machinery
import time

u32 = ctypes.windll.user32
gdi = ctypes.windll.gdi32
u32.SetProcessDPIAware()

TOOL = r'G:\ArknightsCursorExtract\CursorSizeTool\ArknightsCursorSize.pyw'
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


def read_cur():
    u32.SetCursorPos(PT[0] + 7, PT[1] + 7)
    time.sleep(0.5)
    u32.SetCursorPos(*PT)
    time.sleep(0.5)
    ci = CURSORINFO()
    ci.cbSize = ctypes.sizeof(CURSORINFO)
    u32.GetCursorInfo(ctypes.byref(ci))
    ii = ICONINFO()
    u32.GetIconInfo(ci.hCursor, ctypes.byref(ii))
    bm = BITMAP()
    ok = gdi.GetObjectW(ii.hbmColor, ctypes.sizeof(BITMAP), ctypes.byref(bm))
    r = (bm.bmWidth, bm.bmHeight, ii.xHotspot, ii.yHotspot) if ok else None
    if ii.hbmColor:
        gdi.DeleteObject(ii.hbmColor)
    if ii.hbmMask:
        gdi.DeleteObject(ii.hbmMask)
    return r


print('探针点 =', PT, cls_at(PT))
mod = importlib.machinery.SourceFileLoader('acsize', TOOL).load_module()

print('\n=== 走 GUI 真实路径：App.do_apply() ===')
import tkinter as tk

app = mod.App(tk.Tk())
app.sc.set(mod.DEFAULT_SCALE)
app.on_slide(mod.DEFAULT_SCALE)
print('   滑杆值      =', app.sc.get(), ' -> self.scale =', app.scale)
print('   预览读数    =', app.lbl.cget('text'))
t0 = time.time()
app.do_apply(quiet=True)
print('   状态栏      =', app.status.cget('text'))
print('   引擎尺寸    = %dpx · 已装角色 %d 个' % (app.eng.size, len(app.eng.applied)))
print('   耗时        = %.1fs' % (time.time() - t0))

print('\n=== 桌面活光标实测（4 次采样）===')
for i in range(4):
    time.sleep(0.6)
    print('   #%d  %s' % (i + 1, read_cur()))

exp = (115, 115, round(28 * 115 / 96.0), round(20 * 115 / 96.0))
print('\n期望 (w,h,hotx,hoty) =', exp)

import winreg
with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Control Panel\Cursors') as k:
    scheme = winreg.QueryValueEx(k, '')[0]
print('注册表方案名 =', repr(scheme))

app.root.destroy()
