# -*- coding: utf-8 -*-
"""Windows 光标底层：在内存里按【任意像素尺寸】构造 HCURSOR。

为什么必须这么做：
  本机所有「文件式」光标路径（LoadCursorFromFileW / .cur 多光栅 / .ani /
  CursorSize / CursorBaseSize）都会把光标强制解析成 32x32。
  实测：CursorSize 1..15 全 15 档 → 活光标恒 (32,32)；
        加载 256px 的 .cur → GetIconInfo 得到的位图仍是 (32,32)。
  所以要让桌面指针变大，只能绕开文件路径，用 CreateIconIndirect 在内存里
  按目标尺寸现造 HCURSOR，再用 SetSystemCursor 装进系统。
  实测这条路径 48~256px 完全可控。
"""
import ctypes
import threading
import time
from ctypes import wintypes

from PIL import Image, ImageChops, ImageFilter

NATIVE = 96.0

# 17 个系统指针角色：(键, 中文名, SetSystemCursor 的 OCR id, 96px 热点)
# OCR id 为 None 表示 Windows 没有可编程接口（只能靠注册表文件光标）
ROLES = [
    ('Arrow',       '正常选择',       32512, (28, 20)),
    ('Help',        '帮助选择',       32651, (28, 20)),
    ('AppStarting', '后台运行',       32650, (28, 20)),
    ('Wait',        '忙',             32514, (48, 48)),
    ('Crosshair',   '精确选择',       32515, (48, 48)),
    ('IBeam',       '文本选择',       32513, (48, 48)),
    ('NWPen',       '手写',           None,  (8, 9)),
    ('No',          '不可用',         32648, (28, 20)),
    ('SizeNS',      '垂直调整',       32645, (48, 48)),
    ('SizeWE',      '水平调整',       32644, (48, 48)),
    ('SizeNWSE',    '对角线调整 1',   32642, (48, 48)),
    ('SizeNESW',    '对角线调整 2',   32643, (48, 48)),
    ('SizeAll',     '移动',           32646, (48, 48)),
    ('UpArrow',     '候选',           32516, (48, 4)),
    ('Hand',        '链接选择',       32649, (28, 20)),
    ('Pin',         '位置选择',       32671, (28, 20)),
    ('Person',      '人员选择',       32672, (28, 20)),
]
ANIMATED = {'AppStarting', 'Wait', 'No', 'SizeNS', 'SizeWE',
            'SizeNWSE', 'SizeNESW', 'SizeAll'}
ROLE_NAMES = {r[0]: r[1] for r in ROLES}
# 动画角色（8 个）之外的 9 个是静态角色：待机呼吸只给它们做尺寸阶梯
STATIC_KEYS = tuple(r[0] for r in ROLES if r[0] not in ANIMATED)
OCR_BY_KEY = {r[0]: r[2] for r in ROLES}

# ---------------------------------------------------------------- 指针档位
# 一「档」= 指针里的一套 .cur/.ani（`指针\cursors\<目录>\`，文件名后缀同名）。
# 增益 gain 的含义是「指针在 96px 参考画布上占多大」，**和程序里的 scale 是同一个量**
# —— 所以 scale 0.75 对应的就是 72px 那一档，注册进系统时该选它而不是 96px 那档。
# 元组：(目录名 = 文件名后缀, 增益, 方案名里用的档名)
PACK_TIERS = [
    ('small', 0.50, '小'),
    ('medium', 2.0 ** -0.5, '中'),
    ('p72', 0.75, '72px'),
    ('large', 1.00, '大'),
]


def pack_tiers_for(scale):
    """按「离当前 scale 最近」排好序的档位表（最近的在前）。

    最近的一档不一定存在（用户可能只留了某几档），所以调用方要按顺序往下试。
    """
    try:
        g = float(scale)
    except (TypeError, ValueError):
        g = 1.0
    return sorted(PACK_TIERS, key=lambda t: abs(t[1] - g))


def scheme_display_name(tier):
    """档位 → 注册进「鼠标属性 → 指针 → 方案」用的那个方案名。

    格式与 install.ps1 的 `$TierName` 严格对齐（'大 (1.00×)' 等），
    两边任何一处改了这里都必须同步改。
    """
    return '明日方舟 水晶指针 %s (%.2f×)' % (tier[2], tier[1])

# ---------------------------------------------------------------- ctypes 绑定
u32 = ctypes.WinDLL('user32', use_last_error=True)
gdi = ctypes.WinDLL('gdi32', use_last_error=True)


class ICONINFO(ctypes.Structure):
    _fields_ = [('fIcon', wintypes.BOOL), ('xHotspot', wintypes.DWORD),
                ('yHotspot', wintypes.DWORD), ('hbmMask', wintypes.HANDLE),
                ('hbmColor', wintypes.HANDLE)]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [('biSize', wintypes.DWORD), ('biWidth', wintypes.LONG),
                ('biHeight', wintypes.LONG), ('biPlanes', wintypes.WORD),
                ('biBitCount', wintypes.WORD),
                ('biCompression', wintypes.DWORD),
                ('biSizeImage', wintypes.DWORD),
                ('biXPelsPerMeter', wintypes.LONG),
                ('biYPelsPerMeter', wintypes.LONG),
                ('biClrUsed', wintypes.DWORD),
                ('biClrImportant', wintypes.DWORD)]


class BITMAP(ctypes.Structure):
    _fields_ = [('bmType', wintypes.LONG), ('bmWidth', wintypes.LONG),
                ('bmHeight', wintypes.LONG), ('bmWidthBytes', wintypes.LONG),
                ('bmPlanes', wintypes.WORD), ('bmBitsPixel', wintypes.WORD),
                ('bmBits', ctypes.c_void_p)]


class POINT(ctypes.Structure):
    _fields_ = [('x', wintypes.LONG), ('y', wintypes.LONG)]


class CURSORINFO(ctypes.Structure):
    _fields_ = [('cbSize', wintypes.DWORD), ('flags', wintypes.DWORD),
                ('hCursor', wintypes.HANDLE), ('ptScreenPos', POINT)]


u32.CreateIconIndirect.argtypes = [ctypes.POINTER(ICONINFO)]
u32.CreateIconIndirect.restype = wintypes.HANDLE
u32.CopyIcon.argtypes = [wintypes.HANDLE]
u32.CopyIcon.restype = wintypes.HANDLE
u32.DestroyCursor.argtypes = [wintypes.HANDLE]
u32.DestroyCursor.restype = wintypes.BOOL
u32.SetSystemCursor.argtypes = [wintypes.HANDLE, wintypes.DWORD]
u32.SetSystemCursor.restype = wintypes.BOOL
u32.LoadCursorFromFileW.argtypes = [ctypes.c_wchar_p]
u32.LoadCursorFromFileW.restype = wintypes.HANDLE
u32.SystemParametersInfoW.argtypes = [wintypes.UINT, wintypes.UINT,
                                      ctypes.c_void_p, wintypes.UINT]
u32.SystemParametersInfoW.restype = wintypes.BOOL
gdi.CreateDIBSection.argtypes = [wintypes.HDC, ctypes.c_void_p, wintypes.UINT,
                                 ctypes.POINTER(ctypes.c_void_p),
                                 wintypes.HANDLE, wintypes.DWORD]
gdi.CreateDIBSection.restype = wintypes.HBITMAP
gdi.DeleteObject.argtypes = [wintypes.HANDLE]
gdi.DeleteObject.restype = wintypes.BOOL

SPI_SETCURSORS = 0x0057
SPIF_UPDATEINIFILE, SPIF_SENDCHANGE = 0x01, 0x02

REG_CURSORS_PATH = r'Control Panel\Cursors'
# 「当前用的是哪套」和「方案下拉框里有哪些选项」是两个不同的键：
# 前者是 Control Panel\Cursors 下的 17 个角色值，后者是它的 Schemes
# 子键（值名 = 方案名，值 = 17 条路径按 ROLES 顺序逗号分隔）。
# 只写前者，用户的「鼠标属性 → 指针 → 方案」里永远看不到本包。
REG_SCHEMES_PATH = r'Control Panel\Cursors\Schemes'


