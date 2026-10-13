# -*- coding: utf-8 -*-
"""SPI 写入耗时拆解：flags 的哪一位在拖慢它。

SPI_FLAGS = 0x01 (SPIF_UPDATEINIFILE) | 0x02 (SPIF_SENDCHANGE)
0x02 会向所有顶层窗口广播 WM_SETTINGCHANGE —— 这通常是耗时主因。
"""
import ctypes
import ctypes.wintypes as wt
import sys
import time

sys.path.insert(0, r'E:\Qianmory\Desktop\Mouse\源码\arkmouse')
import mousep  # noqa: E402

u32 = ctypes.WinDLL('user32', use_last_error=True)
u32.SystemParametersInfoW.argtypes = [ctypes.c_ulong, ctypes.c_ulong,
                                      ctypes.c_void_p, ctypes.c_ulong]
u32.SystemParametersInfoW.restype = ctypes.c_long

orig = mousep.get_wheel_lines()
print('原始 WheelScrollLines = %r' % orig)
print()
print('%-34s %10s %10s' % ('调用姿势', '单次ms', '改到注册表?'))
print('-' * 58)

variants = [
    ('SET 0x0069 uiParam, flags=0x03（现状）', 0x00,
     lambda v: u32.SystemParametersInfoW(0x0069, v, 0, 0x03)),
    ('SET 0x0069 uiParam, flags=0x01（只写盘）', 0x01,
     lambda v: u32.SystemParametersInfoW(0x0069, v, 0, 0x01)),
    ('SET 0x0069 uiParam, flags=0x00（只改内存）', 0x00,
     lambda v: u32.SystemParametersInfoW(0x0069, v, 0, 0x00)),
    ('纯注册表写入（无 SPI）', 0x00,
     lambda v: mousep.reg_set('WheelScrollLines', str(v), 1, mousep.REG_DESKTOP)),
]

for name, _f, fn in variants:
    # 每次先复位
    mousep.reg_set('WheelScrollLines', '0', 1, mousep.REG_DESKTOP)
    u32.SystemParametersInfoW(0x0069, 0, 0, 0x00)
    time.sleep(0.2)
    t0 = time.time()
    for i in range(10):
        fn(6)
    dt = (time.time() - t0) / 10 * 1000
    time.sleep(0.35)
    got = mousep.reg_get('WheelScrollLines', mousep.REG_DESKTOP)[0]
    print('%-34s %10.1f %10s' % (name, dt, repr(got)))

print()
print('-' * 58)
print('结论：')
print('  若 flags=0x00/0x01 明显更快 → 拖动中用 flags=0x00（只改内存，')
print('  视觉上立刻生效），松手后再用 flags=0x03 落盘 + 广播一次。')

# 还原
u32.SystemParametersInfoW(0x0069, orig, 0, 0x03)
time.sleep(0.3)
print()
print('还原 → %r' % mousep.get_wheel_lines())
