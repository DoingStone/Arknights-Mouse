# -*- coding: utf-8 -*-
"""最后一个假设：这些 SPI 是不是把值放在 uiParam（第2参）而不是 pvParam（第3参）？

背景：SPI_SETMOUSETRAILS(0x5D) / SPI_SETHOVERrTIME(0x67) / SPI_SETWHEELSCROLLLINES(0x69)
      传 pvParam 时返回 1 但读回不变。有些 SPI 的约定是把标量放在 uiParam。
另外也试 uiParam = 值的字节数（sizeof(int)=4）这种「文档写法」。
"""
import ctypes
import sys
import time

sys.path.insert(0, r'E:\Qianmory\Desktop\Mouse\源码\arkmouse')
import mousep

u32 = mousep.u32
F = 0x03
M = mousep.REG_MOUSE
D = mousep.REG_DESKTOP

CASES = [
    # what,          zh,         set,    get,    reg名,              路径, 目标
    ('mouse_trails', '鼠标轨迹', 0x005D, 0x005E, 'MouseTrails', M, 5),
    ('hover_time', '悬停时间', 0x0067, 0x0066, 'MouseHoverTime', M, 777),
    ('wheel_lines', '滚轮行数', 0x0069, 0x0068, 'WheelScrollLines', D, 9),
]

print('=== 传参位置对照：uiParam vs pvParam ===')
for what, zh, sc, gc, rn, rp, target in CASES:
    cur_spi = mousep.spi_get_int(what)
    cur_reg = mousep.reg_get(rn, rp)[0]
    print('\n-- %s (%s) set=0x%04X get=0x%04X  当前 SPI=%r 注册表=%r 目标=%r' % (
        zh, what, sc, gc, cur_spi, cur_reg, target))

    def show(tag, ret):
        time.sleep(0.35)
        print('   %-34s ret=%-3s SPI读回=%-6r 注册表=%r' % (
            tag, ret, mousep.spi_get_int(what), mousep.reg_get(rn, rp)[0]))

    def reset():
        mousep.reg_set(rn, str(cur_reg), 1, rp)
        u32.SystemParametersInfoW(sc, 0, int(cur_spi), F)
        mousep.broadcast_setting_change(rp)
        time.sleep(0.3)

    # V1: 值放 pvParam（已试过，做基线）
    show('V1 值放 pvParam',
         u32.SystemParametersInfoW(sc, 0, int(target), F))
    reset()

    # V2: 值放 uiParam，pvParam 传 0
    show('V2 值放 uiParam, pv=0',
         u32.SystemParametersInfoW(sc, int(target), 0, F))
    reset()

    # V3: 值放 uiParam，pvParam 传 NULL，而且不带 SPIF_UPDATEINIFILE
    show('V3 uiParam + flags=0',
         u32.SystemParametersInfoW(sc, int(target), 0, 0))
    reset()

    # V4: 文档写法 uiParam=sizeof(int)=4, pvParam=byref(value)
    v = ctypes.c_int(int(target))
    show('V4 ui=sizeof(int), pv=byref',
         u32.SystemParametersInfoW(sc, 4, ctypes.byref(v), F))
    reset()

    # V5: uiParam=0, pvParam=值(MAKELONG 形式: 低16位=值)
    show('V5 pv=MAKELONG(v,0)',
         u32.SystemParametersInfoW(sc, 0, int(target) & 0xFFFF, F))
    reset()

    # V6: 直接写注册表 + 广播（已知能改注册表），只观察 SPI 是否跟随
    mousep.reg_set(rn, str(target), 1, rp)
    mousep.broadcast_setting_change(rp)
    show('V6 只写注册表+广播（不调SPI）', 'n/a')
    reset()

    print('   还原 -> SPI=%r 注册表=%r' % (
        mousep.spi_get_int(what), mousep.reg_get(rn, rp)[0]))

print('\n=== 最终状态核对 ===')
for k, v in mousep.get_all().items():
    print('  %-16s = %r' % (k, v))
print('  mask = %r' % ([int(x) for x in mousep.reg_get('UserPreferencesMask', D)[0]],))
