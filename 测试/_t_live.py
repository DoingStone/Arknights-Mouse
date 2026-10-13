# -*- coding: utf-8 -*-
"""PRTS 三项效果的**上屏**验收：真的能看到指针变了才算数。

② 拖动爪子：拿一个真窗口，把物理指针按到它的标题栏上拖 7px，然后一边采
   `GetCursorInfo`（屏幕上真正在显示的那枚 HCURSOR）一边看 prtsfx 推进到哪一帧。
① 点击缩放：在同一个窗口的客户区按下左键，量屏幕上那枚指针的像素尺寸有没有缩。

要点：Tk 必须有**在跑的消息循环**才会响应 WM_NCLBUTTONDOWN 并进入系统移动循环，
所以驱动逻辑跑在子线程里，主线程跑 mainloop。
"""
import ctypes
import ctypes.wintypes as wt
import os
import sys
import threading
import time
import tkinter as tk

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '源码', 'arkmouse'))
import artpack              # noqa: E402
import cursorwin as cw      # noqa: E402
import prtsfx               # noqa: E402

# 回调是在 install() 里用 WINEVENTPROC(self._on_event) 绑的，必须在 start_fx 之前
# 就把类方法换掉，否则绑到的是原方法。
events = []
_orig_oe = prtsfx.DragWatch._on_event
def spy_evt(self, hook, evt, hw, obj, child, thread, t):
    events.append((evt, hw))
    return _orig_oe(self, hook, evt, hw, obj, child, thread, t)
prtsfx.DragWatch._on_event = spy_evt

u32 = cw.u32
u32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
u32.mouse_event.argtypes = [wt.DWORD, wt.DWORD, wt.DWORD, wt.DWORD, ctypes.c_void_p]
u32.LoadCursorW.restype = ctypes.c_void_p
u32.LoadCursorW.argtypes = [ctypes.c_void_p, ctypes.c_void_p]

MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP = 0x0002, 0x0004
WM_CLOSE = 0x0010
OCR_ARROW, OCR_SIZEALL = 32512, 32646

fails = []
def eq(name, got, want):
    ok = got == want
    if not ok:
        fails.append(name)
    print('%s %-46s got=%r want=%r' % ('ok  ' if ok else 'FAIL', name, got, want))


def live_cursor():
    ci = cw.CURSORINFO()
    ci.cbSize = ctypes.sizeof(cw.CURSORINFO)
    if not u32.GetCursorInfo(ctypes.byref(ci)) or not ci.hCursor:
        return 0, 0, 0
    try:
        m = cw.measure_hcursor(ci.hCursor)
    except Exception:
        m = None
    return ci.hCursor, (m[0] if m else 0), (m[1] if m else 0)


def nudge(x, y):
    """挪 1px 再挪回来，逼 Windows 重新决定屏幕上显示哪枚指针。"""
    u32.SetCursorPos(x + 1, y)
    time.sleep(0.03)
    u32.SetCursorPos(x, y)
    time.sleep(0.03)


def nchittest(hwnd, x, y):
    lp = (x & 0xFFFF) | ((y & 0xFFFF) << 16)
    r = ctypes.c_size_t(0)
    u32.SendMessageTimeoutW(ctypes.c_void_p(hwnd), 0x84, 0, ctypes.c_void_p(lp),
                            2, 100, ctypes.byref(r))
    return r.value


gdi = cw.gdi
gdi.GetDIBits.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint,
                          ctypes.c_uint, ctypes.c_void_p, ctypes.c_void_p,
                          ctypes.c_uint]
gdi.GetDIBits.restype = ctypes.c_int
u32.GetDC.argtypes = [ctypes.c_void_p]
u32.GetDC.restype = ctypes.c_void_p
u32.ReleaseDC.argtypes = [ctypes.c_void_p, ctypes.c_void_p]