def dpi_aware():
    """让本进程按物理像素工作（否则 125% 缩放下读数会不一致）。"""
    for fn in (lambda: ctypes.windll.shcore.SetProcessDpiAwareness(2),
               lambda: ctypes.windll.user32.SetProcessDPIAware()):
        try:
            fn()
            return
        except Exception:
            continue


def premul_forward(im):
    """RGBA -> 预乘 alpha 的 RGBA（逐字节等价于原 putpixel 循环）。

    实现从 `load()/putpixel` 换成 `bytes`/`bytearray` 的扁平下标：
    同样是纯 Python 循环，但少了每次取像素对象与逐点回写的开销。
    等价性用 `_probe6.py` 全角色逐字节验证过。
    """
    im = im.convert('RGBA')
    w, h = im.size
    buf = bytearray(im.tobytes())
    for i in range(0, len(buf), 4):
        a = buf[i + 3]
        if a == 255:
            continue                    # f == 1.0，原式也是恒等
        if a == 0:
            buf[i] = buf[i + 1] = buf[i + 2] = 0
            continue
        f = a / 255.0
        buf[i] = int(buf[i] * f + 0.5)
        buf[i + 1] = int(buf[i + 1] * f + 0.5)
        buf[i + 2] = int(buf[i + 2] * f + 0.5)
    return Image.frombytes('RGBA', (w, h), bytes(buf))


def premul_inverse(im):
    """预乘 alpha 的 RGBA -> 直通 alpha（逐字节等价于原 putpixel 循环）。"""
    w, h = im.size
    buf = bytearray(im.tobytes())
    for i in range(0, len(buf), 4):
        a = buf[i + 3]
        if a == 0:
            buf[i] = buf[i + 1] = buf[i + 2] = 0
            continue
        f = 255.0 / a
        v = int(buf[i] * f + 0.5)
        buf[i] = 255 if v > 255 else v
        v = int(buf[i + 1] * f + 0.5)
        buf[i + 1] = 255 if v > 255 else v
        v = int(buf[i + 2] * f + 0.5)
        buf[i + 2] = 255 if v > 255 else v
    return Image.frombytes('RGBA', (w, h), bytes(buf))


def premul_resize(im, size):
    """预乘 alpha 的 LANCZOS 缩放（避免透明区黑边渗色）。"""
    im = im.convert('RGBA')
    if im.size == (size, size):
        return im.copy()
    return premul_inverse(premul_forward(im).resize(
        (size, size), Image.LANCZOS))


def premul_resize_from(pm, size):
    """已是【预乘】状态的母版 -> 目标尺寸的直通 alpha 图。

    阶梯化构建里同一帧要出多个尺寸，预乘只做一次（`premul_forward`
    是每帧最贵的一步），所以把它拆出来复用。
    """
    if pm.size == (size, size):
        return premul_inverse(pm)
    return premul_inverse(pm.resize((size, size), Image.LANCZOS))


# ---------------------------------------------------------------- 暗描边补全
#
# 为什么需要这一段（实测根因，不是审美偏好）：
#
# 本包美术里，Arrow / Hand / Person / Help / Pin / No 都自带一圈**暗描边**
# （实心像素最小亮度 20–35，暗像素占 2.2–4.1%），所以它们放在任何背景上都
# 清楚。但拖拽族 SizeAll / SizeNS / SizeWE / SizeNWSE / SizeNESW 以及
# Crosshair / Wait / IBeam 是**纯近白色细线**：实测实心像素（alpha≥200）
# 最小亮度 117–183、暗像素占比 0.0%，等于整幅美术连一个暗像素都没有。
#
# 后果：在 Windows 最常见的浅色窗口/桌面上（亮度 ≈243），
#   SizeAll  最大对比 1.89、765 个像素里 0 个达到 WCAG 3.0
#   SizeNS   1.93 / SizeWE 1.91 / SizeNWSE 1.81 / SizeNESW 1.81（同样 0 个）
#   Arrow    11.55（69 个达标）
# 也就是说**日常拖动窗口时，系统取的就是 SizeAll，而它在浅色背景上与背景
# 亮度几乎相等 —— 这就是"看不到拖动图标"的根因**。
#
# 修法：用「膨胀 alpha − 原 alpha」得到形状外沿的一圈环带，把它作为描边色
# 合成到原图**下层**。原图一个像素都不动（外观、热点、抗锯齿边缘全部保持
# 原样），只在原先透明/半透明的地方补暗边。实测对比度：
#   SizeAll 1.89→7.50、SizeNS 1.93→7.27、SizeWE 1.91→7.15、
#   SizeNWSE/NESW 1.81→5.93、Crosshair 2.50→6.51、Wait 2.54→4.21、
#   IBeam 2.33→8.24；已可见的角色因判据不过关而**完全不动**。
OUTLINE_RGB = (46, 52, 64)      # 与包内 Arrow 自带的暗描边 (61,58,59) 同色系
OUTLINE_ALPHA = 235
OUTLINE_RADIUS = 1
# 判据用的浅色背景亮度（Windows 窗口/资源管理器/设置页常见值）
OUTLINE_TEST_BG = 243
# 判据阈值：WCAG 非文本图形下限。最高对比 < 此值 = 该角色在浅底上看不见。
OUTLINE_MIN_CONTRAST = 3.0
_OUTLINE_CACHE = '_outline_cache'
# 参与判据的最小 alpha（更淡的像素本来就只是抗锯齿余晖，不构成可辨认形状）
_OUTLINE_MIN_ALPHA = 40


def _solid_min_luma(im):
    """实心像素（alpha≥200）里的最小亮度；没有实心像素时返回 255。

    只用于诊断打印（哪些角色自带暗描边），不参与判定。
    """
    im = im.convert('RGBA')
    a = list(im.getchannel('A').getdata())
    l = list(im.convert('L').getdata())
    best = 255
    for i, av in enumerate(a):
        if av >= 200 and l[i] < best:
            best = l[i]
    return best


def _srgb_lin(c):
    c = c / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _rel_luma(r, g, b):
    return 0.2126 * _srgb_lin(r) + 0.7152 * _srgb_lin(g) + 0.0722 * _srgb_lin(b)


def max_contrast(im, bg=OUTLINE_TEST_BG):
    """母版合成到背景 bg 上之后，能达到的最大 WCAG 对比度。

    这就是"看不看得见"的**验收判据本身**——不是它的代理指标。用它当
    `needs_outline` 的门，好处是天然幂等：补过描边的图最高对比已经达标，
    再跑一次不会被重复补第二圈。之前用「实心像素最小亮度」当门，虽然能
    分族，但补完描边后 Wait(137)/Crosshair(100) 仍会再次触发，导致描边
    越补越粗。
    """
    im = im.convert('RGBA')
    px = im.load()
    w, h = im.size
    lb = _rel_luma(bg, bg, bg)
    best = 1.0
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a < _OUTLINE_MIN_ALPHA:
                continue
            al = a / 255.0
            l = _rel_luma(r * al + bg * (1 - al),
                          g * al + bg * (1 - al),
                          b * al + bg * (1 - al))
            hi, lo = (l, lb) if l > lb else (lb, l)
            c = (hi + 0.05) / (lo + 0.05)
            if c > best:
                best = c
    return best


def needs_outline(im):
    """这幅母版在浅色背景上是否达不到 WCAG 3.0（= 需要补暗描边）。

    实测分界（浅底 243）：Arrow/Hand/Person/Help/Pin/No/AppStarting 最高
    对比 8.9–11.6 直接过关；IBeam 2.31、SizeAll 1.87、SizeNS 1.93、
    SizeWE 1.90、SizeNWSE/NESW 1.79、Crosshair 2.47、Wait 2.52 全部低于
    3.0，正是"日常拖动窗口时看不见"的那一族。
    """
    return max_contrast(im) < OUTLINE_MIN_CONTRAST


