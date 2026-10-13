# -*- coding: utf-8 -*-
"""验证一个「零副作用且不依赖鼠标位置」的探针：

LoadCursorW(None, IDC_ARROW) 能不能取到【当前】被 SetSystemCursor 换过的
系统箭头？如果能，量它的位图尺寸就能在任何时候判断指针有没有被重置，
完全不需要碰鼠标。
"""
import ctypes
import ctypes.wintypes as wt
import os
import sys
import time

APP = r'E:\Qianmory\Desktop\Mouse'
sys.path.insert(0, os.path.join(APP, '源码', 'arkmouse'))
import cursorwin as cw  # noqa: E402

u32 = ctypes.windll.user32
# MAKEINTRESOURCE 是宏，不是导出函数 —— 直接把整数当指针传即可
u32.LoadCursorW.argtypes = [wt.HINSTANCE, ctypes.c_void_p]
u32.LoadCursorW.restype = wt.HANDLE
u32.LoadCursorW.restype = wt.HANDLE

IDS = {'Arrow': 32512, 'IBeam': 32513, 'Wait': 32514, 'Crosshair': 32515,
       'UpArrow': 32516, 'SizeNWSE': 32513 + 130, 'Hand': 32649,
       'SizeAll': 32646, 'No': 32648}


class POINT(ctypes.Structure):
    _fields_ = [('x', ctypes.c_long), ('y', ctypes.c_long)]


u32.GetCursorPos.argtypes = [ctypes.POINTER(POINT)]


def pos():
    p = POINT()
    u32.GetCursorPos(ctypes.byref(p))
    return p.x, p.y


print('=== A) LoadCursorW 能不能读到当前系统箭头？ ===')
res = {}
for name, i in IDS.items():
    h = u32.LoadCursorW(None, ctypes.c_void_p(i))
    if not h:
        print('  %-10s LoadCursorW 失败' % name)
        continue
    m = cw.measure_hcursor(int(h))
    res[name] = m
    print('  %-10s id=%-6d hcur=%-12d → %s' % (name, i, h, m))

print('\n=== B) 关键判据 ===')
# 当前设置.json 是 0.75× → 72px。若 LoadCursorW 返回当前系统光标，
# Arrow 应该是 (72,72,21,15)；若返回内置默认，会是 (32,32,?)。
arr = res.get('Arrow')
print('  Arrow 实测 = %s' % (arr,))
print('  期望（若返回当前系统光标）= (72, 72, 21, 15)')
print('  期望（若返回内置默认）    = (32, 32, ...)')
if arr and arr[0] == 72:
    print('  ⇒ ✅ LoadCursorW 返回的是【当前】系统光标 —— 可用作零副作用探针')
elif arr and arr[0] == 32:
    print('  ⇒ ❌ LoadCursorW 只返回内置默认 32px，不能用作探针')
else:
    print('  ⇒ ❓ 结果异常：%s' % (arr,))

print('\n=== C) 该探针是否零副作用（反复调用 30 次）===')
b4 = pos()
t0 = time.time()
for _ in range(30):
    h = u32.LoadCursorW(None, ctypes.c_void_p(32512))
    cw.measure_hcursor(int(h))
dt = time.time() - t0
after = pos()
print('  前=%s 后=%s 位移=%d px  30 次耗时 %.3fs（%.2f ms/次）'
      % (b4, after, abs(after[0] - b4[0]) + abs(after[1] - b4[1]), dt,
         dt * 1000 / 30))

print('\n=== D) 换个位置再读（证明与鼠标位置无关）===')
u32.SetCursorPos(80, 1100)   # 左下角任务栏附近
time.sleep(0.15)
h = u32.LoadCursorW(None, ctypes.c_void_p(32512))
print('  鼠标在 (80,1100) 时 Arrow = %s' % (cw.measure_hcursor(int(h)),))
u32.SetCursorPos(1900, 300)  # 右上方
time.sleep(0.15)
h = u32.LoadCursorW(None, ctypes.c_void_p(32512))
print('  鼠标在 (1900,300) 时 Arrow = %s' % (cw.measure_hcursor(int(h)),))
print('  ⇒ 两者应完全一致（与鼠标位置无关）')
