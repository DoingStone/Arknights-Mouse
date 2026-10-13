# -*- coding: utf-8 -*-
"""路径解析：开发时用源码目录，打包成 exe 后既支持单文件也支持目录版。"""
import os
import sys


def is_frozen():
    return bool(getattr(sys, 'frozen', False))


def _exe_dir():
    if is_frozen():
        return os.path.dirname(os.path.abspath(sys.executable))
    # 源码模式：.../源码/arkmouse/paths.py -> .../
    return os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))))


def _meipass():
    return getattr(sys, '_MEIPASS', None)


APP_DIR = _exe_dir()
"""exe（或源码根）所在目录 —— 状态文件、用户可改的东西放这里。"""

BUNDLE_DIR = _meipass() or APP_DIR
"""打包进 exe 的只读资源所在目录。"""


def find_art():
    """定位自包含美术包 art.bin。"""
    here = os.path.dirname(os.path.abspath(__file__))
    cands = [
        os.path.join(BUNDLE_DIR, 'art.bin'),
        os.path.join(APP_DIR, 'art.bin'),
        os.path.join(here, 'art.bin'),
        os.path.join(APP_DIR, '指针', 'art.bin'),
        os.path.join(os.path.dirname(APP_DIR), 'art.bin'),
        os.path.join(os.path.dirname(here), 'art.bin'),
    ]
    for p in cands:
        if os.path.isfile(p):
            return p
    return None


def find_fx():
    """定位 PRTS 移植层的美术包 fx.bin（点击原帧 / 拖动爪子 / 待机帧）。

    和 art.bin 一样必须进 exe 的 datas，否则打包版找不到、三项效果会静默关闭
    （prtsfx 里 has() 返回 False，err 会记一句「fx.bin 里没有 …族」）。
    """
    here = os.path.dirname(os.path.abspath(__file__))
    cands = [
        os.path.join(BUNDLE_DIR, 'fx.bin'),
        os.path.join(APP_DIR, 'fx.bin'),
        os.path.join(here, 'fx.bin'),
        os.path.join(APP_DIR, '指针', 'fx.bin'),
        os.path.join(os.path.dirname(here), 'fx.bin'),
    ]
    for p in cands:
        if os.path.isfile(p):
            return p
    return None


def find_pack():
    """定位「指针」目录（含 .cur/.ani 与 install.ps1），没有则返回 None。"""
    here = os.path.dirname(os.path.abspath(__file__))
    cands = [
        os.path.join(APP_DIR, '指针'),
        os.path.join(BUNDLE_DIR, '指针'),
        os.path.join(os.path.dirname(here), '指针'),
    ]
    if is_frozen():
        cands.append(os.path.join(os.path.dirname(APP_DIR), '指针'))
    for p in cands:
        if os.path.isdir(p):
            return p
    return None
STATE = os.path.join(APP_DIR, '设置.json')


def child_env():
    """给「本程序再拉起一个自己」用的子进程环境（守护 ↔ 界面互相拉起都走这里）。

    PyInstaller 单文件模式会把 exe 解包到 %TEMP%\\_MEIxxxxxx，并且把解包目录通过
    环境变量交给子进程；子进程的引导器看到就直接**复用同一个目录**（这是引导器
    自带的省事行为，不是我们写的）。而本程序的两个角色恰好是一方比另一方活得久：

      · 界面 → 守护：关掉界面时守护还在跑，它把 _imaging.cp311-win_amd64.pyd 等
        已加载的模块锁在自己的地址空间里，界面的引导器就删不掉自己的解包目录，
        于是弹「Failed to remove temporary directory: ...\\_MEIxxxxxx」；
      · 守护 → 界面：反过来一模一样。

    把引导器注入的这几个变量剥掉，子进程就会解包到自己独占的目录，两个角色彻底
    解耦：谁退出谁清自己的。按前缀剥而不是按具体名字，是为了跨 PyInstaller 版本
    都成立（旧版叫 _MEIPASS2，新版叫 _PYI_APPLICATION_HOME_DIR）。
    代价是子进程要重新解包一次（约 1~2 秒、约 30 MB 临时空间），换的是不再漏目录。
    """
    env = dict(os.environ)
    for k in list(env):
        if k.startswith('_PYI_') or k.startswith('_MEI'):
            env.pop(k, None)
    return env
