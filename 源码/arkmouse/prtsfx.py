# -*- coding: utf-8 -*-
"""PRTS 三项效果的移植层：① 点击弹簧  ② 拖动爪子  ③ 待机帧动画。

出处（PRTS 参考工程，下面的行号就是那个文件的行号，可逐条核对）：
  E:\\Qianmory\\下载\\QuarkDownload\\_prts_build\\motion\\src\\Runtime.cs
    IdleFrame     379-386    待机帧序（进入段 60fps / 循环段 15fps，342 帧一圈）
    VisualPhase   388-425    待机相 -> 帧名（含退出过渡，本移植只取进入+循环）
    PollMove      992-1008   拖动兜底：比较窗口矩形，位移 >3px 才算「在拖」
    InitDrag     1031-1035   SetWinEventHook(EVENT_SYSTEM_MOVESIZESTART/END = 10/11)
    ProbeCaption 1037-1049   WM_NCHITTEST == HTCAPTION 判「光标在标题栏上」
    MoveEvent    1051-1088   上面那个钩子的回调：起拖 / 结束
    DragVisual   1090-1113   拖动视觉存活期（松手后还有 884ms 尾巴）
    DragFrame    1115-1137   拖动帧序（进入→开始→循环 / 收尾→回位）
    HandFrame    1154-1191   点击弹簧（刚度 520、阻尼 30、340Hz 子步、1% 量化）
    Tick          838-891    相 -> 下发的编排（拖动相直接顶掉 HandFrame）

美术：`..\\_prts_build\\extract\\PRTS-Replica-v8-96x-<phase>.cur`（一帧一文件，
      每族热点都是 (28,20)），已由 `提取工具\\import_prts_fx.py` 打成 `fx.bin`
      （与本工程 art.bin 同格式，用 artpack.ArtPack 直接读）。

与 PRTS 的两处**有意**差异，都写在对应位置的注释里：
  * PRTS 宿主本来就有消息泵，本工程的动画线程（cursorwin.CursorAnim）是纯轮询
    线程 —— 这里自带一个 PeekMessage 泵（`DragWatch.pump`）。钩子装不上就整项
    静默关闭（`DragWatch.install` 返回 False），绝不让指针卡住。
  * PRTS 用 107 张预渲染的 hand_<role>_NNN 美术表示弹簧压缩量；本工程没有那批
    美术，改成「同一个量化帧号 -> 倍率 -> 吸到像素阶梯」，量化粒度（1% 压缩量）
    与 PRTS 完全一致，所以时间轴上的台阶感是同一个。
"""
import ctypes
import os
import threading
import time
from ctypes import wintypes

import artpack
import cursorwin as cw

_u32 = ctypes.WinDLL('user32', use_last_error=True)
_k32 = ctypes.WinDLL('kernel32', use_last_error=True)

# ---------------------------------------------------------------- 常量（PRTS 出处）
SPRING_STIFF = 520.0          # Runtime.cs:1180  `520.0 * (target - compression)`
SPRING_DAMP = 30.0            # Runtime.cs:1180  `- 30.0 * velocity`
SPRING_SUB = 1.0 / 240.0      # Runtime.cs:1178  `Math.Min(num, 1.0 / 240.0)`
SPRING_DT_MAX = 0.08          # Runtime.cs:1169  `Math.Min(0.08, ...)`
MIN_PRESS_MS = 75             # Runtime.cs:1173  `minPressUntil = now + 75`
COMPRESS_LO, COMPRESS_HI = -0.06, 1.0   # Runtime.cs:1189 `Math.Max(-0.06, Math.Min(1.0, c))`
REST_FRAME = 6                # 压缩量 0 -> 帧号 0*100+6 = 6

DRAG_TAIL_MS = 884            # Runtime.cs:1098  `now - dragEndAt < 884`
CAPTION_WINDOW_MS = 1500      # Runtime.cs:1061/1065 `elapsed - captionAt >= 1500`
MOVE_EPS = 3                  # Runtime.cs:1000  位移阈值
DRAG_FPS = 60                 # Runtime.cs:1119/1131 拖动帧序是 60fps 时间基
IDLE_ENTER_MS = 500           # Runtime.cs:383/385 进入段 500ms
IDLE_ENTER_N = 30             # Runtime.cs:383     idle_enter_frame_000..029 @60fps
IDLE_LOOP_FPS = 15            # Runtime.cs:385     idle_frame_%04d @15fps
IDLE_LOOP_N = 342             # Runtime.cs:385     % 342
IDLE_START_MS = 5000          # Motion.cs:73 `idle >= int.Parse(Config.Get("seconds")) * 1000`