def dump_live_cursor(path):
    """把「屏幕上那枚指针」的位图原样抠出来存 PNG —— 这是「到底画了什么」的
    唯一硬证据（句柄和 GetObject 的尺寸都可能骗人）。"""
    from PIL import Image
    ci = cw.CURSORINFO()
    ci.cbSize = ctypes.sizeof(cw.CURSORINFO)
    if not u32.GetCursorInfo(ctypes.byref(ci)) or not ci.hCursor:
        return None
    ii = cw.ICONINFO()
    if not u32.GetIconInfo(wt.HANDLE(ci.hCursor), ctypes.byref(ii)):
        return None
    try:
        bm = cw.BITMAP()
        if not gdi.GetObjectW(ii.hbmColor, ctypes.sizeof(cw.BITMAP), ctypes.byref(bm)):
            return None
        w, h = int(bm.bmWidth), int(bm.bmHeight)
        bi = cw.BITMAPINFOHEADER()
        bi.biSize = ctypes.sizeof(cw.BITMAPINFOHEADER)
        bi.biWidth = w
        bi.biHeight = -h
        bi.biPlanes = 1
        bi.biBitCount = 32
        bi.biCompression = 0
        buf = ctypes.create_string_buffer(w * h * 4)
        hdc = u32.GetDC(None)
        n = gdi.GetDIBits(hdc, ii.hbmColor, 0, h, buf, ctypes.byref(bi), 0)
        u32.ReleaseDC(None, hdc)
        if not n:
            return None
        im = Image.frombuffer('RGBA', (w, h), buf, 'raw', 'BGRA', 0, 1).copy()
        im.save(path)
        bbox = im.getbbox()
        return (w, h, bbox)
    finally:
        if ii.hbmColor:
            gdi.DeleteObject(ii.hbmColor)
        if ii.hbmMask:
            gdi.DeleteObject(ii.hbmMask)


size = cw.desktop_cursor_size()[0]
pack = artpack.load(os.path.join(HERE, '源码', 'arkmouse', 'art.bin'))
eng = cw.Engine()
fxo = cw.fx_options({'click_anim': True, 'click_style': 'prts', 'drag_claw': True,
                     'idle_anim': False, 'idle_prts': False, 'tick_ms': 8})
eng.build(size, pack, fx=fxo)
print('桌面指针尺寸 = %d  阶梯 = %s' % (size, cw.anim_rungs(size, fxo)))

root = tk.Tk()
root.title('PRTSFX-LIVE-TEST')
root.geometry('360x220+320+320')
root.attributes('-topmost', True)
root.configure(bg='#202020')
root.update()
hwnd = int(root.frame(), 16)
rect = wt.RECT()
u32.GetWindowRect(ctypes.c_void_p(hwnd), ctypes.byref(rect))

tx = rect.left + (rect.right - rect.left) // 3
ty = None
for dy in range(6, 46, 2):
    if nchittest(hwnd, tx, rect.top + dy) == 2:
        ty = rect.top + dy
        break
print('窗口 hwnd=0x%x rect=(%d,%d,%d,%d) 标题栏点=(%d,%s)' % (
    hwnd, rect.left, rect.top, rect.right, rect.bottom, tx, ty))
if ty is None:
    print('找不到标题栏，放弃（不冒险点错地方）')
    root.destroy(); sys.exit(2)

old = cw.POINT()
u32.GetCursorPos(ctypes.byref(old))
h_arrow_before = u32.LoadCursorW(None, ctypes.c_void_p(OCR_ARROW))
print('装我们指针之前的 Arrow 句柄 = 0x%x' % h_arrow_before)

eng.apply_all()
import atexit                                                        # noqa: E402
atexit.register(lambda: ctypes.windll.user32.SystemParametersInfoW(0x0057, 0, None, 0))
print('applied = %d 个角色' % len(eng.applied))
h_arrow_after = u32.LoadCursorW(None, ctypes.c_void_p(OCR_ARROW))
print('装我们指针之后的 Arrow 句柄 = 0x%x' % h_arrow_after)

# set_raw 是我们把 PRTS 帧送上屏的唯一通道，它的成功次数就是「真的调了
# SetSystemCursor 且系统答应了」的直接证据。句柄/尺寸探针会骗人，这个不会。
RAW_OK = {}
_orig_setraw = cw.Engine.set_raw


def spy_setraw(self, key, src):
    ok = _orig_setraw(self, key, src)
    if ok:
        RAW_OK[key] = RAW_OK.get(key, 0) + 1
    return ok


cw.Engine.set_raw = spy_setraw

# ① 走的是 apply_at（阶梯 + icon_at），得单独记一笔：它成功下发的 use 尺寸
# 直接说明弹簧把指针压到了多少像素。
APPLIED_USES = []
CLICK_USES = {}
APPLY_TRACE = []
APPLY_ERR = []
_orig_applyat = cw.Engine.apply_at


def spy_applyat(self, key, idx, px):
    try:
        ok = _orig_applyat(self, key, idx, px)
    except Exception as e:                                          # noqa: BLE001
        if len(APPLY_ERR) < 5:
            APPLY_ERR.append('%s/%s/%r: %s: %s' % (key, idx, px,
                                                   type(e).__name__, e))
        raise
    if len(APPLY_TRACE) < 24:
        APPLY_TRACE.append((key, int(px) if px is not None else None, ok))
    if ok:
        APPLIED_USES.append(int(px))
    return ok


