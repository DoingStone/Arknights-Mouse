# -*- coding: utf-8 -*-
"""权威判定：每个 SPI setter 的 pvParam 到底要「传值」还是「传址」。
对每个参数各试两种传参，记录读回值，得出唯一正确约定。
"""
import ctypes
import sys
import time

sys.path.insert(0, r'E:\Qianmory\Desktop\Mouse\源码\arkmouse')
import mousep

u32 = mousep.u32
FLAGS = 0x03
CASES = [
    ('mouse_speed', '指针速度', 0x0071, 0x0070, 5),
    ('mouse_trails', '鼠标轨迹', 0x005D, 0x005E, 5),
    ('hover_time', '悬停时间', 0x0067, 0x0066, 777),
    ('wheel_lines', '滚轮行数', 0x0069, 0x0068, 9),
    ('double_click', '双击速度', 0x001F, 0x001E, 333),
]
print('=== 整数类 SPI：传值 vs 传址 ===')
print('（每项先记录当前值，分别用两种方式设置同一个目标值，看哪个真能改变读回值）')
for what, zh, setc, getc, target in CASES:
    cur = mousep.spi_get_int(what)
    print('\n-- %s %s  set=0x%04X get=0x%04X  当前=%r 目标=%r' % (
        zh, what, setc, getc, cur, target))

    # 方式 1：传值
    r1 = u32.SystemParametersInfoW(setc, 0, target, FLAGS)
    time.sleep(0.35)
    v1 = mousep.spi_get_int(what)
    print('   传值   ret=%-3s -> 读回=%-8r %s' % (
        r1, v1, '✓ 生效' if v1 == target else '✗'))

    # 方式 2：传址
    r2 = u32.SystemParametersInfoW(setc, 0,
                                   ctypes.byref(ctypes.c_int(target)), FLAGS)
    time.sleep(0.35)
    v2 = mousep.spi_get_int(what)
    print('   传址   ret=%-3s -> 读回=%-8r %s' % (
        r2, v2, '✓ 生效' if v2 == target else '✗'))

    # 方式 3：传址（c_uint 版，unsigned SPI 用）
    r3 = u32.SystemParametersInfoW(setc, 0,
                                   ctypes.byref(ctypes.c_uint(target)), FLAGS)
    time.sleep(0.35)
    v3 = mousep.spi_get_int(what)
    print('   传址u  ret=%-3s -> 读回=%-8r %s' % (
        r3, v3, '✓ 生效' if v3 == target else '✗'))

    # 还原
    if cur is not None:
        u32.SystemParametersInfoW(setc, 0, cur, FLAGS)
        u32.SystemParametersInfoW(setc, 0, ctypes.byref(ctypes.c_int(cur)), FLAGS)
        time.sleep(0.3)
    print('   还原(%r) -> 读回=%r' % (cur, mousep.spi_get_int(what)))

print('\n=== 最终的 get_all() ===')
for k, v in mousep.get_all().items():
    print('  %-16s = %r' % (k, v))
