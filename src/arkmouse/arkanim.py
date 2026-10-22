# -*- coding: utf-8 -*-
"""动效层：Tkinter 没有 CSS transition，用 after() 分步插值。

明日方舟 UI 动效规范（references/ui-style.md）的硬约束：
  - 150–300ms，linear / ease-out，**禁止 elastic / bounce / back**
  - 按钮按下 80ms、悬停 150ms、页签 200ms、开关 200ms、数字 200ms
  - 闪烁频率 ≤3Hz
本项目额外红线：**任何动效不得引起布局位移**（此前修过「拖滑杆导致整页
横移」）。所以只改颜色/透明度这类纯绘制属性，绝不碰 width/height/pack。
"""
import time

# ease-out（三次方）：起手快、收尾稳，符合「终端 UI」利落的调性
def _ease_out(t):
    return 1.0 - (1.0 - t) ** 3


def _lerp_hex(a, b, t):
    """在两个 #rrggbb 之间线性插值。t=0 取 a，t=1 取 b。"""
    def rgb(h):
        h = h.lstrip('#')
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
    try:
        ra, ga, ba = rgb(a)
        rb, gb, bb = rgb(b)
    except Exception:
        return b
    t = 0.0 if t < 0 else (1.0 if t > 1 else float(t))
    return '#%02x%02x%02x' % (
        int(ra + (rb - ra) * t),
        int(ga + (gb - ga) * t),
        int(ba + (bb - ba) * t))


class Tween(object):
    """单个控件的单条颜色补间。挂在 app 上，避免被 GC。"""

    def __init__(self, app, widget, attr, c0, c1, ms, on_done=None):
        self.app = app
        self.widget = widget
        self.attr = attr          # 'bg' / 'fg' / 'activebackground' ...
        self.c0 = c0
        self.c1 = c1
        self.ms = max(1, int(ms))
        self.on_done = on_done
        self._job = None
        self._t0 = None

    def start(self):
        self.cancel()
        self._t0 = time.monotonic()
        self._step()
        return self

    def _step(self):
        try:
            el = (time.monotonic() - self._t0) * 1000.0
        except Exception:
            return
        t = min(1.0, el / self.ms)
        col = _lerp_hex(self.c0, self.c1, _ease_out(t))
        try:
            self.widget.configure(**{self.attr: col})
        except Exception:
            self.cancel()
            return
        if t >= 1.0:
            self._job = None
            if self.on_done:
                try:
                    self.on_done()
                except Exception:
                    pass
            return
        self._job = self.app.root.after(16, self._step)   # ~60fps

    def cancel(self):
        if self._job is not None:
            try:
                self.app.root.after_cancel(self._job)
            except Exception:
                pass
            self._job = None


class Animator(object):
    """App 的动效调度器。所有补间都登记在这里，换主题/关窗时统一取消。"""

    # 规范里的时长（ms）
    T_HOVER = 150     # 悬停渐变
    T_PRESS = 80      # 按下
    T_STATE = 200     # 状态/开关/数字

    def __init__(self, app):
        self.app = app
        self._live = {}       # id(widget+attr) -> Tween
        self._press = {}      # id(widget) -> Tween（按下专用，允许并存）

    def cancel_all(self):
        for tw in list(self._live.values()) + list(self._press.values()):
            try:
                tw.cancel()
            except Exception:
                pass
        self._live.clear()
        self._press.clear()

    def fade_color(self, widget, attr, c_from, c_to, ms=None, done=None):
        """把 widget 的 attr 从 c_from 补间到 c_to。同键重入会顶掉旧补间。"""
        ms = self.T_STATE if ms is None else ms
        key = (id(widget), attr)
        old = self._live.pop(key, None)
        if old:
            old.cancel()
        tw = Tween(self.app, widget, attr, c_from, c_to, ms, on_done=done)
        self._live[key] = tw
        tw.start()
        return tw

    def fade_style(self, stylename, attr, c_from, c_to, ms=None, done=None):
        """ttk 版：把样式表 stylename 的 attr 从 c_from 补间到 c_to。"""
        ms = self.T_STATE if ms is None else ms
        key = ('style', stylename, attr)
        old = self._live.pop(key, None)
        if old:
            old.cancel()
        tw = StyleTween(self.app, stylename, attr, c_from, c_to, ms,
                        on_done=done)
        self._live[key] = tw
        tw.start()
        return tw

    def press_pulse(self, widget, c_normal, c_press):
        """按钮按下：瞬时压暗（80ms），松手弹回（150ms）。不改尺寸。"""
        key = id(widget)
        old = self._press.pop(key, None)
        if old:
            old.cancel()
        def back():
            self._press[key] = Tween(self.app, widget, 'background',
                                     c_press, c_normal, self.T_HOVER)
            self._press[key].start()
        tw = Tween(self.app, widget, 'background', c_normal, c_press,
                   self.T_PRESS, on_done=back)
        self._press[key] = tw
        tw.start()


