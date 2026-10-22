# -*- coding: utf-8 -*-
"""鼠标相关参数的读写（速度 / 加速 / 双击 / 滚轮 / 轨迹 / 左右键 / 吸附 /
打字时隐藏 / 指针阴影 / 点击锁定），以及一键备份与还原。

读写策略（每条都经本机实测验证，详见各函数注释）：
  * SystemParametersInfoW 只对【指针速度 mouse_speed 0x0071】真正生效；
    轨迹 0x005D / 悬停 0x0067 / 滚轮 0x0069 的 set 会返回 1 但读回值纹丝不动。
  * 那三项的真正落点是注册表 + 广播 WM_SETTINGCHANGE。
  * 布尔类 SPI 的 pvParam 约定不统一：vanish/shadow/lock 要传值，
    swap/snap 在本机三条路径全无效（见 BOOL_SPI_UNSUPPORTED）。
  * 注册表里除 ActiveWindowTracking 是 DWORD 外，其余都是 REG_SZ 字符串 ——
    写回时必须保持 REG_SZ，否则某些系统组件回读会类型不符。
  * 读数一律以注册表为准（SPI GET 与注册表可能脱钩，比如 MouseHoverTime）。
"""
import ctypes
import json
import os
import time
import winreg
from ctypes import wintypes

u32 = ctypes.WinDLL('user32', use_last_error=True)

u32.SystemParametersInfoW.argtypes = [wintypes.UINT, wintypes.UINT,
                                      ctypes.c_void_p, wintypes.UINT]
u32.SystemParametersInfoW.restype = wintypes.BOOL
u32.GetDoubleClickTime.argtypes = []
u32.GetDoubleClickTime.restype = wintypes.UINT
u32.SetDoubleClickTime.argtypes = [wintypes.UINT]
u32.SetDoubleClickTime.restype = wintypes.BOOL

SPIF_UPDATEINIFILE, SPIF_SENDCHANGE = 0x01, 0x02
SPI_FLAGS = SPIF_UPDATEINIFILE | SPIF_SENDCHANGE

SPI = {
    'mouse_accel':        (0x0003, 0x0004),   # int[3]: 阈值1 阈值2 加速
    'swap_buttons':       (0x0020, 0x0021),
    'wheel_lines':        (0x0068, 0x0069),
    'wheel_chars':        (0x006C, 0x006D),
    'mouse_trails':       (0x005E, 0x005D),
    'snap_to_default':    (0x005F, 0x0060),
    'hover_width':        (0x0062, 0x0063),
    'hover_height':       (0x0064, 0x0065),
    'hover_time':         (0x0066, 0x0067),
    'mouse_speed':        (0x0070, 0x0071),
    'cursor_shadow':      (0x101A, 0x101B),
    'click_lock':         (0x101E, 0x101F),
    'mouse_vanish':       (0x1020, 0x1021),
    'click_lock_time':    (0x2008, 0x2009),
    'active_wnd_track':   (0x1000, 0x1001),
}

REG_MOUSE = r'Control Panel\Mouse'
# Win10 1703 起，滚轮行数的注册表落点搬到了 Desktop 键（Mouse 键下已不再有该项）
REG_DESKTOP = r'Control Panel\Desktop'
WHEEL_KEYS = ('WheelScrollLines', 'WheelScrollChars', 'MouseWheelRouting')
# 本机实测【无法写入】的布尔开关（SPI 传值 / SPI 传址 / 写注册表+广播 三条路径全无效，
# GetSystemMetrics(SM_SWAPBUTTON=23) 也恒为 0）。界面据此标注「本机不支持」。
BOOL_SPI_UNSUPPORTED = ('swap_buttons', 'snap_to_default')
# ⚠ 最隐蔽的一个坑：这几项 SPI 的标量放在 **uiParam（第 2 参）**，不是 pvParam（第 3 参）。
#   放错位置时 SystemParametersInfoW 照样返回 1，但值纹丝不动 —— 看起来像「API 无效」。
#   实测对照（set 同一个目标值，看哪个能改）：
#     鼠标轨迹 0x005D   pvParam=5 → 读回 0 ✗   ｜ uiParam=5, pv=0 → 读回 5 ✓（连注册表也写了）
#     悬停时间 0x0067   pvParam=777 → 读回 10 ✗ ｜ uiParam=777, pv=0 → 读回 777 ✓
#     滚轮行数 0x0069   pvParam=9 → 读回 0 ✗   ｜ uiParam=9, pv=0 → 读回 9 ✓
#   这与 MSDN 一致：SPI_SETMOUSETRAILS / SPI_SETHOVERTIME / SPI_SETWHEELSCROLLLINES
#   都写明取值在 uiParam。反之 SPI_SETMOUSESPEED(0x0071) 用的是 pvParam。
SPI_UI_PARAM = ('mouse_trails', 'hover_time', 'wheel_lines')
MOUSE_STR_VALUES = ('MouseSensitivity', 'MouseSpeed', 'MouseThreshold1',
                    'MouseThreshold2', 'DoubleClickSpeed', 'MouseTrails',
                    'SwapMouseButtons', 'SnapToDefaultButton',
                    'WheelScrollLines', 'MouseHoverTime', 'MouseHoverWidth',
                    'MouseHoverHeight', 'Beep', 'ExtendedSounds')


