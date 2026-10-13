# -*- coding: utf-8 -*-
"""诊断：桌面指针实际像素尺寸 vs 游戏内指针尺寸。
1) DPI / 屏幕 / SM_CXCURSOR
2) HKCU\Control Panel\Cursors 全量转储
3) 找到游戏窗口，报告窗口/客户区尺寸
4) 截取游戏窗口，看软件指针是否在画面里（可量尺寸）
5) CursorBaseSize 阶梯测试：写入 -> 广播 -> 读 SM_CXCURSOR（试完还原）
"""
import ctypes
import os
import time
import winreg
from ctypes import wintypes

u32 = ctypes.WinDLL('user32', use_last_error=True)
k32 = ctypes.WinDLL('kernel32', use_last_error=True)
gdi = ctypes.WinDLL('gdi32', use_last_error=True)

OUTDIR = r'G:\ArknightsCursorExtract\_diag'
os.makedirs(OUTDIR, exist_ok=True)

# ---------- 0. DPI 感知 ----------
aware = None
try:
    if u32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)):
        aware = 'PER_MONITOR_AWARE_V2'
except Exception:
    pass
if aware is None:
    try:
        shc = ctypes.WinDLL('shcore', use_last_error=True)
        if shc.SetProcessDpiAwareness(2) == 0:
            aware = 'PER_MONITOR_AWARE(shcore)'
    except Exception:
        pass
print('=== 0. DPI 感知 ===')
print('  ', aware)

try:
    dpi = u32.GetDpiForSystem()
except Exception:
    hdc = u32.GetDC(0)
    dpi = gdi.GetDeviceCaps(hdc, 88)
    u32.ReleaseDC(0, hdc)
print('  系统 DPI =', dpi, ' 缩放 = %.3f' % (dpi / 96.0))

SM = {n: u32.GetSystemMetrics(i) for n, i in
      [('CXSCREEN', 0), ('CYSCREEN', 1), ('CXCURSOR', 13), ('CYCURSOR', 14),
       ('CXICON', 11), ('CYICON', 12)]}
print('  屏幕 = {0}x{1}   SM_CXCURSOR={2} SM_CYCURSOR={3}  SM_CXICON={4}'.format(
    SM['CXSCREEN'], SM['CYSCREEN'], SM['CXCURSOR'], SM['CYCURSOR'], SM['CXICON']))

try:
    import tkinter
    print('  tkinter: 可用', tkinter.TkVersion)
except Exception as e:
    print('  tkinter: 不可用 ->', e)

# ---------- 1. 注册表 ----------
REG = r'Control Panel\Cursors'


def dump_reg():
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG) as k:
        n = winreg.QueryInfoKey(k)[1]
        rows = []
        for i in range(n):
            nm, val, typ = winreg.EnumValue(k, i)
            rows.append((nm, val, typ))
    return rows


print()
print('=== 1. HKCU\\{0} ==='.format(REG))
for nm, val, typ in dump_reg():
    label = '(default)' if nm == '' else nm
    if isinstance(val, str) and len(val) > 62:
        val = '...' + val[-58:]
    print('  {0:<22} = {1}'.format(label, val))


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
                            0x0002, 2000, ctypes.byref(r))
    u32.SystemParametersInfoW(0x0057, 0, None, 0x01 | 0x02)


# ---------- 2. 找游戏窗口 ----------
WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
u32.GetWindowTextW.argtypes = [wintypes.HWND, ctypes.c_wchar_p, ctypes.c_int]
u32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
u32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.c_void_p]
u32.GetClientRect.argtypes = [wintypes.HWND, ctypes.c_void_p]
u32.IsWindowVisible.argtypes = [wintypes.HWND]


def proc_of(hwnd):
    pid = wintypes.DWORD()
    u32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    h = k32.OpenProcess(0x1000, False, pid.value)
    name = None
    if h:
        buf = ctypes.create_unicode_buffer(1024)
        sz = wintypes.DWORD(1024)
        k32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(sz))
        k32.CloseHandle(h)
        name = buf.value
    return pid.value, name


found = []


def cb(hwnd, lp):
    if not u32.IsWindowVisible(hwnd):
        return True
    ln = u32.GetWindowTextLengthW(hwnd)
    if ln <= 0:
        return True
    buf = ctypes.create_unicode_buffer(ln + 2)
    u32.GetWindowTextW(hwnd, buf, ln + 2)
    title = buf.value
    _, pname = proc_of(hwnd)
    if title and pname and ('Arknights' in pname or '明日方舟' in title or 'Montagne' in title):
        r = wintypes.RECT()
        u32.GetWindowRect(hwnd, ctypes.byref(r))
        cl = wintypes.RECT()
        u32.GetClientRect(hwnd, ctypes.byref(cl))
        fg = u32.GetForegroundWindow()
        found.append((hwnd, title, pname, r, cl, hwnd == fg))
    return True


u32.EnumWindows(WNDENUMPROC(cb), 0)

print()
print('=== 2. 游戏窗口 ===')
if not found:
    print('  未找到（游戏可能没在运行 / 窗口无标题）')
for hwnd, title, pname, r, cl, isfg in found:
    print('  hwnd     =', hwnd)
    print('  title    =', title)
    print('  exe      =', pname)
    print('  窗口矩形 = ({0},{1})-({2},{3})  {4}x{5}'.format(
        r.left, r.top, r.right, r.bottom, r.right - r.left, r.bottom - r.top))
    print('  客户区   = {0}x{1}'.format(cl.right - cl.left, cl.bottom - cl.top))
    print('  前台     =', isfg)

# ---------- 3. 截游戏窗口 ----------
print()
print('=== 3. 截屏 ===')
try:
    from PIL import ImageGrab
    full = ImageGrab.grab(all_screens=True)
    fp = os.path.join(OUTDIR, 'screen_full.png')
    full.save(fp)
    print('  全屏截图 ->', fp, full.size)
    if found:
        r = found[0][3]
        l, t = max(0, r.left), max(0, r.top)
        rr, bb = min(full.size[0], r.right), min(full.size[1], r.bottom)
        if rr > l and bb > t:
            crop = full.crop((l, t, rr, bb))
            cp = os.path.join(OUTDIR, 'game_window.png')
            crop.save(cp)
            print('  游戏窗口截图 ->', cp, crop.size)
except Exception as e:
    print('  截图失败 ->', repr(e))

# ---------- 4. CursorBaseSize 阶梯 ----------
print()
print('=== 4. CursorBaseSize 阶梯测试（结束会还原）===')
orig = read_val('CursorBaseSize')
print('  原始 CursorBaseSize =', orig)
LADDER = [16, 24, 32, 36, 40, 44, 48, 52, 56, 60, 64, 72, 80, 88, 96,
          104, 112, 120, 128, 144, 160, 192, 224, 256, 320]
for v in LADDER:
    write_val('CursorBaseSize', v)
    broadcast()
    time.sleep(0.40)
    back = read_val('CursorBaseSize')
    cw, ch = u32.GetSystemMetrics(13), u32.GetSystemMetrics(14)
    flag = '' if (back == v) else '  <-- 回读不同!'
    print('  写入 {0:>3} -> 回读 {1!s:>5}  SM_CXCURSOR={2:>3} SM_CYCURSOR={3:>3}{4}'.format(
        v, back, cw, ch, flag))

write_val('CursorBaseSize', orig)
broadcast()
time.sleep(0.6)
print()
print('=== 5. 还原后 ===')
print('  CursorBaseSize =', read_val('CursorBaseSize'),
      ' SM_CXCURSOR =', u32.GetSystemMetrics(13))
