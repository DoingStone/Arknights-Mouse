# -*- coding: utf-8 -*-
"""迁移收尾：把旧的开机自启键换成新的 exe 路径。

旧：HKCU\\...\\Run\\ArknightsCursorSize -> pythonw.exe "G:\\...\\CursorSizeTool\\ArknightsCursorSize.pyw" --apply 1.20
新：HKCU\\...\\Run\\ArknightsMouse      -> "E:\\Qianmory\\Desktop\\Mouse\\明日方舟鼠标.exe" --apply 1.20
"""
import sys
import winreg

RUN = r'Software\Microsoft\Windows\CurrentVersion\Run'
OLD = 'ArknightsCursorSize'
NEW = 'ArknightsMouse'
NEW_CMD = '"E:\\Qianmory\\Desktop\\Mouse\\明日方舟鼠标.exe" --apply 1.20'

print('=== 0) 当前 Run 键全部项 ===')


def dump_run():
    out = {}
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN) as k:
            n = winreg.QueryInfoKey(k)[1]
            for i in range(n):
                name, data, typ = winreg.EnumValue(k, i)
                out[name] = (data, typ)
    except OSError as e:
        print('  打不开 Run 键：%s' % e)
    return out


for name, (data, typ) in sorted(dump_run().items()):
    mark = ''
    if name == OLD:
        mark = '   <-- 旧工具，应删除'
    elif name == NEW:
        mark = '   <-- 新键'
    print('  %-28s type=%d  %r%s' % (name, typ, data, mark))

print('\n=== 1) 写新键 %s ===' % NEW)
with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, RUN, 0,
                        winreg.KEY_SET_VALUE) as k:
    winreg.SetValueEx(k, NEW, 0, winreg.REG_SZ, NEW_CMD)
got = winreg.QueryValueEx(
    winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN), NEW)
print('  写入 %r' % NEW_CMD)
print('  回读 %r type=%d  %s' % (got[0], got[1],
                                '✓' if got[0] == NEW_CMD else '✗'))

print('\n=== 2) 删除旧键 %s ===' % OLD)
try:
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN, 0,
                        winreg.KEY_SET_VALUE) as k:
        winreg.DeleteValue(k, OLD)
    print('  已删除 ✓')
except FileNotFoundError:
    print('  本来就不存在（无需删除）')
except OSError as e:
    print('  删除失败：%s' % e)

print('\n=== 3) 最终 Run 键 ===')
d = dump_run()
for name, (data, typ) in sorted(d.items()):
    print('  %-28s type=%d  %r' % (name, typ, data))
print('\n  旧键已清除=%s  新键正确=%s' % (
    OLD not in d, d.get(NEW, ('', 0))[0] == NEW_CMD))

print('\n=== 4) 目标 exe 是否存在 ===')
import os
exe = r'E:\Qianmory\Desktop\Mouse\明日方舟鼠标.exe'
if os.path.isfile(exe):
    print('  %s  %.2f MB ✓' % (exe, os.path.getsize(exe) / 1048576))
else:
    print('  ✗ 不存在：%s（等 exe 构建完成后再检查）' % exe)
