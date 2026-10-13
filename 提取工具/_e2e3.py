# -*- coding: utf-8 -*-
"""端到端实测 v3 —— 扫尺寸，找出「哪些尺寸真的能装上桌面」。

v2 的教训：
  - 192px 装上了（hotspot 56,40 = round(28,20)*192/96，正是我们的箭头），
    115px 却读到旧的 32px。
  - 怀疑是「鼠标没动 → 系统不重算光标」或「首次 apply 有竞态」。
  - 因此本版每次都把鼠标挪开再挪回，并在 2 秒内多次采样看是否被回滚。
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
print('探针点 =', PT, cls_at(PT) if PT else '')
if not PT:
    raise SystemExit('找不到桌面像素')


def raw_read():
    ci = CURSORINFO()
    ci.cbSize = ctypes.sizeof(CURSORINFO)
    if not u32.GetCursorInfo(ctypes.byref(ci)):
        return ('GetCursorInfo fail',)
    ii = ICONINFO()
    if not u32.GetIconInfo(ci.hCursor, ctypes.byref(ii)):
        return ('GetIconInfo fail',)
    bm = BITMAP()
    ok = gdi.GetObjectW(ii.hbmColor, ctypes.sizeof(BITMAP), ctypes.byref(bm))
    r = ((bm.bmWidth, bm.bmHeight) if ok else None,
         (ii.xHotspot, ii.yHotspot))
    if ii.hbmColor:
        gdi.DeleteObject(ii.hbmColor)
    if ii.hbmMask:
        gdi.DeleteObject(ii.hbmMask)
    return r


def measure(jiggle=True, samples=4, gap=0.45):
    """把鼠标挪开再挪回，强制系统重算光标；多次采样。"""
    if jiggle:
        u32.SetCursorPos(PT[0] + 7, PT[1] + 7)
        time.sleep(gap)
    u32.SetCursorPos(*PT)
    time.sleep(gap)
    out = []
    for _ in range(samples):
        out.append(raw_read())
        time.sleep(gap)
    return out


print('\n=== 基线 ===')
for s in measure():
    print('   ', s)

eng = mod.Engine()
eng.animate = False

print('\n=== 尺寸扫描（只动 Arrow）===')
print('   %-8s %-14s %-24s %s' % ('尺寸', '装入结果', '桌面实测(位图/热点)', '判定'))
results = {}
for n in (48, 64, 96, 115, 128, 192, 256):
    eng.build(n)
    ok = eng.apply('Arrow', 0)
    got = measure()
    bitmaps = sorted(set(tuple(g[0]) if g[0] else None for g in got))
    verdict = '通过' if bitmaps == [(n, n)] else '未通过'
    if verdict == '通过':
        results[n] = True
    print('   %-8d %-14s %-24s %s' % (n, ok, '%s x%d' % (bitmaps, len(got)),
                                      verdict))
    if verdict == '未通过':
        for g in got:
            print('        sample:', g)

print('\n=== 恢复 ===')
print('   恢复 %d 个角色' % eng.restore_scheme())
eng.destroy()
time.sleep(0.8)
for s in measure():
    print('   ', s)
print('\n可装上的尺寸:', sorted(results))