# ---- ttk 颜色补间 ----
#
# ttk 控件（Button / Checkbutton / Notebok.Tab）的颜色**不由 widget 自己的
# -bg 决定**，而由样式表（clam 主题）的 style lookup 决定；widget.configure(bg=...)
# 会被直接忽略。所以要让 hover / press 产生平滑渐变，只能**改样式表本身**。
#
# 做法：给每个控件发一个专属样式名（继承它的原样式），把它的 'background'
# 补间到目标色。样式名唯一 → 只影响这一个控件，不波及同款按钮。
class StyleTween(Tween):
    """对 ttk 样式表的某个属性做补间（而不是 widget 选项）。

    ⚠️ Tween 的 after 调度走 root.after，但探针/后台线程里 Tk 可能不在
    主循环；这里把 after 调用包一层保护，调度失败直接落终值并收工，
    绝不把补间卡在中间态。
    """

    def __init__(self, app, stylename, attr, c0, c1, ms, on_done=None):
        self.stylename = stylename
        self._style = app.style
        super(StyleTween, self).__init__(
            app, app.root, attr, c0, c1, ms, on_done=on_done)

    def _schedule(self, fn):
        """排下一帧；root.after 不可用时直接落终值收工，绝不卡在中间态。"""
        try:
            self._job = self.app.root.after(16, fn)
        except Exception:
            self._job = None
            try:
                self._style.configure(self.stylename,
                                      **{self.attr: self.c1})
            except Exception:
                pass
            self._done()

    def _done(self):
        self._job = None
        if self.on_done:
            try:
                self.on_done()
            except Exception:
                pass

    def _step(self):
        try:
            el = (time.monotonic() - self._t0) * 1000.0
        except Exception:
            return
        t = min(1.0, el / self.ms)
        col = _lerp_hex(self.c0, self.c1, _ease_out(t))
        try:
            self._style.configure(self.stylename, **{self.attr: col})
        except Exception:
            self.cancel()
            return
        if t >= 1.0:
            self._done()
            return
        self._schedule(self._step)


def ensure_anim_style(app, widget, base_style):
    """给控件发一个专属样式名（幂等），返回 (stylename, st)。

    继承 base_style 的全部外观，只是名字独立，补间时互不干扰。
    注意 ttk 控件没有 style() 配置项，widget.cget('style') 会报
    unknown option —— 调用方必须把 base_style 显式传进来。
    """
    st = app.style
    sn = getattr(widget, '_ark_style', None)
    if not sn:
        sn = '%s.Anim%d' % (base_style, id(widget))
        # 起始外观 = 基样式当前外观（含 active/pressed/disabled 映射）
        try:
            cur = st.lookup(base_style, 'background')
            if cur:
                st.configure(sn, background=cur)
        except Exception:
            pass
        try:
            st.map(sn, **st.map(base_style))
        except Exception:
            pass
        widget._ark_style = sn
        widget._ark_base_style = base_style
        try:
            widget.configure(style=sn)
        except Exception:
            pass
    return sn, st
