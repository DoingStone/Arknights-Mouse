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

# 进程加固的「早期」部分必须在 tkinter 之前生效：只设 SetErrorMode 和
# WER 排除，让下面这个 import 失败/崩溃也不弹系统错误框。真正的注入防御
# 在 main() 里调 harden.apply()（那时 tkinter 已经导入完，预热才有意义）。
import harden
harden.early()

import tkinter as tk
from tkinter import messagebox, ttk

from PIL import Image, ImageDraw, ImageTk

import arkanim
import artpack
import arktheme as T
import cursorwin as cw
import mousep
import packbuild
import paths
import store

# 科技风 / PRTS 主题令牌统一收在 arktheme（深蓝黑操作台底 + 方舟金点缀 +
# 冰蓝数据色；WCAG 相对亮度实测：正文 ≥4.5:1、次要文字 ≥4.5:1、
# 禁用文字 ≥3:1、描边与层级 ≥1.6:1）。改色请改 arktheme，先复算对比度。
BG = T.BG         # 窗口底（操作台）
BG2 = T.BG2       # 次级底（兼容旧引用）
CARD = T.CARD     # 卡片面板
EDGE = T.EDGE     # 卡片 / 控件描边
EDGE_H = T.EDGE_H  # 描边（悬停 / 聚焦）
RAISE = T.RAISE   # 控件底
RAISE_H = T.RAISE_H  # 控件底（悬停）
RAISE_P = T.RAISE_P  # 控件底（按下）
TAB_ACTIVE = T.TAB_ACTIVE  # 未选中页签的悬停底
WELL = T.WELL     # 内凹槽
FG = T.FG
FG2 = T.FG2
DIM = T.DIM
DIS_BG = T.DIS_BG  # 禁用控件底
DIS_FG = T.DIS_FG  # 禁用控件文字
ACC = T.ACC       # 方舟金
ACC_D = T.ACC_D
ACC_H = T.ACC_H
ACC_INK = T.ACC_INK  # 金底上的深色字
OK = T.OK
BAD = T.BAD
FONT = T.FONT
MONO = T.MONO     # 等宽：读数 / 编号 / 状态
MINI = T.MINI     # 8pt 技术小字（页脚签名等，≥3:1）

# 模块级这些名字是「导入时刻」的取值快照。深色是默认主题，所以它们默认
# 就对；一旦切到浅色主题，只有走 T.* 动态取值的代码（arktheme 内部与
# main.pyw 的 _recolor）才拿得到新配色。**新增界面代码请一律用 T.XXX
# 或 self._color('XXX')，不要用这里的模块常量**，否则换主题会漏改。
#
# 2026-10 补丁：上面这条规矩对「_build() 里几百处历史引用」太不现实，
# 漏一处就是浅色主题下一片深色方块（实际发生过）。所以改成
# **主题切换时把模块全局量重新绑定成当前调色板**（_sync_globals），
# 这样老代码不用动也自动跟随主题。仍是快照，但每次换主题都会刷新。
_COLOR_KEYS = ('BG', 'BG2', 'CARD', 'EDGE', 'EDGE_H', 'RAISE', 'RAISE_H',
               'RAISE_P', 'TAB_ACTIVE', 'WELL', 'FG', 'FG2', 'DIM', 'DIS_BG',
               'DIS_FG', 'ACC', 'ACC_D', 'ACC_H', 'ACC_INK', 'OK', 'BAD',
               'MINI')


def _sync_globals():
    """把模块级颜色常量重新绑定成**当前主题**的取值。

    `_build()` 里几百处引用的是 BG/CARD/FG… 这些模块全局量，它们在
    导入时就被钉成了深色。换到浅色主题后若不刷新，建出来的卡片内标签
    全是深色方块（白底上开一片片黑块，实际出过这个事故）。
    """
    g = globals()
    for _k in _COLOR_KEYS:
        g[_k] = T.color(_k)


_sync_globals()
PREVIEW = 400   # 预览画布边长（正方形，4.00× = 384px 也不裁切）

TIERS = [('small', '小', '48px · 精致'),
         ('medium', '中', '68px · 标准'),
         ('p72', '72px', '72px · 0.75×'),
         ('large', '大', '96px · 原生')]


# ---------------------------------------------------------------- 预览画布
def make_preview(pack, key, scale, canvas_px):
    """把某个角色按 scale 合成到画布上，返回 PIL Image。

    科技风预览台（arktheme.render_preview）：20px 技术网格 + 4px 扫描线 +
    HUD 内框角标 + 32px 系统默认参考框 + 红十字热点。棋盘底已由网格取代。
    """
    return T.render_preview(pack, key, scale, canvas_px)