EVENT_MOVESIZESTART = 10      # Runtime.cs:1034
EVENT_MOVESIZEEND = 11        # Runtime.cs:1034
WINEVENT_OUTOFCONTEXT = 0     # Runtime.cs:1034 最后一个参数 0u
WM_NCHITTEST = 0x0084         # Runtime.cs:1044 消息号 132
HTCAPTION = 2                 # Runtime.cs:1044 `result == 2`
GA_ROOT = 2                   # Runtime.cs:1042 `GetAncestor(..., 2u)`
SMTO_ABORTIFHUNG = 2          # Runtime.cs:1044 flags 2u
PM_REMOVE = 1

# 效果作用到哪几个角色键上。
#   * PRTS `Tick:863-866` 在拖动相里把 `text` 强制成 "normal"，再经 `Ids["normal"]`
#     下发 —— "normal" 就是 Arrow（32512）。本工程补上 SizeAll（32646）：Windows
#     进入窗口移动循环时显示的是 IDC_SIZEALL，两个槽一起换才不会漏。
#   * 待机相 PRTS 用 `VisualPhase:388-425` 卡死 `role == "normal"`，所以只动 Arrow。
DRAG_KEYS = ('Arrow', 'SizeAll')
IDLE_KEYS = ('Arrow',)

# ① 点击挤压用 PRTS 的原帧（不是把常态帧做缩放 —— 见 import_prts_fx.py 的说明：
# hand_normal_106 与「把 006 按质量比缩放」的交并比只有 0.807，是逐帧烘死的非
# 均匀挤压）。PRTS 只给这 5 个角色烘了 hand_*，其余角色它自己也没有点击动画。
CLICK_ART = {
    'Arrow':  'hand_normal',      # Runtime.cs:142 Roles[0]  normal  → Ids 32512
    'Help':   'hand_helpsel',     # Roles[1]  helpsel
    'Hand':   'hand_link',        # Roles[14] link
    'Pin':    'hand_pin',         # Roles[16] pin
    'Person': 'hand_person',      # Roles[15] person
}
CLICK_FAMILIES = tuple(sorted(set(CLICK_ART.values())))
DRAG_FAMILIES = ('grab_enter', 'grab_begin', 'grab_loop', 'grab_end', 'grab_return')
IDLE_FAMILIES = ('idle_enter_frame', 'idle_frame')

# 幅度端点：拿 PRTS 自己的 hand_<role>_NNN.cur 逐帧量 alpha 质量比得到的
#   hand_*_006（压缩量 0.00）= 1.0000×  基准
#   hand_*_106（压缩量 1.00）= 0.9456×  <- SCALE_AT_FULL
#   hand_*_000（压缩量 -0.06）= 1.0397× <- SCALE_AT_OVER
SCALE_AT_FULL = 0.9456
SCALE_AT_OVER = 1.0397
PRTS_MIN_SCALE = SCALE_AT_FULL      # 0.9456
PRTS_MAX_SCALE = SCALE_AT_OVER      # 1.0397


def scale_of_frame(frame):
    """PRTS 的量化帧号 -> 倍率（分段线性过上面那三个实测端点）。"""
    q = int(frame) - REST_FRAME                 # q = round(压缩量 * 100)，∈ [-6, 100]
    if q >= 0:
        return 1.0 + (q / 100.0) * (SCALE_AT_FULL - 1.0)
    return 1.0 + (q / -float(REST_FRAME)) * (SCALE_AT_OVER - 1.0)


def idle_frame(elapsed_ms):
    """PRTS `IdleFrame`（Runtime.cs:379-386）逐行移植 -> (族名, 帧号)。"""
    e = max(0, int(elapsed_ms))
    if e < IDLE_ENTER_MS:
        return 'idle_enter_frame', min(IDLE_ENTER_N - 1, int(e * 60 / 1000))
    return 'idle_frame', int((e - IDLE_ENTER_MS) * IDLE_LOOP_FPS / 1000) % IDLE_LOOP_N


