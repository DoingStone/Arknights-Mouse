# -*- coding: utf-8 -*-
"""量 build() 在不同尺寸下的耗时与 GDI/内存占用，判断大尺寸是否可用。"""
import ctypes
import importlib.machinery
import importlib.util
import os
import time
from ctypes import wintypes

TOOL = r'G:\ArknightsCursorExtract\CursorSizeTool\ArknightsCursorSize.pyw'
loader = importlib.machinery.SourceFileLoader('acsize', TOOL)
spec = importlib.util.spec_from_loader('acsize', loader)
mod = importlib.util.module_from_spec(spec)
loader.exec_module(mod)

gdi = mod.gdi
k32 = ctypes.WinDLL('kernel32', use_last_error=True)


class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
    _fields_ = [('cb', wintypes.DWORD), ('PageFaultCount', wintypes.DWORD),
                ('PeakWorkingSetSize', ctypes.c_size_t),
                ('WorkingSetSize', ctypes.c_size_t),
                ('QuotaPeakPagedPoolUsage', ctypes.c_size_t),
                ('QuotaPagedPoolUsage', ctypes.c_size_t),
                ('QuotaPeakNonPagedPoolUsage', ctypes.c_size_t),
                ('QuotaNonPagedPoolUsage', ctypes.c_size_t),
                ('PagefileUsage', ctypes.c_size_t),
                ('PeakPagefileUsage', ctypes.c_size_t)]


psapi = ctypes.WinDLL('psapi', use_last_error=True)
k32.GetCurrentProcess.restype = wintypes.HANDLE
psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE,
                                       ctypes.POINTER(PROCESS_MEMORY_COUNTERS),
                                       wintypes.DWORD]


def mem_mb():
    pmc = PROCESS_MEMORY_COUNTERS()
    pmc.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
    psapi.GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(pmc),
                               pmc.cb)
    return pmc.WorkingSetSize / 1048576.0


u32 = ctypes.WinDLL('user32', use_last_error=True)
# GetGuiResources 在 user32 里，不在 gdi32
u32.GetGuiResources.argtypes = [wintypes.HANDLE, wintypes.DWORD]
u32.GetGuiResources.restype = wintypes.DWORD


def gdi_count():
    h = k32.GetCurrentProcess()
    return int(u32.GetGuiResources(h, 0)), int(u32.GetGuiResources(h, 1))

print('基线  内存 %.1f MB  GDI=%s' % (mem_mb(), gdi_count()))
print()
print(' 尺寸  角色  总帧数   耗时s   内存MB   GDI(对象/用户)')
rows = []
for size in (32, 48, 64, 96, 128, 192, 256, 384):
    e = mod.Engine()
    t0 = time.time()
    keys = e.build(size)
    dt = time.time() - t0
    nframes = sum(len(v) for v in e.masters.values())
    gu, gu2 = gdi_count()
    mb = mem_mb()
    rows.append({'size': size, 'roles': len(keys), 'frames': nframes,
                 'sec': round(dt, 2), 'mem_mb': round(mb, 1),
                 'gdi': gu, 'user': gu2})
    print(' %-5d %-5d %-9d %-7.2f %-8.1f %d/%d' % (
        size, len(keys), nframes, dt, mb, gu, gu2))
    e.destroy()

print()
print('--- 逐帧 CopyIcon+SetSystemCursor 速率测试（96px, 8 个动画角色）---')
e = mod.Engine()
e.build(96)
e.apply_all()
t0 = time.time()
N = 300
for i in range(N):
    for k in ('AppStarting', 'Wait', 'No', 'SizeNS', 'SizeWE', 'SizeNWSE',
              'SizeNESW', 'SizeAll'):
        lst = e.masters[k]
        e.apply(k, i % len(lst))
dt = time.time() - t0
print('  %d 次全角色刷新耗时 %.2fs -> 每轮 8 角色 %.1f ms'
      % (N, dt, dt / N * 1000))
print('  => 理论上限约 %.0f 轮/秒（20ms 节拍需要 50 轮/秒）' % (N / dt))

print()
print('--- 帧去重（有多少帧其实是重复图象）---')
for k in ('AppStarting', 'Wait', 'No', 'SizeAll'):
    lst = e.masters.get(k) or []
    if not lst:
        continue
    # 用 96px 源图做内容哈希
    frames = mod.role_frames(k)
    sig = []
    for (im, hx, hy) in frames:
        sig.append(hash(im.tobytes()))
    print('  %-12s 帧数 %-3d 不同内容 %-3d' % (k, len(sig), len(set(sig))))

e.destroy()
print()
print('结束  内存 %.1f MB  GDI=%s' % (mem_mb(), gdi_count()))
