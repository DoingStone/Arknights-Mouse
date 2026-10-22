# -*- coding: utf-8 -*-
"""明日方舟鼠标 · 科技风 / PRTS 主题层（arktheme）

设计来源：ui-ux-pro-max 设计引擎 · Tech/HUD 风格规格（hud / tech / data），
叠加明日方舟 PRTS 终端美学：

  · 深蓝黑操作台底色 + 方舟金（#f5c451）主强调 + 冰蓝（#7fd4ff）数据色
  · 切角面板（chamfer）：舟 UI 标志性的斜切边框，1px 细线 + 四角 HUD 角标
  · 扫描线 / 网格底纹：预览台与窗口背景的低亮度技术纹理
  · 等宽数字（Consolas）：所有读数、状态、编号走等宽，营造终端感
  · PRTS 水晶自旋：art.bin 里 Wait 族 72 帧动画（16ms/帧），
    就是游戏里那个旋转的水晶菱形 —— 头部常驻、守护状态指示都用它

对比度均为 WCAG 相对亮度实测：正文 ≥4.5:1、次要文字 ≥4.5:1、
禁用文字 ≥3:1、描边与层级 ≥1.6:1。改色前请先复算，不要凭肉眼判断。
"""
import tkinter as tk

from PIL import Image, ImageTk

# ---------------------------------------------------------------- 令牌
BG = '#0a0d13'      # 窗口底（操作台）
BG2 = '#10141d'     # 次级底（兼容旧引用）
CARD = '#121722'    # 卡片面板（对窗口底 1.17:1，能从背景浮起来）
CARD2 = '#171d2b'   # 控件底（比卡片亮一档）
EDGE = '#2a3348'    # 卡片 / 控件描边（对卡片 1.9:1）
EDGE_H = '#46536f'  # 描边（悬停 / 聚焦，对卡片 3.3:1）
RAISE = '#1b2231'   # 控件底（兼容旧引用，同 CARD2）
RAISE_H = '#232c3f'  # 控件底（悬停）
RAISE_P = '#2c374e'  # 控件底（按下）
TAB_ACTIVE = '#1a2130'  # 未选中页签的悬停底
WELL = '#070a0f'    # 内凹槽（预览台）
FG = '#e8ecf3'      # 正文
FG2 = '#aeb6c6'     # 次要文字
DIM = '#7d8699'     # 弱文字（对卡片 4.7:1）
DIS_BG = '#1a1f2c'  # 禁用控件底
DIS_FG = '#6d7690'  # 禁用控件文字（对禁用底 3.6:1）
ACC = '#f5c451'     # 方舟金（主强调）
ACC_D = '#c99a35'   # 金（按下）
ACC_H = '#ffd97a'   # 金（悬停）
ACC_INK = '#1a1503'  # 金底上的深色字
ICE = '#7fd4ff'     # 冰蓝（PRTS 数据色，对卡片 9.9:1）
OK = '#5fd18b'      # 通过（绿）
BAD = '#ef6f6f'     # 异常（红）
GRID = '#0e131c'    # 窗口背景网格线（对 BG 1.15:1，只做纹理）
MINI = '#69738a'    # 8pt 技术小字（页脚签名等，对卡片 ≥3:1）

FONT = 'Microsoft YaHei UI'
MONO = 'Consolas'   # 等宽：读数 / 编号 / 状态

# 预览台网格
PREV_GRID = '#0f1520'    # 20px 主网格
PREV_GRID2 = '#131b29'   # 100px 加亮网格
PREV_SCAN = '#0c121b'    # 扫描线（4px 一条，压暗）
PREV_FRAME = '#1c2637'   # 预览台内框