def _ticks():
    return int(_k32.GetTickCount()) & 0xFFFFFFFF


def idle_ms():
    """距最后一次输入多少毫秒（对应 Runtime.cs:858 的 `TickCount - l.time`）。"""
    li = LASTINPUTINFO()
    li.cbSize = ctypes.sizeof(LASTINPUTINFO)
    if not _u32.GetLastInputInfo(ctypes.byref(li)):
        return 0
    return (_ticks() - int(li.dwTime)) & 0xFFFFFFFF


# ---------------------------------------------------------------- 结构体 / 原型
class POINT(ctypes.Structure):
    _fields_ = [('x', wintypes.LONG), ('y', wintypes.LONG)]


class RECT(ctypes.Structure):
    _fields_ = [('left', wintypes.LONG), ('top', wintypes.LONG),
                ('right', wintypes.LONG), ('bottom', wintypes.LONG)]


class MSG(ctypes.Structure):
    _fields_ = [('hwnd', ctypes.c_void_p), ('message', wintypes.UINT),
                ('wParam', ctypes.c_size_t), ('lParam', ctypes.c_ssize_t),
                ('time', wintypes.DWORD), ('pt', POINT)]


class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [('cbSize', wintypes.UINT), ('dwTime', wintypes.DWORD)]


WINEVENTPROC = ctypes.WINFUNCTYPE(None, ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p,
                                  ctypes.c_int, ctypes.c_int, ctypes.c_uint, ctypes.c_uint)

_u32.SetWinEventHook.argtypes = (wintypes.UINT, wintypes.UINT, ctypes.c_void_p,
                                 WINEVENTPROC, wintypes.UINT, wintypes.UINT, wintypes.UINT)
_u32.SetWinEventHook.restype = ctypes.c_void_p
_u32.UnhookWinEvent.argtypes = (ctypes.c_void_p,)
_u32.UnhookWinEvent.restype = wintypes.BOOL
_u32.PeekMessageW.argtypes = (ctypes.POINTER(MSG), ctypes.c_void_p,
                              wintypes.UINT, wintypes.UINT, wintypes.UINT)
_u32.PeekMessageW.restype = wintypes.BOOL
_u32.TranslateMessage.argtypes = (ctypes.POINTER(MSG),)
_u32.TranslateMessage.restype = wintypes.BOOL
_u32.DispatchMessageW.argtypes = (ctypes.POINTER(MSG),)
_u32.DispatchMessageW.restype = ctypes.c_ssize_t
_u32.GetCursorPos.argtypes = (ctypes.POINTER(POINT),)
_u32.GetCursorPos.restype = wintypes.BOOL
_u32.WindowFromPoint.argtypes = (POINT,)
_u32.WindowFromPoint.restype = ctypes.c_void_p
_u32.GetAncestor.argtypes = (ctypes.c_void_p, wintypes.UINT)
_u32.GetAncestor.restype = ctypes.c_void_p
_u32.SendMessageTimeoutW.argtypes = (ctypes.c_void_p, wintypes.UINT, ctypes.c_size_t,
                                     ctypes.c_ssize_t, wintypes.UINT, wintypes.UINT,
                                     ctypes.POINTER(ctypes.c_size_t))
_u32.SendMessageTimeoutW.restype = ctypes.c_void_p
_u32.GetWindowRect.argtypes = (ctypes.c_void_p, ctypes.POINTER(RECT))
_u32.GetWindowRect.restype = wintypes.BOOL
_u32.GetLastInputInfo.argtypes = (ctypes.POINTER(LASTINPUTINFO),)
_u32.GetLastInputInfo.restype = wintypes.BOOL
_u32.DestroyCursor.argtypes = (ctypes.c_void_p,)
_u32.DestroyCursor.restype = wintypes.BOOL
_k32.GetTickCount.restype = wintypes.DWORD


