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
        os.path.join(APP_DIR, 'cursors', 'art.bin'),
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
        os.path.join(APP_DIR, 'cursors', 'fx.bin'),
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
        os.path.join(APP_DIR, 'cursors'),
        os.path.join(BUNDLE_DIR, 'cursors'),
        os.path.join(os.path.dirname(here), 'cursors'),
    ]
    if is_frozen():
        cands.append(os.path.join(os.path.dirname(APP_DIR), 'cursors'))
    for p in cands:
        if os.path.isdir(p):
            return p
    return None
STATE = os.path.join(APP_DIR, 'settings.json')


# ---------------------------------------------------------------- 用户数据
USER_DIR = os.path.join(APP_DIR, 'userdata')
"""运行时生成的东西都放这里：日志、守护状态、鼠标参数备份。

放 APP_DIR 根下的话，用户看到的就是「一堆 txt/json 混在说明文档中间」。
设置.json 不搬 —— 它是**用户会去手动编辑的配置**，留在根目录更好找，
发布包里也是按根目录放的。
"""

RUN_LOG = os.path.join(USER_DIR, 'run.log')
ERR_LOG = os.path.join(USER_DIR, 'error.log')
GUARD_STATUS = os.path.join(USER_DIR, 'guard_status.txt')
BACKUP_CUR = os.path.join(USER_DIR, 'mouse_backup_current.json')


def backup_path(stamp):
    """鼠标参数备份文件（stamp 形如 20261020_1838）。"""
    return os.path.join(USER_DIR, 'mouse_backup_%s.json' % stamp)


def ensure_user_dir():
    try:
        os.makedirs(USER_DIR, exist_ok=True)
    except OSError:
        pass
    return USER_DIR


_LEGACY_DIRS = (
    # (旧名, 新名) —— v3 把目录名全改成英文
    ('用户数据', 'userdata'),
    ('指针', 'cursors'),
    ('源码', 'src'),
)

# 旧文件名 -> 新文件名。前 4 条是「根目录平铺 -> userdata」的 v2 迁移，
# 后几条是 v3 的中文名 -> 英文名。两类都在这儿做，顺序无关（幂等）。
_LEGACY_FILES = (
    ('设置.json', 'settings.json'),
    ('运行日志.txt', 'run.log'),
    ('错误日志.txt', 'error.log'),
    ('守护状态.txt', 'guard_status.txt'),
    ('鼠标参数备份_当前.json', 'mouse_backup_current.json'),
    ('明日方舟鼠标.exe', 'ArknightsMouse.exe'),
)

# 旧备份文件名前缀（带日期的那种）
_LEGACY_BACKUP_PREFIX = '鼠标参数备份_'
_BACKUP_PREFIX = 'mouse_backup_'


def _try_rename(old, new):
    """old 存在且 new 不存在时才改名；任何异常都吞掉。"""
    if not os.path.exists(old) or os.path.exists(new):
        return False
    try:
        os.makedirs(os.path.dirname(new) or '.', exist_ok=True)
        os.replace(old, new)
        return True
    except OSError:
        return False


def _migrate_legacy():
    """把旧版的中文目录名/文件名改成英文（幂等，可反复跑）。

    为什么不做全局替换、只做「目标不存在才搬」：
      升级时新旧两套可能同时存在（比如用户手动复制过），此时**宁可不搬**，
      也不能把新数据覆盖掉。而且搬不动（文件被占用、只读目录）也必须让程序
      能起来 —— 目录名是工程整洁问题，不该拿启动成功率去换。
    """
    # 1) 目录
    for old_n, new_n in _LEGACY_DIRS:
        _try_rename(os.path.join(APP_DIR, old_n), os.path.join(APP_DIR, new_n))

    # 2) userdata 目录里的中文文件名（在目录改名之后做，路径已是新目录）
    for old_n, new_n in _LEGACY_FILES[1:5]:
        _try_rename(os.path.join(USER_DIR, old_n),
                    os.path.join(USER_DIR, new_n))

    # 3) 根目录的中文文件名（设置.json / 旧 exe）
    for old_n, new_n in (('设置.json', 'settings.json'),
                         ('明日方舟鼠标.exe', 'ArknightsMouse.exe')):
        _try_rename(os.path.join(APP_DIR, old_n),
                    os.path.join(APP_DIR, new_n))

    # 4) 旧的 v2 平铺生成物 -> userdata（再补一次，兼容从更老的版本直接升上来）
    ensure_user_dir()
    for old_n, new_n in _LEGACY_FILES[1:5]:
        _try_rename(os.path.join(APP_DIR, old_n),
                    os.path.join(USER_DIR, new_n))

    # 5) 带日期的备份：鼠标参数备份_<stamp>.json -> mouse_backup_<stamp>.json
    try:
        for n in os.listdir(USER_DIR):
            if not n.startswith(_LEGACY_BACKUP_PREFIX):
                continue
            stamp = n[len(_LEGACY_BACKUP_PREFIX):]
            if stamp == '当前.json':
                continue
            _try_rename(os.path.join(USER_DIR, n),
                        os.path.join(USER_DIR, _BACKUP_PREFIX + stamp))
    except OSError:
        pass


_migrate_legacy()


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
