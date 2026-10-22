# -*- coding: utf-8 -*-
"""常驻守护：让指针始终停留在用户设定的样式与大小。

为什么必须要有守护进程
----------------------
`SetSystemCursor` 装进去的是【内存】光标。Windows 会在很多时机从注册表方案
重新加载光标，那一刻内存光标就被抹掉，回落到 `LoadCursorFromFileW` 解析出的
**32×32**（本机实测：任何 .cur 都被解析成 32px，无论里面有几档光栅）。

已实测会触发重载、把光标打回 32px 的动作：
  * `SystemParametersInfo(SPI_SETCURSORS, ...)` —— explorer 启动/重启时就会调
  * 修改「辅助功能 → 鼠标指针大小」(`Accessibility\\CursorSize`)
  * 锁屏 / 切换用户 / 显示设置变化 / 插拔显示器

这就是「开机启动后指针还是很小」「重启后变回原版」的根因：自启程序先跑完
（日志里确实是 115px），随后 explorer 初始化时重载光标，把 115px 冲掉了。

守护策略
--------
1. 事件驱动：监听 `WM_SETTINGCHANGE` / `WM_DISPLAYCHANGE` / `WM_WTSSESSION_CHANGE`
   （会话解锁），一收到就复核。
2. 轮询兜底：每 POLL 秒量一次当前桌面光标尺寸。
3. 尺寸不符连续 MISS 次 → 用 art.bin 重新构造并重新下发。
4. 每轮检查 `设置.json` 的修改时间，用户改了大小不需要重启守护。
5. 托盘图标常驻，用户**看得见它活着**；右键菜单可立即重应用 / 打开界面 /
   开关自启 / 退出守护。
6. 命名互斥体保证只有一个守护实例。
"""
import ctypes
import ctypes.wintypes as wt
import os
import sys
import threading
import time
import winreg

import artpack
import cursorwin as cw
import mousep
import paths
import store

# ---------------------------------------------------------------- 常量
MUTEX_NAME = 'ArknightsMouseGuard_v1'
STATUS_FILE = 'guard_status.txt'
# 方案名不再写死：它由「当前 scale 对应哪一档」决定（见 cw.scheme_display_name）。
# 以前是一个常量 '明日方舟 水晶指针 大 (1.00×)'，结果 scale=0.75 的用户在
# 「鼠标属性 → 方案」里登记的也是 96px 那档 —— 登记的和显示的不是一回事。

WM_APP = 0x8000
WM_TRAY = WM_APP + 1
WM_SETTINGCHANGE = 0x001A
WM_DISPLAYCHANGE = 0x007E
WM_WTSSESSION_CHANGE = 0x02B1
WM_ENDSESSION = 0x0016
WM_CLOSE = 0x0010
WM_DESTROY = 0x0002
WM_COMMAND = 0x0111
WM_NULL = 0x0000
WM_RBUTTONUP = 0x0205
WM_LBUTTONDBLCLK = 0x0203

NIM_ADD, NIM_MODIFY, NIM_DELETE = 0, 1, 2
NIF_MESSAGE, NIF_ICON, NIF_TIP, NIF_INFO = 0x01, 0x02, 0x04, 0x10
NIIF_INFO = 0x00000001

MF_STRING, MF_SEPARATOR, MF_CHECKED = 0x0000, 0x0800, 0x0008
TPM_RIGHTBUTTON, TPM_RETURNCMD = 0x0002, 0x0100

ID_REAPPLY, ID_OPEN, ID_AUTO, ID_EXIT = 1001, 1002, 1003, 1004

WTS_SESSION_UNLOCK = 0x8
NOTIFY_FOR_THIS_SESSION = 0

POLL = 1.5           # 轮询间隔（秒）
MISS = 2             # 连续几次不符才重下发（防误判）
POLL_FAST = 0.4      # 刚重下发后的密集复核窗口
FAST_ROUNDS = 5

u32 = ctypes.WinDLL('user32', use_last_error=True)
k32 = ctypes.WinDLL('kernel32', use_last_error=True)
shell32 = ctypes.WinDLL('shell32', use_last_error=True)

