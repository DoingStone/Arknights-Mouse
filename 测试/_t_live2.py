# -*- coding: utf-8 -*-
"""①③ 上屏端到端：真按键 + 真静止，看 prtsfx 到底往屏幕上推了什么帧。

② 已经单独验过（_t_live.py：钩子收到 10/11、窗口被拖动、帧序正确），这里不再
重复拖动 —— ①③ 不需要 Tk 窗口、不需要消息泵，脚本线性跑完即可。
"""
import atexit
import ctypes
import json
import os
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '源码', 'arkmouse'))

import cursorwin as cw
import paths
import store
import artpack
import prtsfx as px

u32 = cw.u32
MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP = 0x0002, 0x0004


@atexit.register
def _restore():
    try:
        u32.SystemParametersInfoW(0x0057, 0, None, 0)
    except Exception:
        pass


def live_cursor():
    ci = cw.CURSORINFO()
    ci.cbSize = ctypes.sizeof(cw.CURSORINFO)
    if not u32.GetCursorInfo(ctypes.byref(ci)):
        return None
    return (int(ci.hCursor or 0), ci.flags)


def nudge(x, y):
    u32.SetCursorPos(x + 3, y + 3)
    time.sleep(0.03)
    u32.SetCursorPos(x, y)
    time.sleep(0.03)


saved = store.load()
fxo = store.fx_settings(saved)
print('设置 =', json.dumps(fxo, ensure_ascii=False))
print()

pack = artpack.load(paths.find_art())
eng = cw.Engine()
t0 = time.time()
n = len(eng.build(cw.NATIVE * float(saved.get('scale', 1.0)), pack, fx=fxo))
print('build: %d 个角色，%.2fs，size=%d' % (n, time.time() - t0, eng.size))
print('apply_all ->', eng.apply_all())

STAMPS = []                                   # (t, stamp, 帧字典键, 接管键)
KEYS = {}                                     # set_raw 成功次数
_orig_setraw = cw.Engine.set_raw


def spy_setraw(self, key, src):
    ok = _orig_setraw(self, key, src)
    if ok:
        KEYS[key] = KEYS.get(key, 0) + 1
    return ok


cw.Engine.set_raw = spy_setraw

f = eng.start_fx(fxo)
for _ in range(60):
    if f is not None and f.prts is not None:
        break
    time.sleep(0.05)
p = getattr(f, 'prts', None)
print('CursorAnim=%r  PrtsFx=%r' % (f is not None, p is not None))
if p is None:
    print('prtsfx 没装起来，放弃')
    eng.stop_fx(); eng.destroy(); sys.exit(3)
print('  err=%r  click_art=%s  idle_on=%s idle_keys=%s  drag_keys=%s' % (
    p.err, sorted(p.click_art.items()), p.idle_on, p.idle_keys, p.drag_keys))

_orig_ff = p.frames_for


def spy_ff(now, down):
    fr, st = _orig_ff(now, down)
    STAMPS.append((round(time.time() - T0, 3), st, tuple(sorted(fr))))
    del STAMPS[:-400]
    return fr, st


p.frames_for = spy_ff
T0 = time.time()

old = cw.POINT()
u32.GetCursorPos(ctypes.byref(old))
cx, cy = int(old.x), int(old.y)
nudge(cx, cy)


def seen(filt):
    out, last = [], None
    for _t, st, keys in STAMPS:
        if not st or not any(k.startswith(filt) for k in keys + (st,)):
            continue
        if st != last:
            out.append(st)
            last = st
    return out


print()
print('===== ① 点击挤压（按住 400ms 再松手）=====')
print('  屏幕指针 %r' % (live_cursor(),))
n0 = len(STAMPS)
u32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
time.sleep(0.40)
u32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
time.sleep(1.2)
seq = seen('hand_')
print('  frames_for 里 hand_* 的帧序 = %s' % (seq,))
hand_keys = sorted(set(k for _t, st, ks in STAMPS for k in ks))
print('  这一轮被 PRTS 帧接管的角色 = %s' % (hand_keys,))
print('  采样条数 = %d' % (len(STAMPS) - n0))

print()
print('===== ③ 待机动画（静置 %.1fs）=====' % (p.idle_start_ms / 1000.0 + 1.5))
print('  先动一下鼠标把待机计时清零')
for _ in range(6):
    u32.SetCursorPos(cx + _, cy)
    time.sleep(0.05)
STAMPS[:] = []
n0 = len(STAMPS)
time.sleep(p.idle_start_ms / 1000.0 + 1.6)
seq = seen('idle_')
print('  frames_for 里 idle_* 的帧序（前 8 + 后 4）= %s' % (seq[:8] + ['...'] + seq[-4:],))
print('  idle 帧种类 = %d，idle_active = %s，idle_since = %r'
      % (len(seq), p.idle_active, p.idle_since))
idle_keys = sorted(set(k for _t, st, ks in STAMPS for k in ks))
print('  这一轮被待机帧接管的角色 = %s' % (idle_keys,))

print()
print('===== 汇总 =====')
print('  set_raw 成功下发次数（按角色）= %s' % (KEYS,))
print('  ① 出现 hand_normal 帧 = %s' % any(s.startswith('hand_normal:') for s in seq + seen('hand_')))
print('  ③ 出现 idle_enter_frame 帧 = %s'
      % any(s.startswith('idle_enter_frame:') for s in seen('idle_')))
print('  ③ 出现 idle_frame 循环帧 = %s'
      % any(s.startswith('idle_frame:') for s in seen('idle_')))

u32.SetCursorPos(int(old.x), int(old.y))
eng.stop_fx()
eng.destroy()
u32.SystemParametersInfoW(0x0057, 0, None, 0)
print('指针已复位')
