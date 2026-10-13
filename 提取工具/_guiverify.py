# -*- coding: utf-8 -*-
"""验证 GUI 的每一条写入路径都真的生效（用真实控件 + 真实事件循环）。
   * 两个「本机不支持」的开关必须处于 disabled 状态
   * 其余每个滑杆/开关点一下就应改变系统读数
   * 测完把系统还原
"""
import os
import sys
import time

sys.path.insert(0, r'E:\Qianmory\Desktop\Mouse\源码\arkmouse')

import tkinter as tk

import main as app_mod          # main.pyw 以模块方式导入
import mousep

sys.path.insert(0, os.path.join(r'E:\Qianmory\Desktop\Mouse\源码\arkmouse'))
os.chdir(r'E:\Qianmory\Desktop\Mouse\源码\arkmouse')

before = mousep.get_all()
print('=== 测试前 ===')
for k, v in before.items():
    print('  %-16s = %r' % (k, v))

root = tk.Tk()
app = app_mod.App(root)
root.update()
root.update_idletasks()
time.sleep(0.4)
root.update()

PASS, FAIL = [], []

print('\n=== 1) 「本机不支持」的开关应被禁用 ===')
for key, zh in (('swap', '左右键互换'), ('snap', '吸附到默认按钮')):
    cb = app.mb[key][0]
    dis = 'disabled' in cb.state()
    (PASS if dis else FAIL).append(zh)
    print('  %-16s disabled=%s %s' % (zh, dis, '✓' if dis else '✗ 应该禁用'))

print('\n=== 2) 可用的开关：invoke 后系统读数必须跟着变 ===')
for key, zh, field in (('vanish', '打字时隐藏指针', '打字时隐藏指针'),
                       ('shadow', '指针阴影', '指针阴影'),
                       ('lock', '点击锁定', '点击锁定')):
    o = mousep.get_all()[field]
    app.mb[key][0].invoke()
    root.update()
    time.sleep(0.35)
    n = mousep.get_all()[field]
    good = (n != o)
    (PASS if good else FAIL).append(zh)
    print('  %-16s %s -> %s %s' % (zh, o, n, '✓' if good else '✗ 没变'))
    app.mb[key][0].invoke()
    root.update()
    time.sleep(0.35)

print('\n=== 3) 滑杆：set 后调用回调，系统读数必须跟着变 ===')
for name, zh, field, target in (
        ('speed', '指针速度', '鼠标速度', 5),
        ('dbl', '双击速度', '双击速度', 333),
        ('wheel', '滚轮行数', '滚轮行数', 9),
        ('trail', '鼠标轨迹', '鼠标轨迹', 5),
        ('hover', '悬停时间', '悬停时间', 777)):
    o = mousep.get_all()[field]
    sc = app.mv[name]
    sc.set(target)
    root.update()
    cbname = {'speed': '_on_speed', 'dbl': '_on_dbl', 'wheel': '_on_wheel',
              'trail': '_on_trail', 'hover': '_on_hover'}[name]
    getattr(app, cbname)(target)
    root.update()
    time.sleep(0.4)
    n = mousep.get_all()[field]
    good = (n == target)
    (PASS if good else FAIL).append(zh)
    print('  %-16s 目标=%-6r 读回=%-6r %s' % (zh, target, n, '✓' if good else '✗'))

print('\n=== 4) refresh_mouse 不应改变任何东西 ===')
s1 = mousep.get_all()
app.refresh_mouse()
root.update()
time.sleep(0.4)
s2 = mousep.get_all()
same = (s1 == s2)
(PASS if same else FAIL).append('刷新无副作用')
print('  刷新前后一致=%s %s' % (same, '✓' if same else '✗'))
if not same:
    for k in s1:
        if s1[k] != s2.get(k):
            print('     %s: %r -> %r' % (k, s1[k], s2.get(k)))

print('\n=== 5) 还原 ===')
for what, field in (('mouse_vanish', '打字时隐藏指针'),
                    ('cursor_shadow', '指针阴影'),
                    ('click_lock', '点击锁定')):
    mousep.spi_set_bool(what, before[field])
mousep.set_sensitivity(before['鼠标速度'])
mousep.set_mouse_speed(before['鼠标速度'])
mousep.set_double_click(before['双击速度'])
mousep.set_wheel_lines(before['滚轮行数'])
mousep.set_mouse_trails(before['鼠标轨迹'])
mousep.set_hover_time(before['悬停时间'])
time.sleep(0.5)
after = mousep.get_all()
ok = True
for k in before:
    if before[k] != after.get(k):
        print('  ✗ %s: 原=%r 现值=%r' % (k, before[k], after.get(k)))
        ok = False
print('  还原与原始完全一致=%s %s' % (ok, '✓' if ok else '✗'))
(PASS if ok else FAIL).append('还原')

root.destroy()

print('\n========================================')
print('通过 %d 项：%s' % (len(PASS), '、'.join(PASS)))
if FAIL:
    print('失败 %d 项：%s' % (len(FAIL), '、'.join(FAIL)))
else:
    print('失败 0 项 —— GUI 全部路径验证通过 ✓')