# ---------------------------------------------------------------- ① 点击弹簧
class ClickSpring(object):
    """PRTS `HandFrame`（Runtime.cs:1154-1191）逐行移植。

    PRTS 的返回值是帧名 `hand_<role>_<num4+6>`；本移植返回同一个量化帧号
    （`num4 + 6`，0..106），**静止收敛时返回 None**（对应 Runtime.cs:1188 的
    `return ""`，表示「这一帧没有相位、交回常态处理」）。弹簧本身（目标值、
    刚度、阻尼、240Hz 子步、75ms 最短按下、dt 上限 0.08s）逐字照抄。
    """

    def __init__(self):
        self.reset()

    def reset(self):
        self.compression = 0.0
        self.velocity = 0.0
        self.at = None
        self.down = False
        self.min_press_until = 0.0

    def step(self, now_ms, down):
        if self.at is None:
            self.at = now_ms                                  # :1167 springAt = now
        dt = min(SPRING_DT_MAX, max(0.0, (now_ms - self.at) / 1000.0))   # :1169
        self.at = now_ms
        if down and not self.down:                            # :1171-1174
            self.min_press_until = now_ms + MIN_PRESS_MS
        self.down = bool(down)
        while dt > 0.0:                                       # :1176-1183
            h = min(dt, SPRING_SUB)
            target = 1.0 if (down or now_ms < self.min_press_until) else 0.0
            self.velocity += (SPRING_STIFF * (target - self.compression)
                              - SPRING_DAMP * self.velocity) * h
            self.compression += self.velocity * h
            dt -= h
        if (not down and now_ms >= self.min_press_until
                and abs(self.compression) < 0.0001 and abs(self.velocity) < 0.001):
            self.compression = self.velocity = 0.0            # :1184-1187
            return None                                       # :1188 return ""
        q = int(round(max(COMPRESS_LO, min(COMPRESS_HI, self.compression)) * 100.0))  # :1189
        return q + REST_FRAME                                 # :1190