# ---------------------------------------------------------------- SPI 基础
def spi_get_int(what, default=None):
    v = ctypes.c_int(0)
    get = SPI[what][0]
    if u32.SystemParametersInfoW(get, 0, ctypes.byref(v), 0):
        return int(v.value)
    return default


def spi_set_int(what, value, broadcast=True):
    """写整数类 SPI。

    ⚠ 传参位置不统一（本机实测，见 SPI_UI_PARAM 的注释）：
      * mouse_speed 0x0071 —— 值放 pvParam（第 3 参），byref 或传值都行；
      * mouse_trails 0x005D / hover_time 0x0067 / wheel_lines 0x0069 ——
        值必须放 **uiParam（第 2 参）**、pvParam 传 0。
      放错位置不会报错，只会静默失效（返回 1 但值不变）。

    ⚠ 性能：broadcast=False 只写盘不广播（flags=0x01），实测 0.0 ms；
    广播（flags=0x03）要 404 ms —— 因为它同步通知所有顶层窗口。
    拖动滑杆时用 broadcast=False，松手后再补一次 broadcast=True。
    """
    setc = SPI[what][1]
    flags = SPI_FLAGS if broadcast else SPIF_UPDATEINIFILE
    if what in SPI_UI_PARAM:
        return bool(u32.SystemParametersInfoW(
            setc, int(value), 0, flags))
    # 其余项的值放 pvParam，而且是【直接传值】——传 byref 指针会被拒绝（ret=0）。
    return bool(u32.SystemParametersInfoW(
        setc, 0, int(value), flags))


def spi_get_bool(what, default=None):
    v = ctypes.c_int(0)
    get = SPI[what][0]
    if u32.SystemParametersInfoW(get, 0, ctypes.byref(v), 0):
        return bool(v.value)
    return default


def spi_set_bool(what, value):
    """布尔类 SPI 的 pvParam 约定【不一致】，本机实测真值表如下：

        开关                             传值   传址(byref)   传址(c_void_p)
        打字隐藏指针 mouse_vanish         ✓      ✗             ✓
        指针阴影     cursor_shadow        ✓      ✗             ✓
        点击锁定     click_lock           ✓      ✗             ✓
        左右键互换   swap_buttons         ✗      ✗             ✗
        吸附默认按钮 snap_to_default      ✗      ✗             ✗

    所以：前三个必须【传值】；后两个在本机三条路径（SPI 传值 / SPI 传址 /
    写注册表 + 广播）全部无效 —— 与其显示一个假的「成功」，不如老实返回 False，
    由界面标注「本机不支持」。
    """
    if what in BOOL_SPI_UNSUPPORTED:
        return False
    return bool(u32.SystemParametersInfoW(
        SPI[what][1], 0, 1 if value else 0, SPI_FLAGS))


def spi_get_mouse():
    """返回 (阈值1, 阈值2, 加速开关 0/1/2)。"""
    arr = (ctypes.c_int * 3)(0, 0, 0)
    if u32.SystemParametersInfoW(SPI['mouse_accel'][0], 0, ctypes.byref(arr),
                                 0):
        return (int(arr[0]), int(arr[1]), int(arr[2]))
    return None


def spi_set_mouse(t1, t2, accel):
    arr = (ctypes.c_int * 3)(int(t1), int(t2), int(accel))
    return bool(u32.SystemParametersInfoW(SPI['mouse_accel'][1], 0,
                                          ctypes.byref(arr), SPI_FLAGS))


# ---------------------------------------------------------------- 注册表
def reg_get(name, path=REG_MOUSE):
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as k:
            return winreg.QueryValueEx(k, name)
    except OSError:
        return (None, None)


