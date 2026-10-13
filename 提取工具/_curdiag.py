# -*- coding: utf-8 -*-
"""诊断：光标方案名为何变成 HuiRan，以及 17 角色当前指向哪里。"""
import os
import winreg

REG = r'Control Panel\Cursors'
ROLES = ['Arrow', 'Help', 'AppStarting', 'Wait', 'Crosshair', 'IBeam',
         'NWPen', 'No', 'SizeNS', 'SizeWE', 'SizeNWSE', 'SizeNESW',
         'SizeAll', 'UpArrow', 'Hand', 'Pin', 'Person']

k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG)
name, t = winreg.QueryValueEx(k, '')
print('方案名 = %r (type=%d)' % (name, t))
print()
PACK = r'E:\Qianmory\Desktop\Mouse\指针\cursors\large'
for r in ROLES:
    try:
        v, _ = winreg.QueryValueEx(k, r)
    except FileNotFoundError:
        v = None
    ok = 'OK ' if v and v.lower().startswith(PACK.lower()) else '   '
    print('  %s %-12s %s' % (ok, r, v))
print()
print('=== Schemes 子键 ===')
try:
    s = winreg.OpenKey(k, 'Schemes')
    i = 0
    while True:
        try:
            n, v, _t = winreg.EnumValue(s, i)
        except OSError:
            break
        print('  %-40s %s' % (n, str(v)[:80]))
        i += 1
    winreg.CloseKey(s)
except FileNotFoundError:
    print('  （无 Schemas 键）')
winreg.CloseKey(k)
