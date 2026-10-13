# -*- coding: utf-8 -*-
"""建立开机自启：写 HKCU\\...\\Run 项，用 pythonw --apply 1.20 静默应用。

注意：--apply 内部若 state.json 里 animate=True 会常驻并跑动画线程，
这正是我们想要的（开机后动画和尺寸都恢复）。
"""
import subprocess
import winreg
import os
import sys

HERE = r'G:\ArknightsCursorExtract\CursorSizeTool'
TOOL = os.path.join(HERE, 'ArknightsCursorSize.pyw')
PYW = r'C:\Users\22442\AppData\Local\Programs\Python\Python311\pythonw.exe'
REG_RUN = r'Software\Microsoft\Windows\CurrentVersion\Run'
NAME = 'ArknightsCursorSize'

assert os.path.exists(TOOL), TOOL
assert os.path.exists(PYW), PYW

cmd = '"%s" "%s" --apply 1.20' % (PYW, TOOL)
print('自启命令:', cmd)

with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, REG_RUN, 0,
                        winreg.KEY_SET_VALUE) as k:
    winreg.SetValueEx(k, NAME, 0, winreg.REG_SZ, cmd)

with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_RUN) as k:
    val, typ = winreg.QueryValueEx(k, NAME)
print('回读: type=%s value=%s' % (typ, val))
print('一致:', val == cmd)
