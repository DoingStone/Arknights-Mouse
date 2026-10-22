# -*- coding: utf-8 -*-
"""设置持久化：指针尺寸 / 动画 / 开机自启 / 窗口位置。

默认文件是 exe（或源码根）旁边的「设置.json」。
"""
import json
import os
import sys
import winreg

import paths

REG_RUN = r'Software\Microsoft\Windows\CurrentVersion\Run'
AUTORUN_NAME = 'ArknightsMouse'

DEFAULTS = {
    'scale': 1.20,        # 实测标定：等于游戏内「鼠标指针比例设置 0.75」
    'animate': True,
    'autostart': False,
    'geometry': '',
    # UI 主题：'dark' 深色 PRTS 操作台（默认，历史观感）| 'light' 浅色档案台
    'theme': 'dark',
    # ---- 点击缩放 / 拖动爪子 / 待机（cursorwin.CursorAnim 读这些键）----
    # 点击挤压有两套风格（cursorwin.CLICK_STYLES）：
    #   prts（默认）= 用 fx.bin 里 PRTS 自己的 hand_<role>_NNN 原帧（逐帧烘死的
    #                 非均匀挤压，不缩放），只有 Arrow/Help/Hand/Pin/Person 有。
    #   game        = 游戏原版规格，0.75 / 1.25 取自 PCMouseHandler 的
    #                 MIN_SIZE / MAX_SIZE，映射 scale = 0.75 + 0.5·t。
    'click_anim': True,     # ① 点击挤压
    'click_style': 'prts',  # 'prts' | 'game'
    'drag_claw': True,      # ② PRTS 拖动爪子（SetWinEventHook 装不上时自动静默关闭）
    'idle_prts': True,      # ③ PRTS 待机帧动画（342 帧独立美术）
    'idle_start_ms': 5000,  # 静止多久后开始待机动画（PRTS 侧默认 5 秒）
    'min_scale': 0.90,     # game 风格缩放下限（用户要求约缩 10%）
    'max_scale': 1.10,     # game 风格缩放上限
    'down_ms': 90,         # game 风格按下段时长（曲线未取到，见 cursorwin 段注释）
    'up_ms': 190,          # game 风格抬起回弹段时长（同上）
    'tick_ms': 8,          # 键态采样间隔
    'rung_max': 25,        # 尺寸阶梯最多分几档
}

# 交给 cursorwin.fx_options() 的键。engine.build(..., fx=...) 拿到非空 dict
# 才启用效果并铺尺寸阶梯；传 None 就只有一套静态指针。
FX_KEYS = ('click_anim', 'click_style', 'drag_claw', 'idle_prts', 'idle_start_ms',
           'min_scale', 'max_scale', 'down_ms', 'up_ms',
           'tick_ms', 'rung_max')


def fx_settings(d=None):
    """从设置字典里取出 FX 那一段，交给 cursorwin.fx_options() 用。"""
    src = load() if d is None else d
    return dict((k, src.get(k, DEFAULTS[k])) for k in FX_KEYS)


def load():
    d = dict(DEFAULTS)
    try:
        # utf-8-sig 而不是 utf-8：用记事本改过 设置.json 后文件会带 BOM，
        # json.load 遇到 BOM 直接抛 JSONDecodeError，被下面 except 吞掉后
        # **全部设置静默回落成默认值**（用户表现就是「改了设置不生效/自己变回去」）。
        # utf-8-sig 对有无 BOM 都能读，成本为零。
        with open(paths.STATE, 'r', encoding='utf-8-sig') as f:
            got = json.load(f)
        if isinstance(got, dict):
            d.update(got)
    except Exception:
        pass
    # 开机自启的权威来源是注册表 Run 键（可能被外面手动增删），
    # 所以读设置时以注册表为准，避免文件里显示的和实际不符。
    d['autostart'] = get_autostart()
    return d


def save(d):
    try:
        tmp = paths.STATE + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(d, f, ensure_ascii=False, indent=1)
        os.replace(tmp, paths.STATE)
        return True
    except Exception:
        return False


# ---------------------------------------------------------------- 开机自启
def app_command(scale=None):
    """返回写进 Run 键的完整命令行。

    v2 关键改动：开机自启不再把尺寸写进命令行，而是启动【守护】(--guard)。
    守护自己读「设置.json」作为唯一尺寸来源，并且常驻维护指针不被系统重置。

    为什么必须这么改（问题2 的根因）：
      旧版写的是 `--apply 1.000`，那个数字是「上次勾选开机自启那一刻」的滑杆
      值的快照。用户之后把大小改成 1.20 并只点「应用」，命令行仍是 1.000，
      于是开机按 96px 下发 —— 用户看到的就是「开机后指针还是很小」。
      现在命令行不带任何尺寸，守护每轮都从「设置.json」读，改一次永久生效。

    scale 参数保留只为兼容旧调用点，不再使用。
    """
    # 优先用部署好的 exe：用户平时双击的就是它，自启也该走同一条路。
    # （从源码直接跑时没有 exe，才退回 pythonw + main.pyw。）
    exe = os.path.join(paths.APP_DIR, 'ArknightsMouse.exe')
    if os.path.isfile(exe) and not paths.is_frozen():
        return '"%s" --guard' % os.path.abspath(exe)
    if paths.is_frozen():
        cmd = '"%s"' % os.path.abspath(sys.executable)
    else:
        pyw = _find_pythonw()
        entry = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             'main.pyw')
        cmd = '"%s" "%s"' % (pyw, entry)
    return cmd + ' --guard'


def _find_pythonw():
    exe = sys.executable or 'python.exe'
    d, n = os.path.split(exe)
    pyw = os.path.join(d, 'pythonw.exe')
    return pyw if os.path.isfile(pyw) else exe


def get_autostart():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_RUN) as k:
            winreg.QueryValueEx(k, AUTORUN_NAME)
        return True
    except OSError:
        return False


def set_autostart(on, scale=None):
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_RUN, 0,
                        winreg.KEY_SET_VALUE) as k:
        if on:
            winreg.SetValueEx(k, AUTORUN_NAME, 0, winreg.REG_SZ,
                              app_command(scale))
        else:
            try:
                winreg.DeleteValue(k, AUTORUN_NAME)
            except OSError:
                pass
    return get_autostart()


def fix_autostart_path():
    """Run 键里如果还指着改名前的 exe，就地改成当前命令行（幂等）。

    改名（明日方舟鼠标.exe → ArknightsMouse.exe）不会自动更新注册表，而
    自启项指向一个不存在的文件时，开机是**静默失败**——用户只会觉得「加了
    自启但没生效」，很难自己查出原因。所以启动时顺手修一次。
    """
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_RUN) as k:
            cur, _t = winreg.QueryValueEx(k, AUTORUN_NAME)
    except OSError:
        return False
    cur = str(cur)
    cmd = app_command()
    # 只修「指向的 exe 已经不在了」这种情况，用户自己改过路径的不动
    exe = cur.split('"')[1] if cur.startswith('"') else cur.split(' ')[0]
    if os.path.isfile(exe) or not cmd:
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_RUN, 0,
                            winreg.KEY_SET_VALUE) as k:
            winreg.SetValueEx(k, AUTORUN_NAME, 0, winreg.REG_SZ, cmd)
        return True
    except OSError:
        return False
