# -*- coding: utf-8 -*-
"""明日方舟鼠标 · 指针与鼠标参数

两个页签：
  「指针大小」  把 17 个系统指针角色按任意像素尺寸装进系统（等价于游戏里
                的「鼠标指针比例设置」，默认 1.20× = 115px 就是游戏 0.75 观感）
  「鼠标参数」  速度 / 加速 / 双击 / 滚轮 / 轨迹 / 左右键 / 吸附 / 隐藏 /
                阴影 / 点击锁定，附带一键备份还原

命令行：
  main.pyw                     打开界面
  main.pyw --apply 1.20        静默应用到 1.20×（开机自启用）
  main.pyw --restore           恢复 Windows 原本的文件光标
  main.pyw --install large     安装指针（小 / 中 / 大）
"""
import os
import sys
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk

from PIL import Image, ImageDraw, ImageTk

import artpack
import cursorwin as cw
import mousep
import paths
import store

# 深色主题：冷灰蓝底 + 明日方舟金（#f5c451）点缀。
# 下列取值为 WCAG 相对亮度实测结果：正文 ≥4.5:1、次要文字 ≥4.5:1、
# 禁用文字 ≥3:1、描边与层级 ≥1.6:1。改色前请先复算，不要凭肉眼判断。
BG = '#0f1218'     # 窗口底
BG2 = '#1b202d'    # 次级底（兼容旧引用）
CARD = '#1b202d'   # 卡片面板（对窗口底 1.15:1，卡片能从背景里浮起来）
EDGE = '#3d4661'   # 卡片 / 控件描边（对卡片 1.74:1）
EDGE_H = '#5b6785'  # 描边（悬停 / 聚焦，对卡片 2.88:1）
RAISE = '#2b3344'  # 控件底
RAISE_H = '#353e52'  # 控件底（悬停）
RAISE_P = '#414c63'  # 控件底（按下）
TAB_ACTIVE = '#222836'  # 未选中页签的悬停底
WELL = '#0b0e13'   # 内凹槽
FG = '#eceef4'
FG2 = '#b8bfcd'
DIM = '#8b93a8'
DIS_BG = '#202634'  # 禁用控件底
DIS_FG = '#7e879c'  # 禁用控件文字（对禁用底 4.2:1，旧值 #5a6070 仅 2.62:1）
ACC = '#f5c451'
ACC_D = '#d9a93c'
ACC_H = '#ffd66e'
ACC_INK = '#241c07'  # 金底上的深色字
OK = '#5fd18b'
BAD = '#ef6f6f'
FONT = 'Microsoft YaHei UI'

PREVIEW = 400   # 预览画布边长（正方形，4.00× = 384px 也不裁切）

TIERS = [('small', '小', '48px · 精致'),
         ('medium', '中', '68px · 标准'),
         ('p72', '72px', '72px · 0.75×'),
         ('large', '大', '96px · 原生')]


