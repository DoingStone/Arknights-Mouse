# -*- coding: utf-8 -*-
"""决定性诊断：游戏内指针是 Windows 画的，还是游戏自己画的？
方法：把光标移到游戏窗口内两个不同位置，各截一次图（BitBlt 截屏【不含】系统光标层），
      若两次截图出现差异 -> 差异就是游戏自己画进画面的指针。
      同时量出它的真实像素尺寸。
另外用 GetIconInfo 尝试量系统光标的活尺寸（带错误码）。
"""
import ctypes
import os
import time
from ctypes import wintypes

u32 = ctypes.WinDLL('user32', use_last_error=True)
gdi = ctypes.WinDLL('gdi32', use_last_error=True)
k32 = ctypes.WinDLL('kernel32', use_last_error=True)

OUT = r'G:\ArknightsCursorExtract\_diag'
os.makedirs(OUT, exist_ok=True)

try:
    u32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
except Exception:
    pass

from PIL import ImageGrab, ImageChops  # noqa: E402


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
u32.LoadCursorFromFileW.argtypes = [ctypes.c_wchar_p]
u32.LoadCursorFromFileW.restype = wintypes.HANDLE
u32.CopyIcon.argtypes = [wintypes.HANDLE]
u32.CopyIcon.restype = wintypes.HANDLE
u32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
u32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
u32.GetSystemMetrics.argtypes = [ctypes.c_int]
gdi.GetObjectW.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p]
gdi.GetObjectW.restype = ctypes.c_int
gdi.DeleteObject.argtypes = [wintypes.HANDLE]
u32.DestroyCursor.argtypes = [wintypes.HANDLE]


def bitmap_size(hbm):
    if not hbm:
        return None
    bm = BITMAP()
    if not gdi.GetObjectW(hbm, ctypes.sizeof(BITMAP), ctypes.byref(bm)):
        return None
    return (int(bm.bmWidth), int(bm.bmHeight), int(bm.bmBitsPixel))


def measure(handle, label):
    ii = ICONINFO()
    ok = u32.GetIconInfo(handle, ctypes.byref(ii))
    err = ctypes.get_last_error()
    if not ok:
        print('  {0}: GetIconInfo 失败 err={1}'.format(label, err))
        return None
    res = bitmap_size(ii.hbmColor)
    print('  {0}: color={1} mask={2}  hotspot=({3},{4})'.format(
        label, res, bitmap_size(ii.hbmMask), ii.xHotspot, ii.yHotspot))
    if ii.hbmColor:
        gdi.DeleteObject(ii.hbmColor)
    if ii.hbmMask:
        gdi.DeleteObject(ii.hbmMask)
    return res


def screen():
    return ImageGrab.grab(all_screens=True)


ENUM = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
u32.GetWindowTextW.argtypes = [wintypes.HWND, ctypes.c_wchar_p, ctypes.c_int]
u32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
u32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.c_void_p]

game = []


def cb(hwnd, lp):
    ln = u32.GetWindowTextLengthW(hwnd)
    if ln <= 0:
        return True
    buf = ctypes.create_unicode_buffer(ln + 2)
    u32.GetWindowTextW(hwnd, buf, ln + 2)
    if buf.value == '明日方舟':
        r = wintypes.RECT()
        u32.GetWindowRect(hwnd, ctypes.byref(r))
        game.append((hwnd, r))
    return True


u32.EnumWindows(ENUM(cb), 0)
print('=== 0. 游戏窗口 ===')
if game:
    hwnd, r = game[0]
    print('  hwnd={0} rect=({1},{2})-({3},{4}) {5}x{6}'.format(
        hwnd, r.left, r.top, r.right, r.bottom, r.right - r.left, r.bottom - r.top))
else:
    print('  未找到')
    raise SystemExit('游戏未运行')

hwnd, r = game[0]
CL = (r.left, r.top, r.right, r.bottom)

print()
print('=== 1. 量系统光标的活尺寸 ===')
ci = CURSORINFO()
ci.cbSize = ctypes.sizeof(CURSORINFO)
ok = u32.GetCursorInfo(ctypes.byref(ci))
print('  GetCursorInfo ok={0} err={1} flags={2} hCursor={3} pos=({4},{5})'.format(
    ok, ctypes.get_last_error(), ci.flags, ci.hCursor,
    ci.ptScreenPos.x, ci.ptScreenPos.y))