def add_outline(im, rgb=OUTLINE_RGB, alpha=OUTLINE_ALPHA, radius=OUTLINE_RADIUS):
    """在图形外侧补一圈暗描边（合成到原图下层），返回新图。

    原图不透明处由原图完全遮住，因此**已可见的角色外观零变化**；
    只在原先透明的地方长出一圈 1px 的暗边。
    """
    im = im.convert('RGBA')
    a = im.getchannel('A')
    grown = a.filter(ImageFilter.MaxFilter(2 * radius + 1))
    ring = ImageChops.subtract(grown, a)          # 形状外侧那一圈
    if not ring.getbbox():
        return im
    ring = ring.point(lambda v: (v * alpha) // 255)
    lay = Image.new('RGBA', im.size, rgb + (0,))
    lay.putalpha(ring)
    out = Image.alpha_composite(lay, im)          # lay 在下，im 在上
    # alpha_composite 是整数运算，原图全不透明处理论上原样返回；
    # 为绝对保险，把这些像素逐个还原成原值（描边绝不改动原图）。
    solid = a.point(lambda v: 255 if v >= 255 else 0)
    if solid.getbbox():
        out.paste(im, (0, 0), solid)
    return out


def frames_with_outline(pack, key):
    """取角色的全部帧；缺暗描边时就地补上，结果缓存在 pack 上只算一次。"""
    frames = pack.frames(key)
    if not frames:
        return frames
    cache = getattr(pack, _OUTLINE_CACHE, None)
    if cache is None:
        cache = {}
        try:
            setattr(pack, _OUTLINE_CACHE, cache)
        except Exception:
            cache = None
    if cache is None:
        return frames
    hit = cache.get(key)
    if hit is None:
        if needs_outline(frames[0][0]):
            hit = [(add_outline(im), hx, hy) for (im, hx, hy) in frames]
        else:
            hit = frames
        cache[key] = hit
    return hit


def _dib(im, w, h):
    bi = BITMAPINFOHEADER()
    bi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bi.biWidth = w
    bi.biHeight = -h                       # 负数 = 顶向下
    bi.biPlanes = 1
    bi.biBitCount = 32
    bi.biCompression = 0
    bits = ctypes.c_void_p()
    hbm = gdi.CreateDIBSection(None, ctypes.byref(bi), 0, ctypes.byref(bits),
                               None, 0)
    if not hbm:
        raise OSError('CreateDIBSection(彩色) 失败')
    data = im.convert('RGBA').tobytes('raw', 'BGRA')
    ctypes.memmove(bits, data, min(len(data), w * h * 4))
    return hbm


def _mask(w, h):
    bi = BITMAPINFOHEADER()
    bi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bi.biWidth = w
    bi.biHeight = -h
    bi.biPlanes = 1
    bi.biBitCount = 1
    bits = ctypes.c_void_p()
    hbm = gdi.CreateDIBSection(None, ctypes.byref(bi), 0, ctypes.byref(bits),
                               None, 0)
    if not hbm:
        raise OSError('CreateDIBSection(掩码) 失败')
    ctypes.memset(bits, 0, ((w + 31) // 32) * 4 * h)
    return hbm


def make_hcursor_im(im, size, hs96):
    """从一张【已是目标尺寸、直通 alpha】的图造 HCURSOR。

    `make_hcursor`（从 96px 源图）与 `make_hcursor_pm`（从预乘母版）
    都收敛到这里，保证「同一个尺寸」永远只有一条构造路径。
    """
    color = _dib(im, size, size)
    mask = _mask(size, size)
    ii = ICONINFO()
    ii.fIcon = False                       # False = 光标（热点生效）
    ii.xHotspot = int(round(hs96[0] * size / NATIVE))
    ii.yHotspot = int(round(hs96[1] * size / NATIVE))
    ii.hbmMask = mask
    ii.hbmColor = color
    hc = u32.CreateIconIndirect(ctypes.byref(ii))
    err = ctypes.get_last_error()
    gdi.DeleteObject(color)
    gdi.DeleteObject(mask)
    if not hc:
        raise OSError('CreateIconIndirect 失败 err=%d' % err)
    return hc, (ii.xHotspot, ii.yHotspot)


def make_hcursor_pm(pm, size, hs96):
    """从【预乘状态的 96px 母版】直接出目标尺寸的 HCURSOR。"""
    return make_hcursor_im(premul_resize_from(pm, size), size, hs96)


def make_hcursor(im96, size, hs96):
    """按指定像素尺寸造 HCURSOR，热点等比缩放。返回 (HCURSOR, (hx,hy))。"""
    return make_hcursor_im(premul_resize(im96, size), size, hs96)


def measure_hcursor(hcur):
    """读一个 HCURSOR 的真实位图尺寸与热点 -> (w,h,hx,hy) 或 None。"""
    ii = ICONINFO()
    if not u32.GetIconInfo(wintypes.HANDLE(hcur), ctypes.byref(ii)):
        return None
    try:
        bm = BITMAP()
        if not gdi.GetObjectW(ii.hbmColor, ctypes.sizeof(BITMAP),
                              ctypes.byref(bm)):
            return None
        return (int(bm.bmWidth), int(bm.bmHeight),
                int(ii.xHotspot), int(ii.yHotspot))
    finally:
        if ii.hbmColor:
            gdi.DeleteObject(ii.hbmColor)
        if ii.hbmMask:
            gdi.DeleteObject(ii.hbmMask)


u32.GetIconInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(ICONINFO)]
u32.GetIconInfo.restype = wintypes.BOOL
gdi.GetObjectW.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p]
gdi.GetObjectW.restype = ctypes.c_int

DESKTOP_CLASSES = ('Progman', 'WorkerW', 'SysListView32', 'SHELLDLL_DefView',
                   'Shell_TrayWnd')


u32.FindWindowW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p]
u32.FindWindowW.restype = wintypes.HWND
u32.GetClassNameW.argtypes = [wintypes.HWND, ctypes.c_wchar_p, ctypes.c_int]
u32.GetClassNameW.restype = ctypes.c_int
u32.WindowFromPoint.argtypes = [POINT]
u32.WindowFromPoint.restype = wintypes.HWND
u32.GetParent.argtypes = [wintypes.HWND]
u32.GetParent.restype = wintypes.HWND
u32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.c_void_p]
u32.GetWindowRect.restype = wintypes.BOOL
u32.GetCursorPos.argtypes = [ctypes.POINTER(POINT)]
u32.GetCursorPos.restype = wintypes.BOOL
u32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
u32.SetCursorPos.restype = wintypes.BOOL
u32.GetSystemMetrics.argtypes = [ctypes.c_int]
u32.GetSystemMetrics.restype = ctypes.c_int


def _top_class(hwnd):
    """向上爬 6 层取顶层窗口类名。"""
    top = hwnd
    for _ in range(6):
        p = u32.GetParent(top)
        if not p:
            break
        top = p
    if not top:
        return ''
    buf = ctypes.create_unicode_buffer(256)
    u32.GetClassNameW(top, buf, 256)
    return buf.value


def find_desktop_point():
    """找一个真正属于桌面的坐标（否则 GetCursorInfo 会读到悬停窗口的光标）。

    ⚠️ 曾经踩过的坑：`FindWindowW('WorkerW', None)` 在本机找到的是一个
    136x38 的小窗口（rect `(0,0)-(136,38)`），它的三个候选点落在
    `(74,17) / (47,24) / (102,30)` —— **屏幕左上角**。旧实现按
    `DESKTOP_CLASSES` 顺序取第一个能过类名校验的窗口，于是把鼠标钉到了
    `(74,17)`，表现为「鼠标一直被拽到左上角」。
    现在改为：候选窗口的面积必须 >= 屏幕面积的 50%（真桌面才够大），
    并按面积从大到小排序，取到的点再回验一次顶层类名。
    """
    sw = u32.GetSystemMetrics(0)   # SM_CXSCREEN
    sh = u32.GetSystemMetrics(1)   # SM_CYSCREEN
    min_area = sw * sh * 0.5

    cands = []
    for cls in DESKTOP_CLASSES:
        h = u32.FindWindowW(cls, None)
        if not h:
            continue
        r = wintypes.RECT()
        if not u32.GetWindowRect(h, ctypes.byref(r)):
            continue
        w, hh = r.right - r.left, r.bottom - r.top
        if w * hh < min_area:      # 太小的不是真桌面（WorkerW 陷阱）
            continue
        cands.append((w * hh, cls, r))
    cands.sort(reverse=True, key=lambda c: c[0])

    for _area, _cls, r in cands:
        for fx, fy in ((0.55, 0.45), (0.35, 0.65), (0.75, 0.80)):
            x = int(r.left + (r.right - r.left) * fx)
            y = int(r.top + (r.bottom - r.top) * fy)
            hw = u32.WindowFromPoint(POINT(x, y))
            if hw and _top_class(hw) in DESKTOP_CLASSES:
                return x, y
    # 兜底：屏幕正中央（那里一定是桌面，不存在别的全屏窗口时）
    return sw // 2, sh // 2


