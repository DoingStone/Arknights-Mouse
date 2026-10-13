# -*- coding: utf-8 -*-
"""回归测试：`CursorAnim.describe()`（根治 `no attribute 'idle'` 那个崩溃）。

崩溃原因是 GUI / CLI 各自手写一份「效果描述」，删掉待机呼吸时只改了效果层。
现在描述只有 describe() 一个来源，这个脚本负责钉死三件事：
  1. 每一种参数组合下 describe() 都不抛异常（旧写法会在 f.idle 上炸）；
  2. 描述内容跟着参数走（prts/game、待机、爪子、全关）；
  3. 真的把 Engine + fx 驱动跑起来之后再问一次，仍然不抛。
"""
import os
import sys
import time
import itertools

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '源码', 'arkmouse'))

import artpack                                              # noqa: E402
import cursorwin as cw                                      # noqa: E402
import paths                                                # noqa: E402

FAIL = []


def eq(name, got, want):
    if got == want:
        print('ok   %-42s %s' % (name, got))
    else:
        FAIL.append(name)
        print('FAIL %-42s got=%r want=%r' % (name, got, want))


def ok(name, cond, extra=''):
    if cond:
        print('ok   %-42s %s' % (name, extra))
    else:
        FAIL.append(name)
        print('FAIL %-42s %s' % (name, extra))


pack = artpack.load(paths.find_art())
eng = cw.Engine()
size = cw.desktop_cursor_size()[0]

print('== 1. 全部参数组合下 describe() 不抛异常 ==')
combos = list(itertools.product(
    (True, False), ('prts', 'game'), (True, False), (True, False)))
for ca, st, dc, ip in combos:
    o = {'click_anim': ca, 'click_style': st, 'drag_claw': dc, 'idle_prts': ip}
    try:
        a = cw.CursorAnim(eng, o)
        d = a.describe()
    except Exception as e:
        FAIL.append('describe(%r)' % (o,))
        print('FAIL %r -> %s: %s' % (o, type(e).__name__, e))
        continue
    ok('describe 组合 %s/%s/%s/%s' % (ca, st, dc, ip), isinstance(d, list),
       '-> %s' % (d,))
print('  组合数 = %d' % len(combos))

print('== 2. 描述内容跟着参数走 ==')
a = cw.CursorAnim(eng, {'click_anim': True, 'click_style': 'prts',
                        'drag_claw': True, 'idle_prts': True})
eq('prts 默认三项全开', a.describe(),
   ['点击挤压（PRTS 原帧）', '拖动爪子', '待机动画 5 秒后开始'])
a = cw.CursorAnim(eng, {'click_anim': True, 'click_style': 'game',
                        'drag_claw': False, 'idle_prts': False})
d = a.describe()
ok('game 风格只报点击缩放', len(d) == 1 and d[0].startswith('点击缩放'),
   '-> %s' % (d,))
a = cw.CursorAnim(eng, {'click_anim': False, 'drag_claw': False,
                        'idle_prts': False})
eq('三项全关 -> 空清单（界面显示「手感效果已关」）', a.describe(), [])
a = cw.CursorAnim(eng, {'click_anim': False, 'drag_claw': False,
                        'idle_prts': True, 'idle_start_ms': 9000})
eq('待机秒数跟着 idle_start_ms 走', a.describe(), ['待机动画 9 秒后开始'])
a = cw.CursorAnim(eng, {'click_anim': False, 'drag_claw': False,
                        'idle_prts': True, 'idle_start_ms': 'x'})
eq('idle_start_ms 非法也不抛、落回默认 5 秒', a.describe(),
   ['待机动画 5 秒后开始'])

print('== 3. 真驱动跑起来之后再问一次 ==')
fx = cw.fx_options({'click_anim': True, 'click_style': 'prts',
                    'drag_claw': True, 'idle_prts': True})
eng.build(size, pack, fx=fx)
ok('apply_all', bool(eng.apply_all()))
f = eng.start_fx(fx)
ok('start_fx 返回 CursorAnim', f is not None)
try:
    d0 = f.describe()
    ok('刚 start_fx 就能 describe', bool(d0), '-> %s' % (d0,))
    time.sleep(1.2)
    d1 = f.describe()
    ok('跑 1.2 秒后 describe 仍不抛', bool(d1), '-> %s' % (d1,))
    eq('驱动起来后描述与配置一致', d1, d0)
    any_ = f.prts is not None
    ok('PrtsFx 已在驱动线程装配', any_)
except Exception as e:
    FAIL.append('describe-after-start')
    print('FAIL 驱动后 describe -> %s: %s' % (type(e).__name__, e))
finally:
    eng.stop_fx()
    eng.destroy()
    time.sleep(0.3)

print()
print('FAILED: %d %s' % (len(FAIL), FAIL))
sys.exit(1 if FAIL else 0)