def reg_set(name, value, typ, path=REG_MOUSE):
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path, 0,
                        winreg.KEY_SET_VALUE) as k:
        winreg.SetValueEx(k, name, 0, typ, value)


def reg_set_str(name, value, path=REG_MOUSE):
    """注册表里的字符串项一律按 REG_SZ 写（本机原值就是字符串）。"""
    reg_set(name, str(value), winreg.REG_SZ, path)


# ---------------------------------------------------------------- 滚轮行数
# 实测（本机 Win11）：SPI 0x0068 的 GET 恒返回 0；真正生效的落点是
# HKCU\Control Panel\Desktop\WheelScrollLines（REG_SZ 字符串）。
#
# ⚠ 关键坑（实测 A/B 对照）：写完注册表后【绝不能】再调 SPI 0x0069 ——
#   它会立刻把 Windows 缓存里的旧值冲回注册表，把刚写的值抹掉：
#     写 3 → 回读 3 ；再调 SPI 0x0069 → 回读又变回 0。
#   正确做法 = 写注册表 + 广播 WM_SETTINGCHANGE，让已打开的窗口重读：
#     写 3 → 广播 → 回读 3（且 2 秒后仍是 3）。
def broadcast_setting_change(section=r'Control Panel\Desktop'):
    """广播 WM_SETTINGCHANGE，通知所有窗口某节注册表设置已变。"""
    HWND_BROADCAST = 0xFFFF
    WM_SETTINGCHANGE = 0x001A
    SMTO_ABORTIFHUNG = 0x0002
    res = ctypes.c_ulong()
    try:
        u32.SendMessageTimeoutW(HWND_BROADCAST, WM_SETTINGCHANGE, 0,
                                ctypes.c_wchar_p(section),
                                SMTO_ABORTIFHUNG, 500, ctypes.byref(res))
        return True
    except Exception:
        return False


def get_wheel_lines(default=3):
    v = reg_get('WheelScrollLines', REG_DESKTOP)[0]
    if v is None:
        return spi_get_int('wheel_lines', default)
    try:
        return int(str(v).strip())
    except (ValueError, TypeError):
        return default


def set_wheel_lines(v, verify=True):
    """0 = 一次滚一屏（合法值）；>0 = 每次滚几行。返回是否写入成功。

    走 SPI 0x0069，值必须放 uiParam（见 SPI_UI_PARAM）。用对位置后 SPI 会连
    Desktop 键的 WheelScrollLines 一起写好（实测写 9 → 注册表 '9'）。

    ⚠ 顺序坑：先前用错误传参时，写完注册表再调 SPI 会把缓存里的旧值冲回注册表。
    现在传参正确，SPI 是权威写入路径，不再手动写注册表。

    ⚠ 性能坑（v2 修）：回读校验里的 sleep 让单次调用耗时 0.65 s。而 tk.Scale 的
    command 在拖动时【每一个像素步进】都触发 —— 拖一次滑杆会冻结界面十几秒，
    用户看到的就是「滚轮设置没反应」。所以 verify=False 时立刻返回，校验交给
    GUI 的防抖定时器在停止拖动后做一次。
    """
    n = max(0, min(100, int(v)))
    ok = spi_set_int('wheel_lines', n, broadcast=False)
    if not verify:
        return ok
    time.sleep(0.25)
    return ok and get_wheel_lines(default=-1) == n


def commit_wheel_lines(n):
    """拖动结束后补一次广播（让所有窗口收到 WM_SETTINGCHANGE）并复核。"""
    n = max(0, min(100, int(n)))
    spi_set_int('wheel_lines', n, broadcast=True)
    time.sleep(0.25)
    return get_wheel_lines(default=-1) == n


# ---------------------------------------------------------------- 语义封装
def get_all():
    """读出全部鼠标参数的当前值，返回 dict。"""
    d = {}
    ma = spi_get_mouse()
    if ma:
        d['阈值1'] = ma[0]
        d['阈值2'] = ma[1]
        d['加速'] = ma[2]
    d['鼠标速度'] = spi_get_int('mouse_speed')
    d['滚轮行数'] = get_wheel_lines()
    d['双击速度'] = int(u32.GetDoubleClickTime())
    d['鼠标轨迹'] = spi_get_int('mouse_trails')
    d['左右键互换'] = spi_get_bool('swap_buttons')
    d['吸附到默认按钮'] = spi_get_bool('snap_to_default')
    d['打字时隐藏指针'] = spi_get_bool('mouse_vanish')
    d['指针阴影'] = spi_get_bool('cursor_shadow')
    d['点击锁定'] = spi_get_bool('click_lock')
    d['悬停时间'] = spi_get_int('hover_time')
    if d['悬停时间'] is None:
        ht = reg_get('MouseHoverTime')[0]
        d['悬停时间'] = int(ht) if ht is not None else None
    return d