u32.CreateWindowExW.argtypes = [wt.DWORD, wt.LPCWSTR, wt.LPCWSTR, wt.DWORD,
                                ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                ctypes.c_int, wt.HWND, wt.HMENU, wt.HINSTANCE,
                                ctypes.c_void_p]
u32.CreateWindowExW.restype = wt.HWND
u32.RegisterClassW.argtypes = [ctypes.c_void_p]
u32.RegisterClassW.restype = wt.ATOM
u32.DestroyWindow.argtypes = [wt.HWND]
u32.PostQuitMessage.argtypes = [ctypes.c_int]
u32.DefWindowProcW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
u32.DefWindowProcW.restype = ctypes.c_long
u32.LoadIconW.argtypes = [wt.HINSTANCE, wt.LPCWSTR]
u32.LoadIconW.restype = wt.HICON
u32.CreatePopupMenu.restype = wt.HMENU
u32.AppendMenuW.argtypes = [wt.HMENU, wt.UINT, ctypes.c_size_t, wt.LPCWSTR]
u32.DestroyMenu.argtypes = [wt.HMENU]
u32.TrackPopupMenu.argtypes = [wt.HMENU, wt.UINT, ctypes.c_int, ctypes.c_int,
                               ctypes.c_int, wt.HWND, ctypes.c_void_p]
u32.TrackPopupMenu.restype = wt.BOOL
u32.GetCursorPos.argtypes = [ctypes.c_void_p]
u32.PostMessageW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
u32.SetForegroundWindow.argtypes = [wt.HWND]
u32.RegisterWindowMessageW.argtypes = [wt.LPCWSTR]
u32.RegisterWindowMessageW.restype = wt.UINT
k32.GetModuleHandleW.argtypes = [wt.LPCWSTR]
k32.GetModuleHandleW.restype = wt.HMODULE
k32.CreateMutexW.argtypes = [ctypes.c_void_p, wt.BOOL, wt.LPCWSTR]
k32.CreateMutexW.restype = wt.HANDLE
k32.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
k32.OpenProcess.restype = wt.HANDLE
k32.TerminateProcess.argtypes = [wt.HANDLE, wt.UINT]
k32.GetExitCodeProcess.argtypes = [wt.HANDLE, ctypes.c_void_p]
k32.CloseHandle.argtypes = [wt.HANDLE]
shell32.Shell_NotifyIconW.argtypes = [wt.DWORD, ctypes.c_void_p]
shell32.Shell_NotifyIconW.restype = wt.BOOL
shell32.ExtractIconW.argtypes = [wt.HINSTANCE, wt.LPCWSTR, wt.UINT]
shell32.ExtractIconW.restype = wt.HICON


class NOTIFYICONDATA(ctypes.Structure):
    _fields_ = [('cbSize', wt.DWORD), ('hWnd', wt.HWND), ('uID', wt.UINT),
                ('uFlags', wt.UINT), ('uCallbackMessage', wt.UINT),
                ('hIcon', wt.HICON), ('szTip', wt.WCHAR * 128),
                ('dwState', wt.DWORD), ('dwStateMask', wt.DWORD),
                ('szInfo', wt.WCHAR * 256), ('uVersion', wt.UINT),
                ('szInfoTitle', wt.WCHAR * 64), ('dwInfoFlags', wt.DWORD)]


class WNDCLASS(ctypes.Structure):
    _fields_ = [('style', wt.UINT), ('lpfnWndProc', ctypes.c_void_p),
                ('cbClsExtra', ctypes.c_int), ('cbWndExtra', ctypes.c_int),
                ('hInstance', wt.HINSTANCE), ('hIcon', wt.HICON),
                ('hCursor', wt.HANDLE), ('hbrBackground', wt.HBRUSH),
                ('lpszMenuName', wt.LPCWSTR), ('lpszClassName', wt.LPCWSTR)]


WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_long, wt.HWND, wt.UINT,
                             wt.WPARAM, wt.LPARAM)


def log(msg):
    """写 运行日志.txt（追加，带时间戳）。"""
    try:
        p = paths.RUN_LOG
        with open(p, 'a', encoding='utf-8') as f:
            f.write('[%s] %s\n' % (time.strftime('%Y-%m-%d %H:%M:%S'), msg))
    except Exception:
        pass


