# -*- coding: utf-8 -*-
"""③ PRTS 待机帧动画的上屏验收（临时用：跑完把 fx.bin 还原成只含拖动爪子的版本）。

不碰窗口、不碰拖动，只做一件事：让鼠标静止，看 15fps 的 idle 帧序会不会真的
被驱动、真的下发到 Arrow 上。
"""
import ctypes
import sys
import time

sys.path.insert(0, r'E:\Qianmory\Desktop\Mouse\源码')
sys.path.insert(0, r'E:\Qianmory\Desktop\Mouse\源码\arkmouse')   # prtsfx 里是 import artpack
from arkmouse import cursorwin as cw, paths, prtsfx      # noqa: E402
import artpack                                            # noqa: E402  （prtsfx 也是这么导入的）

fails = []


def eq(name, got, want):
    ok = got == want
    print('%s %s  got=%r want=%r' % ('ok  ' if ok else 'FAIL', name, got, want))
    if not ok:
        fails.append(name)
    return ok


pack_path = paths.find_art()
pack = artpack.load(pack_path)
size = cw.desktop_cursor_size()[0]
print('桌面指针尺寸 =', size)

fxo = cw.fx_options({'click_anim': False, 'drag_claw': False,
                     'idle_prts': True, 'idle_start_ms': 1000})
print('fxo =', {k: fxo[k] for k in ('idle_prts', 'idle_start_ms', 'drag_claw', 'click_anim')})

eng = cw.Engine.__new__(cw.Engine)
eng.__init__()
eng.build(size, pack, fx=fxo)

fx = prtsfx.FxFrames()
eq('fx.bin 里有 idle_frame 族', fx.has('idle_frame'), True)
eq('fx.bin 里有 idle_enter_frame 族', fx.has('idle_enter_frame'), True)
eq('idle_frame 帧数 = PRTS 的 342', fx.pack.frame_count('idle_frame'), 342)
eq('idle_enter_frame 帧数 = PRTS 的 30', fx.pack.frame_count('idle_enter_frame'), 30)

RAW_OK = {}
_orig = cw.Engine.set_raw


def spy(self, key, src):
    ok = _orig(self, key, src)
    if ok:
        RAW_OK[key] = RAW_OK.get(key, 0) + 1
    return ok


cw.Engine.set_raw = spy

eng.apply_all()
f = eng.start_fx(fxo)
for _ in range(60):
    if f is not None and getattr(f, 'prts', None) is not None:
        break
    time.sleep(0.1)
p = f.prts
print('PrtsFx err=%r  idle_on=%s' % (p.err, p.idle_on))

stamps = []
_of = p.frames_for


def sf(now):
    fr, st = _of(now)
    if st:
        stamps.append(st)
    return fr, st


p.frames_for = sf

print('静置 4 秒，采样 idle 帧序 ...')
t0 = time.time()
while time.time() - t0 < 4.0:
    time.sleep(0.1)

seen = []
for s in stamps:
    if s not in seen:
        seen.append(s)
print('推进到的帧相（前 24 个）:', seen[:24])
print('帧相总数 =', len(seen), ' set_raw 下发 =', RAW_OK)

if p.err:
    print('注：err 非空 ->', p.err)

eq('idle_active 起来了', p.idle_active, True)
eq('先走 idle_enter_frame 段', any(s.startswith('idle_enter_frame') for s in seen), True)
eq('进入 idle_frame 循环段', any(s.startswith('idle_frame') for s in seen), True)
eq('set_raw 真的把待机帧下发给了 Arrow', RAW_OK.get('Arrow', 0) > 10, True)

# PRTS RegressionTests.cs:49-55 的四个时刻点
from arkmouse.prtsfx import idle_frame as IF                          # noqa: E402
eq('idle_frame(0)', IF(0), ('idle_enter_frame', 0))
eq('idle_frame(499)', IF(499), ('idle_enter_frame', 29))
eq('idle_frame(500)', IF(500), ('idle_frame', 0))
eq('idle_frame(567)', IF(567), ('idle_frame', 1))
eq('idle_frame(23300)', IF(23300), ('idle_frame', 0))

eng.stop_fx()
time.sleep(0.3)
eng.destroy()
time.sleep(0.3)
after = cw.CURSORINFO()
after.cbSize = ctypes.sizeof(cw.CURSORINFO)
cw.u32.GetCursorInfo(ctypes.byref(after))
print('destroy() 之后屏幕指针 =',
      cw.measure_hcursor(after.hCursor) if after.hCursor else None)

print()
print('FAILED: %d %s' % (len(fails), fails if fails else ''))
sys.exit(1 if fails else 0)