def desktop_cursor_size(jiggle=True, restore=True):
    """读桌面当前活光标的 (w, h, hx, hy)。

    ⚠️ 为了绕过「GetCursorInfo 返回的是悬停窗口自己的光标」这个问题，
    本函数必须把鼠标临时钉到桌面点上 —— 所以它**会移动鼠标**。
    `restore=True`（默认）会在量完后把鼠标放回原位，把干扰降到最小；
    但真正要紧的是 `guard` 别每轮都调它（见 guard.py 的 check()）。
    """
    pt = find_desktop_point()
    if pt is None:
        return None
    orig = POINT()
    have_orig = bool(u32.GetCursorPos(ctypes.byref(orig)))
    try:
        if jiggle:
            u32.SetCursorPos(pt[0] + 7, pt[1] + 7)
            time.sleep(0.06)
        u32.SetCursorPos(pt[0], pt[1])
        time.sleep(0.12)
        ci = CURSORINFO()
        ci.cbSize = ctypes.sizeof(CURSORINFO)
        if not u32.GetCursorInfo(ctypes.byref(ci)):
            return None
        if not ci.hCursor:
            return None
        return measure_hcursor(int(ci.hCursor))
    finally:
        if restore and have_orig:
            u32.SetCursorPos(orig.x, orig.y)


def hovered_cursor_size():
    """**不移动鼠标**，读鼠标当前所在窗口的光标 (w,h,hx,hy)。

    与 `desktop_cursor_size` 的关键区别：它不做任何 `SetCursorPos`。
    代价是返回值取决于鼠标当时压在哪个窗口上（Chrome 会返回它自己的
    光标），所以**不能当作权威读数**；只能拿来跑「签名匹配」——
    见 `cursor_signature_sets`。

    为什么需要它：守护要周期性确认「指针还在不在」，而
    `desktop_cursor_size` 为了绕过悬停窗口的问题必须钉鼠标 ——
    每 1.5 秒钉一次就是「鼠标一直被拽到左上角」的事故来源。轮询路径
    必须是无副作用的。
    """
    ci = CURSORINFO()
    ci.cbSize = ctypes.sizeof(CURSORINFO)
    if not u32.GetCursorInfo(ctypes.byref(ci)):
        return None
    if not ci.hCursor:
        return None
    return measure_hcursor(int(ci.hCursor))


def cursor_signature_sets(size):
    """返回 (本包签名集, 重置成 32px 的签名集)。

    签名 = (位图宽, 位图高, 热点 x, 热点 y)。17 个角色各自的热点在
    96px 下不同（Arrow 是 (28,20)，IBeam 是 (48,48)…），所以把
    尺寸和热点一起比，就能在不移动鼠标的前提下判断：
    鼠标当前压着的这个光标，到底是不是「我们装的那一套」。
    """
    exp, rst = set(), set()
    for _key, _zh, _ocr, hs in ROLES:
        for s, dst in ((int(size), exp), (32, rst)):
            dst.add((s, s, int(round(hs[0] * s / NATIVE)),
                     int(round(hs[1] * s / NATIVE))))
    return exp, rst


u32.LoadCursorW.argtypes = [wintypes.HINSTANCE, ctypes.c_void_p]
u32.LoadCursorW.restype = wintypes.HANDLE

# OCR id -> 角色键（用 LoadCursorW 探测当前系统光标时要用）
OCR_TO_KEY = {r[2]: r[0] for r in ROLES if r[2]}
# 探测用的一组角色：覆盖四种不同热点，任一被重置都能看出来
PROBE_KEYS = ('Arrow', 'IBeam', 'Hand', 'SizeAll', 'UpArrow', 'No')


def system_cursor_sizes():
    """**零副作用**读「当前系统装着的」光标尺寸 —— 权威探针。

    原理：`LoadCursorW(None, MAKEINTRESOURCE(OCR_*))` 返回的不是内置
    默认光标，而是**当前系统光标本身** —— `SetSystemCursor` 换过之后
    它就返回换过的那一个。实测（设置.json 72px 时）：
        Arrow (72,72,21,15) / IBeam (72,72,36,36) / Hand (72,72,21,15)
        UpArrow (72,72,36,3) / SizeAll (72,72,36,36) / No (72,72,21,15)
    全部与预期逐字节吻合，且 30 次调用 0.002 s（0.05 ms/次）、
    **鼠标零位移、读数与鼠标位置完全无关**。

    返回 {角色键: (w, h, hx, hy)}；失败的角色不出现在结果里。

    ⚠️ 这是守护轮询**唯一该用**的探针。旧实现（把鼠标钉到桌面点再
    GetCursorInfo）每 1.5 秒把鼠标拽走一次，就是「鼠标一直在左上角」
    的事故来源 —— 那与鼠标是否悬停在某些窗口上也无关。
    """
    u32.LoadCursorW.argtypes = [wintypes.HINSTANCE, ctypes.c_void_p]
    u32.LoadCursorW.restype = wintypes.HANDLE
    out = {}
    for ocr, key in OCR_TO_KEY.items():
        if key not in PROBE_KEYS:
            continue
        h = u32.LoadCursorW(None, ctypes.c_void_p(ocr))
        if not h:
            continue
        m = measure_hcursor(int(h))
        if m:
            out[key] = m
    return out


def cursor_over_desktop():
    """**零副作用**读鼠标当前压着的窗口的光标（兼容旧调用点）。

    注意：本函数只在鼠标压在桌面/任务栏上时才返回读数，因此**大部分
    时间返回 None**，不适合做轮询判据 —— 轮询请用 `system_cursor_sizes()`。
    保留它只是为了 `main.pyw` 界面上「你此刻看到的是哪个光标」这类提示。
    """
    p = POINT()
    if not u32.GetCursorPos(ctypes.byref(p)):
        return None
    hw = u32.WindowFromPoint(p)
    if not hw:
        return None
    if _top_class(hw) not in DESKTOP_CLASSES:
        return None
    return hovered_cursor_size()


