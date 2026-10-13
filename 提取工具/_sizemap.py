# -*- coding: utf-8 -*-
"""测出 HKCU\\Software\\Microsoft\\Accessibility\\CursorSize (1..15) -> 系统实际渲染的像素尺寸。
用 GetCursorInfo+GetIconInfo 读【活光标位图】的真实宽高，并报告 Windows 从我们的 .cur 里挑了哪一档光栅。
试完还原成原值。
"""
import ctypes
import json
import os
import time
import winreg
from ctypes import wintypes

u32 = ctypes.WinDLL('user32', use_last_error=True)
gdi = ctypes.WinDLL('gdi32', use_last_error=True)

ACC = r'Software\Microsoft\Accessibility'
REG = r'Control Panel\Cursors'
OUT = r'G:\ArknightsCursorExtract\_diag'
os.makedirs(OUT, exist_ok=True)

try:
    u32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
except Exception:
    pass


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
u32.GetDpiForSystem.restype = wintypes.UINT


def live():
    ci = CURSORINFO()
    ci.cbSize = ctypes.sizeof(CURSORINFO)
    if not u32.GetCursorInfo(ctypes.byref(ci)) or not ci.hCursor:
        return None
    ii = ICONINFO()
    if not u32.GetIconInfo(ci.hCursor, ctypes.byref(ii)):
        return None
    res = None
    if ii.hbmColor:
        bm = BITMAP()
        if gdi.GetObjectW(ii.hbmColor, ctypes.sizeof(BITMAP), ctypes.byref(bm)):
            res = (int(bm.bmWidth), int(bm.bmHeight))
        gdi.DeleteObject(ii.hbmColor)
    if ii.hbmMask:
        gdi.DeleteObject(ii.hbmMask)
    return res


def broadcast():
    r = ctypes.c_ulong()
    u32.SendMessageTimeoutW(0xFFFF, 0x001A, 0, 'Control Panel\\Cursors',
                            0x0002, 2000, ctypes.byref(r))
    u32.SystemParametersInfoW(0x0057, 0, None, 0x01 | 0x02)


def getd(root, path, name):
    try:
        with winreg.OpenKey(root, path) as k:
            return winreg.QueryValueEx(k, name)
    except OSError:
        return (None, None)


def setd(root, path, name, val):
    with winreg.OpenKey(root, path, 0, winreg.KEY_SET_VALUE) as k:
        winreg.SetValueEx(k, name, 0, winreg.REG_DWORD, val)


print('=== 前置 ===')
dpi = u32.GetDpiForSystem()
print('  DPI =', dpi, ' 缩放 = %.3f' % (dpi / 96.0))
print('  SM_CXCURSOR =', u32.GetSystemMetrics(13), '(固定常量，不随设置变)')
print('  屏幕 = {0}x{1}'.format(u32.GetSystemMetrics(0), u32.GetSystemMetrics(1)))
orig_cs = getd(winreg.HKEY_CURRENT_USER, ACC, 'CursorSize')
orig_cb = getd(winreg.HKEY_CURRENT_USER, REG, 'CursorBaseSize')
print('  原 Accessibility\\CursorSize =', orig_cs)
print('  原 Control Panel\\Cursors\\CursorBaseSize =', orig_cb)
print('  当前活光标 =', live())

print()
print('=== Accessibility\\CursorSize 1..15 -> 实际渲染尺寸 ===')
rows = []
for cs in range(1, 16):
    setd(winreg.HKEY_CURRENT_USER, ACC, 'CursorSize', cs)
    broadcast()
    time.sleep(0.7)
    m = live()
    rows.append({'cursor_size': cs, 'bitmap': m})
    ratio = ''
    if m and m[1]:
        ratio = '  占屏高 %.2f%%' % (100.0 * m[1] / 1440.0)
    print('  CursorSize={0:>2}  ->  活光标 {1}{2}'.format(cs, m, ratio))

print()
print('=== 还原 ===')
setd(winreg.HKEY_CURRENT_USER, ACC, 'CursorSize', orig_cs[0] if orig_cs[0] else 1)
broadcast()
time.sleep(0.8)
print('  CursorSize =', getd(winreg.HKEY_CURRENT_USER, ACC, 'CursorSize'))
print('  CursorBaseSize =', getd(winreg.HKEY_CURRENT_USER, REG, 'CursorBaseSize'))
print('  活光标 =', live())

with open(os.path.join(OUT, 'cursor_size_map.json'), 'w', encoding='utf-8') as f:
    json.dump({'dpi': dpi, 'screen': [2560, 1440], 'rows': rows}, f,
              ensure_ascii=False, indent=1)
print('  映射已写入 _diag\\cursor_size_map.json')
