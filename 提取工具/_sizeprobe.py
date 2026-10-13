# -*- coding: utf-8 -*-
"""诊断：Windows 实际用多大的系统指针，以及 CursorBaseSize 能否连续调节。"""
import ctypes
import winreg
import time
from ctypes import wintypes

u32 = ctypes.WinDLL('user32', use_last_error=True)
u32.GetSystemMetrics.argtypes = [ctypes.c_int]
u32.GetSystemMetrics.restype = ctypes.c_int
u32.SystemParametersInfoW.argtypes = [wintypes.UINT, wintypes.UINT, ctypes.c_void_p, wintypes.UINT]
u32.SystemParametersInfoW.restype = wintypes.BOOL
u32.SendMessageTimeoutW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM,
                                    ctypes.c_wchar_p, wintypes.UINT, wintypes.UINT,
                                    ctypes.POINTER(ctypes.c_ulong)]
u32.SendMessageTimeoutW.restype = ctypes.c_void_p

SM_CXCURSOR = 13
SM_CYCURSOR = 14
SPI_SETCURSORS = 0x0057
REG = r'Control Panel\Cursors'


def met():
    return u32.GetSystemMetrics(SM_CXCURSOR), u32.GetSystemMetrics(SM_CYCURSOR)


def read_val(name):
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG) as k:
        try:
            return winreg.QueryValueEx(k, name)[0]
        except OSError:
            return None


def write_val(name, v):
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG, 0, winreg.KEY_SET_VALUE) as k:
        if v is None:
            try:
                winreg.DeleteValue(k, name)
            except OSError:
                pass
        else:
            winreg.SetValueEx(k, name, 0, winreg.REG_DWORD, v)


def broadcast():
    r = ctypes.c_ulong()
    u32.SendMessageTimeoutW(0xFFFF, 0x001A, 0, 'Control Panel\\Cursors',
                            0x0002, 1500, ctypes.byref(r))
    u32.SystemParametersInfoW(SPI_SETCURSORS, 0, None, 0x01 | 0x02)


print('=== 1. 当前状态 ===')
base = read_val('CursorBaseSize')
print('  CursorBaseSize       =', base)
print('  SM_CXCURSOR/Y        =', met())
print('  方案名 (default)      =', read_val(''))
print('  Arrow                =', read_val('Arrow'))

print()
print('=== 2. CursorBaseSize 能否连续调节？（逐个试，试完还原）===')
orig = base
results = []
for v in [32, 40, 48, 56, 64, 72, 80, 96, 112, 128, 144, 160, 192, 256]:
    write_val('CursorBaseSize', v)
    broadcast()
    time.sleep(0.45)
    w, h = met()
    back = read_val('CursorBaseSize')
    results.append((v, back, w, h))
    print('  写入 {0:>3} -> 回读 {1!s:>4}   SM_CXCURSOR={2:>3} SM_CYCURSOR={3:>3}'.format(v, back, w, h))

# 还原
write_val('CursorBaseSize', orig)
broadcast()
time.sleep(0.5)
print()
print('=== 3. 还原后 ===')
print('  CursorBaseSize =', read_val('CursorBaseSize'), ' SM =', met())
