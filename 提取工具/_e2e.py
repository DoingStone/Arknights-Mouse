# -*- coding: utf-8 -*-
"""端到端实测：用工具自己的 Engine 按 1.20x(115px) 构造并装上 Arrow，
然后真的去量桌面光标位图尺寸，验证「所见即所得」成立。
只动 Arrow 一个角色，测完立刻恢复。"""
import ctypes
import ctypes.wintypes as W
import importlib.machinery
import os
import sys
import time

u32 = ctypes.windll.user32
gdi = ctypes.windll.gdi32
u32.SetProcessDPIAware()

TOOL = r'G:\ArknightsCursorExtract\CursorSizeTool\ArknightsCursorSize.pyw'
mod = importlib.machinery.SourceFileLoader('acsize', TOOL).load_module()


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

DESK_PT = (1536, 1036)


def measure():
    """钉到桌面类窗口上再量活光标。"""
    u32.SetCursorPos(*DESK_PT)
    time.sleep(0.30)
    ci = CURSORINFO()
    ci.cbSize = ctypes.sizeof(CURSORINFO)
    if not u32.GetCursorInfo(ctypes.byref(ci)):
        return None
    cls = ctypes.create_unicode_buffer(256)
    u32.GetClassNameW(u32.WindowFromPoint(W.POINT(*DESK_PT)), cls, 256)
    ii = ICONINFO()
    if not u32.GetIconInfo(ci.hCursor, ctypes.byref(ii)):
        return {'err': 'GetIconInfo failed'}
    bm = BITMAP()
    ok = gdi.GetObjectW(ii.hbmColor, ctypes.sizeof(BITMAP), ctypes.byref(bm))
    if ii.hbmColor:
        gdi.DeleteObject(ii.hbmColor)
    if ii.hbmMask:
        gdi.DeleteObject(ii.hbmMask)
    if not ok:
        return {'bitmap': None, 'hotspot': [ii.xHotspot, ii.yHotspot],
                'class': cls.value}
    return {'bitmap': [bm.bmWidth, bm.bmHeight],
            'hotspot': [ii.xHotspot, ii.yHotspot], 'class': cls.value}


print('=== 0. 测试前桌面光标 ===')
b = measure()
print('  ', b)

eng = mod.Engine()

print('=== 1. 按 1.20x 构造全部角色 ===')
n = int(round(mod.NATIVE * 1.20))
print('   目标像素尺寸 n =', n)
t0 = time.time()
eng.build(n)
print('   build 耗时 %.2fs' % (time.time() - t0))

print('=== 2. 逐个角色的 HCURSOR 位图尺寸（构造结果自证）===')
sizes = {}
for key, zh, ocr, hs in mod.ROLES:
    m = eng.masters.get(key)
    if not m:
        sizes[key] = None
        continue
    hcur = m[0]
    ii = ICONINFO()
    if u32.GetIconInfo(hcur, ctypes.byref(ii)):
        bm = BITMAP()
        ok = gdi.GetObjectW(ii.hbmColor, ctypes.sizeof(BITMAP),
                            ctypes.byref(bm))
        if ii.hbmColor:
            gdi.DeleteObject(ii.hbmColor)
        if ii.hbmMask:
            gdi.DeleteObject(ii.hbmMask)
        sizes[key] = (bm.bmWidth, bm.bmHeight) if ok else None
    else:
        sizes[key] = None
bad = {k: v for k, v in sizes.items() if v != (n, n)}
print('   17 个角色位图尺寸全部 == (%d,%d) : %s' % (n, n, not bad))
if bad:
    print('   异常:', bad)

print('=== 3. 真的装上系统（只动 Arrow）===')
eng.animate = False
ok = eng.apply('Arrow', 0)
print('   SetSystemCursor(Arrow) ->', ok)
time.sleep(0.5)

print('=== 4. 量桌面活光标 ===')
a = measure()
print('  ', a)
got = a.get('bitmap') if a else None
print()
print('   ★ 目标 (%d, %d)   实测 %s   =>  %s' %
      (n, n, got, '通过' if got == [n, n] else '未通过'))

print('=== 5. 恢复 ===')
cnt = eng.restore_scheme()
eng.destroy()
time.sleep(0.6)
r = measure()
print('   恢复 %d 个角色；恢复后桌面光标 = %s' % (cnt, r))
