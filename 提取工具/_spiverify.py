# -*- coding: utf-8 -*-
"""验证 mousep 的拖动路径已经变成 0 ms 级，且松手后的 commit_* 仍能落盘。"""
import sys
import time

sys.path.insert(0, r'E:\Qianmory\Desktop\Mouse\源码\arkmouse')
import mousep  # noqa: E402

base = mousep.get_all()
print('基线: 滚轮=%s 悬停=%s 轨迹=%s' % (base['滚轮行数'], base['悬停时间'],
                                          base['鼠标轨迹']))
print()

print('=== A) 拖动路径（broadcast=False）===')
for name, fn, val in [('set_wheel_lines', mousep.set_wheel_lines, 5),
                      ('set_hover_time', mousep.set_hover_time, 300),
                      ('set_mouse_trails', mousep.set_mouse_trails, 3)]:
    t0 = time.time()
    for _ in range(20):
        fn(val, verify=False)
    dt = (time.time() - t0) / 20 * 1000
    print('  %-18s 20 次平均 %8.1f ms/次' % (name, dt))

print()
print('=== B) 松手路径（broadcast=True + 回读）===')
for name, fn, val, rd in [
        ('commit_wheel_lines', mousep.commit_wheel_lines, 5,
         lambda: mousep.get_wheel_lines()),
        ('commit_hover_time', mousep.commit_hover_time, 300,
         lambda: mousep.spi_get_int('hover_time')),
        ('commit_mouse_trails', mousep.commit_mouse_trails, 3,
         lambda: mousep.spi_get_int('mouse_trails'))]:
    t0 = time.time()
    ok = fn(val)
    dt = (time.time() - t0) * 1000
    print('  %-20s ok=%-5s 读回=%-5s %6.0f ms' % (name, ok, rd(), dt))

print()
print('=== C) 还原 ===')
mousep.set_wheel_lines(base['滚轮行数'])
mousep.set_hover_time(base['悬停时间'])
mousep.set_mouse_trails(base['鼠标轨迹'])
d = mousep.get_all()
print('  滚轮=%s 悬停=%s 轨迹=%s' % (d['滚轮行数'], d['悬停时间'], d['鼠标轨迹']))
print('  与基线一致：%s' % (d['滚轮行数'] == base['滚轮行数']
                          and d['悬停时间'] == base['悬停时间']
                          and d['鼠标轨迹'] == base['鼠标轨迹']))
