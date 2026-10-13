# -*- coding: utf-8 -*-
"""修正自启动注册表键：改为 --guard，并复核设置.json 的 autostart 一致性。"""
import json
import os
import sys

APP = r'E:\Qianmory\Desktop\Mouse'
sys.path.insert(0, os.path.join(APP, '源码', 'arkmouse'))
import store  # noqa: E402

STATE = os.path.join(APP, '设置.json')

print('=== 之前 ===')
cur = store._read_run() if hasattr(store, '_read_run') else None
import winreg  # noqa: E402
try:
    k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, store.REG_RUN)
    old, typ = winreg.QueryValueEx(k, store.AUTORUN_NAME)
    winreg.CloseKey(k)
except FileNotFoundError:
    old, typ = None, None
print('  Run\\%s = %r' % (store.AUTORUN_NAME, old))
print('  设置.json = %s' % open(STATE, encoding='utf-8').read().strip())

print('\n=== 写入 --guard（指向 exe）===')
EXE_CMD = '"%s" --guard' % os.path.join(APP, '明日方舟鼠标.exe')
k = winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, store.REG_RUN, 0,
                       winreg.KEY_SET_VALUE)
winreg.SetValueEx(k, store.AUTORUN_NAME, 0, winreg.REG_SZ, EXE_CMD)
winreg.CloseKey(k)
ok = True
k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, store.REG_RUN)
new, typ = winreg.QueryValueEx(k, store.AUTORUN_NAME)
winreg.CloseKey(k)
print('  ok=%s' % ok)
print('  新值 = %r (type=%d)' % (new, typ))
print('  含 --guard : %s' % ('--guard' in new))
print('  含 --apply : %s' % ('--apply' in new))
print('  exe 路径正确 : %s' % (new.strip('"').lower().startswith(
    os.path.join(APP, '明日方舟鼠标.exe').lower())))

# 让 设置.json 也跟着一致
d = json.load(open(STATE, encoding='utf-8'))
d['autostart'] = store.get_autostart()
json.dump(d, open(STATE, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
print('\n=== 之后 ===')
print('  Run 键      = %r' % new)
print('  设置.json   = %s' % open(STATE, encoding='utf-8').read().strip())
print('  get_autostart() = %s' % store.get_autostart())

print('\n=== Run 键全部项 ===')
k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, store.REG_RUN)
i = 0
while True:
    try:
        n, v, t = winreg.EnumValue(k, i)
    except OSError:
        break
    print('  %-22s %s' % (n, v[:90]))
    i += 1
winreg.CloseKey(k)