def set_mouse_speed(v):
    return spi_set_int('mouse_speed', max(1, min(20, int(v))))


def set_double_click(ms, verify=True):
    """双击速度：走 SetDoubleClickTime。实测生效有延迟（约 0.3s），故 sleep 后回读校验。

    注意：注册表的 DoubleClickSpeed 不会跟着变 —— 它在登录时才被读取，
    运行期的改动只存在于内存。所以刷新界面时以 GetDoubleClickTime() 为准。

    verify=False 用于滑杆拖动中（见 set_wheel_lines 的性能坑说明）。
    """
    ms = max(100, min(900, int(ms)))
    u32.SetDoubleClickTime(ms)
    if not verify:
        return True
    time.sleep(0.35)
    return int(u32.GetDoubleClickTime()) == ms


def verify_double_click(ms):
    time.sleep(0.35)
    return int(u32.GetDoubleClickTime()) == max(100, min(900, int(ms)))


def set_mouse_trails(v, verify=True):
    """0 = 关闭；>1 = 轨迹条数（Windows 只接受 0 或 >=2）。

    走 SPI 0x005D，但值必须放 uiParam（见 SPI_UI_PARAM）。用对了位置后
    SPI 会连注册表 MouseTrails 一起写好，不需要手动改注册表。

    verify=False 用于滑杆拖动中（见 set_wheel_lines 的性能坑说明）。
    """
    v = int(v)
    if v == 1:
        v = 2
    v = 0 if v <= 0 else v
    ok = spi_set_int('mouse_trails', v, broadcast=False)
    if not verify:
        return ok
    time.sleep(0.25)
    return ok and spi_get_int('mouse_trails') == v


def commit_mouse_trails(v):
    """拖动结束后补一次广播并复核。"""
    v = int(v)
    if v == 1:
        v = 2
    v = 0 if v <= 0 else v
    spi_set_int('mouse_trails', v, broadcast=True)
    time.sleep(0.25)
    return spi_get_int('mouse_trails') == v


def set_swap_buttons(on):
    return spi_set_bool('swap_buttons', on)


def set_snap_to_default(on):
    return spi_set_bool('snap_to_default', on)


def set_mouse_vanish(on):
    return spi_set_bool('mouse_vanish', on)


def set_cursor_shadow(on):
    return spi_set_bool('cursor_shadow', on)


def set_click_lock(on):
    return spi_set_bool('click_lock', on)


def set_acceleration(t1, t2, accel, sync_registry=True):
    """同时写 SPI 与注册表的阈值/加速项，保证重启后仍是这个值。"""
    ok = spi_set_mouse(t1, t2, accel)
    if sync_registry:
        try:
            reg_set_str('MouseThreshold1', int(t1))
            reg_set_str('MouseThreshold2', int(t2))
            reg_set_str('MouseSpeed', int(accel))
        except OSError:
            pass
    return ok


def set_sensitivity(v):
    """灵敏度 1..20，写注册表 MouseSensitivity 并刷新（SPI 无对应项）。"""
    v = max(1, min(20, int(v)))
    reg_set_str('MouseSensitivity', v)
    # 让系统重新读取：改 SPI_SETMOUSE 会触发重载
    ma = spi_get_mouse()
    if ma:
        spi_set_mouse(ma[0], ma[1], ma[2])
    return True


def set_hover_time(ms, verify=True):
    """悬停时间（毫秒）：走 SPI 0x0067，值必须放 uiParam（见 SPI_UI_PARAM）。

    用对位置后 SPI 会连注册表 MouseHoverTime 一起写好。
    注意 SPI GET 0x0066 是可靠的读法（用对位置后它就同步了）。

    verify=False 用于滑杆拖动中（见 set_wheel_lines 的性能坑说明）。
    """
    ms = max(10, min(10000, int(ms)))
    ok = spi_set_int('hover_time', ms, broadcast=False)
    if not verify:
        return ok
    time.sleep(0.25)
    return ok and spi_get_int('hover_time') == ms


def commit_hover_time(ms):
    """拖动结束后补一次广播并复核。"""
    ms = max(10, min(10000, int(ms)))
    spi_set_int('hover_time', ms, broadcast=True)
    time.sleep(0.25)
    return spi_get_int('hover_time') == ms


