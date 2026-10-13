# -*- coding: utf-8 -*-
"""修复后的全量验收：每个 setter 都要「读回等于目标值」才算通过。
测完把每一项都还原成测得前的原值。
"""
import sys
import time

sys.path.insert(0, r'E:\Qianmory\Desktop\Mouse\源码\arkmouse')
import mousep

print('=== 测试前原值 ===')
before = mousep.get_all()
for k, v in before.items():
    print('  %-16s = %r' % (k, v))
mask0 = mousep.reg_get('UserPreferencesMask', mousep.REG_DESKTOP)[0]
reg0 = {}
for n, p in (('MouseTrails', mousep.REG_MOUSE),
             ('MouseHoverTime', mousep.REG_MOUSE),
             ('WheelScrollLines', mousep.REG_DESKTOP)):
    reg0[n] = mousep.reg_get(n, p)[0]
print('  mask=%r  reg=%r' % ([int(x) for x in mask0], reg0))

PASS, FAIL = [], []


def check(zh, fn, target, read):
    try:
        ok = fn()
    except Exception as e:
        ok = '异常 %s' % e
    time.sleep(0.3)
    got = read()
    good = (got == target)
    (PASS if good else FAIL).append(zh)
    print('  %-16s 目标=%-8r 返回=%-6s 读回=%-8r %s' % (
        zh, target, ok, got, '✓' if good else '✗'))


print('\n=== 1) 整数类（修复重点）===')
o = before['鼠标轨迹']
check('鼠标轨迹', lambda: mousep.set_mouse_trails(5), 5,
      lambda: mousep.spi_get_int('mouse_trails'))
mousep.set_mouse_trails(o)
o = before['悬停时间']
check('悬停时间', lambda: mousep.set_hover_time(777), 777,
      lambda: mousep.spi_get_int('hover_time'))
mousep.set_hover_time(o)
o = before['滚轮行数']
check('滚轮行数', lambda: mousep.set_wheel_lines(9), 9,
      lambda: mousep.get_wheel_lines(default=-1))
mousep.set_wheel_lines(o)
o = before['鼠标速度']
check('鼠标速度', lambda: mousep.set_mouse_speed(5), 5,
      lambda: mousep.spi_get_int('mouse_speed'))
mousep.set_mouse_speed(o)
o = before['双击速度']
check('双击速度', lambda: mousep.set_double_click(333), 333,
      lambda: int(mousep.u32.GetDoubleClickTime()))
mousep.set_double_click(o)

print('\n=== 2) 布尔类（传值路径）===')
for what, zh, key in (('mouse_vanish', '打字隐藏指针', '打字时隐藏指针'),
                      ('cursor_shadow', '指针阴影', '指针阴影'),
                      ('click_lock', '点击锁定', '点击锁定')):
    o = before[key]
    tg = (not o)
    check(zh, (lambda w, t: (lambda: mousep.spi_set_bool(w, t)))(what, tg), tg,
          (lambda w: (lambda: mousep.spi_get_bool(w)))(what))
    mousep.spi_set_bool(what, o)

print('\n=== 3) 不支持项（应老实返回 False）===')
for what, zh in (('swap_buttons', '左右键互换'),
                 ('snap_to_default', '吸附到默认按钮')):
    r = mousep.spi_set_bool(what, True)
    print('  %-16s 返回=%s %s' % (zh, r, '✓ 正确地拒绝了' if r is False else '✗ 假装成功'))
    if r is False:
        PASS.append(zh)
    else:
        FAIL.append(zh)

print('\n=== 4) 备份 / 还原 全链路 ===')
import os
import tempfile
bp = os.path.join(tempfile.gettempdir(), '_mouse_verify_backup.json')
# 必须先备份（原始状态），再改动，最后还原回到原始状态
doc = mousep.backup(bp)
mousep.set_hover_time(555)
mousep.set_wheel_lines(7)
mid = mousep.get_all()
changed = (mid['悬停时间'] == 555 and mid['滚轮行数'] == 7)
print('  改动生效=%s（悬停=%r 滚轮=%r）' % (
    changed, mid['悬停时间'], mid['滚轮行数']))
n = mousep.restore(bp)
time.sleep(0.5)
after = mousep.get_all()
same = True
for k in before:
    if before[k] != after.get(k):
        print('  ✗ %s: 原=%r 还原后=%r' % (k, before[k], after.get(k)))
        same = False
print('  备份项数=%d  还原后与原始完全一致=%s' % (n, same))
(PASS if (same and changed) else FAIL).append('备份还原')
if not changed:
    FAIL.append('改动未生效')

mask1 = mousep.reg_get('UserPreferencesMask', mousep.REG_DESKTOP)[0]
print('  mask 还原=%s' % ('✓' if mask1 == mask0 else '✗ %r' % (mask1,)))
if mask1 != mask0:
    FAIL.append('mask')

print('\n=== 5) 最终 get_all() ===')
for k, v in after.items():
    print('  %-16s = %r' % (k, v))

print('\n========================================')
print('通过 %d 项：%s' % (len(PASS), '、'.join(PASS)))
if FAIL:
    print('失败 %d 项：%s' % (len(FAIL), '、'.join(FAIL)))
else:
    print('失败 0 项 —— 全部通过 ✓')