if ok and ci.hCursor:
    measure(ci.hCursor, '  系统当前光标')

print()
print('=== 2. 我们自己包的 .cur：系统加载后会变成多大 ===')
for f in ['Arknights_Crystal_Arrow_large.cur']:
    p = os.path.join(r'G:\ArknightsCursorExtract\CrystalCursorPack\cursors\large', f)
    h = u32.LoadCursorFromFileW(p)
    if not h:
        print('  {0}: LoadCursorFromFile 失败 err={1}'.format(f, ctypes.get_last_error()))
    else:
        measure(h, '  ' + f)
        u32.DestroyCursor(h)

# ---------- 3. 游戏是否自绘指针 ----------
print()
print('=== 3. 游戏窗口两次截图差分（BitBlt 不含系统光标）===')
orig = wintypes.POINT()
u32.GetCursorPos(ctypes.byref(orig))
print('  原光标位置 = ({0},{1})'.format(orig.x, orig.y))

# 游戏窗口内两个点，相距足够远
P1 = (r.left + 400, r.top + 400)
P2 = (r.left + 1100, r.top + 700)

shots = []
for i, p in enumerate([P1, P2]):
    u32.SetCursorPos(p[0], p[1])
    time.sleep(1.1)
    im = screen()
    fp = os.path.join(OUT, 'game_shot_{0}.png'.format(i))
    im.save(fp)
    cur = wintypes.POINT()
    u32.GetCursorPos(ctypes.byref(cur))
    print('  第{0}次：目标({1},{2}) 实测({3},{4})  截图{5} -> {6}'.format(
        i, p[0], p[1], cur.x, cur.y, im.size, os.path.basename(fp)))
    shots.append(im)

u32.SetCursorPos(orig.x, orig.y)

d = ImageChops.difference(shots[0], shots[1])
bbox = d.getbbox()
print()
print('  两图差异包围盒 =', bbox)
if bbox is None:
    print('  => 游戏窗口截图里【没有】指针 -> 游戏用的是系统光标（Windows 画的）')
else:
    x0, y0, x1, y1 = bbox
    print('  => 截图里有东西变了，尺寸 {0}x{1}'.format(x1 - x0, y1 - y0))

    # 抠出两次的差异块看看
    for i, im in enumerate(shots):
        d2 = ImageChops.difference(im, im.point(lambda v: v))
        # 找出该图相对"另一图"不同的所有块
        other = shots[1 - i]
        dd = ImageChops.difference(im, other)
        bb = dd.getbbox()
        if bb:
            crop = im.crop(bb)
            fp = os.path.join(OUT, 'game_diff_{0}.png'.format(i))
            crop.save(fp)
            # 放大 4 倍便于观察
            crop.resize((crop.width * 4, crop.height * 4), 0).save(
                os.path.join(OUT, 'game_diff_{0}_4x.png'.format(i)))
            print('   图{0} 差异块 {1} -> game_diff_{0}.png (+_4x)'.format(i, crop.size))

    # 分别在与指针位置相关的区域里找指针
    for i, p in enumerate([P1, P2]):
        im = shots[i]
        reg = (p[0] - 90, p[1] - 90, p[0] + 90, p[1] + 90)
        reg = (max(0, reg[0]), max(0, reg[1]),
               min(im.width, reg[2]), min(im.height, reg[3]))
        crop = im.crop(reg)
        fp = os.path.join(OUT, 'game_at_cur_{0}.png'.format(i))
        crop.save(fp)
        crop.resize((crop.width * 4, crop.height * 4), 0).save(
            os.path.join(OUT, 'game_at_cur_{0}_4x.png'.format(i)))
        print('   指针候选区 {0} -> game_at_cur_{0}.png (+_4x)'.format(i, crop.size))

print()
print('=== 4. 桌面区域的同样测试（对照组）===')
D1 = (60, 700)
D2 = (900, 400)
ds = []
for i, p in enumerate([D1, D2]):
    u32.SetCursorPos(p[0], p[1])
    time.sleep(1.0)
    im = screen()
    ds.append(im)
u32.SetCursorPos(orig.x, orig.y)
bb = ImageChops.difference(ds[0], ds[1]).getbbox()
print('  桌面两次截图差异包围盒 =', bb,
      '-> None 表示截屏不含系统光标（符合预期）' if bb is None else '')