# ---------------------------------------------------------------- 双主题
# 明日方舟 UI 的骨架是「深炭灰操作台」，但同一套骨架也撑得住「档案台」
# 浅色变体：保持切角 + 1px 细边框 + 方舟金点睛 + 等宽读数，只把灰阶
# 反相到纸面（L0 浅灰 → 卡片纯白 → 内凹槽冷灰），主色由「方舟金」换成
# 浅底上对比度达标的「档案金」#9a6f00（对白 4.52:1，满足正文门槛）。
#
# 对比度（WCAG 相对亮度实测，脚本 _contrast2.py）：
#   light：正文/卡 17.6、次要 8.8、弱字 5.2、禁用字 3.2、金 4.5 —— 全 PASS
#   dark ：正文/卡 15.1、次要 8.8、弱字 4.9、禁用字 3.6、金 11.0 —— 全 PASS
# 改任何色值先复跑 _contrast2.py。
_PALETTE = {
    'dark': {
        'BG': '#0a0d13', 'BG2': '#10141d', 'CARD': '#121722', 'CARD2': '#171d2b',
        'EDGE': '#2a3348', 'EDGE_H': '#46536f', 'RAISE': '#1b2231',
        'RAISE_H': '#232c3f', 'RAISE_P': '#2c374e', 'TAB_ACTIVE': '#1a2130',
        'WELL': '#070a0f', 'FG': '#e8ecf3', 'FG2': '#aeb6c6', 'DIM': '#7d8699',
        'MINI': '#69738a', 'DIS_BG': '#1a1f2c', 'DIS_FG': '#6d7690',
        'ACC': '#f5c451', 'ACC_D': '#c99a35', 'ACC_H': '#ffd97a',
        'ACC_INK': '#1a1503', 'ICE': '#7fd4ff', 'OK': '#5fd18b', 'BAD': '#ef6f6f',
        'GRID': '#0e131c', 'PREV_GRID': '#0f1520', 'PREV_GRID2': '#131b29',
        'PREV_SCAN': '#0c121b', 'PREV_FRAME': '#1c2637',
    },
    'light': {
        'BG': '#eef1f6', 'BG2': '#e3e8f0', 'CARD': '#ffffff', 'CARD2': '#f4f7fb',
        'EDGE': '#b8c2d3', 'EDGE_H': '#7d8ba3', 'RAISE': '#e7ecf4',
        'RAISE_H': '#d8e0ec', 'RAISE_P': '#c3cee0', 'TAB_ACTIVE': '#dde5f0',
        'WELL': '#d5dded', 'FG': '#141922', 'FG2': '#414b5c', 'DIM': '#616d80',
        'MINI': '#78849a', 'DIS_BG': '#dfe4ec', 'DIS_FG': '#737e91',
        'ACC': '#9a6f00', 'ACC_D': '#7d5a00', 'ACC_H': '#b7870c',
        'ACC_INK': '#ffffff', 'ICE': '#0f6f95', 'OK': '#1a7f4b', 'BAD': '#b23b3b',
        'GRID': '#dde3ec', 'PREV_GRID': '#cdd6e3', 'PREV_GRID2': '#bcc7d6',
        'PREV_SCAN': '#c2ccd9', 'PREV_FRAME': '#96a3b6',
    },
}

# 当前主题名（set_theme 改；read_theme() 查询）
_theme = ['dark']


def set_theme(name):
    """切换配色主题：'dark' | 'light'。只改色值，不碰任何控件。

    本模块的模块级常量（BG / CARD / …）是**导入时刻的快照**，切换后不会
    自动跟着变；动态取值请用 color()。main.pyw 的 _recolor() 会把控件
    底色逐个刷成新值，arktheme 内部的绘制函数（grid_background /
    hazard_stripe / TechCard / render_preview）则在重绘时走 color()，因此
    只要触发一次重绘就全部跟随。
    """
    n = 'light' if str(name).strip().lower() == 'light' else 'dark'
    _theme[0] = n
    return n


def read_theme():
    return _theme[0]


def color(key, theme=None):
    """按名取当前（或指定）主题的色值；未知键回退深色表，再回退 '#000000'。"""
    t = _PALETTE.get(theme or _theme[0], _PALETTE['dark'])
    return t.get(key, _PALETTE['dark'].get(key, '#000000'))


# 本模块内部绘制代码用的动态别名（每次重绘现取，换主题自动跟随）
def _c(k):
    return color(k)



# ---------------------------------------------------------------- 窗口网格底纹
def grid_background(root):
    """给根窗口铺一层 28px 技术网格（放在最底层，只从卡片边距里透出来）。"""
    cv = tk.Canvas(root, bg=_c('BG'), highlightthickness=0, bd=0)
    cv.place(x=0, y=0, relwidth=1, relheight=1)
    try:
        # Canvas 把 lower() 占用为「标签降层」，窗口降层得走底层 tk 调用
        cv.tk.call('lower', cv._w)
    except Exception:
        pass

    def draw(_e=None):
        cv.delete('all')
        cv.configure(bg=_c('BG'))
        w, h = cv.winfo_width(), cv.winfo_height()
        if w < 8 or h < 8:
            return
        step = 28
        for x in range(0, w, step):
            cv.create_line(x, 0, x, h, fill=_c('GRID'))
        for y in range(0, h, step):
            cv.create_line(0, y, w, y, fill=_c('GRID'))

    cv.bind('<Configure>', draw)
    # 换主题后由 _recolor() 调一次，立即重铺（否则要等下次 <Configure>）
    cv.redraw = draw
    return cv