class Engine(object):
    """把 17 个角色的指针按指定尺寸装进系统，并驱动动画。"""

    def __init__(self):
        self.lock = threading.RLock()
        self.size = 115
        self.masters = {}        # 角色键 -> [HCURSOR, ...]，base 档（用户设定的尺寸）
        self.tier_sizes = {'base': 115}
        self.hotspots = {}
        self.hotspots96 = {}
        self.anim_rates = {}     # key -> 每帧毫秒（None = 静态）
        self.anim_idx = {}
        self.anim_thread = None
        self.anim_stop = threading.Event()
        self.animate = True
        self.applied = set()
        self.last_error = ''
        # ---- 点击缩放 / 待机呼吸：按需现造的尺寸阶梯 ----
        self.pack = None         # build() 时记下，供阶梯现造时取帧
        self.fx = None           # CursorAnim：动画驱动线程
        self.fx_opts = {}
        self.ladder = {}         # (角色键, 像素) -> {帧号: HCURSOR}，现造后缓存
        self.ladder_lru = []     # 上面那些键的最近使用顺序
        self.ladder_n = 0        # 阶梯里现有多少个图标（用来限长）
        self.ladder_max = 1400   # 上限：GDI 句柄有限，超了就淘汰最久没用过的
        self.pm_cache = {}       # (角色键, 帧号) -> 预乘母版，重采样都从它出发
        self.wants = set()       # 已登记、正等后台线程现造的 (角色, 帧, 像素)
        self.want_q = []
        self.builder = None      # 后台现造线程：绝不让动画 tick 去干光栅化的活
        self.builder_stop = threading.Event()

    def build(self, size, pack, only=None, fx=None):
        """按尺寸造好全部角色的 HCURSOR。pack 是 artpack.ArtPack。

        fx 是 `fx_options()` 的结果。**None/空 dict = 不启用点击缩放/待机呼吸**，
        这时连尺寸阶梯都不造：守护、只想要一套静态指针的脚本不必为多出来的上千个
        GDI 句柄和几秒钟买单。动画要用的其它尺寸由阶梯按需现造（见 icon_at）。

        循环刻意写成「帧在外层」：`premul_forward` 是每帧最贵的一步（96px 源图
        逐像素），放在外层它就每帧只算一次，之后所有用途共用同一份预乘母版。
        """
        self.stop_fx()          # 必须在拿锁之前：stop() 要 join 动画线程
        with self.lock:
            self.destroy()
            self.size = int(round(size))
            self.fx_opts = dict(fx) if isinstance(fx, dict) else {}
            self.pack = pack
            self.tier_sizes = {'base': self.size}
            o = fx_options(self.fx_opts)
            fx_run = bool(self.fx_opts) and fx_any_on(o)
            # 只有 ① 和呼吸会改尺寸，② ③ 都用 base 档现成的图标 —— 后者不该为
            # 一条用不上的尺寸阶梯买单。
            ladder_on = fx_run and fx_scales(o) != (1.0, 1.0)
            rungs = anim_rungs(self.size, o) if ladder_on else (self.size,)
            if ladder_on:
                # 动画会走到的每个像素尺寸都登记进 tier_sizes：守护靠它判断
                # 「屏幕上的尺寸是不是我们发的」，动画中途的尺寸不能被当成被重置。
                for i, px in enumerate(rungs):
                    self.tier_sizes['r%d' % i] = px
            keys = [k for k in (only or pack.roles) if k in pack.roles]
            for key in keys:
                # 用 frames_with_outline 而不是 pack.frames：拖拽族的近白细线在
                # 浅色背景上不可见（根因见文件里「暗描边补全」段注释），这里就地把
                # 它们的暗描边补上；已带暗描边的角色原样返回。
                frames = frames_with_outline(pack, key)
                if not frames:
                    continue
                hs96 = pack.hotspot(key)
                bucket, hsset = [], []
                for (im, _hx, _hy) in frames:
                    pm = premul_forward(im)          # 每帧只算一次
                    self.pm_cache[(key, len(bucket))] = pm
                    try:
                        hc, hs = make_hcursor_pm(pm, self.size, hs96)
                    except OSError as e:
                        self.last_error = str(e)
                        continue
                    bucket.append(hc)
                    hsset.append(hs)
                if bucket:
                    self.masters[key] = bucket
                if hsset:
                    self.hotspots[key] = hsset
                self.hotspots96[key] = hs96
                if len(self.masters.get(key, [])) > 1:
                    rates = pack.rates_ms(key)
                    if rates:
                        self.anim_rates[key] = max(10, int(sum(rates) / float(len(rates))))
                    else:
                        # 源 .ani 无 rate 数组时用 anih.dispRate（jiffies，1/60s）
                        self.anim_rates[key] = 20
                else:
                    self.anim_rates[key] = None
        if ladder_on:
            # 阶梯分两种铺法，都是为了「真正点下去的那一刻不卡」：
            #   * 单帧角色（箭头、文本光标、手型……）一次性铺满 —— 日常绝大多数
            #     点击落在它们身上，铺满只要半秒左右，换来第一次点击就是顺的。
            #   * 多帧角色（转圈、拖拽那几族）只登记需求，交给后台线程慢慢铺：
            #     它们帧多，同步铺满会让 build 多等十几秒。
            with self.lock:
                keys = [k for k in self.masters if len(self.masters[k]) == 1]
            for key in keys:
                for px in rungs:
                    if px != self.size:
                        self.icon_at(key, 0, px)
            for key in list(self.masters.keys()):
                if len(self.masters.get(key, [])) == 1:
                    continue
                for px in rungs:
                    if px != self.size:
                        self.want(key, 0, px)
        return sorted(self.masters.keys())
    def destroy(self):
        """销毁 base 档与尺寸阶梯里的全部 HCURSOR，并停掉后台现造线程。"""
        seen = set()
        groups = list(self.masters.values())
        for d in self.ladder.values():
            groups.append(list(d.values()))
        for lst in groups:
            for h in lst:
                if h in seen:
                    continue
                seen.add(h)
                try:
                    u32.DestroyCursor(h)
                except Exception:
                    pass
        self.masters = {}
        self.tier_sizes = {'base': self.size}
        self.hotspots, self.anim_idx = {}, {}
        self.applied = set()
        self.ladder, self.ladder_lru, self.ladder_n = {}, [], 0
        self.pm_cache = {}
        self.wants, self.want_q = set(), []
        self.builder_stop.set()
        self.builder = None
    def apply(self, key, idx=0, px=None):
        """把某个角色的第 idx 帧装进系统（必要时现造那一档，**会阻塞**）。

        px 省略（或正好等于 base 尺寸）就用 base 档。动画 tick 不要走这里 ——
        它们走 apply_at()，那个绝不现造图标。这里给 build 的预热和收尾复位用。
        """
        base = self.masters.get(key)
        if not base:
            return False
        ocr = OCR_BY_KEY.get(key)
        if ocr is None:
            return False
        i = idx % max(1, len(base))
        src = base[i]
        if px is not None and int(px) != self.size:
            got = self.icon_at(key, i, int(px))
            if got is None:
                return False
            src = got
        return self._set(key, ocr, src)

    def apply_at(self, key, idx, px):
        """动画 tick 专用：**绝不现造图标**。

        返回 True（已下发）/ False（角色不可用）/ None（那一档还没造好，已登记
        需求，让后台线程去造 —— 本 tick 先跳过这个角色，保留上一帧的样子）。
        """
        base = self.masters.get(key)
        if not base:
            return False
        ocr = OCR_BY_KEY.get(key)
        if ocr is None:
            return False
        i = idx % max(1, len(base))
        src = base[i]
        if px is not None and int(px) != self.size:
            got = self.cached(key, i, int(px))
            if got is None:
                self.want(key, i, int(px))
                return None
            src = got
        return self._set(key, ocr, src)

    def _set(self, key, ocr, src):
        h = u32.CopyIcon(src)
        if not h:
            return False
        ok = bool(u32.SetSystemCursor(h, ocr))
        if ok:
            self.applied.add(key)
        else:
            u32.DestroyCursor(h)
        return ok

    def set_raw(self, key, src):
        """把一枚现成的 HCURSOR 装到角色 key 上。

        给 PRTS 移植层（prtsfx）用：那边每帧的图标来自 fx.bin，既不在 masters
        里、也不该进 ladder，所以绕过 apply_at 的取帧逻辑，只借 _set 的下发路径
        （CopyIcon + SetSystemCursor + applied 记账）。
        """
        if not src:
            return False
        ocr = OCR_BY_KEY.get(key)
        if ocr is None:
            return False
        with self.lock:
            return self._set(key, ocr, src)

    def apply_all(self):
        """把所有角色的 base 档装进系统。"""
        with self.lock:
            for key in list(self.masters.keys()):
                self.apply(key, self.anim_idx.get(key, 0))
            return len(self.applied)

    # ---- 尺寸阶梯：动画要用的非 base 尺寸，按需现造 ----
    def cached(self, key, idx, px):
        """只看缓存：有就返回 HCURSOR，没有返回 None（不造、不登记）。"""
        with self.lock:
            d = self.ladder.get((key, int(px)))
            if d is None or idx not in d:
                return None
            self._ladder_touch((key, int(px)))
            return d[idx]

    def _master(self, key, idx):
        """(角色, 帧) 的预乘母版与 96px 热点；重活都在锁外做。"""
        ck = (key, idx)
        with self.lock:
            pm = self.pm_cache.get(ck)
            hs96 = self.hotspots96.get(key)
            pack = self.pack
        if pack is None:
            return None, None
        if hs96 is None:
            hs96 = pack.hotspot(key)
            with self.lock:
                self.hotspots96[key] = hs96
        if pm is None:
            frames = frames_with_outline(pack, key)
            if not frames:
                return None, None
            pm = premul_forward(frames[idx % len(frames)][0])
            with self.lock:
                self.pm_cache[ck] = pm
        return pm, hs96

    def icon_at(self, key, idx, px):
        """取 (角色, 像素) 那一档的第 idx 帧；没有就现造并缓存。失败返回 None。"""
        px = int(px)
        ck = (key, px)
        with self.lock:
            d = self.ladder.get(ck)
            if d is not None and idx in d:
                self._ladder_touch(ck)
                return d[idx]
        pm, hs96 = self._master(key, idx)
        if pm is None:
            return None
        try:
            # 取帧 + LANCZOS 缩放 + CreateIconIndirect 是毫秒级的活，放在锁外做，
            # 免得每秒上百个图标把帧动画线程一起堵住。
            hc, _hs = make_hcursor_pm(pm, px, hs96)
        except OSError as e:
            self.last_error = str(e)
            return None
        with self.lock:
            d = self.ladder.setdefault(ck, {})
            if idx in d:                     # 别的线程抢先造好了
                try:
                    u32.DestroyCursor(hc)
                except Exception:
                    pass
                self._ladder_touch(ck)
                return d[idx]
            d[idx] = hc
            self.ladder_n += 1
            self._ladder_touch(ck)
            self._ladder_trim()
        return hc

    def _ladder_touch(self, ck):
        try:
            self.ladder_lru.remove(ck)
        except ValueError:
            pass
        self.ladder_lru.append(ck)

    def _ladder_trim(self):
        while self.ladder_n > self.ladder_max and self.ladder_lru:
            old = self.ladder_lru.pop(0)
            d = self.ladder.pop(old, None)
            if not d:
                continue
            for h in d.values():
                self.ladder_n -= 1
                try:
                    u32.DestroyCursor(h)
                except Exception:
                    pass

    def want(self, key, idx, px):
        """登记一个「希望马上有」的阶梯图标，后台线程会去造。"""
        px = int(px)
        if px == self.size:
            return
        item = (key, idx, px)
        with self.lock:
            d = self.ladder.get((key, px))
            if d is not None and idx in d:
                return
            if item in self.wants:
                return
            self.wants.add(item)
            self.want_q.append(item)
            # 需求堆积说明后台追不上：丢最旧的，只保新鲜的 —— 动画只关心
            # 眼下这一帧该长什么样，过期的档造出来也没人看。
            while len(self.want_q) > 256:
                self.wants.discard(self.want_q.pop(0))
        self._ensure_builder()

    def _ensure_builder(self):
        t = self.builder
        if t is not None and t.is_alive():
            return
        self.builder_stop.clear()
        self.builder = threading.Thread(target=self._builder_loop, daemon=True)
        self.builder.start()

    def _builder_loop(self):
        """把 want() 登记过的档一个个造出来。除了这里，没有别处会在
        SetSystemCursor 的时间轴上做光栅化。"""
        while not self.builder_stop.is_set():
            with self.lock:
                item = self.want_q.pop(0) if self.want_q else None
            if item is None:
                time.sleep(0.02)
                continue
            key, idx, px = item
            try:
                self.icon_at(key, idx, px)
            except Exception as e:
                self.last_error = str(e)
            with self.lock:
                self.wants.discard(item)

    def tick_anim(self, now, last):
        """按各角色的每帧毫秒推进帧号，返回本轮真正换帧的角色键。

        `start_anim()` 的线程与 `CursorAnim` 共用它，这样无论谁在跑，
        帧号都只会被推进一次。**它只推进、不下发**。
        """
        moved = []
        for key, ms in list(self.anim_rates.items()):
            if not ms:
                continue
            if now - last.get(key, 0.0) < ms / 1000.0:
                continue
            last[key] = now
            self.anim_idx[key] = (self.anim_idx.get(key, 0) + 1) % max(
                1, len(self.masters.get(key, [1])))
            moved.append(key)
        return moved

    def _fx_owns_output(self):
        return self.fx is not None and self.fx.active

    def start_anim(self):
        if self.anim_thread and self.anim_thread.is_alive():
            return

        def loop():
            last = {}
            while not self.anim_stop.is_set():
                now = time.time()
                with self.lock:
                    moved = self.tick_anim(now, last)
                    # FX 在跑时 SetSystemCursor 归 FX 独占 —— 否则动画线程
                    # 会把按下档/呼吸档又刷回 base 档，效果闪一下就没了。
                    if not self._fx_owns_output():
                        for key in moved:
                            self.apply(key, self.anim_idx.get(key, 0))
                time.sleep(0.012)

        self.anim_stop.clear()
        self.anim_thread = threading.Thread(target=loop, daemon=True)
        self.anim_thread.start()

    def stop_anim(self):
        self.anim_stop.set()

    # ---- 点击缩放 / 待机呼吸 ----
    def stop_fx(self):
        """停掉动画线程。**不要在自己持锁时调用**：它会 join 动画线程，
        而动画线程的收尾要拿同一把锁，会一直等到 join 超时。"""
        f = self.fx
        self.fx = None
        if f is not None:
            f.stop()
        return f

    def start_fx(self, opt=None):
        """按设置装配动画并启动。返回 CursorAnim 实例或 None。

        opt 省略时用 build() 时存下的 fx_opts。
        """
        self.stop_fx()
        o = fx_options(opt if opt is not None else self.fx_opts)
        if not fx_any_on(o):
            return None
        f = CursorAnim(self, o)
        if not f.on:
            return None
        self.fx = f
        f.start()
        return f

    def restore_files(self, reg_cursors):
        """按注册表里登记的文件光标还原（即回到系统原本的 32px 观感）。"""
        import os
        import winreg
        self.stop_anim()
        self.destroy()
        ok = 0
        for r in ROLES:
            key, ocr = r[0], r[2]
            if ocr is None:
                continue
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, reg_cursors) as k:
                    path = winreg.QueryValueEx(k, key)[0]
            except OSError:
                continue
            if not path or not os.path.exists(path):
                continue
            h = u32.LoadCursorFromFileW(path)
            if h and u32.SetSystemCursor(h, ocr):
                ok += 1
        u32.SystemParametersInfoW(SPI_SETCURSORS, 0, None,
                                  SPIF_UPDATEINIFILE | SPIF_SENDCHANGE)
        return ok