# ================================================================ 守护核心
class Guard(object):
    def __init__(self):
        self.pack = None
        self.eng = cw.Engine()
        self.scale = float(store.load().get('scale', 1.20))
        self.state_mtime = self._mtime()
        self.applied = None          # 已下发的像素尺寸
        self.misses = 0
        self.fast = 0
        self.running = True
        self.hwnd = None
        self.nid = None
        self.ticks = 0
        self._scheme = None          # 角色 -> 本包文件绝对路径（缓存）
        self._tier = None            # 当前 scale 对应的指针档位（缓存）
        self._fx = store.fx_settings()   # 已下发的点击缩放/待机呼吸参数快照
        self._anim = bool(store.load().get('animate', True))

    # ---- 设置.json 变化侦测 ----
    def _mtime(self):
        try:
            return os.path.getmtime(paths.STATE)
        except OSError:
            return 0.0

    def _reload_state(self):
        m = self._mtime()
        if m == self.state_mtime:
            return False
        self.state_mtime = m
        d = store.load()
        new = float(d.get('scale', 1.20))
        fx = store.fx_settings(d)
        anim = bool(d.get('animate', True))
        what = None
        if abs(new - self.scale) > 1e-6:
            self.scale = new
            # 档位/方案名都跟着 scale 走，缓存必须一起作废 —— 否则换了档位
            # 还在用旧档的文件清单和旧方案名，「鼠标属性」里登记的就不是
            # 眼前这套了。
            self._tier = None
            self._scheme = None
            what = '档位改为 %.3f×（%dpx）' % (new, int(round(cw.NATIVE * new)))
        elif fx != self._fx:
            what = '点击缩放/待机呼吸参数变化'
        elif anim != self._anim:
            what = '待机动画开关变化'
        if what is None:
            return False
        log('设置.json 变化 → %s' % what)
        return True

    # ---- 下发 ----
    def load_pack(self):
        if self.pack is None:
            ap = paths.find_art()
            if not ap:
                log('找不到 art.bin，守护无法工作')
                return False
            self.pack = artpack.load(ap)
        return True

    def do_apply(self, why=''):
        if not self.load_pack():
            return False
        size = int(round(cw.NATIVE * self.scale))
        try:
            d = store.load()
            fx = store.fx_settings(d)
            n = len(self.eng.build(size, self.pack, fx=fx))
            got = self.eng.apply_all()
            self.applied = size
            self.misses = 0
            self.fast = FAST_ROUNDS
            self._fx = fx
            self._anim = bool(d.get('animate', True))
            log('已下发 %d/%d 个角色 · %dpx（%s）'
                % (got, n, size, why or '守护'))
            if self._anim:
                self.eng.start_anim()
            else:
                self.eng.stop_anim()
            # 点击缩放 / 待机呼吸必须**在 apply_all 之后**启动：
            # start_fx() 只是挂上驱动线程，真正下发由它的 tick 负责。
            self.eng.start_fx(fx)
            # 「鼠标属性 → 指针 → 方案」下拉框里有没有本包，是另一个键
            # （Schemes 子键），顺手补齐。幂等，没事就不写。
            self.register_scheme()
            return True
        except Exception as e:
            log('下发失败：%s' % e)
            return False

    # ---- 注册表方案（问题3 的另一半） ----
    def scheme_tier(self):
        """当前 scale 该用哪一档（返回 PACK_TIERS 里的元组）。

        增益 gain 和 scale 是同一个量：scale 0.75 就是「指针占 96px 画布的
        75%」，也就是 72px 那一档。以前这里写死 'large'，于是 scale=0.75 的
        用户被登记成 96px 档 —— 登记的和眼睛看到的不是一回事。

        理想档位不存在时（用户只留了某几档）按距离往下退，全都没有才返回
        None。默认设置 scale=0.75 → 'p72'，正是现在实际显示的那套。
        """
        if self._tier is not None:
            return self._tier
        pk = paths.find_pack()
        if not pk:
            return None
        for tier in cw.pack_tiers_for(self.scale):
            d = os.path.join(pk, 'cursors', tier[0])
            if all(os.path.isfile(os.path.join(
                    d, 'Arknights_Crystal_%s_%s%s' % (r[0], tier[0], ext)))
                    for r in cw.ROLES for ext in ('.cur', '.ani')):
                self._tier = tier
                return tier
        # 没有哪一档是 17 个角色全齐的，退而求其次：只要目录在就用它
        for tier in cw.pack_tiers_for(self.scale):
            d = os.path.join(pk, 'cursors', tier[0])
            if os.path.isdir(d):
                self._tier = tier
                return tier
        return None

    def scheme_name(self):
        """要注册进「鼠标属性 → 方案」的方案名（跟着当前档位走）。"""
        tier = self.scheme_tier()
        if tier is None:
            return cw.scheme_display_name(cw.PACK_TIERS[-1])
        return cw.scheme_display_name(tier)

    def scheme_files(self):
        """把「指针」里的 17 个文件映射成 角色 -> 绝对路径。"""
        if self._scheme:
            return self._scheme
        pk = paths.find_pack()
        tier = self.scheme_tier()
        if not pk or tier is None:
            return {}
        d = os.path.join(pk, 'cursors', tier[0])
        m = {}
        for r in cw.ROLES:
            key = r[0]
            for ext in ('.cur', '.ani'):
                p = os.path.join(d, 'Arknights_Crystal_%s_%s%s' % (key, tier[0], ext))
                if os.path.isfile(p):
                    m[key] = p
                    break
        self._scheme = m
        return m

    def scheme_blob(self):
        """把 17 个角色路径拼成「方案」（Schemes 子键）要的格式。

        格式是 17 条绝对路径、逗号分隔，顺序固定为 cursorwin.ROLES 的顺序：
        Arrow, Help, AppStarting, Wait, Crosshair, IBeam, NWPen, No,
        SizeNS, SizeWE, SizeNWSE, SizeNESW, SizeAll, UpArrow, Hand,
        Pin, Person。这个顺序是从本机已有的第三方方案条目里反推出来的，
        和 ROLES 逐位对齐（Windows 没有公开这个顺序的文档）。

        少一个角色就整条不写 —— 残缺的方案条目会让 Windows 把缺的那几个
        角色清成空，用户点一下反而把指针弄丢几个。

        分隔符是**纯逗号、不带空格**。写成 ", " 系统也认（解析时会吃掉空格），
        但本机 12 条系统内置方案和已有的第三方方案条目全部是不带空格的写法，
        保持一致；值类型同样用 REG_EXPAND_SZ（路径里没有 %变量% 时与 REG_SZ
        完全等价，纯粹是为了和基准一致）。
        """
        m = self.scheme_files()
        if len(m) < len(cw.ROLES):
            return None
        return ','.join(m[r[0]] for r in cw.ROLES)

    def register_scheme(self):
        """把本包写进「鼠标属性 → 指针 → 方案」的下拉列表（幂等）。

        只写 17 个角色槽位是不够的：那只决定「现在用的是哪套」，而
        「下拉框里有哪些可选方案」是 HKCU\\Control Panel\\Cursors\\Schemes
        子键。缺了这一条，用户在鼠标属性里既看不到本包，也没法在系统把
        方案冲掉之后自己从列表里选回来 —— 只能靠本程序重写。

        顺手把**别的档位**留下的旧条目摘掉：守护会按当前 scale 把方案改回
        来，留着「大 (1.00×)」这类过期条目，用户点了也只会立刻被改回去，
        等于挖了个坑。只删名字能和我们 PACK_TIERS 逐字对上的那些，用户
        自己另存的方案一律不动。

        注意这里**不做** broadcast：写方案条目不会触发系统重载光标，
        不需要（也不应该）惊动正在用的那套。
        """
        blob = self.scheme_blob()
        if not blob:
            return False
        tier = self.scheme_tier()
        name = self.scheme_name()
        stale = [cw.scheme_display_name(t) for t in cw.PACK_TIERS
                 if tier is None or t[0] != tier[0]]
        # 先单独读一次。别想着用后面那个 KEY_SET_VALUE 的手柄读 ——
        # 那个手柄没有查询权限，QueryValueEx 会抛 OSError，被下面的
        # except 吃掉之后就变成「永远重写」，幂等是假的。
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                cw.REG_SCHEMES_PATH) as k:
                if winreg.QueryValueEx(k, name)[0] == blob:
                    return self._prune_schemes(stale, name)
        except OSError:
            pass
        try:
            with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER,
                                    cw.REG_SCHEMES_PATH, 0,
                                    winreg.KEY_SET_VALUE) as k:
                winreg.SetValueEx(k, name, 0, winreg.REG_EXPAND_SZ, blob)
            log('已把本包注册进「鼠标属性 → 方案」：%s' % name)
            self._prune_schemes(stale, name)
            return True
        except Exception as e:
            log('注册方案条目失败：%s' % e)
            return False

    def _prune_schemes(self, stale, keep):
        """删掉本包其它档位留下的过期方案条目（只删名字能对上的）。"""
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                cw.REG_SCHEMES_PATH, 0,
                                winreg.KEY_SET_VALUE) as k:
                for old in stale:
                    if not old or old == keep:
                        continue
                    try:
                        winreg.DeleteValue(k, old)
                        log('清掉过期方案条目：%s' % old)
                    except OSError:
                        pass          # 本来就没有，正常
        except OSError:
            pass

    def scheme_ok(self):
        """注册表里 17 个角色是否都指向本包（拿 Arrow 当探针，够快）。

        系统在某些时机（切换主题、系统「鼠标设置」被打开并保存、
        辅助功能设置变化）会把整份方案改回旧方案，此时内存光标和
        注册表同时被覆盖 —— 只重下发内存光标是不够的。
        """
        m = self.scheme_files()
        probe = m.get('Arrow')
        if not probe:
            return True  # 没有指针就不管
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, cw.REG_CURSORS_PATH) as k:
                cur = winreg.QueryValueEx(k, 'Arrow')[0]
        except OSError:
            return True
        return bool(cur) and cur.lower() == probe.lower()

    def fix_scheme(self):
        """把注册表方案写回本包，并广播，让系统重新加载。"""
        m = self.scheme_files()
        if not m:
            log('找不到指针目录，无法修复注册表方案')
            return False
        try:
            with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER,
                                    cw.REG_CURSORS_PATH, 0,
                                    winreg.KEY_SET_VALUE) as k:
                for key, p in m.items():
                    # 槽位用 REG_EXPAND_SZ：Windows 自己写槽位（HKLM 的
                    # ...\Control Panel\Cursors\Default）和第三方皮肤都是这个
                    # 类型。绝对路径里没有 %变量% 时与 REG_SZ 完全等价。
                    winreg.SetValueEx(k, key, 0, winreg.REG_EXPAND_SZ, p)
                winreg.SetValueEx(k, '', 0, winreg.REG_SZ, self.scheme_name())
            # 槽位修好了，顺手保证「方案下拉框」里也有本包 —— Windows 冲方案
            # 时这两个键会一起丢，只修槽位的话用户还是选不回来。
            self.register_scheme()
            # 广播：让 shell / 应用重新读取方案（会触发系统按方案重载光标，
            # 所以必须在写完注册表之后再重下发一次内存光标）
            mousep.broadcast_setting_change()
            log('注册表方案已被系统改回 → 已重写为本包（%s）' % self.scheme_name())
            return True
        except Exception as e:
            log('重写注册表方案失败：%s' % e)
            return False

    # ---- 复核 ----
    def check(self):
        if self.applied is None:
            # 守护启动时先把注册表方案认回来，再下发内存光标
            if not self.scheme_ok():
                self.fix_scheme()
            return self.do_apply('首次')
        # 注册表方案被改回旧方案 → 先修注册表，再重下发
        if not self.scheme_ok():
            self.fix_scheme()
            return self.do_apply('方案被改回，已修复')
        # ⚠️ 这里**绝对不能**调 desktop_cursor_size()：那个函数为了绕过
        # 「GetCursorInfo 返回悬停窗口自己的光标」必须 SetCursorPos 把鼠标
        # 钉到桌面点上，而本循环每 POLL 秒跑一次 —— 之前就是这样变成
        # 「鼠标每 1.5 秒被拽回左上角」的。
        # 现在用 system_cursor_sizes()：LoadCursorW 直接返回**当前系统
        # 光标**（实测 72px 时 Arrow=(72,72,21,15)），0.05 ms/次、
        # 鼠标零位移、与鼠标位置完全无关。
        cur = cw.system_cursor_sizes()
        if not cur:
            return False        # 一个都读不到，这轮不做判断
        # ⚠️ 判断标准必须是「宽度在不在本引擎认识的那组档位里」，**不能**
        # 拿 base 尺寸去比：启用点击缩放/待机呼吸之后，指针正常就会停在
        # 104（按下）或 112…118（呼吸）这些档上，拿 applied 比会把每一次
        # 呼吸都误判成「被重置」，然后 do_apply() 把效果整个杀掉 —— 表现
        # 就是「指针每隔几秒被自己人重置一次」。
        ok_sizes = set(int(v) for v in self.eng.tier_sizes.values())
        if not ok_sizes:
            ok_sizes = {self.applied}
        bad = [k for k, v in cur.items() if v[0] not in ok_sizes]
        if not bad:
            self.misses = 0
            return False
        # NWPen（手写）没有 SetSystemCursor 接口，采样到它时会偏小，
        # 但它只在触控笔输入时出现，正常悬停不会命中，这里不特殊处理。
        self.misses += 1
        if self.misses >= MISS:
            k = bad[0]
            log('检测到光标被重置：%s 实测 %dx%d，应为 %dpx → 重新下发'
                % (k, cur[k][0], cur[k][1], self.applied))
            return self.do_apply('检测到重置')
        return False

    # ---- 状态文件（给 GUI 读） ----
    def write_status(self):
        try:
            p = paths.GUARD_STATUS
            with open(p, 'w', encoding='utf-8') as f:
                f.write('%d\n%s\n%d\n%s\n' % (
                    os.getpid(), time.strftime('%Y-%m-%d %H:%M:%S'),
                    self.applied or 0, '%.3f' % self.scale))
        except Exception:
            pass

    # ---- 主循环（在后台线程跑复核，主线程跑消息循环） ----
    def worker(self):
        while self.running:
            try:
                if self._reload_state():
                    self.do_apply('设置变化')
                else:
                    self.check()
                self.ticks += 1
                if self.ticks % 5 == 0:
                    self.write_status()
            except Exception as e:
                log('守护循环异常：%s' % e)
            time.sleep(POLL_FAST if self.fast > 0 else POLL)
            if self.fast > 0:
                self.fast -= 1

    def stop(self):
        self.running = False
        try:
            # stop_fx() 必须先于 destroy()：它的收尾要把指针复位到 base 档，
            # 而那份 HCURSOR 马上就会被 destroy() 释放掉。
            self.eng.stop_fx()
            self.eng.stop_anim()
            self.eng.destroy()
        except Exception:
            pass