# ---------------------------------------------------------------- 备份还原
BACKUP_KEYS = ('MouseSensitivity', 'MouseSpeed', 'MouseThreshold1',
               'MouseThreshold2', 'DoubleClickSpeed', 'MouseTrails',
               'SwapMouseButtons', 'SnapToDefaultButton', 'WheelScrollLines',
               'MouseHoverTime', 'MouseHoverWidth', 'MouseHoverHeight',
               'Beep', 'ExtendedSounds', 'ActiveWindowTracking',
               'SmoothMouseXCurve', 'SmoothMouseYCurve')


def backup(path):
    """把 HKCU\\Control Panel\\Mouse 整键 + Desktop 的滚轮项 + 关键 SPI 值存成 json。"""
    vals = {}
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_MOUSE) as k:
            n = winreg.QueryInfoKey(k)[1]
            for i in range(n):
                name, data, typ = winreg.EnumValue(k, i)
                if isinstance(data, bytes):
                    data = [int(b) for b in data]
                vals[name] = {'v': data, 't': int(typ)}
    except OSError:
        pass
    # 滚轮项住在 Desktop 键（见文件上方说明），单独备份，只存存在的项
    dvals = {}
    for name in WHEEL_KEYS:
        v, t = reg_get(name, REG_DESKTOP)
        if v is not None:
            dvals[name] = {'v': v, 't': int(t)}
    doc = {
        'registry': vals,
        'desktop': dvals,
        'spi': {
            'mouse_accel': spi_get_mouse(),
            'mouse_speed': spi_get_int('mouse_speed'),
            'wheel_lines': get_wheel_lines(),
            'double_click': int(u32.GetDoubleClickTime()),
            'mouse_trails': spi_get_int('mouse_trails'),
            'swap_buttons': spi_get_bool('swap_buttons'),
            'snap_to_default': spi_get_bool('snap_to_default'),
            'mouse_vanish': spi_get_bool('mouse_vanish'),
            'cursor_shadow': spi_get_bool('cursor_shadow'),
            'click_lock': spi_get_bool('click_lock'),
        },
    }
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    return doc


def restore(path):
    """从备份 json 还原（注册表原样写回，再按 SPI 重设一遍）。"""
    with open(path, 'r', encoding='utf-8') as f:
        doc = json.load(f)
    n = 0
    for name, item in doc.get('registry', {}).items():
        v, t = item['v'], item['t']
        if t == winreg.REG_BINARY and isinstance(v, list):
            v = bytes(v)
        try:
            reg_set(name, v, t)
            n += 1
        except OSError:
            pass
    s = doc.get('spi', {})
    # Desktop 键的滚轮项（老备份没有这一节，用 .get 保证兼容）
    for name, item in doc.get('desktop', {}).items():
        try:
            reg_set(name, item['v'], item['t'], REG_DESKTOP)
            n += 1
        except OSError:
            pass
    if s.get('mouse_accel'):
        spi_set_mouse(*s['mouse_accel'])
    if s.get('mouse_speed') is not None:
        spi_set_int('mouse_speed', s['mouse_speed'])
    if s.get('wheel_lines') is not None:
        set_wheel_lines(s['wheel_lines'])
    if s.get('double_click'):
        u32.SetDoubleClickTime(s['double_click'])
    if s.get('mouse_trails') is not None:
        spi_set_int('mouse_trails', s['mouse_trails'])
    for key, what in (('swap_buttons', 'swap_buttons'),
                      ('snap_to_default', 'snap_to_default'),
                      ('mouse_vanish', 'mouse_vanish'),
                      ('cursor_shadow', 'cursor_shadow'),
                      ('click_lock', 'click_lock')):
        if s.get(key) is not None:
            spi_set_bool(what, s[key])
    return n


def open_system_mouse_panel():
    """打开 Windows 自带的鼠标设置面板（做对照用）。"""
    try:
        ctypes.windll.shell32.ShellExecuteW(
            None, 'open', 'main.cpl', None, None, 1)
        return True
    except Exception:
        return False


def probe():
    """自检：逐项读写一遍，报告哪些项在本机可用。"""
    out = []
    for what in sorted(SPI.keys()):
        g = SPI[what][0]
        v = ctypes.c_int(-999)
        ok = bool(u32.SystemParametersInfoW(g, 0, ctypes.byref(v), 0))
        out.append((what, hex(g), ok, int(v.value) if ok else None))
    return out
