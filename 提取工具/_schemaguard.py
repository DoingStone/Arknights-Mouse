# -*- coding: utf-8 -*-
"""验证守护的注册表方案自愈：改坏方案 -> 守护应改回来。"""
import os
import sys
import time
import winreg

APP = r'E:\Qianmory\Desktop\Mouse'
SRC = os.path.join(APP, '源码', 'arkmouse')
sys.path.insert(0, SRC)
import guard       # noqa: E402
import cursorwin as cw   # noqa: E402
import store       # noqa: E402

cw.dpi_aware()
REG = cw.REG_CURSORS_PATH
PACK = os.path.join(APP, '指针', 'cursors', 'large')


def arrow():
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG) as k:
        return winreg.QueryValueEx(k, 'Arrow')[0]


def name():
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG) as k:
        return winreg.QueryValueEx(k, '')[0]


def n_pack():
    n = 0
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG) as k:
        for r in cw.ROLES:
            try:
                v = winreg.QueryValueEx(k, r[0])[0]
            except OSError:
                continue
            if v and v.lower().startswith(PACK.lower()):
                n += 1
    return n


print('=== 现状 ===')
print('  方案名 = %r' % name())
print('  Arrow  = %s' % arrow())
print('  指向本包的角色数 = %d / 17' % n_pack())
print('  scheme_ok() = %s' % guard.Guard().scheme_ok())

print()
print('=== 模拟系统把方案改回旧方案 ===')
with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, REG, 0,
                        winreg.KEY_SET_VALUE) as k:
    winreg.SetValueEx(k, 'Arrow', 0, winreg.REG_SZ,
                      r'C:\WINDOWS\Cursors\HuiRanBlueBorderedBig\Normal.cur')
    winreg.SetValueEx(k, '', 0, winreg.REG_SZ, 'HuiRan鼠标指针蓝色（大-有框）')
print('  改坏后 Arrow = %s' % arrow())
print('  改坏后 方案名 = %r' % name())
print('  scheme_ok() = %s  <- 应 False' % guard.Guard().scheme_ok())

print()
print('=== 启动守护，看它能否自愈 ===')
import subprocess  # noqa: E402
p = subprocess.Popen([sys.executable, os.path.join(SRC, 'main.pyw'), '--guard'],
                     cwd=APP, creationflags=0x00000008)
print('  守护 pid = %d' % p.pid)

for i in range(12):
    time.sleep(1.5)
    n = n_pack()
    print('  %4.1fs  Arrow=%s…  指向本包 %d/17  方案名=%r'
          % ((i + 1) * 1.5, os.path.basename(arrow())[:24], n, name()[:22]))
    if n == 17:
        break

print()
ok = n_pack() == 17
print('结果：%s' % ('✓ 守护成功改回本包方案' if ok else '✗ 未改回'))

st = guard.guard_status()
print('守护状态 = %s' % (st,))
print('桌面光标 = %s' % (cw.desktop_cursor_size(),))

print()
print('=== 守护日志尾部 ===')
lp = os.path.join(APP, '运行日志.txt')
if os.path.isfile(lp):
    for ln in open(lp, encoding='utf-8').read().strip().split('\n')[-8:]:
        print('  ' + ln)
