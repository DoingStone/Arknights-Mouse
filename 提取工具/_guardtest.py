# -*- coding: utf-8 -*-
"""守护进程端到端验收（问题 1/2/3 的核心）。

流程：
  1. 抹掉内存光标（模拟「重启后被系统重置」）
  2. 启动 --guard（模拟开机自启）
  3. 采样：应变成 115px
  4. 【关键】再次调 SPI_SETCURSORS 抹掉内存光标（模拟 explorer 重启/锁屏解锁）
  5. 等待守护的轮询周期，采样：应自动恢复 115px
  6. 改 设置.json 的 scale，验证守护能跟随
  7. 停止守护，还原
"""
import ctypes
import json
import os
import subprocess
import sys
import time

APP = r'E:\Qianmory\Desktop\Mouse'
SRC = os.path.join(APP, '源码', 'arkmouse')
sys.path.insert(0, SRC)
import cursorwin as cw      # noqa: E402
import guard as gd          # noqa: E402

u32 = ctypes.WinDLL('user32', use_last_error=True)
u32.SystemParametersInfoW.argtypes = [ctypes.c_ulong, ctypes.c_ulong,
                                      ctypes.c_void_p, ctypes.c_ulong]
u32.SystemParametersInfoW.restype = ctypes.c_long

STATE = os.path.join(APP, '设置.json')
EXE = os.path.join(APP, '明日方舟鼠标.exe')
PYW = os.path.join(os.environ['LOCALAPPDATA'], 'Programs', 'Python',
                   'Python311', 'pythonw.exe')
MAIN = os.path.join(SRC, 'main.pyw')
MODE = os.environ.get('GUARD_MODE', 'src')


def launch(args):
    if MODE == 'exe':
        return subprocess.Popen([EXE] + args, cwd=APP,
                                creationflags=0x00000008)
    return subprocess.Popen([PYW, MAIN] + args, cwd=APP,
                            creationflags=0x00000008)


def sample(n=1, gap=0.4):
    out = []
    for _ in range(n):
        time.sleep(gap)
        v = cw.desktop_cursor_size()
        out.append(v[0] if isinstance(v, (tuple, list)) else v)
    return out


def nuke_cursors():
    """抹掉内存光标：SPI_SETCURSORS 会让系统从注册表方案重载。"""
    u32.SystemParametersInfoW(0x0057, 0, None, 0x01 | 0x02)


print('=' * 62)
print(' 守护进程端到端验收  (MODE=%s)' % MODE)
print('=' * 62)

saved = json.load(open(STATE, encoding='utf-8'))
saved_scale = saved.get('scale', 1.20)
print('设置.json scale = %s' % saved_scale)

# ---------- 1. 抹掉内存光标 ----------
print('\n[1] 抹掉内存光标')
nuke_cursors()
time.sleep(1.0)
print('    抹掉后 = %s' % sample(2))

# ---------- 2. 启动守护 ----------
print('\n[2] 启动守护（模拟开机自启）')
if gd.guard_status()[0]:
    gd.kill_guard(gd.guard_status()[1])
    time.sleep(1.0)
proc = launch(['--guard'])
print('    已启动 pid=%d' % proc.pid)
time.sleep(6.0)

alive, pid, size, scale = gd.guard_status()
print('    guard_status: alive=%s pid=%d size=%d scale=%.3f'
      % (alive, pid, size, scale))
step2 = sample(3)
print('    启动后 = %s' % step2)
ok2 = all(v == size for v in step2) if size else False

# ---------- 3. 抹掉内存光标，看守护能否自愈 ----------
print('\n[3] 【关键】抹掉内存光标（模拟 explorer 重启/锁屏解锁）')
nuke_cursors()
time.sleep(0.8)
gone = sample(2, gap=0.3)
print('    抹掉后立刻 = %s' % gone)
print('    等待守护轮询自愈（POLL=%ss, MISS=%d）...' % (gd.POLL, gd.MISS))
healed = sample(8, gap=1.0)
print('    自愈过程 = %s' % healed)
ok3 = any(v == size for v in healed) if size else False

# ---------- 4. 守护是否跟随 设置.json ----------
print('\n[4] 改 设置.json（1.20 -> 1.00），守护应跟随')
ok4 = False
try:
    d = json.load(open(STATE, encoding='utf-8'))
    d['scale'] = 1.00
    json.dump(d, open(STATE, 'w', encoding='utf-8'), ensure_ascii=False,
              indent=2)
    time.sleep(7.0)
    step4 = sample(3)
    print('    scale=1.00 后 = %s（期望 96）' % step4)
    ok4 = any(v == 96 for v in step4)
finally:
    d = json.load(open(STATE, encoding='utf-8'))
    d['scale'] = saved_scale
    json.dump(d, open(STATE, 'w', encoding='utf-8'), ensure_ascii=False,
              indent=2)
    time.sleep(7.0)

# ---------- 5. 收尾 ----------
print('\n[5] 停止守护 + 复核')
gd.kill_guard(gd.guard_status()[1])
time.sleep(1.0)
print('    守护 alive = %s' % gd.guard_status()[0])

print('\n' + '=' * 62)
print(' 结论')
print('=' * 62)
print('  [2] 守护启动即下发到 %dpx ......... %s' % (size, '通过' if ok2 else '失败'))
print('  [3] 被抹掉后自动恢复 ............... %s' % ('通过' if ok3 else '失败'))
print('  [4] 跟随 设置.json 改尺寸 .......... %s' % ('通过' if ok4 else '失败'))
print('  运行日志尾部：')
rl = os.path.join(APP, '运行日志.txt')
if os.path.exists(rl):
    lines = open(rl, encoding='utf-8', errors='replace').read().splitlines()
    for ln in lines[-12:]:
        print('    | %s' % ln)
