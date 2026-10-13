# -*- coding: utf-8 -*-
"""最小诊断：keys_state() 看不看得见注入的按键。

① 的整条链路都建立在 keys_state() 之上；如果这里读不到，弹簧根本不会压缩。
用 Shift 试，它按一下不会点坏任何东西。
"""
import ctypes
import sys
import time

sys.path.insert(0, r'E:\Qianmory\Desktop\Mouse\源码')
from arkmouse import cursorwin as cw          # noqa: E402

u32 = cw.u32
VK_SHIFT = 0x10
KEYUP = 0x0002

u32.keybd_event.argtypes = [ctypes.c_ubyte, ctypes.c_ubyte, ctypes.c_uint, ctypes.c_void_p]

print('按前 keys_state((VK_SHIFT,)) =', cw.keys_state((VK_SHIFT,)))
print('  GetAsyncKeyState(VK_SHIFT) =', u32.GetAsyncKeyState(VK_SHIFT))
u32.keybd_event(VK_SHIFT, 0, 0, None)
time.sleep(0.05)
print('按住 keys_state((VK_SHIFT,)) =', cw.keys_state((VK_SHIFT,)))
print('  GetAsyncKeyState(VK_SHIFT) =', u32.GetAsyncKeyState(VK_SHIFT))
u32.keybd_event(VK_SHIFT, 0, KEYUP, None)
time.sleep(0.05)
print('松开 keys_state((VK_SHIFT,)) =', cw.keys_state((VK_SHIFT,)))