# ============================================ 点击缩放（游戏原版）/ 待机呼吸
# 下面这组常量不是调出来的手感，是从游戏本体里取出来的：
#
#   PCMouseHandler._PlayAnim(t) 的机器码（GameAssembly.dll，RVA 0x1483D70）逐条是
#       movaps xmm6, xmm1            ; t 是入参
#       mulss  xmm6, [0x6E3FDA4]     ; × 0.5f   （.rdata 里 00 00 00 3f）
#       addss  xmm6, [0x6E3FF24]     ; + 0.75f  （.rdata 里 00 00 40 3f）
#       Transform.set_localScale(m_cacheScale * xmm6)      ; 0x181483E90
#   即 **scale(t) = 0.75 + 0.5·t**：t=0 → 0.75×、t=1 → 1.25×、t=0.5 → 1.0×（静止）。
#   两端点还各自对上 global-metadata.dat 里的字段默认值
#   PCMouseHandler.MIN_SIZE = 0.75f / MAX_SIZE = 1.25f（fieldDefaultValues，
#   dataIndex 200792 / 200796，raw 00 00 40 3f / 00 00 a0 3f），互相印证。
#   _PlayAnim 只在第一次进入时把当时的 localScale 存进 m_cacheScale（[rbx+0x5c]
#   那个守卫），所以倍率是绝对的，点多少次都不会越缩越小。
#
# **没取到的部分**：触发端 OnMouseDownEvent / OnMouseUpEvent 各投喂一条
# AnimationCurve（_onBtnDownAnim / _onBtnUpAnim），那两条曲线的关键帧时间、值与
# 切线锁在 StreamingAssets\AB\Windows\anon\f7bcd64480c4566f25d65d642f5fba95.bin
# 里 —— 该 bundle 的数据块用了非标准压缩（flag=4，实测排除 LZ4 / LZMA1 全 225 组
# props / LZMA2 / deflate / zlib / bz2 / brotli / LZO；也不是 UnityCN 加密，签名是
# 明文 UnityFS\0），本机既没有能解它的 lzham 解码器、也没有 C/C++ 编译器现编一个，
# 所以**时长与缓动取不到**。于是把它们写成显式可改的关键帧表：公式本身不受影响，
# 端点严格落在游戏那两个常量上，改表就是改手感。按下取「向 MIN 走」，抬起取
# 「回到 MAX 再落回静止」—— 因为那段没取到，这是按「按下缩小、松手回弹」的
# 既有观感定的，不是从游戏里读出来的。
ANIM_MIN_SCALE = 0.75      # = PCMouseHandler.MIN_SIZE
ANIM_MAX_SCALE = 1.25      # = PCMouseHandler.MAX_SIZE
ANIM_REST_T = 0.5          # t=0.5 → 1.0×，静止时用的那个点

