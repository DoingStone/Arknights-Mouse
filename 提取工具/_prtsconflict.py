# -*- coding: utf-8 -*-
"""决定性冲突测试：PRTS-Motion-96.exe 运行时，会不会把本工具装的
内存光标（115px）打回 32px？

步骤：
  1. 装 115px（走工具引擎），确认桌面 = 115。
  2. 按它自己的命令行启动 PRTS-Motion-96.exe。
  3. 持续采样 25 秒，看尺寸是否被改回。
  4. 若不冲突则留着（它本来就是开机自启）；若冲突则报告。
  5. 无论如何最后把 115px 重新装上，保证结束状态正确。
"""
import ctypes
import ctypes.wintypes as W
import importlib.machinery
import os
import subprocess
import time

u32 = ctypes.windll.user32
gdi = ctypes.windll.gdi32
u32.SetProcessDPIAware()

TOOL = r'G:\ArknightsCursorExtract\CursorSizeTool\ArknightsCursorSize.pyw'
PRTS_EXE = (r'C:\Users\22442\AppData\Local\PRTS\Replica-v8-Windows'
            r'\PRTS-Motion-96.exe')
PRTS_DIR = (r'C:\Users\22442\AppData\Local\PRTS\Replica-v8-Windows'
            r'\cursors-34497b84e5b0d7cf')
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
print('探针点 =', PT, cls_at(PT))


def read_size():
    u32.SetCursorPos(*PT)
    time.sleep(0.18)
    ci = CURSORINFO()
    ci.cbSize = ctypes.sizeof(CURSORINFO)
    if not u32.GetCursorInfo(ctypes.byref(ci)):
        return None
    ii = ICONINFO()
    if not u32.GetIconInfo(ci.hCursor, ctypes.byref(ii)):
        return None
    bm = BITMAP()
    ok = gdi.GetObjectW(ii.hbmColor, ctypes.sizeof(BITMAP), ctypes.byref(bm))
    r = (bm.bmWidth, bm.bmHeight) if ok else None
    if ii.hbmColor:
        gdi.DeleteObject(ii.hbmColor)
    if ii.hbmMask:
        gdi.DeleteObject(ii.hbmMask)
    return r


def prts_pids():
    r = subprocess.run(
        ['powershell', '-NoProfile', '-Command',
         "(Get-Process 'PRTS-Motion-96' -ErrorAction SilentlyContinue).Id"],
        capture_output=True, text=True)
    return [int(x) for x in r.stdout.split() if x.strip().isdigit()]


mod = importlib.machinery.SourceFileLoader('acsize', TOOL).load_module()
eng = mod.Engine()
eng.animate = False
eng.build(115)
eng.apply_all()
time.sleep(1.0)
print('\n=== 1. 装好 115px ===')
print('   桌面 =', read_size())

print('\n=== 2. PRTS 进程现状 ===')
print('   pids =', prts_pids() or '(未运行)')

print('\n=== 3. 启动 PRTS-Motion-96.exe ===')
proc = subprocess.Popen([PRTS_EXE, PRTS_DIR],
                        cwd=os.path.dirname(PRTS_EXE))
print('   已启动 pid =', proc.pid)
time.sleep(3.0)
print('   PRTS pids =', prts_pids())

print('\n=== 4. 持续采样 25 秒（每 1.5s）===')
seen = {}
for i in range(17):
    s = read_size()
    seen[s] = seen.get(s, 0) + 1
    print('   t=%4.1fs  %s' % (i * 1.5, s))
    time.sleep(1.5)

print('\n=== 5. 结论 ===')
print('   尺寸分布:', seen)
if list(seen) == [(115, 115)]:
    print('   ★ PRTS-Motion 不冲突：25 秒内尺寸稳定保持 115x115 ✔')
    print('     （它只重装它自己的文件光标，不打内存光标）')
    conflict = False
else:
    print('   ★ 冲突：尺寸被改动 ->', seen)
    conflict = True

print('\n=== 6. 结束状态修正：重新装上 115px ===')
eng.apply_all()
time.sleep(1.0)
final = read_size()
print('   桌面 =', final, ' =>', 'OK' if final == (115, 115) else '需检查')

if not conflict:
    print('\n   PRTS 保持运行（它本来就是开机自启，未改动）')
else:
    print('\n   建议：在工具里点「检测 PRTS 冲突」关掉它的开机自启')