# ================================================================ 托盘 + 消息循环
def run_tray(g):
    inst = k32.GetModuleHandleW(None)
    # explorer 重启（任务栏重建）时系统会清空所有托盘图标，应用必须收
    # TaskbarCreated 消息自己重新挂回去。以前**从未**处理这条消息，所以
    # 重启 explorer / 资源管理器崩溃恢复之后图标就永久消失，且没有任何日志。
    taskbar_created = u32.RegisterWindowMessageW('TaskbarCreated')

    def add_icon():
        """挂托盘图标。失败要重试并记账 —— 原实现把返回值丢了，失败完全静默。"""
        ic = shell32.ExtractIconW(inst, sys.executable, 0)
        if not ic:
            ic = u32.LoadIconW(None, wt.LPCWSTR(32512))      # IDI_APPLICATION
        nid = NOTIFYICONDATA()
        nid.cbSize = ctypes.sizeof(NOTIFYICONDATA)
        nid.hWnd = g.hwnd
        nid.uID = 1
        nid.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP
        nid.uCallbackMessage = WM_TRAY
        nid.hIcon = ic
        nid.szTip = '明日方舟鼠标 · 指针守护（%dpx）' % (g.applied or 0)
        for _ in range(3):
            if shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(nid)):
                g.nid = nid
                return True
            time.sleep(0.3)
        log('托盘图标注册失败（NIM_ADD 连续 3 次返回 0，err=%s）'
            % ctypes.get_last_error())
        g.nid = nid
        return False

    def on_menu(cmd):
        if cmd == ID_REAPPLY:
            g.do_apply('手动')
            balloon(g, '已重新应用', '%dpx' % (g.applied or 0))
        elif cmd == ID_OPEN:
            spawn_gui()
        elif cmd == ID_AUTO:
            store.set_autostart(not store.get_autostart())
            balloon(g, '开机自启',
                    '已开启' if store.get_autostart() else '已关闭')
        elif cmd == ID_EXIT:
            balloon(g, '已退出守护', '指针不再被自动维护')
            g.stop()
            u32.DestroyWindow(g.hwnd)
            u32.PostQuitMessage(0)

    def wndproc(hwnd, msg, wp, lp):
        if msg == taskbar_created:
            add_icon()               # 任务栏重建后必须重新挂图标
            return 0
        if msg == WM_TRAY:
            if lp == WM_RBUTTONUP:
                u32.SetForegroundWindow(hwnd)
                hm = u32.CreatePopupMenu()
                u32.AppendMenuW(hm, MF_STRING, ID_REAPPLY, '立即重新应用')
                u32.AppendMenuW(hm, MF_STRING, ID_OPEN, '打开设置界面')
                auto = store.get_autostart()
                u32.AppendMenuW(hm, MF_STRING | (MF_CHECKED if auto else 0),
                                ID_AUTO, '开机自动启动')
                u32.AppendMenuW(hm, MF_SEPARATOR, 0, None)
                u32.AppendMenuW(hm, MF_STRING, ID_EXIT, '退出守护')
                pt = wt.POINT()
                u32.GetCursorPos(ctypes.byref(pt))
                cmd = u32.TrackPopupMenu(hm, TPM_RIGHTBUTTON | TPM_RETURNCMD,
                                         pt.x, pt.y, 0, hwnd, None)
                u32.PostMessageW(hwnd, WM_NULL, 0, 0)
                u32.DestroyMenu(hm)
                if cmd:
                    on_menu(cmd)
                return 0
            if lp == WM_LBUTTONDBLCLK:
                spawn_gui()
                return 0
            return 0
        if msg == WM_SETTINGCHANGE or msg == WM_DISPLAYCHANGE:
            g.fast = FAST_ROUNDS
            g.misses = MISS          # 立刻复核，不等累计
            return 0
        if msg == WM_WTSSESSION_CHANGE:
            if wp == WTS_SESSION_UNLOCK:
                g.misses = MISS
            return 0
        if msg == WM_CLOSE:
            u32.DestroyWindow(hwnd)
            return 0
        if msg == WM_DESTROY:
            u32.PostQuitMessage(0)
            return 0
        return u32.DefWindowProcW(hwnd, msg, wp, lp)

    proc = WNDPROC(wndproc)
    wc = WNDCLASS()
    wc.lpfnWndProc = ctypes.cast(proc, ctypes.c_void_p)
    wc.hInstance = inst
    wc.lpszClassName = 'ArknightsMouseGuardWnd'
    u32.RegisterClassW(ctypes.byref(wc))
    hwnd = u32.CreateWindowExW(0, 'ArknightsMouseGuardWnd',
                               'ArknightsMouseGuard', 0, 0, 0, 0, 0,
                               None, None, inst, None)
    if not hwnd:
        log('创建守护窗口失败：%s' % ctypes.WinError(ctypes.get_last_error()))
        return 1
    g.hwnd = hwnd

    # 会话解锁通知
    try:
        wtsapi = ctypes.WinDLL('wtsapi32', use_last_error=True)
        wtsapi.WTSRegisterSessionNotification.argtypes = [wt.HWND, wt.DWORD]
        wtsapi.WTSRegisterSessionNotification(hwnd, NOTIFY_FOR_THIS_SESSION)
    except Exception:
        pass

    # 托盘图标：优先用 exe 自带的图标（add_icon 内含 3 次重试与失败记账）
    add_icon()

    balloon(g, '指针守护已启动',
            '当前 %dpx · 右键查看菜单' % (g.applied or 0))

    msg = wt.MSG()
    while u32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
        u32.TranslateMessage(ctypes.byref(msg))
        u32.DispatchMessageW(ctypes.byref(msg))
    try:
        shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(g.nid))
    except Exception:
        pass
    return 0