# ---------------------------------------------------------------- HUD 小件
def tech_rule(parent, seg=72):
    """科技分隔线：整条 EDGE 细线 + 左端一段金色（页签标题下用）。

    必须独占一个容器里的整行 —— 和 side='left/right' 的兄弟共处一框时，
    pack 会把它塞进剩下的中缝里，位置就飘了。调用方给它单独一层即可。
    """
    rule = tk.Frame(parent, bg=_c('EDGE'), height=1)
    rule.pack(fill='x', pady=(9, 0))
    rule.pack_propagate(False)
    acc = tk.Frame(rule, bg=_c('ACC'), height=1, width=seg)
    acc.place(x=0, y=0)
    # 换主题时由 _recolor() 沿「子 Frame」刷色，这里只负责建
    return rule


def hazard_stripe(parent, height=5, bg=None):
    """斜纹警示条：金 / 深金 45° 条纹（明日方舟 UI 的经典饰边）。

    bg 调用方给的是**导入时刻快照**（模块级常量），换主题时它不会变。
    所以 draw() 一律用 `_c('BG')`（动态取当前主题），只有显式传了 bg
    （比如想贴在卡片上）才用传进来的值 —— 但那也必须是调用方用
    `T.color('BG')` 现取的值，否则换主题后斜纹底会停在旧色。
    """
    fixed = bg
    cv = tk.Canvas(parent, height=height, bg=fixed or _c('BG'),
                   highlightthickness=0, bd=0)
    cv.pack(fill='x')

    def draw(_e=None):
        cv.delete('all')
        cv.configure(bg=fixed or _c('BG'))
        w = cv.winfo_width()
        if w < 8:
            return
        x = -height
        while x < w + height:
            cv.create_line(x, height, x + height, 0, fill=_c('ACC'), width=2)
            cv.create_line(x + height // 2, height, x + height // 2 + height, 0,
                           fill=_c('ACC_D'), width=2)
            x += 9

    cv.bind('<Configure>', draw)
    cv.redraw = draw
    return cv


def led(parent, color_, text='', bg=None):
    """HUD 状态灯：小方块 + 等宽文案（● 的方块化，避免字体缺字形）。"""
    bg = bg or _c('CARD')
    row = tk.Frame(parent, bg=bg)
    box = tk.Canvas(row, width=8, height=8, bg=bg, highlightthickness=0,
                    bd=0)
    box.create_rectangle(0, 0, 7, 7, fill=color_, outline='')
    box.pack(side='left', padx=(0, 6), pady=(2, 0))
    if text:
        tk.Label(row, text=text, bg=bg, fg=_c('FG2'), font=(MONO, 9)).pack(
            side='left')
    return row


# ---------------------------------------------------------------- 勾选框标记
# clam 主题内置的 Checkbutton.indicator 在「选中」时画的是一个**对称的叉**
# （✗）——语义上读起来像「不可用 / 未勾选」，跟方舟 UI 的「金底白勾」完全相反。
# 形状由 Tk 的 C 层内置元素决定，样式表里的 indicatorsize / indicatorforeground
# 只能改尺寸和颜色、改不了笔画，所以只能整个换掉：
#   element_create 自建 image 元素 → 再改 layout 让 TCheckbutton 用它。
# 元素名按主题区分（元素一旦创建就不能重建，��主题得用新名字）。
_CK_IMAGES = {}      # {元素名: [PhotoImage, ...]}  —— 必须保活，否则被 GC 变空白