# 关键帧表：(归一化进度, t)。t 再经 scale(t) 换成倍率。
ANIM_DOWN_KEYS = ((0.0, 0.50), (1.0, 0.00))              # 1.00× → 0.75×
ANIM_UP_KEYS = ((0.0, 0.00), (0.30, 1.00), (1.0, 0.50))  # 0.75× → 1.25× → 1.00×


def scale_of_t(t):
    """游戏原版映射：scale = MIN_SIZE + (MAX_SIZE - MIN_SIZE) · t。"""
    try:
        v = float(t)
    except (TypeError, ValueError):
        v = ANIM_REST_T
    v = min(1.0, max(0.0, v))
    return ANIM_MIN_SCALE + (ANIM_MAX_SCALE - ANIM_MIN_SCALE) * v


def curve_value(keys, u):
    """按关键帧表线性插值（u 是归一化进度，超出 [0,1] 夹住）。"""
    try:
        u = min(1.0, max(0.0, float(u)))
    except (TypeError, ValueError):
        u = 0.0
    prev = keys[0]
    for k in keys:
        if u <= k[0]:
            if k[0] <= prev[0]:
                return float(k[1])
            f = (u - prev[0]) / float(k[0] - prev[0])
            return float(prev[1]) + (float(k[1]) - float(prev[1])) * f
        prev = k
    return float(keys[-1][1])


VK_LBUTTON, VK_RBUTTON, VK_MBUTTON = 0x01, 0x02, 0x04
VK_XBUTTON1, VK_XBUTTON2 = 0x05, 0x06
PRESS_VKS = (VK_LBUTTON, VK_RBUTTON, VK_MBUTTON)

u32.GetAsyncKeyState.argtypes = [ctypes.c_int]
u32.GetAsyncKeyState.restype = ctypes.c_short


def key_down(vk):
    """物理键态：此刻是否真的按着（不看锁存位）。"""
    return bool(u32.GetAsyncKeyState(int(vk)) & 0x8000)


def key_pressed(vk):
    """自上次询问以来是否发生过一次「按下」。**读取会消费 0x0001 锁存位。**"""
    return bool(u32.GetAsyncKeyState(int(vk)) & 0x0001)


def keys_state(vks=PRESS_VKS):
    """一次取回 (是否按着, 本 tick 是否出现过按下)。

    每个 tick 只该调用一次：锁存位是「读后清零」的，多调一次就白读，
    第二次拿到的一定是 0。
    """
    phys, latch = False, False
    for vk in vks:
        if key_pressed(vk):
            latch = True
        if key_down(vk):
            phys = True
    return phys, latch


FX_DEFAULTS = {
    'click_anim': True,             # ① 点击挤压
    'click_style': 'prts',          # 'prts' = PRTS 原帧；'game' = 游戏原版倍率缩放
    'drag_claw': True,              # ② PRTS 拖动爪子（勾不住钩子时自动静默关闭）
    'idle_prts': True,              # ③ PRTS 待机帧动画
    'idle_start_ms': 5000,          # 待机多久后开始（PRTS Motion.cs:73 的 seconds 默认 5）
    'down_ms': 90,                  # 游戏风格按下段时长（曲线未取到，见上面段注释）
    'up_ms': 190,                   # 游戏风格抬起回弹段时长（同上）
    'tick_ms': 8,                   # 键态采样间隔
    'min_scale': ANIM_MIN_SCALE,    # 游戏风格缩放下限 = 游戏 MIN_SIZE
    'max_scale': ANIM_MAX_SCALE,    # 游戏风格缩放上限 = 游戏 MAX_SIZE
    'rung_max': 25,                 # 尺寸阶梯最多分几档（越大越顺，占用越多）
}

# 两种点击风格的预设。**min_scale / max_scale 由风格单方面决定，不接受调用方
# 覆盖**（界面没有这两个键的入口，见 fx_options 里的说明）。
#   prts：点击用 fx.bin 里的 hand_<role>_NNN 原帧（逐帧烘死的非均匀挤压），
#         **不缩放**，所以这里是 1.0/1.0 —— 阶梯一档都不用铺。
#   game：本工程原有的游戏原版规格，但幅度按用户要求收敛到 ±10%（原来是游戏
#         PCMouseHandler 的 MIN_SIZE=0.75 / MAX_SIZE=1.25，缩 25% 太夸张）。
#         这条是纯倍率缩放，没有手指聚拢的美术。
CLICK_STYLES = {
    'prts': {'min_scale': 1.0, 'max_scale': 1.0},
    'game': {'min_scale': 0.90, 'max_scale': 1.10},
}


def fx_options(d):
    """从设置字典里取动画参数，缺失或非法的项一律回落到默认值。"""
    o = dict(FX_DEFAULTS)
    if isinstance(d, dict):
        for k in FX_DEFAULTS:
            if d.get(k) is not None:
                o[k] = d[k]
    style = str(o.get('click_style') or 'prts').strip().lower()
    if style not in CLICK_STYLES:
        style = FX_DEFAULTS['click_style']
    o['click_style'] = style
    # 幅度由风格决定，**不**跟着调用方给的 min_scale / max_scale 走：prts 风格是
    # 1.0/1.0（用原帧、不缩放），game 风格的 0.75/1.25 是游戏 PCMouseHandler 的
    # MIN_SIZE / MAX_SIZE 常量。这两个键在界面上没有入口（只在日志里作为「本次
    # 实际用了什么幅度」回读），所以旧 设置.json 里存着的数值不会把新风格带偏。
    o.update(CLICK_STYLES[style])
    o['click_anim'] = bool(o['click_anim'])
    o['drag_claw'] = bool(o['drag_claw'])
    o['idle_prts'] = bool(o['idle_prts'])
    for k in ('down_ms', 'up_ms', 'tick_ms', 'rung_max', 'idle_start_ms'):
        try:
            o[k] = max(1, int(o[k]))
        except (TypeError, ValueError):
            o[k] = FX_DEFAULTS[k]
    for k, lo, hi in (('min_scale', 0.25, 1.0), ('max_scale', 1.0, 4.0)):
        try:
            o[k] = min(hi, max(lo, float(o[k])))
        except (TypeError, ValueError):
            o[k] = FX_DEFAULTS[k]
    return o


def fx_any_on(o):
    """这组参数会不会真的产生效果（决定线程/阶梯/图标要不要起）。"""
    return bool(o['click_anim'] or o['idle_prts'] or o['drag_claw'])


def fx_scales(o):
    """这组参数会走到的缩放范围 —— 只有 game 风格的 ① 会改尺寸，prts 二③② 都是 base 档。"""
    if o['click_anim'] and float(o['max_scale']) > float(o['min_scale']):
        return float(o['min_scale']), float(o['max_scale'])
    return 1.0, 1.0