# ---------------------------------------------------------------- 主界面
class App(object):
    def __init__(self, root):
        self.root = root
        self.saved = store.load()
        # UI 主题（'dark' 深色 PRTS 操作台 / 'light' 浅色档案台）。
        # 只换配色：布局、控件、功能一律不动。默认深色，沿用历史观感。
        self.theme = ('light' if str(self.saved.get('theme', 'dark'))
                      .strip().lower() == 'light' else 'dark')
        T.set_theme(self.theme)
        _sync_globals()          # 让 BG/CARD/FG… 这些模块全局量等于当前主题
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
        self.anim = arkanim.Animator(self)   # 悬停/按压渐变调度器
        self.style = ttk.Style(self.root)    # 供 ttk 颜色补间（见 arkanim）
        self.guard_alive = False  # 守护进程状态（refresh_guard 里更新）
        self._scrolls = []        # 可滚动页签的 (内容容器, 画布) 对
        self.STATUS_MAX = 96      # 状态栏单行字数上限（见 say()）

        root.title('明日方舟鼠标 · 指针与鼠标参数')
        root.configure(bg=BG)
        T.grid_background(root)   # 28px 技术网格底纹（最底层，从卡片边距透出）
        self._style()
        self._build()

        # 窗口尺寸：以前是 resizable(False, False) 且没有 geometry()，尺寸完全
        # 由内容撑开。内容一涨、或换到 1366x768 的笔记本（扣掉任务栏只剩约
        # 728px 可用高），窗口就被裁掉，而且用户连拖都拖不动。
        # 现在：可缩放 + 首屏自动收进可用区域 + 下限不小于页签内容的请求尺寸。
        root.resizable(True, True)
        root.update_idletasks()
        # 必须再 update() 一轮：TechCard 的 _fit 在 <Configure> 事件里跑，
        # 而 update_idletasks 不派发事件 —— 不等它跑完，各卡片的请求宽
        # （canvas width 选项）还没写入，窗口量出来的宽度会少一截。
        root.update()
        w, h = root.winfo_reqwidth(), root.winfo_reqheight()
        max_w = max(480, root.winfo_screenwidth() - 80)    # 给窗口装饰留余量
        max_h = max(420, root.winfo_screenheight() - 120)  # 给任务栏留余量
        gw, gh = min(w, max_w), min(h, max_h)
        # 无条件写入 geometry：TechCard 的请求宽是在 <Configure> → _fit 里
        # 异步补上的，窗口在首次 update() 就已按「补全前」的请求映射过一次
        # （969px）。这里量到的 w 已是补全后的 1081，若因「相等」跳过写入，
        # 窗口就停在 969 —— 右列被裁。所以哪怕数值看着一致也必须写回去。
        root.geometry('%dx%d' % (gw, gh))
        # 下限只保「能用」：宽度给足（横向滚动很难用），高度留一个能看清
        # 卡片的最小值即可 —— 内容已经套了滚动容器，不该再拿内容高度当地板，
        # 否则窗口永远缩不下去，滚动条也就永远没机会出现。
        need_w = max(inner.winfo_reqwidth() for inner, _ in self._scrolls) + 48
        root.minsize(min(need_w, gw), min(560, gh))

        self.root.protocol('WM_DELETE_WINDOW', self.on_close)
        # 首帧就按当前主题整体刷一遍。
        # 踩过的坑：_build() 里创建控件用的是模块级常量（BG/FG/DIM…），
        # 而那是**导入时刻的快照，恒等于深色**。用户上次存的是浅色主题时，
        # 不刷就会得到「白卡片 + 一片片深色标签方块」的破图。
        self._style_reset = True
        self._recolor()
        self._style_reset = False
        self.refresh_mouse()
        self.after_idle_check()

    # ---- 样式 ----
    def _style(self):
        st = ttk.Style()
        try:
            st.theme_use('clam')
        except Exception:
            pass
        F = FONT
        # ⚠️ _style() 在换主题时会被**重跑**，所以这里绝不能直接引用模块级
        #    常量（c('BG')/c('WELL')/c('FG')… 它们是**导入时刻**的快照），必须现取
        #    self._color(...)，否则浅色主题下样式表还是深色。
        c = self._color
        BGc, BG2c, CARDc, EDGEc = c('BG'), c('BG2'), c('CARD'), c('EDGE')
        EDGE_Hc, RAISEc, RAISE_Hc, RAISE_Pc = (c('EDGE_H'), c('RAISE'),
                                               c('RAISE_H'), c('RAISE_P'))
        WELLc, FGc, FG2c, DIMc = c('WELL'), c('FG'), c('FG2'), c('DIM')
        DIS_BGc, DIS_FGc = c('DIS_BG'), c('DIS_FG')
        ACCc, ACC_Dc, ACC_Hc, ACC_INKc = (c('ACC'), c('ACC_D'), c('ACC_H'),
                                          c('ACC_INK'))
        OKc, BADc, MINIc = c('OK'), c('BAD'), c('MINI')

        # 基线
        st.configure('.', background=c('BG'), foreground=c('FG'), font=(F, 10))

        # ---- 标签 ----
        # 注意：ttk 控件在 style='' 时按**类名**（TLabel/TButton/...）查样式，
        # 带 'T.' 前缀的名字只在做基类继承时才有意义。这里以前写的是
        # 'T.TLabel' / 'T.TButton' / 'T.TCheckbutton' / 'T.TNotebook'，
        # 没有任何控件引用 → 全部是死代码。下面统一用裸类名。
        st.configure('TLabel', background=c('BG'), foreground=c('FG'), font=(F, 10))
        # 弹窗里用的两个（有控件显式引用，是活的）
        st.configure('H.TLabel', background=c('BG'), foreground=c('FG'),
                     font=(F, 13, 'bold'))
        st.configure('D.TLabel', background=c('BG'), foreground=c('DIM'), font=(F, 9))
        # 卡片内的标签（背景跟着卡片走）；状态读数走等宽，数字不跳动
        st.configure('CardD.TLabel', background=c('CARD'), foreground=c('DIM'),
                     font=(MONO, 9))
        st.configure('CardV.TLabel', background=c('CARD'), foreground=c('OK'),
                     font=(MONO, 10, 'bold'))

        # ---- 按钮（深色底 + 细描边，去掉 clam 默认的浅灰立体感）----
        # 坑：clam 的 Button.border 元素在 relief='flat' 时**根本不画边框**，
        # 此时 bordercolor 被静默忽略。实测（同尺寸按钮，扫描左边缘像素）：
        #   relief='flat'  + borderwidth=1 → 整条边都是底色，无边框
        #   relief='flat'  + borderwidth=2 → 同上，无边框
        #   relief='solid' + borderwidth=1 → 1px bordercolor 边框，正常
        # 所以「幽灵按钮」Chip.TButton 因为底色 = 卡片色，会彻底退化成裸文字
        # （用户看到的「小框不见了」）。必须用 solid 才能让描边真正落笔。
        st.configure('TButton', background=c('RAISE'), foreground=c('FG'),
                     bordercolor=c('EDGE'), lightcolor=c('RAISE'), darkcolor=c('RAISE'),
                     borderwidth=1, relief='solid',
                     focusthickness=2, focuscolor=c('ACC'),
                     padding=(14, 7), anchor='center', font=(F, 10))
        st.map('TButton',
               background=[('disabled', c('DIS_BG')), ('pressed', c('RAISE_P')),
                           ('active', c('RAISE_H'))],
               foreground=[('disabled', c('DIS_FG'))],
               bordercolor=[('focus', c('ACC')), ('active', c('EDGE_H'))])

        # 主按钮：金底深字
        st.configure('Accent.TButton', background=c('ACC'), foreground=c('ACC_INK'),
                     bordercolor=c('ACC'), lightcolor=c('ACC'), darkcolor=c('ACC'),
                     focusthickness=2, focuscolor=c('ACC_INK'),
                     font=(F, 10, 'bold'))
        st.map('Accent.TButton',
               background=[('disabled', c('DIS_BG')), ('pressed', c('ACC_D')),
                           ('active', c('ACC_H'))],
               foreground=[('disabled', c('DIS_FG'))],
               bordercolor=[('pressed', c('ACC_D')), ('active', c('ACC_H'))])

        # 幽灵按钮：贴在卡片上，悬停才亮起描边
        st.configure('Chip.TButton', background=c('CARD'), foreground=c('FG2'),
                     bordercolor=c('EDGE'), lightcolor=c('CARD'), darkcolor=c('CARD'),
                     focusthickness=2, focuscolor=c('ACC'),
                     padding=(8, 6), font=(F, 9))
        st.map('Chip.TButton',
               background=[('disabled', c('DIS_BG')), ('pressed', c('RAISE_P')),
                           ('active', c('RAISE'))],
               foreground=[('active', c('FG')), ('disabled', c('DIS_FG'))],
               bordercolor=[('focus', c('ACC')), ('active', c('EDGE_H'))])
        # 被推荐的档位：金描边 + 金字
        st.configure('ChipAccent.TButton', background=c('CARD'), foreground=c('ACC'),
                     bordercolor=c('ACC'), lightcolor=c('CARD'), darkcolor=c('CARD'),
                     focusthickness=2, focuscolor=c('ACC'),
                     padding=(8, 6), font=(F, 9, 'bold'))
        st.map('ChipAccent.TButton',
               background=[('disabled', c('DIS_BG')), ('pressed', c('RAISE_P')),
                           ('active', c('RAISE'))],
               foreground=[('disabled', c('DIS_FG'))],
               bordercolor=[('active', c('ACC_H'))])

        # ---- 复选 ----
        # 两条坑：
        # 1) indicatorcolor / indicatordarkcolor 是**静默空操作**（ttk 接受但
        #    不渲染）。真正生效的是 indicatorbackground / indicatorforeground
        #    / upperbordercolor / lowerbordercolor / indicatorsize / indicatormargin。
        # 2) clam 主题对 indicatorbackground 自带一条 selected→蓝色 #4772b3 的
        #    映射，不显式覆盖的话勾选态永远是蓝的。
        st.configure('TCheckbutton', background=c('CARD'), foreground=c('FG'),
                     focusthickness=2, focuscolor=c('ACC'), padding=(2, 4),
                     font=(F, 10),
                     indicatorsize=18, indicatormargin=(1, 1, 8, 1),
                     indicatorbackground=c('WELL'), indicatorforeground=c('ACC'),
                     upperbordercolor=c('EDGE'), lowerbordercolor=c('EDGE'),
                     indicatorrelief='flat')
        st.map('TCheckbutton',
               background=[('active', c('CARD'))],
               indicatorbackground=[('selected', c('ACC')), ('disabled', c('DIS_BG'))],
               indicatorforeground=[('selected', c('ACC_INK')),
                                    ('disabled', c('DIS_FG'))],
               upperbordercolor=[('selected', c('ACC')), ('focus', c('ACC'))],
               lowerbordercolor=[('selected', c('ACC')), ('focus', c('ACC'))],
               foreground=[('disabled', c('DIS_FG'))])
        # clam 内置的选中标记是个**对称的叉（✗）**，语义上像「不可用」，
        # 与方舟 UI 的「金底白勾」相反。形状由 Tk C 层决定，样式表改不了笔画
        # （indicatorsize / indicatorforeground 只改尺寸颜色），只能换成 image
        # 元素 —— 见 arktheme.install_check_indicator()。下面这行必须放在
        # 上面 configure/map 之后，它会重写 TCheckbutton 的 layout。
        T.install_check_indicator(st, self.theme)
        # 禁用态单独一套样式：ttk 的 image 元素不认 ('disabled', img) 映射，
        # 想让「本机不支持」那几枚一眼看着不能点，只能换样式名。
        st.configure('Dis.TCheckbutton', background=c('CARD'),
                     foreground=c('DIS_FG'), focusthickness=2,
                     focuscolor=c('ACC'), padding=(2, 4), font=(F, 10))
        st.map('Dis.TCheckbutton',
               background=[('active', c('CARD'))],
               foreground=[('disabled', c('DIS_FG'))])

        # ---- 页签 ----
        st.configure('TNotebook', background=c('BG'), borderwidth=0,
                     tabmargins=(2, 4, 2, 0), focuscolor=c('BG'))
        st.configure('TNotebook.Tab', background=c('BG'), foreground=c('DIM'),
                     padding=(22, 9), borderwidth=0, font=(F, 10),
                     lightcolor=c('BG'), darkcolor=c('BG'), bordercolor=c('BG'))
        st.map('TNotebook.Tab',
               background=[('selected', c('CARD')), ('active', c('TAB_ACTIVE'))],
               foreground=[('selected', c('ACC')), ('active', c('FG2'))],
               lightcolor=[('selected', c('ACC'))], darkcolor=[('selected', c('ACC'))],
               expand=[('selected', (0, 0, 0, 0))])

        # ---- 滑杆（ttk：金色滑块 + 深色轨槽）----
        st.configure('TScale', background=c('ACC'), troughcolor=c('WELL'),
                     bordercolor=c('EDGE'), lightcolor=c('ACC'), darkcolor=c('ACC'),
                     borderwidth=0, sliderlength=26, sliderrelief='flat',
                     gripcount=0)
        # 轨槽带主题底色的变体：卡片里的滑杆用它，避免深色轨槽在浅色主题下
        # 变成一根突兀的黑条（troughcolor 由 _recolor 里重跑 _style 时随令牌走）。
        # ⚠️ ttk 自定义样式必须自己给 layout，否则报
        #    Layout Horizontal.TFill.TScale not found
        for _o in ('Horizontal', 'Vertical'):
            try:
                st.layout('%s.TFill.TScale' % _o,
                          st.layout('%s.TScale' % _o))
            except Exception:
                pass
        st.configure('TFill.TScale', background=c('ACC'), troughcolor=c('WELL'),
                     bordercolor=c('EDGE'), lightcolor=c('ACC'), darkcolor=c('ACC'),
                     borderwidth=0, sliderlength=26, sliderrelief='flat',
                     gripcount=0)
        st.map('TFill.TScale',
               background=[('disabled', c('DIS_FG')), ('pressed', c('ACC_D')),
                           ('active', c('ACC_H'))],
               lightcolor=[('disabled', c('DIS_FG')), ('pressed', c('ACC_D')),
                           ('active', c('ACC_H'))],
               darkcolor=[('disabled', c('DIS_FG')), ('pressed', c('ACC_D')),
                          ('active', c('ACC_H'))],
               troughcolor=[('disabled', c('DIS_BG'))])
        st.map('TScale',
               background=[('disabled', c('DIS_FG')), ('pressed', c('ACC_D')),
                           ('active', c('ACC_H'))],
               lightcolor=[('disabled', c('DIS_FG')), ('pressed', c('ACC_D')),
                           ('active', c('ACC_H'))],
               darkcolor=[('disabled', c('DIS_FG')), ('pressed', c('ACC_D')),
                          ('active', c('ACC_H'))],
               troughcolor=[('disabled', c('DIS_BG'))])

        st.configure('TFrame', background=c('BG'))

        # ---- 滚动条（页签内容超高时才出现，见 _scrollable）----
        for orient in ('Vertical', 'Horizontal'):
            st.configure('%s.TScrollbar' % orient, background=c('RAISE'),
                         troughcolor=c('WELL'), bordercolor=c('EDGE'), arrowcolor=c('DIM'),
                         darkcolor=c('RAISE'), lightcolor=c('RAISE'), borderwidth=0,
                         arrowsize=13, width=11, relief='flat', gripcount=0)
            st.map('%s.TScrollbar' % orient,
                   background=[('pressed', c('RAISE_P')), ('active', c('RAISE_H'))],
                   darkcolor=[('pressed', c('RAISE_P')), ('active', c('RAISE_H'))],
                   lightcolor=[('pressed', c('RAISE_P')), ('active', c('RAISE_H'))],
                   arrowcolor=[('pressed', c('ACC')), ('active', c('ACC'))])

    # ---- 可滚动容器 ----
    def _descendants(self, widget):
        out = []
        for child in widget.winfo_children():
            out.append(child)
            out.extend(self._descendants(child))
        return out

    # ---- 动效 ----
    # 明日方舟 UI 规范：悬停 150ms 渐变、按下 80ms，ease-out，禁弹性回弹。
    # 红线：只改颜色，绝不碰 width/height/pack/grid，否则复发「拖滑杆横移」。
    def _anim_hover(self, w, enter):
        """悬停渐入 150ms / 渐出 300ms（ui-style.md：150–300ms、ease-out）。"""
        c = self._color
        try:
            acc = bool(w._ark_acc)
        except Exception:
            acc = False
        try:
            base = w._ark_base_bg or (c('ACC') if acc else c('RAISE'))
            hi = w._ark_hi_bg or (c('ACC_H') if acc else c('RAISE_H'))
        except Exception:
            base, hi = (c('ACC'), c('ACC_H')) if acc else (c('RAISE'),
                                                           c('RAISE_H'))
        self._fade_widget(w, base, hi if enter else base,
                          self.anim.T_HOVER if enter else 320)

    def _anim_press(self, w, down):
        c = self._color
        try:
            acc = bool(w._ark_acc)
        except Exception:
            acc = False
        try:
            base = w._ark_base_bg or (c('ACC') if acc else c('RAISE'))
        except Exception:
            base = c('ACC') if acc else c('RAISE')
        if down:
            self._fade_widget(w, base,
                              c('ACC_D') if acc else c('RAISE_P'),
                              self.anim.T_PRESS)
        else:
            self._anim_hover(w, True)

    def _fade_widget(self, w, base, target, ms):
        """把控件背景从当前色补间到 target。

        tk 控件直接改 bg；ttk 控件的颜色归样式表管（widget.configure(bg=)
        会被忽略），所以给它发一个专属样式名，在样式表上补间 —— 样式名唯一，
        只影响这一枚，不波及同款按钮。两路都只改颜色，不碰几何。

        ⚠️ ttk 控件没有 style() 配置项，`w.cget('style')` 会报
        unknown option "-style" —— 基样式名必须存在 `_ark_base_style`
        里（_bind_anim 时记下），或由调用方显式给出。
        """
        try:
            self.anim.fade_color(w, 'bg', str(w.cget('bg')), target, ms)
            return                            # tk 控件：已处理
        except Exception:
            pass                              # ttk：往下走
        try:
            base_style = getattr(w, '_ark_base_style', None) or 'TButton'
            sn, st = arkanim.ensure_anim_style(self, w, base_style)
            cur = st.lookup(sn, 'background') or base
            self.anim.fade_style(sn, 'background', cur, target, ms)
        except Exception:
            pass

    def _bind_anim(self, w, base_bg=None, hi_bg=None, acc=False):
        """给一枚可点控件挂上悬停/按压渐变。

        base_bg / hi_bg 用 None 表示「按当前主题现取」：换主题后
        _anim_hover 会重新取色，就不会把旧主题的底色补间回来。
        acc=True 表示这枚是金色系（主按钮/主题 chip 高亮），高亮走
        ACC_H 而不是灰蓝的 RAISE_H。
        """
        w._ark_base_bg = base_bg
        w._ark_hi_bg = hi_bg
        w._ark_acc = bool(acc)
        # 记下 ttk 基样式名：ttk 控件没有 style() 配置项，
        # `w.cget('style')` 会报 unknown option，所以在这里存下来。
        # Chip/ChipAccent 这类没有显式 style 的也必须存真实基样式，
        # 否则 _fade_widget 会按 'TButton' 起步，底色一跳。
        try:
            w._ark_base_style = str(w.cget('style'))
        except Exception:
            w._ark_base_style = ''
        if not w._ark_base_style:
            # ttk 控件的默认样式名 = 类名本身（TButton/TCheckbutton/...）
            try:
                cls = str(w.winfo_class())
                if not cls.startswith('T'):
                    cls = 'T' + cls
                w._ark_base_style = cls
            except Exception:
                pass
        try:
            w.bind('<Enter>', lambda e, x=w: self._anim_hover(x, True),
                   add='+')
            w.bind('<Leave>', lambda e, x=w: self._anim_hover(x, False),
                   add='+')
            w.bind('<ButtonPress-1>', lambda e, x=w: self._anim_press(x, True),
                   add='+')
            w.bind('<ButtonRelease-1>',
                   lambda e, x=w: self._anim_press(x, False), add='+')
        except Exception:
            pass

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
        # 28px 技术网格铺在内容层最底下（place 不参与几何传播，卡片间隙透出）
        T.grid_background(inner)

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
              sub_wrap=760, extra=None):
        """一张卡片：PRTS 切角面板 + HUD 四角金标 + 可选标题/副标题。

        extra：标题行右侧挂件（工厂函数 extra(title_row) → widget），
        比如预览卡的 PRTS 水晶自旋。返回值还是内容框（body）。
        """
        card = T.TechCard(parent, title=title, sub=sub, sub_wrap=sub_wrap,
                          extra=extra)
        card.pack(fill='x', padx=padx, pady=pady)
        return card.body

    def _crystal(self, parent, size, alive=True):
        """PRTS 水晶自旋挂件；没有美术包时退化成一个占位方块。

        背景色一律现取 T.color('CARD') —— 不能用 parent.cget('bg')：换主题后
        parent 可能还没刷到新色，会把旧底色抄下来。
        """
        if self.pack:
            return T.CrystalSpin(parent, self.pack, size=size,
                                 bg=T.color('CARD'), alive=alive)
        ph = tk.Canvas(parent, width=size, height=size,
                       bg=T.color('CARD'), highlightthickness=0)
        ph.create_rectangle(size // 2 - 3, size // 2 - 3, size // 2 + 3,
                            size // 2 + 3, outline=T.color('EDGE'))
        return ph

    def _header(self, parent, sec, title, sub, crystal_size=44):
        """页签头：编号 + 标题 + 副标题 + 右侧 PRTS 水晶 + 科技分隔线。"""
        head = tk.Frame(parent, bg=BG)
        head.pack(fill='x', padx=16, pady=(14, 10))
        row = tk.Frame(head, bg=BG)
        row.pack(fill='x')
        if self.pack and crystal_size:
            T.CrystalSpin(row, self.pack, size=crystal_size, bg=BG
                          ).pack(side='right')
        tk.Label(row, text='SEC.%s //' % sec, bg=BG, fg=ACC,
                 font=(MONO, 10)).pack(side='left', anchor='n', pady=(6, 0))
        tk.Label(row, text='  ' + title, bg=BG, fg=FG,
                 font=(FONT, 15, 'bold')).pack(side='left', anchor='n')
        tk.Label(row, text=sub, bg=BG, fg=DIM, font=(FONT, 9),
                 justify='left', wraplength=700).pack(side='left', anchor='n',
                                                      padx=(14, 0),
                                                      pady=(8, 0))
        T.tech_rule(head)
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
        # 页脚饰边：金 / 深金斜纹警示条（明日方舟 UI 的经典元素）
        # 斜纹底色不传 BG（模块级常量是导入时刻快照，换主题后停在旧色），
        # 交给 hazard_stripe 内部用 T.color('BG') 现取。
        T.hazard_stripe(foot, height=5)
        # 状态栏沿 srow → foot → 根窗口这条链传播请求宽度，一条长消息
        # 仍能把窗口从 1061 撑到 2032（实测 200 字符下推动 41 个控件）。
        # 两道防线：
        #   wraplength 封住**请求宽度**（这是根治点：标签请求宽不再随
        #   文案长度增长），height=1 钉死高度（换行若让 foot 长高 →
        #   Notebook 被压矮 → 竖滚动条越界出现/消失 → 又变成内容横移）；
        #   say() 里再按字数截断，保证正常文案永远一行显示完、不被裁。
        srow = tk.Frame(foot, bg=BG)
        srow.pack(fill='x', pady=(7, 0))
        # 右侧技术标记：等宽小字，给页脚收一个 PRTS 终端签名
        tk.Label(srow, text='ARKMOUSE // PRTS-UI', bg=BG, fg=DIM,
                 font=(MONO, 8)).pack(side='right')
        # 主题开关（浅色 / 深色）：只换配色，布局控件一律不动。
        # 做成两枚 chip 而不是下拉框 —— 点一下即生效，且形状尺寸固定，
        # 切换时不引起任何布局位移（这是本项目反复验证过的红线）。
        tsw = tk.Frame(srow, bg=BG)
        tsw.pack(side='right', padx=(0, 14))
        self.theme_btns = {}
        for tkey, tlabel in (('light', '浅色'), ('dark', '深色')):
            b = tk.Label(tsw, text=tlabel, font=(MONO, 9), width=6,
                         anchor='center', cursor='hand2',
                         relief='solid', bd=1,
                         bg=self._color('BG'), fg=self._color('DIM'))
            b.pack(side='left', padx=2, pady=2)
            b.bind('<Button-1>', lambda _e, k=tkey: self.set_theme(k))
            self._bind_anim(b, acc=True)   # 金色 chip，高亮走 ACC_H
            self.theme_btns[tkey] = b
        self._paint_theme_chips()   # 首帧就把高亮态画出来，不留系统默认灰
        self.status = tk.Label(srow, text='就绪', anchor='w', bg=BG,
                               fg=DIM, font=(MONO, 9), justify='left',
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
            f, '01', '指针大小',
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
                       padx=(14, 7), sub_wrap=396,
                       extra=lambda row: self._crystal(row, 30))
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
                            font=(MONO, 12, 'bold'),
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
                            style='TFill.TScale', command=self.on_slide)
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
            b = ttk.Button(bf, text=txt, style=style,
                           command=lambda x=v: self.set_scale(x))
            b.grid(row=i // 3, column=i % 3,
                   padx=(0 if i % 3 == 0 else 4, 0),
                   pady=(0 if i < 3 else 4, 0), sticky='ew')
            self._bind_anim(b, acc=(style == 'ChipAccent.TButton'))

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
        # PRTS 水晶状态灯：守护运行时旋转，停用时静帧压暗
        self.crystal_guard = self._crystal(gf, 36, alive=False)
        self.crystal_guard.grid(row=0, column=0, padx=(0, 10))
        self.lbl_guard = ttk.Label(gf, text='检测中…',
                                   style='CardD.TLabel')
        self.lbl_guard.grid(row=0, column=1, sticky='w')
        gf.columnconfigure(1, weight=1)
        ttk.Button(gf, text='启动守护', style='Chip.TButton',
                   command=self.do_start_guard).grid(row=0, column=2,
                                                     padx=(0, 4))
        _gs = ttk.Button(gf, text='停止守护', style='Chip.TButton',
                         command=self.do_stop_guard)
        _gs.grid(row=0, column=3)
        for _b in gf.winfo_children():
            if isinstance(_b, ttk.Button):
                self._bind_anim(_b)

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
        # 应用与还原这一排全是可点按钮，统一挂悬停/按压渐变
        for _b in list(af.winfo_children()) + list(sf.winfo_children()):
            if isinstance(_b, ttk.Button):
                self._bind_anim(
                    _b, acc=(_b.cget('style') == 'Accent.TButton'))

    # ============================================ 页签二：鼠标参数
    def _build_mouse_tab(self, f):
        self._header(
            f, '02', '鼠标参数',
            '改完立即生效，只影响当前用户；每个项目都有一键备份 / 还原。')

        self.mv = {}
        self.mb = {}
        # 本机不支持的开关（见下方 switches 表）——刷新时跳过它们
        self.unsupported_switches = {}

        c = self._card(f, '偏好设置')
        g = tk.Frame(c, bg=CARD)
        g.pack(fill='x', pady=(10, 0))
        # 列 0/1 = 行名与副说明（固定宽度，靠 width=12 与文字决定）
        #         width=12：10 个字符单位对「打字时隐藏指针」这类 7 汉字
        #         行名不够（约 93px > 90px），会截成「打字时隐藏指」。
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
            # 金色方块标记 + 分组名（PRTS 节标题样式）
            grow = tk.Frame(g, bg=CARD)
            grow.grid(row=i + 1, column=0, columnspan=4, sticky='w',
                      pady=(0, 2))
            mk = tk.Frame(grow, bg=ACC, width=7, height=7)
            mk.pack(side='left', padx=(0, 8), pady=(2, 0))
            mk.pack_propagate(False)
            tk.Label(grow, text=title, bg=CARD, fg=ACC,
                     font=(FONT, 9, 'bold')).pack(side='left')
            st[0] = i + 2

        def row_label(txt, sub=''):
            i = st[0]
            tk.Label(g, text=txt, bg=CARD, fg=FG, width=12, anchor='w',
                     font=(FONT, 10)).grid(row=i, column=0, sticky='w',
                                           pady=2)
            tk.Label(g, text=sub, bg=CARD, fg=DIM, anchor='w',
                     font=(FONT, 9)).grid(row=i, column=1, sticky='w',
                                          padx=(0, 14), pady=2)
            return i

        def slider(i, key, lo, hi, cmd):
            s = ttk.Scale(g, from_=lo, to=hi, orient='horizontal',
                          style='TFill.TScale', length=220, command=cmd)
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
                # 禁用态要换样式：ttk image 元素不认 ('disabled', img)，
                # 光加 state(['disabled']) 勾选框看起来和可用的一模一样。
                cb.configure(style='Dis.TCheckbutton')
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

    # ============================================ 主题（深色 / 浅色）
    def _color(self, key):
        """按当前主题取色。所有新建控件都该用它，别用导入时刻的模块常量。"""
        return T.color(key)

    def set_theme(self, name):
        """切换深浅主题：只换配色，布局一个像素都不动。

        这是硬约束 —— 本项目此前修过「拖滑杆导致整页横移」，任何换主题
        引发的重新布局都会复发同类问题。所以 _recolor() 只改颜色类选项
        （bg/fg/troughcolor/…），绝不碰 width/height/pack/grid。
        """
        name = T.set_theme(name)
        _sync_globals()          # 模块级颜色常量跟着换（_build 的历史引用靠它）
        self.theme = name
        self._style_reset = True   # 让 _recolor() 从「导入时刻快照」重建标签前景
        self._recolor()
        self._style_reset = False
        try:
            d = dict(self.saved)
            d['theme'] = name
            store.save(d)
            self.saved = d
        except Exception:
            pass
        self._paint_theme_chips()
        self.say('已切换到%s主题' % ('浅色' if name == 'light' else '深色'),
                 self._color('FG2'))

    def _paint_theme_chips(self):
        """主题开关两枚 chip 的高亮态：选中＝金底深字，未选＝描边空心。"""
        for key, b in self.theme_btns.items():
            on = (key == self.theme)
            b.configure(
                bg=self._color('ACC') if on else self._color('BG'),
                fg=self._color('ACC_INK') if on else self._color('DIM'),
                activebackground=self._color('ACC_H') if on
                else self._color('RAISE_H'),
                activeforeground=self._color('ACC_INK') if on
                else self._color('FG'),
                highlightthickness=1,
                highlightbackground=self._color('ACC') if on
                else self._color('EDGE'),
                highlightcolor=self._color('ACC'))

    def _recolor(self):
        """把整个界面刷成当前主题的颜色。

        分四层，顺序有讲究：
          1. ttk 样式：先重跑 _style() —— 按钮/复选/页签/滑杆/滚动条的底色
             全部由 style 表驱动，改样式表即全局生效。
          2. tk 控件：ttk 管不到 tk.Label/tk.Frame/tk.Canvas，逐个按类刷。
          3. 自绘组件：TechCard.recolor() 重画切角多边形，grid_background /
             hazard_stripe 的 redraw() 重画网格与斜纹，这些是画在 canvas 上
             的像素，不重绘不会自己变色。
          4. 内容重绘：预览图是 PIL 画出来的位图，得重渲染一次。
        """
        c = self._color
        self._style()                                   # 1) ttk 样式表

        # 2) tk 控件按类刷。判断依据是控件类名，不用猜业务含义。
        skip_fg_roles = set()                           # 保留语义色的标签（✓/✗/● 等）
        for w in [self.root] + self._descendants(self.root):
            cls = w.winfo_class()
            try:
                if cls in ('Frame', 'Toplevel', 'Tk'):
                    # Tk = 根窗口自己；不刷它的话 root.cget('bg') 会一直
                    # 停在旧主题色（视觉上被网格画布盖住，但探针/截图能看出）
                    w.configure(bg=c('BG'))
                elif cls == 'Canvas':
                    if isinstance(w, T.TechCard):
                        continue            # 卡片壳自己管底色（见第 3 步 recolor）
                    if getattr(w, 'redraw', None):
                        w.redraw()                      # 3) 自绘画布走自己的重绘
                    else:
                        w.configure(bg=c('BG'))
                elif cls == 'Label':
                    # 标签底色必须跟随**父容器**，不能一律用 BG。
                    # 踩过的坑：一律刷成 BG 时，白卡片内的标签会变成
                    # 一块开底色的方块（浅色主题下就是白卡上的一片深灰/黑块，
                    # 非常刺眼）。所以先读父容器的 bg，读不到才退回 BG。
                    bg = c('BG')
                    try:
                        p = w.master
                        if p is not None and str(p.winfo_class()) in (
                                'Frame', 'Tk', 'Toplevel', 'Canvas'):
                            bg = str(p.cget('bg'))
                    except Exception:
                        pass
                    # CardV/CardD 走 ttk 样式
                    st = ''
                    try:
                        st = str(w.cget('style'))
                    except Exception:
                        pass
                    if st in ('CardV.TLabel', 'CardD.TLabel'):
                        w.configure(foreground=c('OK') if st == 'CardV.TLabel'
                                    else c('DIM'))
                        continue
                    w.configure(bg=bg)
                    # 前景：默认换 DIM/FG，但状态色标签（OK/BAD/ACC）保留语义
                    try:
                        cur = str(w.cget('fg')).lower()
                    except Exception:
                        cur = ''
                    if getattr(self, '_style_reset', False):
                        # 换主题时：模块级常量（FG/DIM）是导入时刻快照，
                        # 直接拿来用会把旧主题色刷回去。这里按「控件当时
                        # 用的是哪套语义」重建：白/灰系 → 当前主题对应色。
                        if cur in ('', '#e8e8ee', '#ffffff', '#c9cdd4',
                                   '#e8ecf3', '#141922'):
                            w.configure(fg=c('FG'))
                        elif cur in ('#7f8698', '#8a8f98', '#616d80',
                                     '#69738a', '#7d8699', '#aeb6c6',
                                     '#414b5c'):
                            w.configure(fg=c('DIM'))
                        elif cur in ('#f5c451', '#9a6f00'):
                            w.configure(fg=c('ACC'))
                        continue
                    if cur in ('', '#e8e8ee', '#ffffff', '#c9cdd4'):
                        w.configure(fg=c('FG'))
                    elif cur in ('#7f8698', '#8a8f98', '#616d80', '#69738a'):
                        w.configure(fg=c('DIM'))
            except Exception:
                pass

        # 3) 自绘组件
        for w in self._descendants(self.root):
            if isinstance(w, T.TechCard):
                try:
                    w.recolor()
                except Exception:
                    pass
            red = getattr(w, 'redraw', None)
            if red and w.winfo_class() == 'Canvas':
                try:
                    red()
                except Exception:
                    pass

        # 3b) 底色对齐（关键收尾）：所有 tk 控件的 bg 一律跟随父容器。
        # 必须在 TechCard.recolor() 之后跑 —— 卡片 body 的底色此时才是新的，
        # 早跑会把父色读成旧值。这一步专治「白卡片里嵌着一块块深色方块」：
        # 那些方块就是 _build() 用导入时刻常量（BG/CARD 的深色快照）建出来的
        # Label/Frame，父容器却已经变成浅色。
        for w in self._descendants(self.root):
            cls = w.winfo_class()
            if cls not in ('Frame', 'Label', 'Canvas'):
                continue
            if isinstance(w, T.TechCard):
                continue                     # 卡片壳的底色由 recolor() 决定
            if cls == 'Canvas' and getattr(w, 'redraw', None):
                continue                     # 自绘画布自己管底色
            try:
                p = w.master
                if p is None:
                    continue
                w.configure(bg=str(p.cget('bg')))
            except Exception:
                pass

        # 主题开关 chip 自己也要跟着变
        self._paint_theme_chips()

        # 4) 内容重绘：预览位图 + 守护状态（后者会换 CardV/CardD 样式名）
        try:
            self.refresh_preview()
        except Exception:
            pass
        try:
            self.refresh_guard()
        except Exception:
            pass

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
        self.lbl.config(text='%.2f× · %d×%d px · 热点 (%d, %d)'
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
        """把某一档登记进「鼠标属性 → 指针 → 方案」，和别的鼠标皮肤一样。

        以前这里要求 exe 旁边必须有 `cursors/` 目录**和**里面的 install.ps1：
        只从 GitHub 拿到一个 exe 的人，点到这里就弹「没有找到指针目录」然后
        结束 —— 看起来像程序坏了，其实只是少了几个文件。而指针文件本来
        全部是从内嵌的 art.bin 派生的，随时可以重算出来。

        现在：
          · 目录在就直接用；不在就从 art.bin 现场生成（一档约 3 秒）；
          · 安装本身在进程内写注册表，不再需要 install.ps1 / PowerShell。
        """
        win = tk.Toplevel(self.root)
        win.title('安装指针（文件式）')
        win.configure(bg=BG)
        win.resizable(False, False)
        ttk.Label(win, text='选择要装进「鼠标属性 → 指针 → 方案」的档位',
                  style='H.TLabel').grid(row=0, column=0, columnspan=3,
                                         padx=16, pady=(12, 4), sticky='w')
        ttk.Label(win, text='注意：Windows 用方案加载光标时一律渲染成 32px，'
                            '想要大指针请用「指针大小」页签的「应用」。',
                  style='D.TLabel', wraplength=430, justify='left'
                  ).grid(row=1, column=0, columnspan=3, padx=16,
                         sticky='w')
        f = ttk.Frame(win)
        f.grid(row=2, column=0, columnspan=3, padx=16, pady=10)

        def run(tier_key):
            win.destroy()
            self._install_tier(tier_key)

        for i, (t, zh, desc) in enumerate(TIERS):
            ttk.Button(f, text='%s（%s）' % (zh, desc), width=18,
                       command=lambda x=t: run(x)).grid(row=0, column=i,
                                                        padx=3)
        ttk.Button(f, text='恢复原始光标', width=18,
                   command=lambda: (win.destroy(), self.do_restore())
                   ).grid(row=1, column=0, columnspan=3, pady=6)

    def _install_tier(self, tier_key):
        """装一档：需要的话先把文件造出来，再登记方案。"""
        art = paths.find_art()
        if not art:
            messagebox.showerror('缺少美术包',
                                 '找不到 art.bin，既没有现成的指针文件，'
                                 '也没法现场生成。\n请用完整发布包里的程序。')
            return
        tier = next((t for t in cw.PACK_TIERS if t[0] == tier_key), None)
        if tier is None:
            messagebox.showerror('未知档位', tier_key)
            return
        root = paths.find_pack() or os.path.join(paths.APP_DIR, 'cursors')
        if packbuild.have_tier(root, tier[0]):
            self._finish_install(root, tier)
        else:
            self._build_pack(root, tier, art)

    def _build_pack(self, root, tier, art):
        """现场生成缺的那一档（约 3 秒），带一个进度窗口。"""
        win = tk.Toplevel(self.root)
        win.title('正在生成指针文件')
        win.configure(bg=BG)
        win.resizable(False, False)
        ttk.Label(win, text='本机没有指针文件，正在从内嵌美术包重建…',
                  style='H.TLabel').grid(row=0, column=0, padx=18,
                                         pady=(14, 6), sticky='w')
        msg = ttk.Label(win, text='准备中', style='D.TLabel', width=44)
        msg.grid(row=1, column=0, padx=18, sticky='w')
        bar = ttk.Progressbar(win, length=340, maximum=len(cw.ROLES))
        bar.grid(row=2, column=0, padx=18, pady=(6, 16))

        box = {'done': 0, 'cur': '', 'err': None}

        def progress(done, total, key):
            box['done'], box['cur'] = done, key

        def work():
            try:
                packbuild.build_tier(art, root, tier[0], tier[1],
                                     progress=progress)
            except Exception as e:       # 线程里必须自己兜住，否则悄无声息
                box['err'] = e

        th = threading.Thread(target=work, daemon=True)
        th.start()

        def poll():
            if th.is_alive():
                bar['value'] = box['done']
                msg.configure(text='%s（%d/%d）'
                                  % (box['cur'] or '准备中', box['done'],
                                     len(cw.ROLES)))
                win.after(120, poll)
                return
            win.destroy()
            if box['err'] is not None:
                messagebox.showerror('生成失败', str(box['err']))
                return
            self._finish_install(root, tier)

        poll()

    def _finish_install(self, root, tier):
        """把这一档登记成一份 Windows 方案（写注册表的活交给 packbuild）。"""
        try:
            name, _found = packbuild.register(root, tier[0])
        except (RuntimeError, OSError) as e:
            messagebox.showerror('登记方案失败', str(e))
            return
        self.say('已登记方案「%s」· 17/17 个角色' % name, OK)
        messagebox.showinfo(
            '安装完成',
            '已登记到「鼠标属性 → 指针 → 方案」：\n\n    %s\n\n'
            '打开 鼠标属性 → 指针，在「方案」下拉框里就能选到它。\n'
            '（Windows 用方案加载光标时一律渲染成 32px，想要大指针请用'
            '「指针大小」页签的「应用」。）' % name)

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
            exe_path = os.path.join(paths.APP_DIR, 'ArknightsMouse.exe')
            if getattr(sys, 'frozen', False):
                cmd = [sys.executable, '--guard']
            elif os.path.isfile(exe_path):
                cmd = [exe_path, '--guard']
            else:
                cmd = [sys.executable,
                       os.path.join(paths.APP_DIR, 'src', 'arkmouse',
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
        # PRTS 水晶状态灯跟着守护状态走（占位方块没有 set_alive，静默跳过）
        set_alive = getattr(self.crystal_guard, 'set_alive', None)
        if callable(set_alive):
            set_alive(alive)
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
        p = paths.backup_path(t)
        try:
            d = mousep.backup(p)
            cur = paths.BACKUP_CUR
            mousep.backup(cur)
            self.say('已备份 %d 项到 %s' % (len(d.get('registry', {})),
                                          os.path.basename(p)), OK)
        except Exception as e:
            self.say('备份失败：%s' % e, BAD)

    def do_restore_mouse(self):
        cur = paths.BACKUP_CUR
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
            cur = paths.BACKUP_CUR
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
    err_path = paths.ERR_LOG
    run_path = paths.RUN_LOG
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
        tier_key = argv[i + 1] if i + 1 < len(argv) else 'large'
        return _cli_install(tier_key)
    return None


def _cli_install(tier_key):
    """命令行安装：确保某一档文件在，再登记成 Windows 方案。

    和 GUI 的「安装指针」走同一条路 —— 文件缺了就从 art.bin 现场生成，
    所以只有一个 exe 也能用：`ArknightsMouse.exe --install p72`。

    注意：打包成 --windowed 后 sys.stdout 是 None，print 会抛
    AttributeError。这里一律走 say() 兜住，免得命令行安装无声崩溃。
    """
    def say(msg):
        try:
            print(msg, flush=True)
        except Exception:            # stdout 为 None / 已关闭
            pass

    tier = next((t for t in cw.PACK_TIERS if t[0] == tier_key), None)
    if tier is None:
        say('未知档位：%s（可选：%s）'
            % (tier_key, '、'.join(t[0] for t in cw.PACK_TIERS)))
        return 2
    root = paths.find_pack() or os.path.join(paths.APP_DIR, 'cursors')
    if not packbuild.have_tier(root, tier[0]):
        art = paths.find_art()
        if not art:
            say('既没有现成的指针文件，也找不到 art.bin，无法安装')
            return 2
        say('本机缺少 %s 档的指针文件，正在从 art.bin 重新生成…' % tier[0])
        try:
            packbuild.build_tier(
                art, root, tier[0], tier[1],
                progress=lambda n, total, key: say('  %d/%d %s'
                                                   % (n, total, key)))
        except Exception as e:          # noqa: BLE001 - 命令行要给原因
            say('生成失败：%s' % e)
            return 2
    try:
        name, found = packbuild.register(root, tier[0])
    except (RuntimeError, OSError) as e:
        say('登记方案失败：%s' % e)
        return 2
    say('已登记方案：%s（%d/%d 个角色）' % (name, len(found), len(cw.ROLES)))
    say('目录：%s' % packbuild.tier_dir(root, tier[0]))
    return 0


def _mei_marker(d):
    return os.path.join(d, '.arkpid')


def _pid_alive(pid):
    """判断 PID 是否还活着（Windows）。失败一律当「活着」，宁可少删。

    ⚠️ OpenProcess 失败**不等于进程不存在**：对方以管理员身份运行、而我们
    不是时，OpenProcess 会因 ERROR_ACCESS_DENIED(5) 失败。这时必须当成"活着"，
    否则会把正在运行的实例的解包目录当垃圾删掉 —— 受害者随即在 tk.Tk() 处
    报 Can't find a usable init.tcl 秒退（就是用户说的「闪退」）。
    """
    try:
        import ctypes
        k = ctypes.windll.kernel32
        h = k.OpenProcess(0x1000, False, int(pid))   # PROCESS_QUERY_LIMITED_INFO
        if not h:
            err = ctypes.get_last_error() if hasattr(ctypes, 'get_last_error') \
                else k.GetLastError()
            return err == 5                          # 5 = ERROR_ACCESS_DENIED
        try:
            code = ctypes.c_ulong(0)
            if not k.GetExitCodeProcess(h, ctypes.byref(code)):
                return True
            return code.value == 259                 # STILL_ACTIVE
        finally:
            k.CloseHandle(h)
    except Exception:
        return True


def _sweep_stale_mei():
    """清掉 PyInstaller onefile 遗留的 _MEI* 解包目录（防止越攒越多撑爆磁盘）。

    背景：onefile 每次启动都要把 art.bin/fx.bin/Tcl 等约 30MB 解包到一个
    _MEIxxxxx 目录（正常退出会自己删；被强杀就留下来）。攒多了之后连
    bootloader 都会直接报「Could not create temporary directory!」。
    打包时已用 --runtime-tmpdir 把解包位置钉到工程内 runtime\\，并由
    build_exe.py 负责清理，这里只做兜底。

    ⚠️ **这段代码本身踩过一个大坑，判据必须同时满足两条才删**：
    界面与守护是**两个独立进程**（paths.child_env() 剥掉 _PYI_*/_MEI*，
    让子进程各自解包，避免互相锁住对方的目录）。于是 runtime\\ 下会**同时
    存在多个 _MEI**，其中至少一个属于**正在运行**的另一个实例。
    早先的版本「只要不是我就删」，结果后启动的一方可把先启动一方的目录删掉，
    受害者随即在 tk.Tk() 处炸：

        _tkinter.TclError: Can't find a usable init.tcl in the following
        directories: {...\\runtime\\_MEI000022502\\_tcl_data} ...

    用户看到的就是「打开就报错」。所以现在只删**确定是垃圾**的：
      ① 目录里有 .arkpid 且那个 pid 还活着   → 跳过（别人在用）
      ② 目录里有 .arkpid 但 pid 已死         → 删
      ③ 目录没有 .arkpid                     → 一律跳过（无法区分「正在解包」）
    自己这份永远跳过。没有标记的目录留给 build_exe.py 打包时清。
    """
    if not getattr(sys, 'frozen', False):
        return                                  # 源码运行没有 _MEIPASS
    meipass = getattr(sys, '_MEIPASS', '') or ''
    if not meipass:
        return
    mine = os.path.abspath(meipass)
    tmp = os.path.dirname(mine)                 # 解包目录的上一层
    if not tmp or not os.path.isdir(tmp):
        return

    # 先给自己这份打标记，让别的实例知道「我还在用」
    try:
        with open(_mei_marker(mine), 'w', encoding='utf-8') as f:
            f.write(str(os.getpid()))
    except OSError:
        pass

    try:
        names = os.listdir(tmp)
    except OSError:
        return
    for n in names:
        if not n.startswith('_MEI'):
            continue
        d = os.path.abspath(os.path.join(tmp, n))
        if d == mine:
            continue                            # 自己正在用
        if not os.path.isdir(d):
            continue
        # ① / ② 有没有属主标记，属主还活着吗
        try:
            with open(_mei_marker(d), 'r', encoding='utf-8') as f:
                owner = int((f.read() or '0').strip() or 0)
        except (OSError, ValueError):
            owner = 0
        # 只删「有属主标记且属主已死」的目录 —— 其余一律不动。
        # 没有标记的目录无法与「刚解包完、Python 还没跑到写标记」区分，
        # 误删活目录的代价是对端在 tk.Tk() 处秒退：
        #   _tkinter.TclError: Can't find a usable init.tcl … {…\_MEI…\_tcl_data}
        # 垃圾桶目录交给 build_exe.py 打包时清，宁多留几个也不冒这个风险。
        if not owner:
            continue
        if owner == os.getpid() or _pid_alive(owner):
            continue                            # 自己 / 别人正在用
        # ③ 确认是垃圾 —— 直接写一个文件试试，被占用会失败
        try:
            probe = os.path.join(d, '.arkprobe')
            with open(probe, 'w', encoding='utf-8') as f:
                f.write('x')
            os.remove(probe)
        except OSError:
            continue
        try:
            import shutil
            shutil.rmtree(d, ignore_errors=True)
        except Exception:
            pass


def _fatal(exc):
    """启动期致命异常的兜底：写日志 + 弹一个原生消息框，不要静默秒退。

    背景：--windowed 打包后没有控制台，main() 里抛出的异常既看不到也无处可写，
    表现就是「双击后窗口一闪就没」。把 traceback 落盘 + 弹框，才能拿到证据。
    这里**只用标准库和 ctypes**，不碰 tkinter（崩的可能正是 tkinter）。
    """
    import traceback
    tb = traceback.format_exc()
    try:
        import paths
        p = paths.ERR_LOG
        try:
            d = os.path.dirname(p)
            if d:
                os.makedirs(d, exist_ok=True)
        except OSError:
            pass
        with open(p, 'a', encoding='utf-8') as f:
            f.write('\n\n===== %s 启动失败 =====\n'
                    % time.strftime('%Y-%m-%d %H:%M:%S'))
            f.write(tb)
    except Exception:
        pass
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(
            None,
            ('程序启动失败，已记录到：\n%s\n\n%s\n%s'
             % (getattr(sys.modules.get('paths'), 'ERR_LOG', 'error.log'),
                '-' * 48, tb[-1200:])),
            '明日方舟鼠标 · 启动失败', 0x10)
    except Exception:
        pass
    return 1


def main():
    try:
        # 第一件事：把「非 Microsoft 签名的 PE 不许载入本进程」这条策略挂上。
        # 游戏加加（GamePP）的 GPP64.dll 是全局钩子注入进任意进程的，它一进来就
        # 在自己的钩子代码里 0xc0000005，把本程序一起带走；策略生效后它连加载都
        # 过不去（577），钩子不会在本进程里跑，崩点也就无从触发。必须放在
        # tk.Tk() 之前、且此时 tkinter/PIL 已经导入完毕（apply 内部还会预热
        # prtsfx 等延迟导入模块），否则会误伤自己。
        harden.apply()
        _safe_io()
        _sweep_stale_mei()
        cw.dpi_aware()
        # 目录/文件改名（v3 全英文）后的自启项修正：Run 键若还指着旧 exe，
        # 开机是静默失败，用户只会觉得「自启没生效」。
        try:
            store.fix_autostart_path()
        except Exception:
            pass
        r = cli(sys.argv[1:])
        if r is not None:
            return r
        root = tk.Tk()
        App(root)
        root.mainloop()
        return 0
    except SystemExit:
        raise
    except BaseException:
        return _fatal(sys.exc_info()[1])


if __name__ == '__main__':
    sys.exit(main())
