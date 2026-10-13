# -*- coding: utf-8 -*-
"""1) 备份整个 Cursors 键（含类型）  2) 把 CursorBaseSize 还原成原来的 REG_SZ '64'
3) 查 Accessibility\CursorSize  4) 用 GetIconInfo 量【活的】光标位图真实尺寸
5) 用正确的类型（REG_SZ）做阶梯测试，测完还原
"""
import ctypes
import json
import os
import time
import winreg
from ctypes import wintypes

u32 = ctypes.WinDLL('user32', use_last_error=True)
gdi = ctypes.WinDLL('gdi32', use_last_error=True)

REG = r'Control Panel\Cursors'
ACC = r'Software\Microsoft\Accessibility'
OUT = r'G:\ArknightsCursorExtract\_diag'
os.makedirs(OUT, exist_ok=True)


class ICONINFO(ctypes.Structure):
    _fields_ = [('fIcon', wintypes.BOOL), ('xHotspot', wintypes.DWORD),
                ('yHotspot', wintypes.DWORD), ('hbmMask', wintypes.HBITMAP),
                ('hbmColor', wintypes.HBITMAP)]


class CURSORINFO(ctypes.Structure):
    _fields_ = [('cbSize', wintypes.DWORD), ('flags', wintypes.DWORD),
                ('hCursor', wintypes.HANDLE), ('ptScreenPos', wintypes.POINT)]


class BITMAP(ctypes.Structure):
    _fields_ = [('bmType', wintypes.LONG), ('bmWidth', wintypes.LONG),
                ('bmHeight', wintypes.LONG), ('bmWidthBytes', wintypes.LONG),
                ('bmPlanes', wintypes.WORD), ('bmBitsPixel', wintypes.WORD),
                ('bmBits', ctypes.c_void_p)]


# 关键：显式声明句柄参数类型，否则 64 位句柄会被当成 c_int 溢出
u32.GetCursorInfo.argtypes = [ctypes.POINTER(CURSORINFO)]
u32.GetCursorInfo.restype = wintypes.BOOL
u32.GetIconInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(ICONINFO)]
u32.GetIconInfo.restype = wintypes.BOOL
u32.LoadCursorFromFileW.argtypes = [ctypes.c_wchar_p]
u32.LoadCursorFromFileW.restype = wintypes.HANDLE
gdi.GetObjectW.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p]
gdi.GetObjectW.restype = ctypes.c_int
gdi.DeleteObject.argtypes = [wintypes.HANDLE]
gdi.DeleteObject.restype = wintypes.BOOL
u32.DestroyCursor.argtypes = [wintypes.HANDLE]
u32.DestroyCursor.restype = wintypes.BOOL


def enum_all(root, path):
    out = []
    try:
        with winreg.OpenKey(root, path) as k:
            n = winreg.QueryInfoKey(k)[1]
            for i in range(n):
                nm, val, typ = winreg.EnumValue(k, i)
                out.append((nm, val, typ))
    except OSError as e:
        return None
    return out


def get_val(root, path, name):
    try:
        with winreg.OpenKey(root, path) as k:
            return winreg.QueryValueEx(k, name)
    except OSError:
        return (None, None)


def set_val(root, path, name, val, typ):
    with winreg.OpenKey(root, path, 0, winreg.KEY_SET_VALUE) as k:
        winreg.SetValueEx(k, name, 0, typ, val)


def broadcast():
    r = ctypes.c_ulong()
    u32.SendMessageTimeoutW(0xFFFF, 0x001A, 0, 'Control Panel\\Cursors',
                            0x0002, 2000, ctypes.byref(r))
    u32.SystemParametersInfoW(0x0057, 0, None, 0x01 | 0x02)


def live_cursor():
    """返回当前系统光标位图的真实像素尺寸 (w,h)，失败返回 None。"""
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
            res = (int(bm.bmWidth), int(bm.bmHeight), int(bm.bmBitsPixel))
        gdi.DeleteObject(ii.hbmColor)
    if ii.hbmMask:
        gdi.DeleteObject(ii.hbmMask)
    return res


print('=== 1. 备份整个 Cursors 键 ===')
rows = enum_all(winreg.HKEY_CURRENT_USER, REG) or []
acc_rows = enum_all(winreg.HKEY_CURRENT_USER, ACC)
backup = {'cursors_key': [list(r) for r in rows], 'accessibility': acc_rows}
bp = os.path.join(OUT, 'cursors_reg_backup.json')
with open(bp, 'w', encoding='utf-8') as f:
    json.dump(backup, f, ensure_ascii=False, indent=1)
print('  写入备份 ->', bp, '(%d 个值)' % len(rows))

cur = get_val(winreg.HKEY_CURRENT_USER, REG, 'CursorBaseSize')
print()
print('=== 2. CursorBaseSize 现状 ===')
print('  当前值 =', repr(cur[0]), ' 类型 =', cur[1],
      '(1=SZ 4=DWORD)' if cur[1] in (1, 4) else '')

# 原来的类型是字符串，还原成 REG_SZ '64'
set_val(winreg.HKEY_CURRENT_USER, REG, 'CursorBaseSize', '64', winreg.REG_SZ)
broadcast()
time.sleep(0.6)
now = get_val(winreg.HKEY_CURRENT_USER, REG, 'CursorBaseSize')
print('  已还原为 REG_SZ "64" ->', repr(now[0]), '类型 =', now[1])
print('  活光标位图 =', live_cursor())

print()
print('=== 3. HKCU\\%s ===' % ACC)
if acc_rows:
    for nm, val, typ in acc_rows:
        print('  {0:<22} = {1!r}  (type={2})'.format(nm, val, typ))
else:
    print('  (键不存在 / 无值)')
cs = get_val(winreg.HKEY_CURRENT_USER, ACC, 'CursorSize')
print('  -> CursorSize =', repr(cs[0]), 'type =', cs[1])

print()
print('=== 4. 阶梯：REG_SZ 写入 -> 量活光标 ===')
LADDER = ['32', '48', '64', '96', '128', '160', '192', '224', '256', '320']
live_before = live_cursor()
print('  起始活光标 =', live_before)
for v in LADDER:
    set_val(winreg.HKEY_CURRENT_USER, REG, 'CursorBaseSize', v, winreg.REG_SZ)
    broadcast()
    time.sleep(0.55)
    print('  写入 {0:>4} -> 活光标 {1}'.format(v, live_cursor()))

set_val(winreg.HKEY_CURRENT_USER, REG, 'CursorBaseSize', '64', winreg.REG_SZ)
broadcast()
time.sleep(0.6)
print()
print('=== 5. 还原 ===')
print('  CursorBaseSize =', get_val(winreg.HKEY_CURRENT_USER, REG, 'CursorBaseSize'))
print('  活光标 =', live_cursor())