def balloon(g, title, text):
    """弹一个托盘气泡 —— 这就是「开机确实启动了」的可见反馈。"""
    try:
        nid = g.nid
        nid.uFlags = NIF_INFO
        nid.szInfo = text
        nid.szInfoTitle = title
        nid.dwInfoFlags = NIIF_INFO
        shell32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(nid))
        nid.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP
    except Exception:
        pass


def update_tip(g):
    try:
        nid = g.nid
        nid.uFlags = NIF_TIP
        nid.szTip = '明日方舟鼠标 · 指针守护（%dpx）' % (g.applied or 0)
        shell32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(nid))
        nid.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP
    except Exception:
        pass


def spawn_gui():
    import subprocess
    if getattr(sys, 'frozen', False):
        cmd = [sys.executable]
    else:
        cmd = [sys.executable, os.path.join(paths.APP_DIR, 'src', 'arkmouse',
                                            'main.pyw')]
    try:
        # 同 main.do_start_guard：剥掉 PyInstaller 的解包目录变量，别让界面复用
        # 守护的 _MEIxxxxxx，否则守护退出时删不掉自己的临时目录。
        subprocess.Popen(cmd, cwd=paths.APP_DIR, env=paths.child_env(),
                         creationflags=0x00000008)   # DETACHED_PROCESS
    except Exception as e:
        log('打开界面失败：%s' % e)