cw.Engine.apply_at = spy_applyat

f = eng.start_fx(fxo)
for _ in range(40):
    if f is not None and f.prts is not None:
        break
    time.sleep(0.05)
p = getattr(f, 'prts', None)
print('CursorAnim=%r  PrtsFx=%r' % (f, p))
if p is None:
    print('prtsfx 没装起来，放弃')
    root.destroy(); eng.stop_fx(); eng.destroy(); sys.exit(3)
print('  err=%r 钩子=%s' % (p.err, bool(p.drag and p.drag.hook)))

stamps = []
_orig = p.frames_for
def spy(now):
    fr, st = _orig(now)
    stamps.append((st, tuple(sorted(fr)), len(fr)))
    return fr, st
p.frames_for = spy

dbg = []
def spy_state(now):
    dbg.append((p.drag.moving if p.drag else None,
                p.drag.pending_window if p.drag else None,
                p.drag.caption_pending if p.drag else None))
    return spy(now)
p.frames_for = spy_state

result = {}


def sample(seconds):
    seen = []
    t_end = time.time() + seconds
    while time.time() < t_end:
        h, w, hh = live_cursor()
        if not seen or seen[-1] != (h, w):
            seen.append((h, w))
        time.sleep(0.015)
    return seen


def drive():
    time.sleep(0.5)
    print()
    print('===== ② 拖动爪子 =====')
    u32.SetCursorPos(tx, ty)
    nudge(tx, ty)
    result['before'] = live_cursor()
    print('按到标题栏上（未按）:', result['before'])
    print('  [静止位图]', dump_live_cursor(r'E:\Qianmory\Desktop\Mouse\_live_rest.png'))
    u32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    time.sleep(0.05)
    result['drag0'] = sample(0.40)
    print('  [按住位图]', dump_live_cursor(r'E:\Qianmory\Desktop\Mouse\_live_drag.png'))
    u32.SetCursorPos(tx + 7, ty + 5)
    result['drag1'] = sample(0.90)
    u32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
    time.sleep(0.05)
    r2 = wt.RECT()
    u32.GetWindowRect(ctypes.c_void_p(hwnd), ctypes.byref(r2))
    moved = (r2.left - rect.left, r2.top - rect.top)
    result['moved'] = moved
    result['rel'] = sample(1.2)
    print('  [松手后位图]', dump_live_cursor(r'E:\Qianmory\Desktop\Mouse\_live_rel.png'))
    for k in ('drag0', 'drag1', 'rel'):
        print('  [%s] 屏幕指针序列 (handle,宽): %s' % (
            k, ' -> '.join('0x%x/%d' % (a, b) for a, b in result[k])))
    print('  窗口被拖动位移 = %r（非 0 说明系统移动循环真的跑了）' % (moved,))

    print()
    print('===== ① 点击缩放（prts 弹簧）=====')
    cx, cy = tx + 40, ty + 60
    u32.SetCursorPos(cx, cy)
    nudge(cx, cy)
    APPLIED_USES.clear()
    result['c_before'] = live_cursor()
    print('  [诊断] click=%s idle=%s prts_on=%s rungs=%s' % (
        f.click, f.idle, f.prts_on, f.rungs))
    sp = getattr(f.prts, 'spring', 'NA')
    print('  [诊断] spring=%s last_px=%r dragging=%s' % (
        'None' if sp is None else type(sp).__name__, f.prts.last_px,
        f.prts.dragging()))
    print('  [诊断] last_applied 条数=%d' % len(f.last_applied))
    u32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    time.sleep(0.18)
    result['c_held'] = live_cursor()
    CLICK_USES['held'] = sorted(set(APPLIED_USES))
    print('  按住期间 apply_at 成功下发的尺寸 = %s' % (CLICK_USES['held'],))
    print('  [诊断] 按住时 spring.compression = %r  last_px=%r' % (
        getattr(f.prts.spring, 'compression', 'NA'), f.prts.last_px))
    print('  [按住位图]', dump_live_cursor(r'E:\Qianmory\Desktop\Mouse\_live_click.png'))
    u32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
    time.sleep(0.10)
    result['c_rel'] = live_cursor()
    time.sleep(1.0)
    result['c_settled'] = live_cursor()
    CLICK_USES['settled'] = sorted(set(APPLIED_USES))
    print('按下前 %r -> 按住时 %r -> 松手后 %r -> 稳定 %r' % (
        result['c_before'], result['c_held'], result['c_rel'], result['c_settled']))
    print('  整个点击周期 apply_at 成功下发的尺寸 = %s' % (CLICK_USES['settled'],))
    u32.SetCursorPos(old.x, old.y)
    time.sleep(0.2)
    u32.PostMessageW(ctypes.c_void_p(hwnd), WM_CLOSE, 0, 0)