def anim_rungs(size, opt=None):
    """动画会用到的那串像素尺寸（升序，一定含 base）。"""
    o = fx_options(opt)
    base = int(round(size))
    lo = max(1, int(round(base * float(o['min_scale']))))
    hi = max(lo, int(round(base * float(o['max_scale']))))
    n = hi - lo + 1
    cap = max(2, int(o['rung_max']))
    stride = max(1, -(-n // cap))          # 向上取整，省得 import math
    xs = list(range(lo, hi + 1, stride))
    if xs[-1] != hi:
        xs.append(hi)
    if base not in xs:
        xs.append(base)
    return tuple(sorted(set(xs)))


def nearest_rung(rungs, size, scale):
    """把「base × 倍率」这个连续尺寸吸到最近的阶梯档上。"""
    try:
        want = int(round(int(size) * float(scale)))
    except (TypeError, ValueError):
        return int(size)
    best = None
    for v in rungs:
        if best is None or abs(v - want) < abs(best - want):
            best = v
    return int(size) if best is None else best


class CursorAnim(object):
    """点击缩放 / 待机呼吸的驱动线程。

    事件源用「轮询物理键态」而不是全局鼠标钩子 —— 这直接决定了验收标准里
    「松开事件丢失时也不能卡在缩小状态」能不能从结构上成立：
      * WH_MOUSE_LL 需要本进程里有消息泵，而且会被系统按 LowLevelHooksTimeout
        摘钩（摘掉即永久失效，还不给任何提示）；钩子回调一旦漏掉 WM_LBUTTONUP，
        指针就永远停在缩小状态 —— 这正是要避免的失败模式。
      * GetAsyncKeyState 读的是**物理键态**，没有「事件」可以丢：每个 tick 都从
        当前状态重新推导目标尺寸，「卡住」在结构上不存在。
      * 代价只有轮询间隔（默认 8 ms），远小于人手最短点击时长（约 30 ms）。
      * 0x0001 锁存位兜住「两次轮询之间就完成的极短点击」：按下和松开都发生在
        间隔内时物理态读不到，锁存位读得到。它分不清「按下后仍按着」和「按下又
        松开了」，所以只当作「本 tick 至少按下过一次」：锁存为真就进按下段，
        下一 tick 物理态为假即定下松开时刻，回弹照常发生。
    """

    def __init__(self, eng, opt):
        self.eng = eng
        self.opt = fx_options(opt)
        o = self.opt
        self.click = bool(o['click_anim'])
        self.tick_ms = max(1, int(o['tick_ms']))
        self.down_s = max(1, int(o['down_ms'])) / 1000.0
        self.up_s = max(1, int(o['up_ms'])) / 1000.0
        self.rungs = anim_rungs(eng.size, o)
        # PRTS 移植层：实例在 _loop 里造（SetWinEventHook 绑线程，见那边的注释）。
        self.prts = None
        self.prts_on = bool(self.click or o['drag_claw'] or o['idle_prts'])
        self.on = bool(self.click or o['drag_claw'] or o['idle_prts'])
        self.active = False
        self.errors = 0
        self.stop_evt = threading.Event()
        self.thread = None
        self.reset()

    def reset(self):
        self.state = 'idle'
        self.t0 = 0.0
        self.last_applied = {}

    def describe(self):
        """这一组效果「要做什么」的一句话清单，给 GUI / CLI 回显用。

        必须是**唯一**的描述来源：以前 GUI 和 CLI 各写一份 if，删掉待机呼吸时
        只改了效果层、漏改了界面那份，点「应用」就抛
        `'CursorAnim' object has no attribute 'idle'`。

        照 `self.opt`（已归一化的参数）描述而不是照 `self.prts`（驱动线程里才
        装配好、start_fx() 返回这一刻可能还是 None），所以调用时机不会影响结果。
        """
        o = self.opt
        try:
            start_ms = int(o['idle_start_ms'])
        except (KeyError, TypeError, ValueError):
            start_ms = int(FX_DEFAULTS['idle_start_ms'])
        out = []
        if self.click:
            if o['click_style'] == 'prts':
                out.append('点击挤压（PRTS 原帧）')
            else:
                out.append('点击缩放 %.2f×~%.2f×（%d 档）'
                           % (o['min_scale'], o['max_scale'], len(self.rungs)))
        if o['drag_claw']:
            out.append('拖动爪子')
        if o['idle_prts']:
            out.append('待机动画 %.0f 秒后开始' % (start_ms / 1000.0))
        if self.prts is not None and self.prts.err:
            out.append('（%s）' % self.prts.err)
        return out

    def start(self):
        if self.thread is not None:
            return
        self.stop_evt.clear()
        self.active = True
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def stop(self, timeout=1.0):
        self.stop_evt.set()
        t = self.thread
        self.thread = None
        self.active = False
        if t is not None and t.is_alive():
            t.join(timeout)

    def _loop(self):
        # PRTS 移植层必须**在本线程里**装配：SetWinEventHook 把事件投给调用线程
        # 的消息队列，换个线程装就等于没装。装配失败（fx.bin 缺失、钩子装不上）
        # 一律降级成「这项不做」，绝不影响点击缩放和收尾复位。
        if self.prts_on:
            try:
                import prtsfx
                self.prts = prtsfx.PrtsFx(self.eng, self.opt)
                self.prts.install()
            except Exception:
                self.prts = None
                self.errors += 1
        last = time.time()
        while not self.stop_evt.is_set():
            now = time.time()
            dt = now - last
            last = now
            try:
                with self.eng.lock:
                    self._emit(now, dt)
            except Exception:
                self.errors += 1
            time.sleep(self.tick_ms / 1000.0)
        # 收尾：无论怎么退出都要把指针复位到 base 档 —— 这是「松开事件丢失也不会
        # 卡在缩小状态」的最后一道保证。爪子和待机帧同样靠这一步复位。
        if self.prts is not None:
            try:
                self.prts.close()
            except Exception:
                pass
            self.prts = None
        try:
            with self.eng.lock:
                self._reset_to_base()
        except Exception:
            pass

    def _emit(self, now, dt):
        eng = self.eng
        keys_all = list(eng.masters.keys())
        if not keys_all:
            return
        down, latch = keys_state()
        down = bool(down or latch)
        # PRTS 三项效果：① 点击原帧 / ② 拖动爪子 / ③ 待机帧的相都在这里推进。
        # 结果就是「某些角色这一 tick 该显示哪枚 HCURSOR」，直接换掉即可。
        fx_frames, fx_stamp = {}, ''
        spring_px = None
        if self.prts is not None:
            self.prts.poll()
            fx_frames, fx_stamp = self.prts.frames_for(now, down)
            spring_px = self.prts.click_px(now, down, self.rungs)
        if spring_px is not None:
            # ① game 风格：幅度和时间轴都按 prtsfx.ClickSpring 走（像素阶梯）。
            click_px = spring_px
            self.state = 'down' if down else 'idle'
            self.t0 = now
        elif self.click and self.prts is None:
            if down:
                if self.state != 'down':
                    self.state, self.t0 = 'down', now
                u = (now - self.t0) / self.down_s
                t = curve_value(ANIM_DOWN_KEYS, 1.0 if u > 1.0 else u)
            elif self.state == 'down':
                self.state, self.t0 = 'up', now
                t = curve_value(ANIM_UP_KEYS, 0.0)
            elif self.state == 'up':
                u = (now - self.t0) / self.up_s
                if u >= 1.0:
                    self.state, t = 'idle', ANIM_REST_T
                else:
                    t = curve_value(ANIM_UP_KEYS, u)
            else:
                t = ANIM_REST_T
            click_px = nearest_rung(self.rungs, eng.size, scale_of_t(t))
        else:
            click_px = eng.size
            self.state = 'idle'
        for key in keys_all:
            hc = fx_frames.get(key)
            if hc is not None:
                tag = ('fx', fx_stamp)
                if self.last_applied.get(key) == tag:
                    continue
                if eng.set_raw(key, hc):
                    self.last_applied[key] = tag
                continue
            idx = eng.anim_idx.get(key, 0)
            if self.last_applied.get(key) == (click_px, idx):
                continue
            if eng.apply_at(key, idx, click_px):
                self.last_applied[key] = (click_px, idx)

    def _reset_to_base(self):
        eng = self.eng
        for key in list(eng.masters.keys()):
            try:
                eng.apply(key, eng.anim_idx.get(key, 0))
            except Exception:
                pass
        self.last_applied = {}
        self.state, self.t0 = 'idle', 0.0
