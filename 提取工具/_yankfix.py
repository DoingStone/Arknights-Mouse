# -*- coding: utf-8 -*-
"""验证「鼠标被拽到左上角」的修复：所有轮询路径必须零副作用。

修复前：guard 每 1.5s 调 desktop_cursor_size() → SetCursorPos(74,17)
修复后：guard 每 1.5s 调 system_cursor_sizes() → LoadCursorW，零位移
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


class POINT(ctypes.Structure):
    _fields_ = [('x', ctypes.c_long), ('y', ctypes.c_long)]


u32.GetCursorPos.argtypes = [ctypes.POINTER(POINT)]
u32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]

fails = []


def pos():
    p = POINT()
    u32.GetCursorPos(ctypes.byref(p))
    return p.x, p.y


def check(name, cond, detail=''):
    print('  [%s] %s %s' % ('PASS' if cond else 'FAIL', name, detail))
    if not cond:
        fails.append(name)


print('=== 1) find_desktop_point() 不得再落左上角 ===')
pt = cw.find_desktop_point()
print('     返回 = %s' % (pt,))
check('不是左上角', pt is not None and not (pt[0] < 200 and pt[1] < 200))

print('\n=== 2) system_cursor_sizes() —— 权威探针 ===')
cs = cw.system_cursor_sizes()
for k in sorted(cs):
    print('     %-9s %s' % (k, cs[k]))
check('读到至少 4 个角色', len(cs) >= 4, '实际 %d' % len(cs))
check('Arrow 存在', 'Arrow' in cs)

print('\n=== 3) 探针零副作用（50 次，模拟守护 75 秒轮询）===')
u32.SetCursorPos(1200, 700)
time.sleep(0.2)
b4 = pos()
t0 = time.time()
moved = 0
for i in range(50):
    cw.system_cursor_sizes()
    now = pos()
    moved = max(moved, abs(now[0] - b4[0]) + abs(now[1] - b4[1]))
dt = time.time() - t0
after = pos()
print('     前=%s 后=%s 最大位移=%d px   50 次共 %.3fs（%.2f ms/次）'
      % (b4, after, moved, dt, dt * 1000 / 50))
check('光标零位移', moved <= 2, 'max=%d' % moved)
check('单次 < 5 ms', dt / 50 < 0.005, '%.2f ms' % (dt * 1000 / 50))

print('\n=== 4) 探针与鼠标位置无关（在四个角各读一次）===')
vals = {}
for name, (x, y) in (('左上', (10, 10)), ('右上', (2030, 10)),
                     ('左下', (10, 1140)), ('右下', (2030, 1140))):
    u32.SetCursorPos(x, y)
    time.sleep(0.12)
    vals[name] = cw.system_cursor_sizes().get('Arrow')
    print('     鼠标在%-4s %-12s → Arrow = %s' % (name, (x, y), vals[name]))
check('四角读数一致', len(set(vals.values())) == 1, str(set(vals.values())))

print('\n=== 5) desktop_cursor_size() 仍能还原鼠标位置 ===')
u32.SetCursorPos(1000, 600)
time.sleep(0.15)
b4 = pos()
r = cw.desktop_cursor_size(jiggle=True, restore=True)
time.sleep(0.1)
after = pos()
d = abs(after[0] - b4[0]) + abs(after[1] - b4[1])
print('     前=%s 后=%s 位移=%d  读数=%s' % (b4, after, d, r))
check('量完还原原位', d <= 3, 'moved=%d' % d)

print('\n=== 6) 源码审计：轮询路径不得调 desktop_cursor_size ===')
src = os.path.join(APP, '源码', 'arkmouse')
bad = []
for fn in ('guard.py', 'main.pyw'):
    for i, ln in enumerate(open(os.path.join(src, fn), encoding='utf-8'), 1):
        s = ln.strip()
        if s.startswith('#') or 'desktop_cursor_size(' not in s:
            continue
        bad.append('%s:%d' % (fn, i))
print('     命中 = %s' % (bad or '无'))
check('guard.py 已清除', not [b for b in bad if b.startswith('guard.py')])
check('只剩用户主动按钮一处', len(bad) <= 1, '实际 %d' % len(bad))

print('\n=== 7) 模拟守护 30 轮 check（不得动鼠标）===')
sys.path.insert(0, src)
import guard  # noqa: E402
g = guard.Guard.__new__(guard.Guard)
g.applied = cs['Arrow'][0] if 'Arrow' in cs else 72
g.misses = 0
g.fast = 0
g.ticks = 0
g.scale = 0.75
g.pack = None
g._scheme = None
g.state_mtime = 0
g.eng = cw.Engine()
g.running = True
u32.SetCursorPos(1100, 650)
time.sleep(0.2)
b4 = pos()
moved = 0
for _ in range(30):
    try:
        g.check()
    except Exception as e:
        print('     check() 抛异常：%s' % e)
        fails.append('check() 异常')
        break
    now = pos()
    moved = max(moved, abs(now[0] - b4[0]) + abs(now[1] - b4[1]))
print('     前=%s 后=%s 30 轮最大位移=%d px' % (b4, pos(), moved))
check('守护 check() 零位移', moved <= 2, 'max=%d' % moved)

print('\n' + '=' * 60)
if fails:
    print('失败 %d 项：%s' % (len(fails), fails))
else:
    print('[验收通过] 所有轮询路径零副作用，鼠标不再被拽走')