# ---------------------------------------------------------------- 预览画布
def make_preview(pack, key, scale, canvas_px):
    """把某个角色按 scale 合成到画布上，返回 PIL Image（棋盘底 + 红十字热点）。"""
    im = Image.new('RGBA', (canvas_px, canvas_px), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    c = 14
    for y in range(0, canvas_px, c):
        for x in range(0, canvas_px, c):
            col = (31, 35, 45, 255) if ((x // c + y // c) % 2 == 0) else \
                  (24, 27, 35, 255)
            d.rectangle([x, y, x + c - 1, y + c - 1], fill=col)

    frames = pack.frames(key)
    if frames:
        art = frames[0][0]
        hs96 = pack.hotspot(key) or (0, 0)
        size = max(4, int(round(cw.NATIVE * scale)))
        art = cw.premul_resize(art, size)
        hx = int(round(hs96[0] * size / cw.NATIVE))
        hy = int(round(hs96[1] * size / cw.NATIVE))
        # 让热点落在画布中心
        ox = canvas_px // 2 - hx
        oy = canvas_px // 2 - hy
        im.alpha_composite(art, (ox, oy))
    else:
        d.text((10, 10), '找不到美术资源\n%s' % (paths.find_art() or 'art.bin'),
               fill=(255, 120, 120, 255))

    # 32px 系统默认：右下角一个参考方框，标签靠右排在方框上方，避免压线。
    ref = 32
    bx1 = by1 = canvas_px - 16
    bx0 = by0 = bx1 - ref
    d.rectangle([bx0, by0, bx1, by1], outline=(96, 103, 122, 255))
    d.text((bx1, by0 - 5), '32px 系统默认', fill=(122, 129, 148, 255), anchor='rs')

    # 热点十字（画布中心）：红准星 + 中心亮点
    mx = my = canvas_px // 2
    d.line([mx - 12, my, mx + 12, my], fill=(236, 92, 92, 255), width=1)
    d.line([mx, my - 12, mx, my + 12], fill=(236, 92, 92, 255), width=1)
    d.ellipse([mx - 2, my - 2, mx + 2, my + 2], fill=(255, 120, 120, 255))
    return im.convert('RGB')


# ---------------------------------------------------------------- 主界面
class App(object):
    def __init__(self, root):
        self.root = root
        self.saved = store.load()
        self.scale = float(self.saved.get('scale', 1.20))
        self.pack = None
        self.art_err = ''
        ap = paths.find_art()
        if ap:
            try:
                self.pack = artpack.load(ap)
            except Exception as e:
                self.art_err = '%s: %s' % (ap, e)
        else:
            self.art_err = '找不到 art.bin'
        self.eng = cw.Engine()
        self.photo = None
        self.busy = False
        self._djobs = {}          # 滑杆防抖定时器（见 _debounce）
        self.guard_alive = False  # 守护进程状态（refresh_guard 里更新）
        self._scrolls = []        # 可滚动页签的 (内容容器, 画布) 对
        self.STATUS_MAX = 96      # 状态栏单行字数上限（见 say()）

        root.title('明日方舟鼠标 · 指针与鼠标参数')
        root.configure(bg=BG)
        self._style()
        self._build()

        # 窗口尺寸：以前是 resizable(False, False) 且没有 geometry()，尺寸完全
        # 由内容撑开。内容一涨、或换到 1366x768 的笔记本（扣掉任务栏只剩约
        # 728px 可用高），窗口就被裁掉，而且用户连拖都拖不动。
        # 现在：可缩放 + 首屏自动收进可用区域 + 下限不小于页签内容的请求尺寸。
        root.resizable(True, True)
        root.update_idletasks()
        w, h = root.winfo_reqwidth(), root.winfo_reqheight()
        max_w = max(480, root.winfo_screenwidth() - 80)    # 给窗口装饰留余量
        max_h = max(420, root.winfo_screenheight() - 120)  # 给任务栏留余量
        gw, gh = min(w, max_w), min(h, max_h)
        if (gw, gh) != (w, h):
            root.geometry('%dx%d' % (gw, gh))
        # 下限只保「能用」：宽度给足（横向滚动很难用），高度留一个能看清
        # 卡片的最小值即可 —— 内容已经套了滚动容器，不该再拿内容高度当地板，
        # 否则窗口永远缩不下去，滚动条也就永远没机会出现。
        need_w = max(inner.winfo_reqwidth() for inner, _ in self._scrolls) + 48
        root.minsize(min(need_w, gw), min(560, gh))

        self.root.protocol('WM_DELETE_WINDOW', self.on_close)
        self.refresh_preview()
        self.refresh_mouse()
        self.refresh_guard()
        self.after_idle_check()

    # ---- 样式 ----
    def _style(self):
        st = ttk.Style()
        try:
            st.theme_use('clam')
        except Exception:
            pass
        F = FONT

        # 基线
        st.configure('.', background=BG, foreground=FG, font=(F, 10))

        # ---- 标签 ----
        # 注意：ttk 控件在 style='' 时按**类名**（TLabel/TButton/...）查样式，
        # 带 'T.' 前缀的名字只在做基类继承时才有意义。这里以前写的是
        # 'T.TLabel' / 'T.TButton' / 'T.TCheckbutton' / 'T.TNotebook'，
        # 没有任何控件引用 → 全部是死代码。下面统一用裸类名。
        st.configure('TLabel', background=BG, foreground=FG, font=(F, 10))
        # 弹窗里用的两个（有控件显式引用，是活的）
        st.configure('H.TLabel', background=BG, foreground=FG,
                     font=(F, 13, 'bold'))
        st.configure('D.TLabel', background=BG, foreground=DIM, font=(F, 9))
        # 卡片内的标签（背景跟着卡片走）
        st.configure('CardD.TLabel', background=CARD, foreground=DIM,
                     font=(F, 9))
        st.configure('CardV.TLabel', background=CARD, foreground=OK,
                     font=(F, 10, 'bold'))

        # ---- 按钮（深色底 + 细描边，去掉 clam 默认的浅灰立体感）----
        # 坑：clam 的 Button.border 元素在 relief='flat' 时**根本不画边框**，
        # 此时 bordercolor 被静默忽略。实测（同尺寸按钮，扫描左边缘像素）：
        #   relief='flat'  + borderwidth=1 → 整条边都是底色，无边框
        #   relief='flat'  + borderwidth=2 → 同上，无边框
        #   relief='solid' + borderwidth=1 → 1px bordercolor 边框，正常
        # 所以「幽灵按钮」Chip.TButton 因为底色 = 卡片色，会彻底退化成裸文字
        # （用户看到的「小框不见了」）。必须用 solid 才能让描边真正落笔。
        st.configure('TButton', background=RAISE, foreground=FG,
                     bordercolor=EDGE, lightcolor=RAISE, darkcolor=RAISE,
                     borderwidth=1, relief='solid',
                     focusthickness=2, focuscolor=ACC,
                     padding=(14, 7), anchor='center', font=(F, 10))
        st.map('TButton',
               background=[('disabled', DIS_BG), ('pressed', RAISE_P),
                           ('active', RAISE_H)],
               foreground=[('disabled', DIS_FG)],
               bordercolor=[('focus', ACC), ('active', EDGE_H)])

        # 主按钮：金底深字
        st.configure('Accent.TButton', background=ACC, foreground=ACC_INK,
                     bordercolor=ACC, lightcolor=ACC, darkcolor=ACC,
                     focusthickness=2, focuscolor=ACC_INK,
                     font=(F, 10, 'bold'))
        st.map('Accent.TButton',
               background=[('disabled', DIS_BG), ('pressed', ACC_D),
                           ('active', ACC_H)],
               foreground=[('disabled', DIS_FG)],
               bordercolor=[('pressed', ACC_D), ('active', ACC_H)])

        # 幽灵按钮：贴在卡片上，悬停才亮起描边
        st.configure('Chip.TButton', background=CARD, foreground=FG2,
                     bordercolor=EDGE, lightcolor=CARD, darkcolor=CARD,
                     focusthickness=2, focuscolor=ACC,
                     padding=(8, 6), font=(F, 9))
        st.map('Chip.TButton',
               background=[('disabled', DIS_BG), ('pressed', RAISE_P),
                           ('active', RAISE)],
               foreground=[('active', FG), ('disabled', DIS_FG)],
               bordercolor=[('focus', ACC), ('active', EDGE_H)])
        # 被推荐的档位：金描边 + 金字
        st.configure('ChipAccent.TButton', background=CARD, foreground=ACC,
                     bordercolor=ACC, lightcolor=CARD, darkcolor=CARD,
                     focusthickness=2, focuscolor=ACC,
                     padding=(8, 6), font=(F, 9, 'bold'))
        st.map('ChipAccent.TButton',
               background=[('disabled', DIS_BG), ('pressed', RAISE_P),
                           ('active', RAISE)],
               foreground=[('disabled', DIS_FG)],
               bordercolor=[('active', ACC_H)])

        # ---- 复选 ----
        # 两条坑：
        # 1) indicatorcolor / indicatordarkcolor 是**静默空操作**（ttk 接受但
        #    不渲染）。真正生效的是 indicatorbackground / indicatorforeground
        #    / upperbordercolor / lowerbordercolor / indicatorsize / indicatormargin。
        # 2) clam 主题对 indicatorbackground 自带一条 selected→蓝色 #4772b3 的
        #    映射，不显式覆盖的话勾选态永远是蓝的。
        st.configure('TCheckbutton', background=CARD, foreground=FG,
                     focusthickness=2, focuscolor=ACC, padding=(2, 4),
                     font=(F, 10),
                     indicatorsize=18, indicatormargin=(1, 1, 8, 1),
                     indicatorbackground=WELL, indicatorforeground=ACC,
                     upperbordercolor=EDGE, lowerbordercolor=EDGE,
                     indicatorrelief='flat')
        st.map('TCheckbutton',
               background=[('active', CARD)],
               indicatorbackground=[('selected', ACC), ('disabled', DIS_BG)],
               indicatorforeground=[('selected', ACC_INK),
                                    ('disabled', DIS_FG)],
               upperbordercolor=[('selected', ACC), ('focus', ACC)],
               lowerbordercolor=[('selected', ACC), ('focus', ACC)],
               foreground=[('disabled', DIS_FG)])

        # ---- 页签 ----
        st.configure('TNotebook', background=BG, borderwidth=0,
                     tabmargins=(2, 4, 2, 0), focuscolor=BG)
        st.configure('TNotebook.Tab', background=BG, foreground=DIM,
                     padding=(22, 9), borderwidth=0, font=(F, 10),
                     lightcolor=BG, darkcolor=BG, bordercolor=BG)
        st.map('TNotebook.Tab',
               background=[('selected', CARD), ('active', TAB_ACTIVE)],
               foreground=[('selected', ACC), ('active', FG2)],
               lightcolor=[('selected', ACC)], darkcolor=[('selected', ACC)],
               expand=[('selected', (0, 0, 0, 0))])

        # ---- 滑杆（ttk：金色滑块 + 深色轨槽）----
        st.configure('TScale', background=ACC, troughcolor=WELL,
                     bordercolor=EDGE, lightcolor=ACC, darkcolor=ACC,
                     borderwidth=0, sliderlength=26, sliderrelief='flat',
                     gripcount=0)
        st.map('TScale',
               background=[('disabled', DIS_FG), ('pressed', ACC_D),
                           ('active', ACC_H)],
               lightcolor=[('disabled', DIS_FG), ('pressed', ACC_D),
                           ('active', ACC_H)],
               darkcolor=[('disabled', DIS_FG), ('pressed', ACC_D),
                          ('active', ACC_H)],
               troughcolor=[('disabled', DIS_BG)])

        st.configure('TFrame', background=BG)

        # ---- 滚动条（页签内容超高时才出现，见 _scrollable）----
        for orient in ('Vertical', 'Horizontal'):
            st.configure('%s.TScrollbar' % orient, background=RAISE,
                         troughcolor=WELL, bordercolor=EDGE, arrowcolor=DIM,
                         darkcolor=RAISE, lightcolor=RAISE, borderwidth=0,
                         arrowsize=13, width=11, relief='flat', gripcount=0)
            st.map('%s.TScrollbar' % orient,
                   background=[('pressed', RAISE_P), ('active', RAISE_H)],
                   darkcolor=[('pressed', RAISE_P), ('active', RAISE_H)],
                   lightcolor=[('pressed', RAISE_P), ('active', RAISE_H)],
                   arrowcolor=[('pressed', ACC), ('active', ACC)])

    # ---- 可滚动容器 ----
    def _descendants(self, widget):
        out = []
        for child in widget.winfo_children():
            out.append(child)
            out.extend(self._descendants(child))
        return out

    def _auto_sb(self, sb, first, last, axis):
        """滚动条按需显示：内容装得下就藏起来，不白占一条边。"""
        need = not (float(first) <= 0.0 and float(last) >= 1.0)
        if need and not sb.winfo_ismapped():
            if axis == 'y':
                sb.grid(row=0, column=1, sticky='ns')
            else:
                sb.grid(row=1, column=0, sticky='ew')
        elif not need and sb.winfo_ismapped():
            sb.grid_remove()

    def _scroll_bind(self, widget, cv):
        """把滚轮绑到画布及其全部后代。

        刻意不 bind_all —— 那样会抢走别的控件的滚轮事件。绑定在建好之后再
        递归做一遍，是因为控件树此时才完整。
        """
        def on_wheel(e):
            if e.state & 0x1:      # Shift + 滚轮 → 横向
                cv.xview_scroll(-1 * (e.delta // 120), 'units')
            else:
                cv.yview_scroll(-1 * (e.delta // 120), 'units')
            return 'break'

        for w in [widget] + self._descendants(widget):
            try:
                w.bind('<MouseWheel>', on_wheel)
            except Exception:
                pass

    def _scrollable(self, parent):
        """把页签内容包进「按需滚动」的容器。

        背景：窗口过去不可缩放、尺寸完全由内容撑开，一旦内容高于屏幕可用高
        度（1366x768 笔记本扣掉任务栏只剩约 728px，而优化后内容要 851px），
        底部卡片就永远看不到，用户也无从补救。这里给页签套一层画布：装得下
        时滚动条自动隐藏，装不下时自动出现。
        """
        wrap = tk.Frame(parent, bg=BG)
        wrap.pack(fill='both', expand=True)
        wrap.rowconfigure(0, weight=1)
        wrap.columnconfigure(0, weight=1)

        cv = tk.Canvas(wrap, bg=BG, highlightthickness=0, bd=0)
        cv.grid(row=0, column=0, sticky='nsew')
        vs = ttk.Scrollbar(wrap, orient='vertical', command=cv.yview)
        hs = ttk.Scrollbar(wrap, orient='horizontal', command=cv.xview)
        cv.configure(yscrollcommand=lambda f, l: self._auto_sb(vs, f, l, 'y'),
                     xscrollcommand=lambda f, l: self._auto_sb(hs, f, l, 'x'))

        # 给两条滚动条**永久预留**槽位（各 13px）。
        #
        # 不这样做的话，滚动条靠 grid/grid_remove 出现与消失，会把它占的
        # 13px 从画布身上借走又还回来：窗口一缩到阈值，竖条出现 → 画布
        # 1156→1143 → 所有卡片整体横移 13px；再拖回去又弹回来。用户描述
        # 的「拖动窗口边缘时各个框都在动」就是这一跳（实测每档只有 1 次
        # 状态突变，是确定性的单向阶跃，不是振荡）。
        # minsize 常驻后，第 1 列/行 的宽度只由这个常量决定，与滚动条本身
        # 是否显示彻底解耦，画布宽度也就只由窗口决定。
        SB_W = 13
        wrap.columnconfigure(1, minsize=SB_W)
        wrap.rowconfigure(1, minsize=SB_W)

        inner = tk.Frame(cv, bg=BG)
        win = cv.create_window((0, 0), window=inner, anchor='nw')

        def sync(_e=None):
            # 内层宽度始终跟随视口，让 fill='x' 的卡片随窗口重排。
            #
            # 以前写的是 max(视口宽, 内容自然宽)，会自激成环：窗口一缩小 →
            # 竖滚动条出现并吃掉 13px → 视口(1143) 反而小于内容自然宽(1156)
            # → 判定内容超宽 → 横滚动条出现 → 又吃掉 13px 高度 → 内容更放
            # 不下。两条滚动条于是随每一像素的拖拽反复出现/消失，卡片跟着
            # 左右跳动——即「拖动窗口边缘时各个框都在动」。改成跟随视口后，
            # 内层宽度不再依赖滚动条状态，环就断了。
            vw = cv.winfo_width()
            if vw > 1:                      # 首次布局前会报成 1，跳过
                cv.itemconfigure(win, width=vw)
            cv.configure(scrollregion=cv.bbox('all'))

        inner.bind('<Configure>', sync)
        cv.bind('<Configure>', sync)
        self._scrolls.append((inner, cv))
        return inner
    # ---- 布局 ----
    def _card(self, parent, title=None, sub=None, padx=14, pady=(0, 10),
              sub_wrap=760):
        """一张卡片：深色面板 + 细描边 + 可选标题/副标题。"""
        outer = tk.Frame(parent, bg=CARD, highlightbackground=EDGE,
                         highlightthickness=1)
        outer.pack(fill='x', padx=padx, pady=pady)
        box = tk.Frame(outer, bg=CARD)
        box.pack(fill='x', padx=16, pady=13)
        if title:
            tk.Label(box, text=title, bg=CARD, fg=ACC,
                     font=(FONT, 10, 'bold')).pack(anchor='w')
        if sub:
            tk.Label(box, text=sub, bg=CARD, fg=DIM, font=(FONT, 9),
                     justify='left', wraplength=sub_wrap).pack(anchor='w',
                                                               pady=(3, 0))
        return box

    def _header(self, parent, title, sub):
        head = tk.Frame(parent, bg=BG)
        head.pack(fill='x', padx=16, pady=(14, 10))
        tk.Label(head, text=title, bg=BG, fg=FG,
                 font=(FONT, 15, 'bold')).pack(anchor='w')
        tk.Label(head, text=sub, bg=BG, fg=DIM, font=(FONT, 9),
                 justify='left', wraplength=780).pack(anchor='w', pady=(4, 0))
        return head

    def _build(self):
        nb = ttk.Notebook(self.root)
        self.nb = nb
        nb.pack(fill='both', expand=True, padx=10, pady=(8, 4))

        self.tab_size = ttk.Frame(nb)
        self.tab_mouse = ttk.Frame(nb)
        nb.add(self.tab_size, text='指针大小')
        nb.add(self.tab_mouse, text='鼠标参数')

        self._build_size_tab(self._scrollable(self.tab_size))
        self._build_mouse_tab(self._scrollable(self.tab_mouse))

        # 画布默认没有内容尺寸，得手动把内层内容的请求尺寸回填给它，否则
        # 窗口的请求尺寸会塌成画布默认值，大屏幕上也会顶出一条滚动条。
        # 必须先 update_idletasks：否则 winfo_reqwidth() 还没算出来（返回 1）。
        self.root.update_idletasks()
        for inner, cv in self._scrolls:
            cv.configure(width=inner.winfo_reqwidth(),
                         height=inner.winfo_reqheight())
            self._scroll_bind(inner, cv)
        self.root.update_idletasks()

        foot = tk.Frame(self.root, bg=BG, highlightbackground=EDGE,
                        highlightthickness=0)
        foot.pack(fill='x', padx=14, pady=(0, 10))
        # 状态栏是**根窗口的直接子控件**，它请求多宽，窗口就能被撑多宽。
        # 不设限时一条长消息能把窗口从 1061 撑到 2032（实测 200 字符下
        # 推动 41 个控件）。两道防线：
        #   wraplength 封住**请求宽度**（这是根治点：标签请求宽不再随
        #   文案长度增长），height=1 钉死高度（换行若让 foot 长高 →
        #   Notebook 被压矮 → 竖滚动条越界出现/消失 → 又变成内容横移）；
        #   say() 里再按字数截断，保证正常文案永远一行显示完、不被裁。
        self.status = tk.Label(foot, text='就绪', anchor='w', bg=BG,
                               fg=DIM, font=(FONT, 9), justify='left',
                               wraplength=760, height=1)
        self.status.pack(fill='x')
        hint = ('本工具只调用 Windows 系统接口，不读取、不修改游戏目录。'
                '所有改动都只影响当前用户，随时可一键还原。')
        # 旧值 fg='#5f6577' + 8pt：对窗口底只有 3.2:1，低于正文 4.5:1 的门槛，
        # 是全窗口最难读的一行。改用 DIM 令牌（对 BG 6.1:1）并抬到 9pt。
        tk.Label(foot, text=hint, anchor='w', bg=BG, fg=DIM,
                 font=(FONT, 9), wraplength=760,
                 justify='left').pack(fill='x', pady=(3, 0))

    # ============================================ 页签一：指针大小
    def _build_size_tab(self, f):
        self._header(
            f, '指针大小',
            '和游戏里「鼠标指针比例设置」同一个玩法 —— 但它管的是整台电脑的指针。'
            '滑杆数值 = 屏幕上的实际像素比例。')
        body = tk.Frame(f, bg=BG)
        body.pack(fill='both', expand=True)
        left = tk.Frame(body, bg=BG)
        left.pack(side='left', fill='y')
        # ⚠️ 左栏宽度必须**由常量钉死**，不能由内容撑开。
        #
        #    这是「拖滑杆整页在动」的根治点。左栏原先是 side='left' 且
        #    宽度取自子控件的自然宽度，于是卡片里任何一行文字变长
        #    （预览主行的「0.25× · 24×24 px · 热点 (n, n)」、
        #    「桌面实际…✓/✗」）都会把左栏撑宽 → 右栏被挤着右移 →
        #    尺寸 chip、复选框、按钮整列横移（实测 132 个控件里 36 个
        #    跟着动）。
        #
        #    只给标签加 wraplength 治不干净：wraplength 是**文本换行
        #    宽度**，不含卡片自身的 padx=16×2、highlightthickness、
        #    画布描边，所以 wraplength=400 的标签仍会请求 406px，照样
        #    撑宽 4px（灌超长文字实测仍推动 36 个控件）。
        #
        #    真正的解法：pack_propagate(False) 关掉尺寸传递，宽度只认
        #    这里的配置值。LEFT_W = 画布 PREVIEW(400) + 画布描边 2
        #    + 卡片内边距 32 + 卡片描边 2 + 卡片外边距 21 = 457，
        #    与改动前的实测宽度一致，外观零变化。
        left.configure(width=PREVIEW + 57)
        left.pack_propagate(False)
        right = tk.Frame(body, bg=BG)
        right.pack(side='left', fill='both', expand=True)

        # ---- 预览（左栏）----
        c = self._card(left, '预览',
                       '默认 1.20×（115px）= 游戏内「指针比例 0.75」的观感。',
                       padx=(14, 7), sub_wrap=396)
        cv = tk.Canvas(c, width=PREVIEW, height=PREVIEW, bg=WELL,
                       highlightthickness=1, highlightbackground=EDGE)
        cv.pack(pady=(10, 10))
        self.cv = cv
        # ⚠️ 这一行也必须有固定的 wraplength / height。
        #    它显示「0.25× · 24×24 px · 热点 (n, n)」这类会随滑杆变长的
        #    文字（实测 283→333px）。没有 wraplength 时它会自由撑宽 →
        #    撑宽左栏 → 把右栏整列横向推走（灌入超长文字实测推动 11 个
        #    控件，左栏从 457 涨到 1021px）。锁死宽度后，文字再长也只在
        #    自己格子里换行，左右栏宽度只由常量决定。
        self.lbl = tk.Label(c, text='', bg=CARD, fg=ACC,
                            font=(FONT, 12, 'bold'),
                            justify='left', anchor='w',
                            wraplength=PREVIEW, height=2)
        self.lbl.pack(anchor='w', fill='x')
        # 一眼看出「滑杆设定」和「桌面实际」是否一致 ——
        # 这正是最初那个「游戏里大、桌面小」困惑的答案。
        #
        # ⚠️ wraplength 与 height 必须固定，否则拖滑杆时整页都在动：
        #    这行文案在「✓ 与设定一致」（205px）与「✗ 与设定不符（设定
        #    384px）…」（446px）之间来回变，且换数字还会继续变长。标签
        #    没有 wraplength 就会自由撑宽 → 撑宽左栏 → 把右栏整列（含
        #    尺寸 chip、复选框、按钮）横向推走 44px，实测 132 个控件里
        #    有 36 个跟着位移。固定成「最多 2 行、宽度不超过预览画布」后，
        #    左右栏宽度都只由常量决定，与文字长短彻底无关。
        self.lbl_now = tk.Label(c, text='', bg=CARD, fg=DIM,
                                font=(FONT, 9), justify='left', anchor='w',
                                wraplength=396, height=2)
        self.lbl_now.pack(anchor='w', pady=(4, 0), fill='x')

        # ---- 尺寸调节 ----
        c = self._card(right, '尺寸调节', padx=(7, 14))
        self.sc = ttk.Scale(c, from_=0.25, to=4.00, orient='horizontal',
                            command=self.on_slide)
        self.sc.set(self.scale)
        self.sc.pack(fill='x', pady=(10, 4))
        btns = [('★ 1.20× 游戏内', 1.20, 'ChipAccent.TButton'),
                ('1.00× · 96px', 1.00, 'Chip.TButton'),
                ('0.33× · 32px', 32.0 / cw.NATIVE, 'Chip.TButton'),
                ('1.50× · 144px', 1.50, 'Chip.TButton'),
                ('2.00× · 192px', 2.00, 'Chip.TButton')]
        bf = tk.Frame(c, bg=CARD)
        bf.pack(fill='x', pady=(8, 0))
        for i in range(3):
            bf.columnconfigure(i, weight=1, uniform='chip')
        for i, (txt, v, style) in enumerate(btns):
            ttk.Button(bf, text=txt, style=style,
                       command=lambda x=v: self.set_scale(x)).grid(
                row=i // 3, column=i % 3,
                padx=(0 if i % 3 == 0 else 4, 0),
                pady=(0 if i < 3 else 4, 0), sticky='ew')

        # ---- 效果与启动 ----
        c = self._card(right, '效果与启动', padx=(7, 14))
        self.v_anim = tk.BooleanVar(value=bool(self.saved.get('animate', True)))
        self.v_auto = tk.BooleanVar(value=store.get_autostart())
        self.v_press = tk.BooleanVar(
            value=bool(self.saved.get('click_anim', True)))
        self.v_idle = tk.BooleanVar(
            value=bool(self.saved.get('idle_prts', True)))
        self.v_claw = tk.BooleanVar(
            value=bool(self.saved.get('drag_claw', True)))
        cf = tk.Frame(c, bg=CARD)
        cf.pack(fill='x', pady=(8, 0))
        cf.columnconfigure(0, weight=1)
        cf.columnconfigure(1, weight=1)
        ttk.Checkbutton(cf, text='启用动画（忙 / 后台 / 调整）',
                        variable=self.v_anim,
                        command=self.on_anim).grid(row=0, column=0, sticky='w')
        ttk.Checkbutton(cf, text='开机自动启动（含守护）',
                        variable=self.v_auto,
                        command=self.on_auto).grid(row=0, column=1, sticky='w')
        # 手感类效果：不重开程序、不重开机，点一下立刻生效
        # 标签跟着当前风格走 —— prts 用 fx.bin 里 PRTS 自己的原帧（逐帧烘死的
        # 非均匀挤压，不是倍率缩放）；game 是游戏原版 PCMouseHandler 的 0.75~1.25×。
        _st = str(self.saved.get('click_style') or 'prts').strip().lower()
        if _st not in cw.CLICK_STYLES:
            _st = 'prts'
        _sk = cw.CLICK_STYLES[_st]
        _tip = ('游戏原版 %.2f×~%.2f×' if _st == 'game' else 'PRTS 原帧 %.2f×~%.2f×') \
            % (_sk['min_scale'], _sk['max_scale'])
        ttk.Checkbutton(cf, text='点击挤压（%s）' % _tip,
                        variable=self.v_press,
                        command=self.on_fx).grid(row=1, column=0, sticky='w',
                                                 pady=(4, 0))
        ttk.Checkbutton(cf, text='待机动画（静止后指针动起来）',
                        variable=self.v_idle,
                        command=self.on_fx).grid(row=1, column=1, sticky='w',
                                                 pady=(4, 0))
        ttk.Checkbutton(cf, text='拖动爪子（拖窗口时变手爪）',
                        variable=self.v_claw,
                        command=self.on_fx).grid(row=2, column=0, sticky='w',
                                                 pady=(4, 0))

        # ---- 指针守护 ----
        c = self._card(right, '指针守护',
                       '常驻进程，被系统重置时自动恢复指针。',
                       padx=(7, 14), sub_wrap=560)
        gf = tk.Frame(c, bg=CARD)
        gf.pack(fill='x', pady=(10, 0))
        self.lbl_guard = ttk.Label(gf, text='检测中…',
                                   style='CardD.TLabel')
        self.lbl_guard.grid(row=0, column=0, sticky='w')
        gf.columnconfigure(0, weight=1)
        ttk.Button(gf, text='启动守护', style='Chip.TButton',
                   command=self.do_start_guard).grid(row=0, column=1, padx=(0, 4))
        ttk.Button(gf, text='停止守护', style='Chip.TButton',
                   command=self.do_stop_guard).grid(row=0, column=2)

        # ---- 应用与还原 ----
        c = self._card(right, '应用与还原', padx=(7, 14))
        af = tk.Frame(c, bg=CARD)
        af.pack(fill='x', pady=(10, 0))
        for i in range(4):
            af.columnconfigure(i, weight=1, uniform='act')
        ttk.Button(af, text='应用', style='Accent.TButton',
                   command=self.do_apply).grid(row=0, column=0, sticky='ew')
        ttk.Button(af, text='重新应用',
                   command=self.do_reapply).grid(row=0, column=1, padx=(6, 0),
                                                 sticky='ew')
        ttk.Button(af, text='恢复原始光标',
                   command=self.do_restore).grid(row=0, column=2, padx=(6, 0),
                                                 sticky='ew')
        ttk.Button(af, text='读当前桌面尺寸',
                   command=self.do_measure).grid(row=0, column=3, padx=(6, 0),
                                                 sticky='ew')
        sf = tk.Frame(c, bg=CARD)
        sf.pack(fill='x', pady=(6, 0))
        for i in range(4):
            sf.columnconfigure(i, weight=1, uniform='act2')
        ttk.Button(sf, text='安装指针（文件式）',
                   command=self.do_install_pack).grid(row=0, column=0,
                                                      columnspan=2, sticky='ew')
        ttk.Button(sf, text='打开 Windows 鼠标设置',
                   command=mousep.open_system_mouse_panel).grid(
            row=0, column=2, columnspan=2, padx=(6, 0), sticky='ew')

    # ============================================ 页签二：鼠标参数
    def _build_mouse_tab(self, f):
        self._header(
            f, '鼠标参数',
            '改完立即生效，只影响当前用户；每个项目都有一键备份 / 还原。')

        self.mv = {}
        self.mb = {}
        # 本机不支持的开关（见下方 switches 表）——刷新时跳过它们
        self.unsupported_switches = {}

        c = self._card(f, '偏好设置')
        g = tk.Frame(c, bg=CARD)
        g.pack(fill='x', pady=(10, 0))
        # 列 0/1 = 行名与副说明（固定宽度，靠 width=10 与文字决定）
        # 列 2   = 滑杆 / 勾选框（weight=1，吃掉全部剩余宽度）
        # 列 3   = 右侧状态文案（**必须固定宽度**）
        #
        # ⚠️ 列 3 的宽度一定要钉死。它显示「已关闭（原始 1:1）」/
        #    「已开启（阈值 6 / 10）」这类会变的文案；列宽若由内容撑开，
        #    一行文案变长就会把**整列**往外挤 —— weight=1 的滑杆被压短、
        #    下面每一行的状态文字跟着右移。实测「指针加速」一开一关，
        #    页签二有 16 个控件横向位移 17px。给它一个固定的
        #    width（字符数）后，文字再长也只在自己格子里截断/留白，
        #    绝不推动任何邻居。
        g.columnconfigure(2, weight=1)
        st = [0]            # 当前行号（可变）

        # 状态列固定宽度：够放最长的「已关闭（原始 1:1）」与
        # 「本机不支持」，再长也不撑列。
        STATUS_W = 22

        def group(title):
            i = st[0]
            tk.Frame(g, bg=EDGE, height=1).grid(
                row=i, column=0, columnspan=4, sticky='ew', pady=(10, 7))
            tk.Label(g, text=title, bg=CARD, fg=ACC,
                     font=(FONT, 9, 'bold')).grid(
                row=i + 1, column=0, columnspan=4, sticky='w', pady=(0, 2))
            st[0] = i + 2

        def row_label(txt, sub=''):
            i = st[0]
            tk.Label(g, text=txt, bg=CARD, fg=FG, width=10, anchor='w',
                     font=(FONT, 10)).grid(row=i, column=0, sticky='w',
                                           pady=2)
            tk.Label(g, text=sub, bg=CARD, fg=DIM, anchor='w',
                     font=(FONT, 9)).grid(row=i, column=1, sticky='w',
                                          padx=(0, 14), pady=2)
            return i

        def slider(i, key, lo, hi, cmd):
            s = ttk.Scale(g, from_=lo, to=hi, orient='horizontal',
                          length=220, command=cmd)
            s.grid(row=i, column=2, sticky='ew')
            self.mv[key] = s
            # 状态列固定宽度（见上方 STATUS_W 注释）：文字长度变化
            # 不得推动滑杆或任何邻居。
            lb = ttk.Label(g, text='', style='CardD.TLabel', width=STATUS_W,
                           anchor='w')
            lb.grid(row=i, column=3, sticky='w', padx=(14, 0))
            return s, lb

        def switch(i, key, fn, unsup=False):
            var = tk.BooleanVar(value=False)
            cb = ttk.Checkbutton(g, variable=var,
                                 command=lambda k=key, v=var, f=fn:
                                 self._on_switch(k, v, f))
            cb.grid(row=i, column=2, sticky='w')
            if unsup:
                cb.state(['disabled'])
            self.mb[key] = (cb, var)
            self.unsupported_switches[key] = unsup
            lb = ttk.Label(g, text='本机不支持' if unsup else '',
                           style='CardD.TLabel', width=STATUS_W, anchor='w')
            lb.grid(row=i, column=3, sticky='w', padx=(14, 0))
            return cb, var, lb

        # ---- 移动 ----
        group('移动')
        i = row_label('指针速度', '1~20，越大越快')
        _, self.lbl_speed = slider(i, 'speed', 1, 20,
                                   lambda v: self._on_speed(v))
        st[0] = i + 1

        i = row_label('指针加速', '游戏里建议关掉')
        self.var_accel = tk.BooleanVar(value=False)
        _cb = ttk.Checkbutton(g, variable=self.var_accel,
                              command=self._on_accel)
        _cb.grid(row=i, column=2, sticky='w')
        self.mb['accel'] = (_cb, self.var_accel)
        # 与 slider()/switch() 的状态列同宽（STATUS_W）—— 否则这一行的
        # 「已开启（阈值 6 / 10）」会独自把列撑宽，把上面几行的滑杆压短。
        self.lbl_accel = ttk.Label(g, text='', style='CardD.TLabel',
                                   width=STATUS_W, anchor='w')
        self.lbl_accel.grid(row=i, column=3, sticky='w', padx=(14, 0))
        st[0] = i + 1

        i = row_label('鼠标轨迹', '0 = 关闭；2~10 条尾巴')
        _, self.lbl_trail = slider(i, 'trail', 0, 10,
                                   lambda v: self._on_trail(v))
        st[0] = i + 1

        # ---- 点击与滚动 ----
        group('点击与滚动')
        i = row_label('双击速度', '毫秒，越大越慢')
        _, self.lbl_dbl = slider(i, 'dbl', 100, 900,
                                 lambda v: self._on_dbl(v))
        st[0] = i + 1

        i = row_label('滚轮行数', '0 = 一次滚一屏；>0 = 每格几行')
        _, self.lbl_wheel = slider(i, 'wheel', 0, 25,
                                   lambda v: self._on_wheel(v))
        st[0] = i + 1

        i = row_label('悬停时间', '毫秒，停留多久弹出提示')
        _, self.lbl_hover = slider(i, 'hover', 10, 2000,
                                   lambda v: self._on_hover(v))
        st[0] = i + 1

        # ---- 系统开关 ----
        # unsup=True 的两项：本机实测三条写入路径（SPI 传值 / SPI 传址 / 写
        # 注册表+广播）全部无效。与其显示一个假的「已开启」，不如禁用并注明。
        group('系统开关')
        for key, txt, fn, unsup in [
                ('swap', '左右键互换', 'set_swap_buttons', True),
                ('snap', '吸附到默认按钮', 'set_snap_to_default', True),
                ('vanish', '打字时隐藏指针', 'set_mouse_vanish', False),
                ('shadow', '指针阴影', 'set_cursor_shadow', False),
                ('lock', '点击锁定', 'set_click_lock', False)]:
            i = row_label(txt)
            switch(i, key, fn, unsup)
            st[0] = i + 1

        # ---- 备份与还原 ----
        c = self._card(f, '备份与还原')
        bf = tk.Frame(c, bg=CARD)
        bf.pack(fill='x', pady=(10, 0))
        acts = [('刷新读数', self.refresh_mouse),
                ('备份当前设置', self.do_backup),
                ('还原备份', self.do_restore_mouse),
                ('恢复推荐值', self.do_mouse_defaults),
                ('打开系统鼠标设置', mousep.open_system_mouse_panel)]
        for i in range(len(acts)):
            bf.columnconfigure(i, weight=1, uniform='mact')
        for i, (txt, cmd) in enumerate(acts):
            ttk.Button(bf, text=txt, command=cmd).grid(
                row=0, column=i, padx=(0 if i == 0 else 6, 0), sticky='ew')

    # ============================================ 状态
    def say(self, txt, color=DIM):
        # 状态栏在根窗口的最外层：它请求多宽，窗口就能被撑多宽。
        # 实测把这条标签的文案灌到 200 字符时，窗口从 1081 被撑到 2052，
        # 连带推动 41 个控件。异常文本（'美术资源不可用：%s'）长度不可控，
        # 所以在入口截断，让「窗口宽度」与「消息内容」彻底解耦。
        txt = str(txt)
        if len(txt) > self.STATUS_MAX:
            txt = txt[:self.STATUS_MAX - 1] + '…'
        self.status.config(text=txt, fg=color)

    def after_idle_check(self):
        if self.art_err:
            self.say('美术资源不可用：%s' % self.art_err, BAD)
        self.root.after(1200, self._tick)

    def _tick(self):
        """每 2 秒刷新一次「桌面实际」读数，让用户看到守护有没有在干活。"""
        try:
            self.refresh_now()
        except Exception:
            pass
        self.root.after(2000, self._tick)

    # ============================================ 预览
    def refresh_preview(self):
        if not self.pack:
            self.cv.delete('all')
            self.cv.create_text(
                12, 12, anchor='nw', fill=BAD,
                text='找不到自包含美术包 art.bin\n\n%s' % self.art_err,
                font=(FONT, 10))
            self.lbl.config(text='--')
            return
        key = 'Arrow'
        size = int(round(cw.NATIVE * self.scale))
        pix = make_preview(self.pack, key, self.scale, PREVIEW)
        self.photo = ImageTk.PhotoImage(pix)
        self.cv.delete('all')
        self.cv.create_image(PREVIEW // 2, PREVIEW // 2, image=self.photo)
        hx = int(round((self.pack.hotspot(key) or (0, 0))[0] * size / cw.NATIVE))
        hy = int(round((self.pack.hotspot(key) or (0, 0))[1] * size / cw.NATIVE))
        self.lbl.config(text='%.2f×   ·   %d×%d px   ·   热点 (%d, %d)'
                             % (self.scale, size, size, hx, hy))
        self.refresh_now(size)

    def refresh_now(self, want=None):
        """显示桌面【实际】光标尺寸，并和滑杆设定对比。

        这是回答最初那个困惑的核心：游戏里大、桌面小，因为桌面走的是
        Windows 光标，而不是游戏自绘的指针。这一行让两边的差距肉眼可见。
        """
        if want is None:
            want = int(round(cw.NATIVE * self.scale))
        try:
            # ⚠️ 必须用零副作用的 system_cursor_sizes()：LoadCursorW 直接
            # 返回当前系统光标，不碰鼠标。曾用 desktop_cursor_size()，而它
            # 为了绕过「悬停窗口自己的光标」会把鼠标钉到桌面点上 ——
            # 这里每 2 秒跑一次，就成了「鼠标一直被拽走」。
            cur = cw.system_cursor_sizes().get('Arrow')
            cur = cur[0] if cur else None
        except Exception:
            cur = None
        if not cur:
            self.lbl_now.config(text='桌面实际：读取失败', fg=DIM)
            return
        if cur == want:
            self.lbl_now.config(
                text='桌面实际：%d×%d px  ✓ 与设定一致' % (cur, cur), fg=OK)
        else:
            self.lbl_now.config(
                text='桌面实际：%d×%d px  ✗ 与设定不符（设定 %dpx）'
                     ' —— 点「应用」或启动守护' % (cur, cur, want), fg=BAD)

    def on_slide(self, v):
        try:
            # ttk.Scale 给的是连续值；量化到 0.01 档，等价于原来的 resolution。
            self.scale = round(float(v), 2)
        except ValueError:
            return
        self.refresh_preview()

    def set_scale(self, v):
        self.sc.set(v)
        self.scale = float(v)
        self.refresh_preview()

    # ============================================ 动作
    def do_apply(self, quiet=False):
        if self.busy:
            return
        if not self.pack:
            if not quiet:
                messagebox.showerror('无法应用', self.art_err)
            return
        self.busy = True
        self.say('正在生成 %dpx 指针…' % int(round(cw.NATIVE * self.scale)))
        self.root.update_idletasks()
        try:
            import time
            fx = dict(store.fx_settings(self.saved))
            fx['click_anim'] = bool(self.v_press.get())
            fx['idle_prts'] = bool(self.v_idle.get())
            fx['drag_claw'] = bool(self.v_claw.get())
            t0 = time.time()
            n = len(self.eng.build(cw.NATIVE * self.scale, self.pack, fx=fx))
            got = self.eng.apply_all()
            dt = time.time() - t0
            if self.v_anim.get():
                self.eng.start_anim()
            else:
                self.eng.stop_anim()
            # 手感效果必须在 apply_all 之后启动（它的驱动线程负责后续下发）
            f = self.eng.start_fx(fx)
            self.saved.update(fx)
            self.saved['scale'] = self.scale
            self.saved['animate'] = bool(self.v_anim.get())
            store.save(self.saved)
            miss = len(self.pack.roles) - n
            extra = '' if miss <= 0 else ' · %d 个角色无系统接口，未改' % miss
            # 效果描述只有 CursorAnim.describe() 一个来源（以前这里和 CLI 各写
            # 一份 if，删掉待机呼吸时漏改了这份，点应用就抛 AttributeError）。
            feel = f.describe() if f is not None else []
            self.say('已应用 %d 个角色 · %dpx · 耗时 %.1fs%s'
                     % (got, self.eng.size, dt, extra)
                     + (' · ' + ' · '.join(feel) if feel else ' · 手感效果已关'),
                     OK)
        except Exception as e:
            self.say('应用失败：%s' % e, BAD)
            if not quiet:
                messagebox.showerror('应用失败', str(e))
        finally:
            self.busy = False

    def do_reapply(self):
        self.do_apply()

    def do_restore(self):
        if not messagebox.askyesno(
                '恢复原始光标',
                '将恢复到 Windows 原本登记的指针（也就是 32px 的小指针）。\n'
                '之后可以再点「应用」装回来。要继续吗？'):
            return
        n = self.eng.restore_files(cw.REG_CURSORS_PATH)
        self.say('已恢复原始光标（%d 个角色）' % n, OK)

    def do_measure(self):
        r = cw.desktop_cursor_size()
        if r:
            self.say('当前桌面光标：位图 %d×%d，热点 (%d, %d)'
                     % (r[0], r[1], r[2], r[3]), OK)
        else:
            self.say('读不到桌面光标（可能鼠标不在桌面区域）', BAD)

    def do_install_pack(self):
        p = paths.find_pack()
        if not p:
            messagebox.showinfo('未找到指针',
                                '没有找到「指针」目录。\n'
                                '它应该与本程序放在一起。')
            return
        ps1 = os.path.join(p, 'install.ps1')
        if not os.path.isfile(ps1):
            messagebox.showinfo('未找到安装脚本', ps1)
            return
        win = tk.Toplevel(self.root)
        win.title('安装指针（文件式）')
        win.configure(bg=BG)
        win.resizable(False, False)
        ttk.Label(win, text='选择要安装的档位（写注册表，改完需重新登录或刷新）',
                  style='H.TLabel').grid(row=0, column=0, columnspan=3,
                                         padx=16, pady=(12, 4), sticky='w')
        ttk.Label(win, text='注意：文件式指针在本机被系统限制在 32px，'
                            '想要大指针请用「指针大小」页签的「应用」。',
                  style='D.TLabel', wraplength=420,
                  justify='left').grid(row=1, column=0, columnspan=3,
                                       padx=16, sticky='w')
        f = ttk.Frame(win)
        f.grid(row=2, column=0, columnspan=3, padx=16, pady=10)

        def run(tier):
            win.destroy()
            self._run_ps1(ps1, tier)

        for i, (t, zh, desc) in enumerate(TIERS):
            ttk.Button(f, text='%s（%s）' % (zh, desc), width=18,
                       command=lambda x=t: run(x)).grid(row=0, column=i,
                                                        padx=3)
        ttk.Button(f, text='恢复备份', width=18,
                   command=lambda: (win.destroy(),
                                    self._run_ps1(ps1, None, restore=True))
                   ).grid(row=1, column=0, columnspan=3, pady=6)

    def _run_ps1(self, ps1, tier, restore=False):
        import subprocess
        args = ['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass',
                '-File', ps1]
        if restore:
            args.append('-Restore')
        else:
            args += ['-Tier', tier]
        try:
            subprocess.Popen(args, shell=False)
            self.say('已启动 PowerShell 安装脚本：%s' % os.path.basename(ps1))
        except Exception as e:
            self.say('启动失败：%s' % e, BAD)

    def on_anim(self):
        on = bool(self.v_anim.get())
        self.eng.animate = on
        if on:
            self.eng.start_anim()
            self.say('动画已开启', OK)
        else:
            self.eng.stop_anim()
            self.say('动画已关闭（停在当前帧）')
        self.saved['animate'] = on
        store.save(self.saved)

    def on_fx(self):
        """点击挤压 / 待机动画 / 拖动爪子的开关。

        点击挤压和待机动画用到的多套尺寸是在 build 时**预造**好的（运行时
        只换指针、不再光栅化），所以这两个开关一变就必须重新建一次档；
        build 是几秒的活，直接走 do_apply，免得出现「勾了但没档可切、看起
        来毫无反应」。拖动爪子只用固定的一套尺寸，不需要重档，start_fx
        重启驱动线程就能立刻生效。
        """
        fx = dict(store.fx_settings(self.saved))
        fx['click_anim'] = bool(self.v_press.get())
        fx['idle_prts'] = bool(self.v_idle.get())
        fx['drag_claw'] = bool(self.v_claw.get())
        self.saved.update(fx)
        store.save(self.saved)
        built = dict(getattr(self.eng, 'fx_opts', {}) or {})
        cur = (cw.fx_options(built) if built
               else {'click_anim': False, 'idle_prts': False,
                     'drag_claw': False})
        changed = (bool(cur['click_anim']) != fx['click_anim']
                   or bool(cur['idle_prts']) != fx['idle_prts'])
        if changed and self.pack:
            self.do_apply(quiet=True)
            return
        self.eng.start_fx(fx)
        self.say('点击挤压：%s · 待机动画：%s · 拖动爪子：%s'
                 % ('开' if fx['click_anim'] else '关',
                    '开' if fx['idle_prts'] else '关',
                    '开' if fx['drag_claw'] else '关'), OK)

    def on_auto(self):
        on = bool(self.v_auto.get())
        try:
            got = store.set_autostart(on)
            # 权威状态在注册表 Run 键，但也在 设置.json 里留一份，
            # 否则文件里会一直是默认的 False，和实际不符、看着像没生效。
            self.saved['autostart'] = bool(got)
            store.save(self.saved)
            if got:
                # 开了自启就顺手把守护也起起来 —— 否则用户要等到下次重启
                # 才能真正生效，中间这段时间指针还是会被系统重置。
                self.do_start_guard(quiet=True)
                self.say('开机自动启动：已开启（守护已随之启动）', OK)
            else:
                self.say('开机自动启动：已关闭（守护仍在运行，可在下方手动停止）')
            self.refresh_guard()
        except Exception as e:
            self.say('设置开机自启失败：%s' % e, BAD)
            self.v_auto.set(store.get_autostart())

    # ============================================ 守护进程
    def do_start_guard(self, quiet=False):
        """启动常驻守护（已有实例则什么都不做）。"""
        try:
            import guard
            alive, pid, size, scale = guard.guard_status()
            if alive:
                if not quiet:
                    self.say('守护已在运行（pid=%d · %dpx）' % (pid, size), OK)
                return True
            exe_path = os.path.join(paths.APP_DIR, '明日方舟鼠标.exe')
            if getattr(sys, 'frozen', False):
                cmd = [sys.executable, '--guard']
            elif os.path.isfile(exe_path):
                cmd = [exe_path, '--guard']
            else:
                cmd = [sys.executable,
                       os.path.join(paths.APP_DIR, '源码', 'arkmouse',
                                    'main.pyw'), '--guard']
            import subprocess
            # env=paths.child_env()：剥掉 PyInstaller 注入的解包目录变量，别让守护
            # 复用界面的 _MEIxxxxxx —— 否则关界面时引导器删不掉自己的临时目录
            # （被守护占着），会弹「Failed to remove temporary directory」。
            subprocess.Popen(cmd, cwd=paths.APP_DIR, env=paths.child_env(),
                             creationflags=0x00000008)  # DETACHED_PROCESS
            self.root.after(1200, self.refresh_guard)
            if not quiet:
                self.say('已启动守护（它会在后台维护指针大小）', OK)
            return True
        except Exception as e:
            self.say('启动守护失败：%s' % e, BAD)
            return False

    def do_stop_guard(self):
        try:
            import guard
            alive, pid, size, scale = guard.guard_status()
            if not alive:
                self.say('守护没有在运行')
                self.refresh_guard()
                return
            if messagebox.askyesno(
                    '停止守护',
                    '停止后，系统在某些时机（explorer 重启、锁屏解锁、\n'
                    '显示设置变化）会把指针重置回 32px 的系统小指针，\n'
                    '而且不会再自动恢复。\n\n确定要停止守护吗？'):
                guard.kill_guard(pid)
                self.root.after(800, self.refresh_guard)
                self.say('已停止守护', OK)
        except Exception as e:
            self.say('停止守护失败：%s' % e, BAD)

    def refresh_guard(self):
        """刷新守护状态显示；未运行时自动重试几次（刚启动需要时间）。"""
        try:
            import guard
            alive, pid, size, scale = guard.guard_status()
        except Exception:
            alive, pid, size, scale = False, 0, 0, 0.0
        self.guard_alive = alive
        if alive:
            self.lbl_guard.config(
                text='● 运行中（pid=%d · %dpx · %.2f×）'
                     % (pid, size, scale), style='CardV.TLabel')
        else:
            self.lbl_guard.config(
                text='○ 未运行（指针可能被重置回 32px）',
                style='CardD.TLabel')
        self.root.after(2000, self.refresh_guard)

    # ============================================ 鼠标参数回调
    #
    # v2 性能修复（问题4「滚轮没反应」的一半真因）：
    # tk.Scale 的 command 在【拖动过程中每一个像素步进】都触发，而每个 setter
    # 内部都有 sleep + 回读校验，单次 0.35~0.65 s。拖一次滑杆 = 十几秒界面冻结，
    # 用户拖动时看不到任何反馈，自然会认为「设置没反应」。
    # 现在拖动中只做快速写入（verify=False），停止拖动 0.45 s 后才做一次回读校验。
    def _debounce(self, key, fn):
        """取消上一次待执行的校验，安排 450 ms 后执行一次。"""
        job = self._djobs.get(key)
        if job:
            try:
                self.root.after_cancel(job)
            except Exception:
                pass
        self._djobs[key] = self.root.after(450, fn)

    def _verify_async(self, key, work, done):
        """在后台线程里做「松手提交」（写盘 + 广播 + 回读）。

        问题4 的性能真相：SPI 的 404 ms 全部花在 SPIF_SENDCHANGE 广播上。
        拖动中用 flags=0x01（0 ms），松手后必须补一次广播让所有窗口收到
        WM_SETTINGCHANGE —— 但这一次仍要 ~0.7 s。放到后台线程做，
        GUI 才不会在松手瞬间卡住。
        """
        def run():
            try:
                ok = work()
            except Exception:
                ok = False
            self.root.after(0, lambda: done(ok))
        threading.Thread(target=run, daemon=True).start()

    def _on_speed(self, v):
        # 指针速度走 SPI 0x0071；灵敏度写注册表 MouseSensitivity。
        # 两者是同一件事的两条存储路径，一起写才不会互相覆盖。
        n = int(round(float(v)))
        mousep.set_sensitivity(n)
        mousep.set_mouse_speed(n)
        self.lbl_speed.config(text='已设为 %d' % n)

    def _on_accel(self):
        # 注意：Checkbutton 的 command 触发时，variable 已经是【切换后】的新值，
        # 所以这里不能再用 not 取反，否则会变成双重取反、点了等于没点。
        cb, var = self.mb['accel']
        on = bool(var.get())
        if on:
            mousep.set_acceleration(6, 10, 1)
            self.lbl_accel.config(text='已开启（阈值 6 / 10）')
        else:
            mousep.set_acceleration(0, 0, 0)
            self.lbl_accel.config(text='已关闭（原始 1:1）')

    def _on_dbl(self, v):
        n = int(round(float(v) / 10.0) * 10)
        mousep.set_double_click(n, verify=False)
        self.lbl_dbl.config(text='已设为 %d ms' % n)
        self._debounce('dbl', lambda: self._verify_dbl(n))

    def _verify_dbl(self, n):
        # 双击走 SetDoubleClickTime，不经 SPI，实测 0 ms，可直接同步做。
        if mousep.verify_double_click(n):
            self.lbl_dbl.config(text='已设为 %d ms ✓' % n)
        else:
            self.lbl_dbl.config(text='写入失败（读回不符）')
            self.refresh_mouse()

    def _on_wheel(self, v):
        n = int(round(float(v)))
        mousep.set_wheel_lines(n, verify=False)
        self.lbl_wheel.config(
            text='已设为 0（一次滚一屏）' if n == 0 else '已设为 %d 行' % n)
        self._debounce('wheel', lambda: self._verify_wheel(n))

    def _verify_wheel(self, n):
        def done(ok):
            if ok:
                self.lbl_wheel.config(
                    text=('已设为 0（一次滚一屏）✓' if n == 0
                          else '已设为 %d 行 ✓' % n))
            else:
                self.lbl_wheel.config(text='写入失败（读回不符）')
                self.refresh_mouse()
        self._verify_async('wheel', lambda: mousep.commit_wheel_lines(n), done)

    def _on_trail(self, v):
        n = int(round(float(v)))
        mousep.set_mouse_trails(n, verify=False)
        self.lbl_trail.config(text='已设为 %d' % n)
        self._debounce('trail', lambda: self._verify_trail(n))

    def _verify_trail(self, n):
        def done(ok):
            if ok:
                self.lbl_trail.config(text='已设为 %d ✓' % n)
            else:
                self.lbl_trail.config(text='写入失败（读回不符）')
                self.refresh_mouse()
        self._verify_async('trail',
                           lambda: mousep.commit_mouse_trails(n), done)

    def _on_hover(self, v):
        n = int(round(float(v) / 10.0) * 10)
        mousep.set_hover_time(n, verify=False)
        self.lbl_hover.config(text='已设为 %d ms' % n)
        self._debounce('hover', lambda: self._verify_hover(n))

    def _verify_hover(self, n):
        def done(ok):
            if ok:
                self.lbl_hover.config(text='已设为 %d ms ✓' % n)
            else:
                self.lbl_hover.config(text='写入失败（读回不符）')
                self.refresh_mouse()
        self._verify_async('hover',
                           lambda: mousep.commit_hover_time(n), done)

    def _on_switch(self, key, var, fn):
        # 同 _on_accel：command 触发时 var 已是新值，不要取反。
        on = bool(var.get())
        try:
            ok = getattr(mousep, fn)(on)
            if ok:
                self.say('%s：%s' % (key, '已开启' if on else '已关闭'), OK)
            else:
                self.say('%s：系统拒绝了这个改动（本机不支持）' % key, BAD)
                self.refresh_mouse()
        except Exception as e:
            self.say('%s 设置失败：%s' % (key, e), BAD)

    def refresh_mouse(self):
        d = mousep.get_all()
        def sv(w, v):
            try:
                w.set(v)
            except Exception:
                pass
        if d.get('鼠标速度') is not None:
            sv(self.mv['speed'], d['鼠标速度'])
            self.lbl_speed.config(text='当前 %d' % d['鼠标速度'])
        if d.get('加速') is not None:
            on = d['加速'] != 0
            self.mb['accel'][1].set(on)
            self.lbl_accel.config(
                text=('已开启（阈值 %s / %s）' % (d.get('阈值1'), d.get('阈值2')))
                if on else '已关闭（原始 1:1）')
        if d.get('双击速度'):
            sv(self.mv['dbl'], d['双击速度'])
            self.lbl_dbl.config(text='当前 %d ms' % d['双击速度'])
        if d.get('滚轮行数') is not None:
            n = d['滚轮行数']
            sv(self.mv['wheel'], n)
            self.lbl_wheel.config(
                text='当前 0（滚一屏）' if n == 0 else '当前 %d 行' % n)
        if d.get('鼠标轨迹') is not None:
            sv(self.mv['trail'], d['鼠标轨迹'])
            self.lbl_trail.config(text='当前 %d' % d['鼠标轨迹'])
        if d.get('悬停时间') is not None:
            sv(self.mv['hover'], d['悬停时间'])
            self.lbl_hover.config(text='当前 %d ms' % d['悬停时间'])
        for key, field in (('swap', '左右键互换'), ('snap', '吸附到默认按钮'),
                           ('vanish', '打字时隐藏指针'), ('shadow', '指针阴影'),
                           ('lock', '点击锁定')):
            # 本机不支持的开关被禁用了，不要用读回值去覆盖它的勾选状态
            if self.unsupported_switches.get(key):
                continue
            if d.get(field) is not None:
                self.mb[key][1].set(bool(d[field]))
        self.say('鼠标参数读数已刷新', OK)

    def do_backup(self):
        import datetime
        t = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        p = os.path.join(paths.APP_DIR, '鼠标参数备份_%s.json' % t)
        try:
            d = mousep.backup(p)
            cur = os.path.join(paths.APP_DIR, '鼠标参数备份_当前.json')
            mousep.backup(cur)
            self.say('已备份 %d 项到 %s' % (len(d.get('registry', {})),
                                          os.path.basename(p)), OK)
        except Exception as e:
            self.say('备份失败：%s' % e, BAD)

    def do_restore_mouse(self):
        cur = os.path.join(paths.APP_DIR, '鼠标参数备份_当前.json')
        if not os.path.isfile(cur):
            messagebox.showinfo('没有备份', '还没有备份过。先点「备份当前设置」。')
            return
        if not messagebox.askyesno('还原备份', '把鼠标参数还原成备份时的样子？'):
            return
        try:
            n = mousep.restore(cur)
            self.refresh_mouse()
            self.say('已还原 %d 项' % n, OK)
        except Exception as e:
            self.say('还原失败：%s' % e, BAD)

    def do_mouse_defaults(self):
        if not messagebox.askyesno(
                '恢复推荐值',
                '把指针速度、加速、双击、滚轮、轨迹恢复成 Windows 常见默认值？\n'
                '（指针速度 10、加速关、双击 500ms、滚轮 3 行、轨迹关）\n\n'
                '会自动先备份一次当前设置。'):
            return
        try:
            cur = os.path.join(paths.APP_DIR, '鼠标参数备份_当前.json')
            mousep.backup(cur)
        except Exception:
            pass
        mousep.set_sensitivity(10)
        mousep.set_mouse_speed(10)
        mousep.set_acceleration(0, 0, 0)
        mousep.set_double_click(500)
        mousep.set_wheel_lines(3)
        mousep.set_mouse_trails(0)
        mousep.set_hover_time(400)
        self.refresh_mouse()
        self.say('已恢复推荐值（原设置已备份，可点「还原备份」撤销）', OK)

    # ============================================ 关闭
    def on_close(self):
        try:
            self.saved['scale'] = self.scale
            self.saved['animate'] = bool(self.v_anim.get())
            store.save(self.saved)
        except Exception:
            pass
        # FX 驱动线程活在**本进程**里；窗口一关就没人按键态切换档位了。
        # 所以关窗前必须主动停一次 —— stop_fx() 会把指针复位到 base 档，
        # 否则「关窗那一刻恰好按着鼠标」就会把指针永久留在缩小状态。
        # （守护在跑的话，它下一轮复核会维持同一尺寸，不会有跳变。）
        self.eng.stop_fx()
        if not self.v_anim.get():
            self.eng.stop_anim()
        self.root.destroy()


# ---------------------------------------------------------------- 入口
def _safe_io():
    """--windowed 的 exe 没有控制台，sys.stdout/stderr 是 None，print 会崩。

    分工（早期版本把 stdout 和 stderr 混在一起写「错误日志.txt」，
    结果正常运行的输出也被当成错误，日志永远非空 —— 已拆开）：
      · 普通输出  -> 运行日志.txt（每次启动截断，只保留本次）
      · 异常/报错 -> 错误日志.txt（追加，正常运行时为空）
    """
    err_path = os.path.join(paths.APP_DIR, '错误日志.txt')
    run_path = os.path.join(paths.APP_DIR, '运行日志.txt')
    if sys.stdout is None or sys.stderr is None:
        try:
            out = open(run_path, 'w', encoding='utf-8', buffering=1)
        except Exception:
            out = open(os.devnull, 'w')
        if sys.stdout is None:
            sys.stdout = out

    def _hook(t, v, tb):
        import traceback
        txt = ''.join(traceback.format_exception(t, v, tb))
        try:
            with open(err_path, 'a', encoding='utf-8') as fh:
                fh.write('\n===== %s =====\n%s' % (time.strftime('%Y-%m-%d %H:%M:%S'), txt))
        except Exception:
            pass
        try:
            sys.__stderr__.write(txt)
        except Exception:
            pass

    if sys.stderr is None:
        class _ErrToLog(object):
            def write(self, s):
                if s and s.strip():
                    try:
                        with open(err_path, 'a', encoding='utf-8') as fh:
                            fh.write(s)
                    except Exception:
                        pass

            def flush(self):
                pass

        sys.stderr = _ErrToLog()

    sys.excepthook = _hook
    if threading.current_thread() is threading.main_thread():
        try:
            threading.excepthook = lambda a: _hook(a.exc_type, a.exc_value, a.exc_traceback)
        except Exception:
            pass


def cli(argv):
    if '--restore' in argv:
        cw.dpi_aware()
        e = cw.Engine()
        n = e.restore_files(cw.REG_CURSORS_PATH)
        print('已恢复原始光标：%d 个角色' % n)
        return 0
    if '--guard' in argv:
        # 开机自启入口：常驻守护，自己从 设置.json 读尺寸，并维护指针不被系统重置。
        # 这就是问题1/2/3 的根治点 —— 不再依赖命令行里写死的尺寸快照。
        cw.dpi_aware()
        import guard
        return guard.run()
    if '--guard-status' in argv:
        import guard
        alive, pid, size, scale = guard.guard_status()
        print('守护运行中' if alive else '守护未运行')
        if alive:
            print('  pid=%d  当前 %dpx  %.3f×' % (pid, size, scale))
        return 0
    if '--apply' in argv:
        cw.dpi_aware()
        i = argv.index('--apply')
        # 没显式给尺寸时以 设置.json 为准（命令行不再携带可能陈旧的尺寸快照）
        if i + 1 < len(argv) and not argv[i + 1].startswith('-'):
            scale = float(argv[i + 1])
        else:
            scale = float(store.load().get('scale', 1.20))
        ap = paths.find_art()
        if not ap:
            print('找不到 art.bin')
            return 2
        pk = artpack.load(ap)
        d = store.load()
        fx = store.fx_settings(d)
        e = cw.Engine()
        n = len(e.build(cw.NATIVE * scale, pk, fx=fx))
        got = e.apply_all()
        print('已应用 %d/%d 个角色 · %dpx' % (got, n, e.size))
        keep = False
        if '--no-anim' not in argv and d.get('animate', True):
            e.start_anim()
            print('动画已启动')
            keep = True
        if '--no-fx' not in argv:
            f = e.start_fx(fx)
            if f is not None:
                desc = f.describe()
                print('手感效果已启动：%s' % ' · '.join(desc))
                keep = True
        if keep:
            print('常驻中（关掉本进程即停止）')
            import time
            try:
                while True:
                    time.sleep(3600)
            except KeyboardInterrupt:
                pass
        return 0
    if '--install' in argv:
        i = argv.index('--install')
        tier = argv[i + 1] if i + 1 < len(argv) else 'large'
        p = paths.find_pack()
        if not p:
            print('找不到「指针」目录')
            return 2
        ps1 = os.path.join(p, 'install.ps1')
        import subprocess
        return subprocess.call(['powershell', '-NoProfile',
                                '-ExecutionPolicy', 'Bypass',
                                '-File', ps1, '-Tier', tier])
    return None


def main():
    _safe_io()
    cw.dpi_aware()
    r = cli(sys.argv[1:])
    if r is not None:
        return r
    root = tk.Tk()
    App(root)
    root.mainloop()
    return 0


if __name__ == '__main__':
    sys.exit(main())