# ---------------------------------------------------------------- ② 拖动检测
class DragWatch(object):
    """PRTS `InitDrag` / `MoveEvent` / `ProbeCaption` / `PollMove` / `DragVisual` /
    `DragFrame`（Runtime.cs:1031-1137）的移植。

    唯一的结构差异：PRTS 的宿主进程本来就跑消息泵，本工程的动画线程没有，所以
    自己补一个 `pump()`（每 tick 调一次）。`install()` 返回 False 表示钩子没装上，
    调用方必须把整个拖动效果关掉 —— 宁可不做，也不能让指针卡在爪子上。
    """

    def __init__(self):
        self.hook = None
        self.proc = None            # 必须留引用：回调被 GC 掉就是野指针
        self.moving = False
        self.moving_window = None
        self.pending_window = None
        self.initial_rect = None
        self.drag_at = 0
        self.drag_end_at = -1
        self.caption_at = -(10 ** 9)
        self.caption_pending = False
        self.ended_now = False      # 本轮尾巴刚走完（调用方据此复位弹簧）
        self.t0 = time.time()

    def now(self):
        return int((time.time() - self.t0) * 1000)

    def install(self):
        try:
            self.proc = WINEVENTPROC(self._on_event)
            self.hook = _u32.SetWinEventHook(
                EVENT_MOVESIZESTART, EVENT_MOVESIZEEND, None, self.proc,
                0, 0, WINEVENT_OUTOFCONTEXT)                  # :1031-1035
        except Exception:
            self.hook = None
        return bool(self.hook)

    def uninstall(self):
        self.proc = None
        h, self.hook = self.hook, None
        if h:
            try:
                _u32.UnhookWinEvent(h)
            except Exception:
                pass

    def pump(self):
        """本工程补的消息泵（差异点见模块 docstring）。"""
        msg = MSG()
        n = 0
        while n < 64:
            try:
                if not _u32.PeekMessageW(ctypes.byref(msg), None, 0, 0, PM_REMOVE):
                    break
                _u32.TranslateMessage(ctypes.byref(msg))
                _u32.DispatchMessageW(ctypes.byref(msg))
            except Exception:
                break
            n += 1

    # ---- Runtime.cs:1051-1088 -------------------------------------------------
    def _on_event(self, hook, evt, hwnd, obj, child, thread, t):
        now = self.now()
        if evt == EVENT_MOVESIZESTART:                        # case 10u, :1060-1075
            if self.caption_pending or now - self.caption_at >= CAPTION_WINDOW_MS:
                self.probe_caption()
            if now - self.caption_at >= CAPTION_WINDOW_MS:
                self.pending_window = hwnd
                r = RECT()
                self.initial_rect = r if _u32.GetWindowRect(hwnd, ctypes.byref(r)) else None
                return
            self.moving = True
            self.moving_window = hwnd
            self.drag_at = now
            self.drag_end_at = -1
        elif evt == EVENT_MOVESIZEEND:                        # case 11u, :1076-1085
            if hwnd == self.pending_window:
                self.pending_window = None
            if self.moving and hwnd == self.moving_window:
                self.moving = False
                self.drag_end_at = now

    # ---- Runtime.cs:1037-1049 -------------------------------------------------
    def probe_caption(self):
        self.caption_pending = False
        p = POINT()
        if not _u32.GetCursorPos(ctypes.byref(p)):
            return
        anc = _u32.GetAncestor(_u32.WindowFromPoint(p), GA_ROOT)
        lp = (p.x & 0xFFFF) | ((p.y & 0xFFFF) << 16)
        res = ctypes.c_size_t()
        r = _u32.SendMessageTimeoutW(anc, WM_NCHITTEST, 0, lp,
                                     SMTO_ABORTIFHUNG, 100, ctypes.byref(res))
        if r and int(res.value) == HTCAPTION:
            self.caption_at = self.now()

    # ---- Runtime.cs:992-1008 --------------------------------------------------
    def poll_move(self):
        if not self.pending_window or self.moving or self.initial_rect is None:
            return
        r = RECT()
        if not _u32.GetWindowRect(self.pending_window, ctypes.byref(r)):
            return
        i = self.initial_rect
        if (r.right - r.left != i.right - i.left
                or r.bottom - r.top != i.bottom - i.top):
            self.pending_window = None                        # 尺寸变了 = 在缩放，不是移动
        elif abs(r.left - i.left) + abs(r.top - i.top) > MOVE_EPS:
            self.moving = True
            self.moving_window = self.pending_window
            self.pending_window = None
            self.drag_at = self.now()
            self.drag_end_at = -1

    # ---- Runtime.cs:1090-1113 -------------------------------------------------
    def visual(self, now):
        self.ended_now = False
        if self.moving:
            return True
        if self.drag_end_at >= 0:
            if now - self.drag_end_at < DRAG_TAIL_MS:
                return True
            self.drag_end_at = -1
            self.ended_now = True                             # 调用方据此复位弹簧
        return False

    # ---- Runtime.cs:1115-1137 -------------------------------------------------
    def frame(self, now):
        if self.moving:
            n = int((now - self.drag_at) * DRAG_FPS / 1000)
            if n < 0:
                n = 0
            if n < 12:
                return 'grab_enter', n
            n -= 12
            if n >= 12:
                return 'grab_loop', 0
            return 'grab_begin', n
        n2 = int((now - self.drag_end_at) * DRAG_FPS / 1000)
        if n2 < 0:
            n2 = 0
        if n2 >= 41:
            return 'grab_return', min(11, n2 - 41)
        return 'grab_end', n2


