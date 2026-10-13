# -*- coding: utf-8 -*-
"""PRTS 三项效果的逻辑验收（不上屏，纯算）。

关键：待机帧序的期望值**不是**我编的，直接抄 PRTS 自己的回归测试
`_prts_build\\motion\\src\\RegressionTests.cs:49-55`（Equal(...) 的第三个参数）。
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '源码', 'arkmouse'))

import cursorwin as cw
import prtsfx as px

fails = []


def eq(name, got, want):
    ok = got == want
    if not ok:
        fails.append(name)
    print('%s %-46s got=%r want=%r' % ('ok  ' if ok else 'FAIL', name, got, want))


print('== ③ 待机帧序：对 PRTS RegressionTests.cs:49-55 ==')
eq('IdleFrame(0)', px.idle_frame(0), ('idle_enter_frame', 0))
eq('IdleFrame(499)', px.idle_frame(499), ('idle_enter_frame', 29))
eq('IdleFrame(500)', px.idle_frame(500), ('idle_frame', 0))
eq('IdleFrame(567)', px.idle_frame(567), ('idle_frame', 1))
eq('IdleFrame(23300)', px.idle_frame(23300), ('idle_frame', 0))

print()
print('== ① 幅度端点：对 PRTS hand_<role>_NNN 逐帧 alpha 质量比实测 ==')
eq('scale_of_frame(6)  静止', round(px.scale_of_frame(6), 6), 1.0)
eq('scale_of_frame(106) 压到底', round(px.scale_of_frame(106), 4), px.SCALE_AT_FULL)
eq('scale_of_frame(0)  过冲顶', round(px.scale_of_frame(0), 4), px.SCALE_AT_OVER)

print()
print('== ① 弹簧：Runtime.cs:1154-1191 的行为 ==')
s = px.ClickSpring()
for t in range(0, 40, 8):                      # 静止 40ms，应停在静止帧
    px_ = s.step(t, False)
eq('静止 -> None（表示用常态图标，不换帧）', px_, None)

s = px.ClickSpring()
s.step(0, False)
for t in range(8, 200, 8):                     # 按住 200ms
    px_ = s.step(t, True)
print('    按住 200ms 后 compression=%.4f frame=%d' % (s.compression, px_))
eq('按住到底 -> 帧号 100+6', px_, 106)
peak = px.scale_of_frame(px_)
eq('按住到底倍率', round(peak, 4), 0.9456)

lo_frame = px.REST_FRAME
for t in range(200, 900, 4):                   # 松手 700ms：先回落、再弹过 1.0
    px_ = s.step(t, False)
    if px_ is not None:
        lo_frame = min(lo_frame, px_)
print('    松手后最高弹到帧号 %d（<6 即越过 1.0，过冲顶=0 号帧 1.0397×）' % lo_frame)
eq('回弹确实越过 1.0（出现 <6 号帧）', lo_frame < px.REST_FRAME, True)
eq('回弹不超过过冲顶 0 号帧', lo_frame >= 0, True)
for t in range(900, 4000, 8):                  # 足够久后应回到静止
    px_ = s.step(t, False)
eq('松手足够久 -> None（收敛，回常态图标）', px_, None)

print()
print('== ① 最短按下 75ms（Runtime.cs:1173）：按一瞬也要走完压缩 ==')
s2 = px.ClickSpring()
s2.step(0, False)
s2.step(8, True)
s2.step(16, False)                             # 8ms 就松手
f16 = s2.step(16, False)
s2.step(24, False)
s2.step(32, False)
eq('8ms 点击后仍在压缩段（帧号 > 6）', s2.compression > 0.0, True)

print()
print('== ② 拖动帧序：Runtime.cs:1115-1137（60fps 时间基）==')
d = px.DragWatch()
d.moving = True
d.drag_at = 0
eq('拖 0ms', d.frame(0), ('grab_enter', 0))
eq('拖 100ms', d.frame(100), ('grab_enter', 6))
eq('拖 200ms', d.frame(200), ('grab_begin', 0))
eq('拖 390ms', d.frame(390), ('grab_begin', 11))
eq('拖 400ms', d.frame(400), ('grab_loop', 0))
eq('拖 5000ms', d.frame(5000), ('grab_loop', 0))
d.moving = False
d.drag_end_at = 0
eq('松手 0ms', d.frame(0), ('grab_end', 0))
eq('松手 600ms', d.frame(600), ('grab_end', 36))
eq('松手 683ms（41 帧 = 683.33ms，此处仍是末帧）', d.frame(683), ('grab_end', 40))
eq('松手 684ms（跨过 41 帧边界）', d.frame(684), ('grab_return', 0))
eq('松手 900ms', d.frame(900), ('grab_return', 11))
eq('松手 5000ms', d.frame(5000), ('grab_return', 11))
d.drag_end_at = 700
eq('尾巴在 884ms 内还活着', d.visual(900), True)
eq('尾巴到 1584ms 结束', d.visual(700 + 884), False)

print()
print('== fx.bin 与帧缓存 ==')
fx = px.FxFrames()
eq('fx.bin 载入', fx.pack is not None, True)
print('    族 = %s' % (sorted(fx.pack.roles) if fx.pack else None))
if fx.pack:
    eq('grab_loop 帧数', fx.pack.frame_count('grab_loop'), 2)
    eq('grab_end 帧数', fx.pack.frame_count('grab_end'), 41)
    eq('热点', fx.pack.hotspot('grab_loop'), (28, 20))
    eq('点击原帧 hand_normal 帧数', fx.pack.frame_count('hand_normal'), 107)
    eq('待机循环帧数', fx.pack.frame_count('idle_frame'), 342)
    eq('待机进入帧数', fx.pack.frame_count('idle_enter_frame'), 30)
    for _f in px.CLICK_ART.values():
        eq('点击族 %s 在 fx.bin 里' % _f, fx.has(_f), True)
    for _f in px.DRAG_FAMILIES:
        eq('拖动族 %s 在 fx.bin 里' % _f, fx.has(_f), True)
    for _f in px.IDLE_FAMILIES:
        eq('待机族 %s 在 fx.bin 里' % _f, fx.has(_f), True)
    hc = fx.icon('grab_begin', 3, 115)
    eq('造出一枚 115px 爪子', bool(hc), True)
    if hc:
        eq('量出来的尺寸', cw.measure_hcursor(hc)[0], 115)
    hc2 = fx.icon('hand_normal', 106, 72)
    eq('造出一枚 72px 点击原帧', bool(hc2), True)
    if hc2:
        eq('点击原帧量出来的尺寸', cw.measure_hcursor(hc2)[0], 72)
    eq('同一帧同尺寸拿回同一枚句柄（有缓存）', fx.icon('hand_normal', 106, 72), hc2)
    fx.close()

print()
print('== 参数装配 ==')
o = cw.fx_options({'click_anim': True, 'click_style': 'prts'})
eq('prts 风格不缩放（用原帧）', (o['min_scale'], o['max_scale']), (1.0, 1.0))
eq('prts 风格只铺 base 一档', cw.anim_rungs(115, o), (115,))
eq('prts 风格不改尺寸 -> fx_scales 退回 1.0', cw.fx_scales(o), (1.0, 1.0))
o2 = cw.fx_options({'click_anim': True, 'click_style': 'game'})
eq('game 风格下限（按用户要求收敛到 ~10%）', o2['min_scale'], 0.90)
eq('game 风格上限', o2['max_scale'], 1.10)
eq('game 风格铺阶梯', cw.anim_rungs(115, o2),
   tuple(range(104, 128)))
o3 = cw.fx_options({'click_anim': True, 'click_style': 'prts',
                    'min_scale': 0.75, 'max_scale': 1.25})
eq('旧设置里的 0.75/1.25 不再把 prts 风格带偏', o3['max_scale'], 1.0)
eq('旧设置里的 0.75/1.25 不再把 prts 阶梯铺满', cw.anim_rungs(72, o3), (72,))
eq('非法风格回落 prts', cw.fx_options({'click_style': 'nope'})['click_style'], 'prts')
eq('fx_any_on(全关)', cw.fx_any_on(cw.fx_options(
    {'click_anim': False, 'idle_prts': False, 'drag_claw': False})), False)
eq('fx_any_on(只开爪子)', cw.fx_any_on(cw.fx_options(
    {'click_anim': False, 'idle_prts': False, 'drag_claw': True})), True)
eq('fx_any_on(只开待机)', cw.fx_any_on(cw.fx_options(
    {'click_anim': False, 'idle_prts': True, 'drag_claw': False})), True)
eq('待机默认开', cw.FX_DEFAULTS['idle_prts'], True)
eq('点击默认 prts 风格', cw.FX_DEFAULTS['click_style'], 'prts')

print()
print('FAILED: %d %s' % (len(fails), fails if fails else ''))
sys.exit(1 if fails else 0)
