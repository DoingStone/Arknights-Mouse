# -*- coding: utf-8 -*-
"""判定布尔类 SPI 的 pvParam 约定：传值 vs 传址。逐个开关做真值表。"""
import ctypes
import sys
import time

sys.path.insert(0, r'E:\Qianmory\Desktop\Mouse\源码\arkmouse')
import mousep

u32 = mousep.u32
NAMES = {'swap_buttons': '左右键互换', 'snap_to_default': '吸附默认按钮',
         'mouse_vanish': '打字隐藏指针', 'cursor_shadow': '指针阴影',
         'click_lock': '点击锁定'}

print('=== 真值表：每种传参方式，试设置成与当前相反的值 ===')
for what, zh in NAMES.items():
    get_c, set_c = mousep.SPI[what]
    cur = mousep.spi_get_bool(what)
    want = not bool(cur)
    print('\n-- %s (%s) 0x%04X/0x%04X  当前=%s  目标=%s' % (
        zh, what, get_c, set_c, cur, want))

    # 方式 1：传值（PVOID 里直接放 BOOL）
    for label, third in (
            ('传值', 1 if want else 0),
            ('传址', ctypes.byref(ctypes.c_int(1 if want else 0))),
            ('传址(c_void_p值)', ctypes.c_void_p(1 if want else 0))):
        r = u32.SystemParametersInfoW(set_c, 0, third, mousep.SPI_FLAGS)
        time.sleep(0.3)
        got = mousep.spi_get_bool(what)
        print('   %-18s ret=%-3s -> 读回=%-6s %s' % (
            label, r, got, '✓ 生效' if got == want else '✗ 无效'))

    # 还原到原始值：用刚才生效的那种方式（优先传值）
    u32.SystemParametersInfoW(set_c, 0, 1 if cur else 0, mousep.SPI_FLAGS)
    time.sleep(0.3)
    back = mousep.spi_get_bool(what)
    print('   还原为 %s -> 读回=%s %s' % (
        cur, back, '✓' if back == cur else '✗ 还原失败'))

print('\n=== 双击速度再确认（三次） ===')
o = int(u32.GetDoubleClickTime())
print('  起始 = %s' % o)
for v in (333, 250, o):
    mousep.set_double_click(v)
    time.sleep(0.3)
    print('  set(%s) -> GetDoubleClickTime()=%s' % (v, u32.GetDoubleClickTime()))

print('\n=== 收尾：与最初实测基线对齐 ===')
print('  期望基线: swap=False snap=False vanish=True shadow=False lock=False')
print('  实际:     swap=%s snap=%s vanish=%s shadow=%s lock=%s' % (
    mousep.spi_get_bool('swap_buttons'),
    mousep.spi_get_bool('snap_to_default'),
    mousep.spi_get_bool('mouse_vanish'),
    mousep.spi_get_bool('cursor_shadow'),
    mousep.spi_get_bool('click_lock')))