# ---------------------------------------------------------------- 帧 -> HCURSOR
class FxFrames(object):
    """fx.bin 里的帧按需现造成 HCURSOR 并缓存。

    刻意**不**进 Engine.ladder：那边是给「同一角色的不同像素档」用的，这里每帧
    就一个尺寸（base），混进去会把阶梯的容量和淘汰逻辑搅乱。
    """

    def __init__(self, path=None):
        if path is None:
            # 走 paths.find_fx()：打包版 fx.bin 在 sys._MEIPASS 下，源码版在模块旁。
            # 直接写 __file__ 同目录在 exe 里会落空，三项效果就全静默了。
            try:
                import paths
                path = paths.find_fx()
            except Exception:
                path = None
            if path is None:
                path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    'fx.bin')
        self.path = path
        self.pack = None
        self.err = ''
        self.cache = {}
        self.lock = threading.RLock()
        try:
            if os.path.exists(self.path):
                self.pack = artpack.load(self.path)
            else:
                self.err = 'fx.bin 不存在'
        except Exception as e:
            self.err = str(e)
            self.pack = None

    def has(self, family):
        return self.pack is not None and family in self.pack.roles

    def prewarm(self, families):
        """把这几族的帧列表（含暗描边补全）先算出来，免得第一次触发时卡一下。"""
        if self.pack is None:
            return
        for fam in families:
            if fam in self.pack.roles:
                try:
                    cw.frames_with_outline(self.pack, fam)
                except Exception as e:
                    self.err = str(e)

    def icon(self, family, idx, px):
        if self.pack is None or family not in self.pack.roles:
            return None
        frames = cw.frames_with_outline(self.pack, family)
        if not frames:
            return None
        i = int(idx) % len(frames)
        ck = (family, i, int(px))
        with self.lock:
            got = self.cache.get(ck)
            if got is not None:
                return got
        im = frames[i][0]
        try:
            hc, _hs = cw.make_hcursor_pm(cw.premul_forward(im), int(px),
                                         self.pack.hotspot(family))
        except OSError as e:
            self.err = str(e)
            return None
        with self.lock:
            old = self.cache.get(ck)
            if old is not None:
                try:
                    _u32.DestroyCursor(hc)
                except Exception:
                    pass
                return old
            self.cache[ck] = hc
        return hc

    def close(self):
        with self.lock:
            for hc in self.cache.values():
                try:
                    _u32.DestroyCursor(hc)
                except Exception:
                    pass
            self.cache.clear()


