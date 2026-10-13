# -*- coding: utf-8 -*-
"""冷启动模拟验收：完全杀掉守护 -> 抹掉内存光标 + 改坏注册表方案
-> 按 Run 键原样启动 -> 观察是否自行恢复（模拟开机的完整时序）。"""
import os
import subprocess
import sys
import time
import winreg

APP = r'E:\Qianmory\Desktop\Mouse'
SRC = os.path.join(APP, '源码', 'arkmouse')
sys.path.insert(0, SRC)
import cursorwin as cw   # noqa: E402
import guard       # noqa: E402

cw.dpi_aware()
REG = cw.REG_CURSORS_PATH
PACK = os.path.join(APP, '指针', 'cursors', 'large')


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


def scheme_name():
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG) as k:
        return winreg.QueryValueEx(k, '')[0]


print('=== 0) 杀掉所有守护进程 ===')
subprocess.run(['taskkill', '/F', '/IM', '明日方舟鼠标.exe'],
               capture_output=True)
time.sleep(1.0)
st = guard.guard_status()
print('  守护 = %s' % (st,))
os.remove(os.path.join(APP, '守护状态.txt')) if os.path.isfile(
    os.path.join(APP, '守护状态.txt')) else None

print('\n=== 1) 模拟「开机后系统把一切都重置」===')
# a) 抹掉内存光标
cw.u32.SystemParametersInfoW(0x0057, 0, None, 0x03)
# b) 把注册表方案改回旧方案
with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, REG, 0,
                        winreg.KEY_SET_VALUE) as k:
    for r in cw.ROLES:
        winreg.SetValueEx(k, r[0], 0, winreg.REG_SZ,
                          r'C:\WINDOWS\Cursors\HuiRanBlueBorderedBig\x.cur')
    winreg.SetValueEx(k, '', 0, winreg.REG_SZ, 'HuiRan鼠标指针蓝色（大-有框）')
time.sleep(0.6)
print('  桌面光标 = %s' % (cw.desktop_cursor_size(),))
print('  指向本包 = %d/17' % n_pack())
print('  方案名   = %r' % scheme_name())

print('\n=== 2) 完全按 Run 键原样启动（模拟开机自启）===')
with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                    r'Software\Microsoft\Windows\CurrentVersion\Run') as k:
    cmd = winreg.QueryValueEx(k, 'ArknightsMouse')[0]
print('  Run 键 = %s' % cmd)
subprocess.Popen(cmd, shell=True, cwd='C:' + os.sep)
print('  已启动，开始轮询…')

t0 = time.time()
ok = False
for i in range(16):
    time.sleep(1.5)
    g = cw.desktop_cursor_size(jiggle=False)
    n = n_pack()
    print('  %5.1fs  桌面=%s  指向本包=%d/17  方案名=%r'
          % (time.time() - t0, g[:2], n, scheme_name()[:20]))
    if n == 17 and g[0] == 72:
        ok = True
        break

print('\n结果：%s' % ('✓ 冷启动完整自愈成功' if ok else '✗ 未完全恢复'))
print('  守护 = %s' % (guard.guard_status(),))

print('\n=== 运行日志尾部 ===')
lp = os.path.join(APP, '运行日志.txt')
for ln in open(lp, encoding='utf-8').read().strip().split('\n')[-8:]:
    print('  ' + ln)