def _ck_images(box, edge, mark, size=18, gap=8, dis_fill=None, dis_mark=None):
    """画四枚勾选框位图：常态/选中/禁用/禁用选中。

    返回 PIL Image 列表，顺序 [off, on, off_dis, on_dis]。
    右侧留 gap 像素透明边距 —— image 元素不吃 indicatormargin，
    间距只能画进位图里。

    禁用态要**看起来就和可用态不同**，否则「本机不支持」那几行跟能点的
    一模一样。做法：dis_fill 当底色、描边也用 dis_fill（合成一块压暗的
    实心方块，和可用态的空心细边形成对比），勾用 dis_mark 画在上面。
    """
    from PIL import Image, ImageDraw
    w = size + gap
    out = []
    for on, dis in ((False, False), (True, False), (False, True), (True, True)):
        im = Image.new('RGBA', (w, size), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        if dis:
            bg_c = dis_fill or box
            mk_c = dis_mark or mark
            # 禁用态：整块实心 + 同色描边（没有空心感）
            d.rectangle([0, 0, size - 1, size - 1], fill=bg_c, outline=bg_c,
                        width=1)
            if on:
                d.line([(4.5, size * 0.54), (size * 0.42, size - 5.0),
                        (size - 4.0, 5.0)], fill=mk_c, width=2, joint='curve')
        else:
            d.rectangle([0, 0, size - 1, size - 1],
                        fill=box if on else None, outline=edge, width=1)
            if on:
                d.line([(4.5, size * 0.54), (size * 0.42, size - 5.0),
                        (size - 4.0, 5.0)], fill=mark, width=2, joint='curve')
        out.append(im)
    return out


def install_check_indicator(style, theme):
    """装两套勾选框：可用（空心细边 / 金底白勾）与禁用（压暗实心方块）。

    为什么拆成两个元素 + 两个样式，而不是给一个元素挂 ('disabled', …)？
      ttk 的 image 元素**不认** `('disabled', img)` 这条状态映射（实测：
      给禁用勾选框挂上后仍然画的是常态图）。所以把「禁用长什么样」直接
      做成独立元素，再给禁用的那几个复选框换一个样式名 —— 确定性更高。
      用法：`cb.configure(style='Dis.TCheckbutton')`。

    theme: 'dark' | 'light'（元素名带主题后缀，因为 element_create 不可重建）
    """
    name = 'ArkCk.%s.indicator' % theme
    dname = 'ArkCkDis.%s.indicator' % theme
    if name not in _CK_IMAGES:
        # 每个主题只建一次（element_create 不可重建，重复调用会抛 Duplicate）
        size = 18
        normal = _ck_images(_c('ACC'), _c('EDGE_H'), _c('ACC_INK'), size=size)
        dis = _ck_images(_c('ACC'), _c('EDGE_H'), _c('ACC_INK'), size=size,
                         dis_fill=_c('DIS_BG'), dis_mark=_c('DIS_FG'))
        ph = [ImageTk.PhotoImage(normal[0]), ImageTk.PhotoImage(normal[1]),
              ImageTk.PhotoImage(dis[2]), ImageTk.PhotoImage(dis[3])]
        _CK_IMAGES[name] = ph
        _CK_IMAGES[dname] = ph
        style.element_create(name, 'image', ph[0], ('selected', ph[1]))
        style.element_create(dname, 'image', ph[2], ('selected', ph[3]))

    def _layout(ind):
        return [
            ('Checkbutton.padding', {'sticky': 'nswe', 'children': [
                (ind, {'side': 'left', 'sticky': ''}),
                ('Checkbutton.focus', {'side': 'left', 'sticky': 'w',
                 'children': [('Checkbutton.label', {'sticky': 'nswe'})]}),
            ]}),
        ]

    style.layout('TCheckbutton', _layout(name))
    style.layout('Dis.TCheckbutton', _layout(dname))
    return name


# ---------------------------------------------------------------- 切角卡片
class TechCard(tk.Canvas):
    """明日方舟式切角卡片：斜切多边形底 + 1px 描边 + 四角 HUD 角标。

    用法：
        card = TechCard(parent, title='尺寸调节', sub='…')
        card.pack(fill='x', padx=…, pady=…)
        card.body   ← 往这里 pack 内容（和旧 _card 返回的 box 一样用）

    实现要点：
      · 内容放在 create_window 的 body 框架里，画布只负责「壳」；
      · body 宽度由 canvas window item 的 width 选项钉死（不能用
        body.configure(width=…) —— pack 传播会把它收缩回子级自然宽），
        fill='x' 的子控件随窗口重排；高度回填 body 的请求高度，卡片自动伸缩；
      · <Configure> 里用 tag='shell' 只重画多边形与角标，window 项不动。
    """

    def __init__(self, parent, title=None, sub=None, sub_wrap=760,
                 pad=16, chamfer=10, accent=None, bg=None, edge=None,
                 brackets=True, extra=None):
        """extra：标题行右侧的挂件。传工厂函数 extra(title_row) → widget，
        在回调里创建并返回 —— tkinter 的 widget 建好就不能换爹，
        所以不能在外部 new 好再传进来。"""
        bg = bg or _c('CARD')
        edge = edge or _c('EDGE')
        accent = accent or _c('ACC')
        tk.Canvas.__init__(self, parent, bg=bg, highlightthickness=0, bd=0)
        self.pad = pad
        self.chamfer = chamfer
        self.accent = accent
        self._bg = bg
        self._edge = edge
        self._brackets = brackets
        self._sub_wrap = sub_wrap

        self.body = tk.Frame(self, bg=bg)
        if title:
            row = tk.Frame(self.body, bg=bg)
            row.pack(fill='x')
            mk = tk.Frame(row, bg=self.accent, width=7, height=7)
            mk.pack(side='left', padx=(0, 8), pady=(3, 0))
            mk.pack_propagate(False)
            tk.Label(row, text=title, bg=bg, fg=_c('FG'),
                     font=(FONT, 10, 'bold')).pack(side='left')
            if extra is not None:
                w = extra(row) if callable(extra) else extra
                w.pack(side='right')
            self.title_row = row
        if sub:
            self.sub = tk.Label(self.body, text=sub, bg=bg, fg=_c('DIM'),
                                font=(FONT, 9), justify='left',
                                wraplength=sub_wrap)
            self.sub.pack(anchor='w', pady=(3, 0))
        else:
            self.sub = None

        self._win = self.create_window(pad, pad, window=self.body,
                                       anchor='nw')
        self.bind('<Configure>', self._redraw)
        self.body.bind('<Configure>', lambda e: self.after_idle(self._fit))

    # ---- 画壳 ----
    def _redraw(self, _e=None):
        # 只删「壳」（tag='shell'），绝不能用 delete('all') —— 那会把承载
        # body 的 window 项一起删掉，重建时几何抖动会自激成 265↔35 振荡，
        # root.update() 永远等不到事件枯竭。
        self.delete('shell')
        w, h = self.winfo_width(), self.winfo_height()
        if w < 8 or h < 8:
            return
        # 换主题后色值可能已变：重画时现取，别用 __init__ 里记的旧值
        bg = self._bg or _c('CARD')
        edge = self._edge or _c('EDGE')
        acc = self.accent or _c('ACC')
        c = min(self.chamfer, w // 4, h // 4)
        pts = [c, 0, w - c, 0, w, c, w, h - c, w - c, h, c, h, 0, h - c, 0, c]
        self.create_polygon(pts, fill=bg, outline='', tags='shell')
        self.create_polygon(pts, fill='', outline=edge, width=1,
                            tags='shell')
        if self._brackets:
            a = 11
            for (x, y, dx, dy) in ((1, 1, 1, 1), (w - 1, 1, -1, 1),
                                   (1, h - 1, 1, -1), (w - 1, h - 1, -1, -1)):
                self.create_line(x, y, x + dx * a, y, fill=acc,
                                 width=1, tags='shell')
                self.create_line(x, y, x, y + dy * a, fill=acc,
                                 width=1, tags='shell')
        # 壳画在 window 之后会把内容盖住，显式把内容窗口提到最上
        self.tag_raise(self._win)
        self.after_idle(self._fit)

    def recolor(self):
        """换主题后调用：把壳、标题、正文刷成新配色并重画。"""
        self._bg = None
        self._edge = None
        self.accent = None
        self.configure(bg=_c('CARD'))
        self.body.configure(bg=_c('CARD'))
        for w in self._descendants(self.body):
            cls = w.winfo_class()
            if cls == 'Frame':
                try:
                    w.configure(bg=_c('CARD'))
                except Exception:
                    pass
            elif cls == 'Label':
                try:
                    cur = str(w.cget('font'))
                except Exception:
                    cur = ''
                fg = _c('DIM') if ' 9' in cur and 'bold' not in cur else _c('FG')
                try:
                    w.configure(bg=_c('CARD'), fg=fg)
                except Exception:
                    pass
        if getattr(self, 'title_row', None) is not None:
            for w in self.title_row.winfo_children():
                if w.winfo_class() == 'Frame':
                    w.configure(bg=_c('ACC'))
        self._redraw()

    @staticmethod
    def _descendants(widget):
        out = []
        for child in widget.winfo_children():
            out.append(child)
            out.extend(TechCard._descendants(child))
        return out

    # ---- 尺寸回填 ----
    def _fit(self):
        w = self.winfo_width()
        if w > 8:
            bw = max(60, w - 2 * self.pad)
            # 必须用 canvas window item 的 width 选项拉宽 body：
            # body.configure(width=…) 会被 pack 传播收缩回子级自然宽，
            # fill='x' 的标题行因此只剩 77px，右侧挂件（水晶）被挤丢。
            self.itemconfigure(self._win, width=bw)
            if self.sub is not None:
                self.sub.configure(wraplength=max(120, min(self._sub_wrap,
                                                           bw - 4)))
        # 请求宽度 = 内容自然宽 + 壳。Canvas 的请求宽默认不看 window 项
        # 里的内容，不补这一步父层就传播不到真实内容宽 —— 窗口的请求尺寸
        # 会塌到 804px，右列被裁。
        # 注意不能用 body.winfo_reqwidth()：body 宽度已被上面 itemconfigure
        # 强制，它回的是**强制宽**，拿它算请求宽就成了「请求=当前宽」的循环，
        # 窗口永远撑不回内容自然宽（969px 处右列仍被裁）。
        # 改取 body 各子级的自然请求宽最大值 —— 子级请求宽由各自内容决定，
        # 与父级分到的宽度无关。
        kids = self.body.winfo_children()
        nat_body = max((k.winfo_reqwidth() for k in kids), default=60)
        nat = nat_body + 2 * self.pad + 2
        if str(self.cget('width')) != str(nat):
            self.configure(width=nat)
        # 滞回：差 1px 以内不写回，避免和 pack 的几何计算互相追赶
        want = self.body.winfo_reqheight() + 2 * self.pad + 2
        if abs(want - self.winfo_height()) > 1:
            self.configure(height=want)


# ---------------------------------------------------------------- PRTS 水晶自旋
_FRAME_CACHE = {}


def _spin_frames(pack, size, dim):
    """按尺寸预渲染 Wait 族帧；dim=True 时压暗 55%（守护停用态）。"""
    key = (pack.path, size, dim)
    hit = _FRAME_CACHE.get(key)
    if hit is not None:
        return hit
    out = []
    for im, _hx, _hy in pack.frames('Wait'):
        f = im.resize((size, size), Image.LANCZOS)
        if dim:
            f = Image.blend(f, Image.new('RGBA', f.size, (0, 0, 0, 255)),
                            0.55)
        out.append(ImageTk.PhotoImage(f))
    _FRAME_CACHE[key] = out
    return out


class CrystalSpin(tk.Label):
    """PRTS 水晶自旋指示器 —— art.bin 里 Wait 族的 72 帧水晶动画。

    活着（守护运行 / PRTS 在线）时按 16ms 原帧节拍旋转；
    停用时静帧压暗。帧按尺寸缓存，多个实例共享同一组 PhotoImage。
    """

    def __init__(self, parent, pack, size=44, bg=None, alive=True, rate=16):
        self._frames = _spin_frames(pack, size, False)
        self._dim_frames = _spin_frames(pack, size, True)
        self._alive = alive
        self._i = 0
        self._rate = rate
        self._job = None
        tk.Label.__init__(self, parent, image=self._frames[0],
                          bg=bg or _c('CARD'),
                          bd=0, highlightthickness=0)
        if not alive:
            self.configure(image=self._dim_frames[0])
        else:
            self._tick()

    def _tick(self):
        if not self._alive:
            return
        self._i = (self._i + 1) % len(self._frames)
        self.configure(image=self._frames[self._i])
        self._job = self.after(self._rate, self._tick)

    def set_alive(self, alive):
        alive = bool(alive)
        if alive == self._alive:
            return
        self._alive = alive
        if alive:
            self.configure(image=self._frames[self._i])
            self._tick()
        else:
            if self._job:
                try:
                    self.after_cancel(self._job)
                except Exception:
                    pass
                self._job = None
            self.configure(image=self._dim_frames[0])


# ---------------------------------------------------------------- 预览台渲染
_PIL_FONT_CACHE = {}


def _pil_font(size):
    """PIL 画中文要用真字体（默认位图字库没有汉字，会画出乱码框）。"""
    hit = _PIL_FONT_CACHE.get(size)
    if hit is not None:
        return hit
    from PIL import ImageFont
    f = None
    for p in ('C:/Windows/Fonts/msyh.ttc', 'C:/Windows/Fonts/msyhbd.ttc',
              'C:/Windows/Fonts/simhei.ttf', 'C:/Windows/Fonts/simsun.ttc'):
        try:
            f = ImageFont.truetype(p, size)
            break
        except Exception:
            continue
    if f is None:
        f = ImageFont.load_default()
    _PIL_FONT_CACHE[size] = f
    return f
def render_preview(pack, key, scale, canvas_px):
    """科技风预览台：网格 + 扫描线 + HUD 内框角标 + 32px 参考框 + 热点十字。

    棋盘底换成技术网格：20px 主网格 / 100px 加亮 / 4px 扫描线，
    光标美术照旧按热点居中合成。热点十字保留红色（功能色：提示点击
    落点），预览台四角加金色 HUD 角标。
    """
    from PIL import ImageDraw
    # 预览台配色跟主题走（浅色主题 = 浅灰网格 + 深灰线，光标美术不变）
    def _rgb(key, a=255):
        h = _c(key).lstrip('#')
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), a)

    im = Image.new('RGBA', (canvas_px, canvas_px), _rgb('WELL'))
    d = ImageDraw.Draw(im)

    for x in range(0, canvas_px, 20):
        d.line([x, 0, x, canvas_px], fill=_rgb('PREV_GRID'))
    for y in range(0, canvas_px, 20):
        d.line([0, y, canvas_px, y], fill=_rgb('PREV_GRID'))
    for x in range(0, canvas_px, 100):
        d.line([x, 0, x, canvas_px], fill=_rgb('PREV_GRID2'))
    for y in range(0, canvas_px, 100):
        d.line([0, y, canvas_px, y], fill=_rgb('PREV_GRID2'))
    for y in range(0, canvas_px, 4):
        d.line([0, y, canvas_px, y], fill=_rgb('PREV_SCAN'))

    frames = pack.frames(key) if pack else None
    if frames:
        art = frames[0][0]
        hs96 = pack.hotspot(key) or (0, 0)
        import cursorwin as cw
        size = max(4, int(round(cw.NATIVE * scale)))
        art = cw.premul_resize(art, size)
        hx = int(round(hs96[0] * size / cw.NATIVE))
        hy = int(round(hs96[1] * size / cw.NATIVE))
        ox = canvas_px // 2 - hx
        oy = canvas_px // 2 - hy
        im.alpha_composite(art, (ox, oy))
    else:
        d.text((12, 12), '找不到美术资源\nart.bin', fill=_rgb('BAD'),
               font=_pil_font(12))

    # 预览台 HUD 内框（内缩 10px）+ 四角金色角标
    m = 10
    d.rectangle([m, m, canvas_px - m - 1, canvas_px - m - 1],
                outline=_rgb('PREV_FRAME'))
    a = 18
    for (x, y, dx, dy) in ((m, m, 1, 1), (canvas_px - m - 1, m, -1, 1),
                           (m, canvas_px - m - 1, 1, -1),
                           (canvas_px - m - 1, canvas_px - m - 1, -1, -1)):
        d.line([x, y, x + dx * a, y], fill=_rgb('ACC'), width=1)
        d.line([x, y, x, y + dy * a], fill=_rgb('ACC'), width=1)

    # 32px 系统默认参考框（右下角）
    ref = 32
    bx1 = by1 = canvas_px - 22
    bx0 = by0 = bx1 - ref
    d.rectangle([bx0, by0, bx1, by1], outline=_rgb('EDGE_H'))
    d.text((bx1, by0 - 4), '32px 系统默认', fill=_rgb('MINI'),
           anchor='rs', font=_pil_font(11))

    # 热点十字（画布中心）：红准星 + 中心亮点
    # 红是「准星」语义色，两主题都保持高饱和红（对网格底 ≥3:1）
    mx = my = canvas_px // 2
    d.line([mx - 12, my, mx + 12, my], fill=_rgb('BAD'), width=1)
    d.line([mx, my - 12, mx, my + 12], fill=_rgb('BAD'), width=1)
    d.ellipse([mx - 2, my, mx + 2, my], fill=_rgb('BAD'))
    d.ellipse([mx, my - 2, mx, my + 2], fill=_rgb('BAD'))
    return im.convert('RGB')