# ---------------------------------------------------------------- 门面
class PrtsFx(object):
    """CursorAnim 挂上去就行的门面：三项效果都从这里进出。

    `install()` **必须在动画线程里调**（SetWinEventHook 把事件投给调用线程的
    消息队列）；`frames_for()` / `click_px()` 每 tick 各调一次。
    """

    def __init__(self, eng, opt):
        self.eng = eng
        self.opt = dict(opt or {})
        self.frames = FxFrames()
        self.spring = None
        self.click_art = {}
        self.drag = None
        self.drag_keys = ()
        self.idle_keys = ()
        self.idle_on = False
        self.idle_start_ms = IDLE_START_MS
        self.idle_since = None
        self.idle_active = False
        self.last_px = None
        self.installed = False
        self.err = ''

    # ---- 装配 ----------------------------------------------------------------
    def install(self):
        if self.installed:
            return True
        self.installed = True
        o = self.opt
        style = str(o.get('click_style', 'prts')).lower()
        if o.get('click_anim'):
            self.spring = ClickSpring()                        # ① 弹簧
            if style == 'prts':                                # ① 用 PRTS 原帧
                got = dict((k, fam) for k, fam in CLICK_ART.items()
                           if k in self.eng.masters and self.frames.has(fam))
                if got:
                    self.click_art = got
                    self.frames.prewarm(tuple(sorted(set(got.values()))))
                else:
                    self.err = 'fx.bin 里没有 hand_* 帧族'
        if o.get('drag_claw'):                                 # ② 拖动爪子
            if self.frames.has('grab_loop'):
                d = DragWatch()
                if d.install():
                    self.drag = d
                    self.drag_keys = tuple(k for k in DRAG_KEYS if k in self.eng.masters)
                    self.frames.prewarm(DRAG_FAMILIES)
                else:
                    self.err = 'SetWinEventHook 没装上，拖动爪子已关闭'
            else:
                self.err = 'fx.bin 里没有 grab_* 帧族'
        if o.get('idle_prts'):                                 # ③ 待机帧动画
            if self.frames.has('idle_frame'):
                self.idle_on = True
                self.idle_keys = tuple(k for k in IDLE_KEYS if k in self.eng.masters)
                try:
                    self.idle_start_ms = max(500, int(o.get('idle_start_ms') or IDLE_START_MS))
                except (TypeError, ValueError):
                    self.idle_start_ms = IDLE_START_MS
                self.frames.prewarm(IDLE_FAMILIES)
            else:
                self.err = 'fx.bin 里没有 idle_frame 族'
        return True

    def close(self):
        if self.drag is not None:
            self.drag.uninstall()
            self.drag = None
        self.frames.close()

    # ---- 每 tick -------------------------------------------------------------
    def poll(self):
        """消息泵 + 拖动兜底，每 tick 一次。"""
        if self.drag is None:
            return
        self.drag.pump()
        self.drag.poll_move()

    def dragging(self):
        if self.drag is None:
            return False
        return bool(self.drag.visual(self.drag.now()))

    def _step_idle(self, now):
        """③ 待机计时。对应 Motion.cs:73 / VisualPhase:388-425（只取进入+循环段）。"""
        self.idle_active = False
        if not self.idle_on or not self.idle_keys:
            return
        if idle_ms() < self.idle_start_ms:
            self.idle_since = None
            return
        if self.idle_since is None:
            self.idle_since = now
        self.idle_active = True

    def frames_for(self, now, down):
        """返回 ({角色键: HCURSOR}, 时间戳标记)。空字典 = 本 tick 不接管任何角色。

        优先级照 Runtime.cs:863-868：拖动 → 待机 → 点击（`HandFrame` 自己就会在
        idle 相位下让位，所以待机排它前面）。传进来的 now 是 `CursorAnim._loop`
        的 `time.time()`（**秒**），而 PRTS 那一整套时间常量（500 / 15fps / 342 帧
        / 884ms / 75ms …）全是**毫秒**。在这个唯一的入口上换算一次，模块内部就
        保持与 Runtime.cs 逐字对应的毫秒，不用在每个数字上做心算。
        """
        now_ms = now * 1000.0
        # 拖动优先（Runtime.cs:868：DragFrame 直接顶掉 HandFrame）。注意 drag 用
        # 自己那条 time.time() 起点的毫秒时钟，不跟着这里换算。
        if self.drag is not None and self.drag_keys:
            if self.drag.visual(self.drag.now()):
                if self.drag.ended_now:
                    self._reset_spring()
                fam, idx = self.drag.frame(self.drag.now())
                hc = self.frames.icon(fam, idx, self.eng.size)
                if hc is not None:
                    stamp = '%s:%d' % (fam, idx)
                    return dict((k, hc) for k in self.drag_keys), stamp
                return {}, ''
            if self.drag.ended_now:
                self._reset_spring()
        # 待机次之
        self._step_idle(now_ms)
        if self.idle_active and self.idle_keys:
            fam, idx = idle_frame(now_ms - self.idle_since)
            hc = self.frames.icon(fam, idx, self.eng.size)
            if hc is not None:
                return dict((k, hc) for k in self.idle_keys), '%s:%d' % (fam, idx)
        # 点击挤压（PRTS 原帧）。弹簧每 tick 只能走一步，所以这里走完就不再走。
        if self.click_art and self.spring is not None:
            frame = self.spring.step(now_ms, down)
            if frame is not None:
                out, stamp = {}, ''
                for key, fam in self.click_art.items():
                    hc = self.frames.icon(fam, frame, self.eng.size)
                    if hc is not None:
                        out[key] = hc
                        stamp = '%s:%d' % (fam, frame)
                if out:
                    return out, stamp
        return {}, ''

    def _reset_spring(self):
        """Runtime.cs:1103-1110：拖动尾巴走完，弹簧状态清零。"""
        if self.spring is not None:
            self.spring.reset()
        self.last_px = None

    def click_px(self, now, down, rungs):
        """① 的像素档 —— **只有 game 风格才走这里**（prts 风格用原帧，走 frames_for）。

        拖动或待机期间不推进弹簧（Runtime.cs:868 / :1156）。now 同样来自
        `CursorAnim._loop` 的 `time.time()`（秒），弹簧的 520/30/240Hz/75ms/0.08s
        全是毫秒制，所以在进弹簧前换算（见 frames_for 的说明）。
        """
        if self.spring is None or self.click_art:
            return None
        if self.dragging() or self.idle_active:
            return self.last_px if self.last_px is not None else self.eng.size
        frame = self.spring.step(now * 1000.0, down)
        px = cw.nearest_rung(rungs, self.eng.size,
                             scale_of_frame(REST_FRAME if frame is None else frame))
        self.last_px = px
        return px
