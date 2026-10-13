# -*- coding: utf-8 -*-
"""打包 exe：把 arkmouse 源码 + art.bin 打成一个自包含的 Windows 可执行文件。

用法： python 构建\build_exe.py
产物： 构建\dist\<名字>.exe
"""
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))          # ...\Mouse\构建
ROOT = os.path.dirname(HERE)                               # ...\Mouse
SRC = os.path.join(ROOT, '源码', 'arkmouse')
ENTRY = os.path.join(SRC, 'main.pyw')
ART = os.path.join(SRC, 'art.bin')
FX = os.path.join(SRC, 'fx.bin')          # PRTS 移植层：① 点击原帧 / ② 爪子 / ③ 待机
ICON = os.path.join(HERE, 'app.ico')
NAME = '明日方舟鼠标'
WORK = os.path.join(HERE, '_work')
DIST = os.path.join(HERE, 'dist')

for p in (ENTRY, ART, FX, ICON):
    if not os.path.isfile(p):
        sys.exit('缺少文件：%s' % p)

if os.path.isdir(WORK):
    shutil.rmtree(WORK, ignore_errors=True)

cmd = [
    sys.executable, '-m', 'PyInstaller',
    '--noconfirm', '--clean',
    '--onefile',
    '--windowed',                      # 不弹控制台
    '--name', NAME,
    '--icon', ICON,
    '--add-data', '%s;.' % ART,        # art.bin -> _MEIPASS 根
    '--add-data', '%s;.' % FX,         # fx.bin  -> _MEIPASS 根（PRTS 三项效果靠它）
    '--distpath', DIST,
    '--workpath', WORK,
    '--specpath', WORK,
    '--paths', SRC,
    '--hidden-import', 'PIL._tkinter_finder',
    '--exclude-module', 'numpy',
    '--exclude-module', 'matplotlib',
    '--exclude-module', 'scipy',
    '--exclude-module', 'pytest',
    ENTRY,
]
print(' '.join('"%s"' % c if ' ' in c else c for c in cmd))
print('-' * 70)
r = subprocess.run(cmd, cwd=HERE)
print('-' * 70)
exe = os.path.join(DIST, NAME + '.exe')
if r.returncode == 0 and os.path.isfile(exe):
    print('OK  %s  %.2f MB' % (exe, os.path.getsize(exe) / 1048576.0))
else:
    print('FAILED  returncode=%s' % r.returncode)
    sys.exit(r.returncode or 1)