th = threading.Thread(target=drive, daemon=True)
th.start()

# A/B：主线程（马上要跑 mainloop，消息队列是真的）也装一个同样的钩子。
# 它收到事件而 prtsfx 那个收不到 => 是动画线程/消息泵的问题；
# 两个都收不到 => 根本没发生 MOVESIZESTART。
hook_events = []
_hp = prtsfx.WINEVENTPROC(lambda *a: hook_events.append((a[1], a[2])))
_h2 = prtsfx._u32.SetWinEventHook(10, 11, None, _hp, 0, 0, 0)
print('主线程独立钩子 = %s' % (hex(_h2) if _h2 else None))


def watchdog():
    time.sleep(30)
    print('!! 看门狗：30 秒还没结束，强退。dbg 尾部 =', dbg[-6:], flush=True)
    ctypes.windll.user32.SystemParametersInfoW(0x0057, 0, None, 0)
    os._exit(9)


threading.Thread(target=watchdog, daemon=True).start()
root.mainloop()
th.join(timeout=2)

print('主线程独立钩子收到的事件 =', hook_events[:12], '共', len(hook_events))

print()
print('===== 判定 =====')
fams = [s[0].split(':')[0] for s in stamps if s[0]]
print('拖动/待机期间 prtsfx 推进到的帧相（去重，前 20 个）:')
seen_f = []
for s in stamps:
    if s[0] and s[0] not in seen_f:
        seen_f.append(s[0])
print('   ', seen_f[:20])
print('WinEvent 回调收到的事件 = %s（共 %d 次；10=MOVESIZESTART 11=MOVESIZEEND）'
      % (events[:12], len(events)))
print('窗口位移 = %r' % (result.get('moved'),))
eq('② 拖动时进入了 grab_enter', any(x.startswith('grab_enter') for x in fams), True)
eq('② 拖动时进入了 grab_loop', any(x.startswith('grab_loop') for x in fams), True)
eq('② 松手后走了 grab_end', any(x.startswith('grab_end') for x in fams), True)
eq('② 松手后走了 grab_return', any(x.startswith('grab_return') for x in fams), True)
eq('② 被替换的角色里有 Arrow 或 SizeAll',
   any(('Arrow' in s[1] or 'SizeAll' in s[1]) for s in stamps if s[0]), True)

dw0 = set(w for _, w in result.get('drag0', []))
dw1 = set(w for _, w in result.get('drag1', []))
print('  拖动期间屏幕上的宽度集合 = %s / %s' % (sorted(dw0), sorted(dw1)))
print('  set_raw 成功下发次数（按角色）:', RAW_OK)
print('  apply_at 前 24 次调用 (key, px, ok):', APPLY_TRACE)
print('  apply_at 抛出的异常:', APPLY_ERR or '无')
print('  合成图：_live_rest.png / _live_drag.png / _live_rel.png；'
      'grab 帧的像素由 _grab_pix.png 单独导出')

eq('② set_raw 真的把帧下发给了 Arrow', RAW_OK.get('Arrow', 0) > 0, True)
eq('② set_raw 下发次数够多（≥60 帧）', RAW_OK.get('Arrow', 0) >= 60, True)

eq('① 按住时指针变小', result['c_held'][1] < result['c_before'][1], True)
eq('① 按住时宽度 = round(72*0.9456)', result['c_held'][1], round(size * 0.9456))
eq('① 稳定后回到 72px', result['c_settled'][1], size)
eq('① 按住期间真的下发过 round(72*0.9456) 这一档',
   round(size * 0.9456) in (CLICK_USES.get('held') or []), True)

print()
print('===== 收尾 =====')
eng.stop_fx()
eng.destroy()
time.sleep(0.3)
after = live_cursor()
print('destroy() 之后屏幕指针 =', after)
eq('复位后指针宽度回到 72', after[1] in (size, 0), True)

print()
print('stamps 总数 = %d，其中 grab_* = %d' % (
    len(stamps), sum(1 for x in fams if x.startswith('grab'))))
print('FAILED: %d %s' % (len(fails), fails if fails else ''))
sys.exit(1 if fails else 0)