# ================================================================ 状态查询（给 GUI）
def guard_status():
    """读 守护状态.txt，判断守护是否在跑。返回 (running, pid, size, scale)。"""
    p = paths.GUARD_STATUS
    try:
        with open(p, 'r', encoding='utf-8') as f:
            lines = [x.strip() for x in f.readlines()]
        pid = int(lines[0])
        ts = lines[1]
        size = int(lines[2])
        scale = float(lines[3])
        if time.time() - os.path.getmtime(p) > POLL * 4 + 2:
            return False, pid, size, scale
        h = k32.OpenProcess(0x1000, False, pid)      # QUERY_LIMITED_INFORMATION
        if not h:
            return False, pid, size, scale
        code = wt.DWORD()
        ok = k32.GetExitCodeProcess(h, ctypes.byref(code))
        k32.CloseHandle(h)
        alive = bool(ok) and code.value == 259       # STILL_ACTIVE
        return alive, pid, size, scale
    except Exception:
        return False, 0, 0, 0.0


def kill_guard(pid):
    """结束守护进程（GUI 的「停止守护」按钮用）。"""
    PROCESS_TERMINATE = 0x0001
    h = k32.OpenProcess(PROCESS_TERMINATE, False, int(pid))
    if not h:
        return False
    try:
        ok = bool(k32.TerminateProcess(h, 0))
    finally:
        k32.CloseHandle(h)
        try:
            os.remove(paths.GUARD_STATUS)
        except OSError:
            pass
    return ok


# ================================================================ 入口
def run():
    """启动守护。已被占用则返回 0（视为成功，避免开机重复启动报错）。"""
    mtx = k32.CreateMutexW(None, False, MUTEX_NAME)
    if k32.GetLastError() == 183:                    # ERROR_ALREADY_EXISTS
        log('守护已在运行，本次跳过')
        return 0
    g = Guard()
    g.do_apply('守护启动')
    g.write_status()
    t = threading.Thread(target=g.worker, name='guard', daemon=True)
    t.start()
    try:
        return run_tray(g)
    finally:
        g.stop()
        try:
            os.remove(paths.GUARD_STATUS)
        except OSError:
            pass


if __name__ == '__main__':
    sys.exit(run())
