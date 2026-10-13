# -*- coding: utf-8 -*-
"""迁移终局验收：把所有交付项逐条核对一遍。"""
import ctypes
import ctypes.wintypes as wt
import json
import os
import subprocess
import time
import winreg

u32 = ctypes.WinDLL('user32', use_last_error=True)
gdi = ctypes.WinDLL('gdi32', use_last_error=True)
TOP = r'E:\Qianmory\Desktop\Mouse'
PACK = os.path.join(TOP, '指针')
EXE = os.path.join(TOP, '明日方舟鼠标.exe')

OK, BAD = [], []


def chk(name, cond, extra=''):
    (OK if cond else BAD).append(name)
    print('  [%s] %-30s %s' % ('✓' if cond else '✗', name, extra))


class ICONINFO(ctypes.Structure):
    _fields_ = [('fIcon', wt.BOOL), ('xHotspot', wt.DWORD),
                ('yHotspot', wt.DWORD), ('hbmMask', wt.HANDLE),
                ('hbmColor', wt.HANDLE)]


class CURSORINFO(ctypes.Structure):
    _fields_ = [('cbSize', wt.DWORD), ('flags', wt.DWORD),
                ('hCursor', wt.HANDLE), ('ptScreenPos', wt.POINT)]


class BITMAP(ctypes.Structure):
    _fields_ = [('bmType', ctypes.c_long), ('bmWidth', ctypes.c_long),
                ('bmHeight', ctypes.c_long), ('bmWidthBytes', ctypes.c_long),
                ('bmPlanes', wt.WORD), ('bmBitsPixel', wt.WORD),
                ('bmBits', ctypes.c_void_p)]


u32.GetCursorInfo.argtypes = [ctypes.POINTER(CURSORINFO)]
u32.GetIconInfo.argtypes = [wt.HANDLE, ctypes.POINTER(ICONINFO)]
gdi.GetObjectW.argtypes = [wt.HANDLE, ctypes.c_int, ctypes.c_void_p]
gdi.DeleteObject.argtypes = [wt.HANDLE]
u32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
u32.IsWindowVisible.argtypes = [wt.HANDLE]


def measure(n=5):
    got = []
    for _ in range(n):
        u32.SetCursorPos(1536, 1036)
        time.sleep(0.10)
        u32.SetCursorPos(1537, 1037)
        time.sleep(0.10)
        ci = CURSORINFO()
        ci.cbSize = ctypes.sizeof(CURSORINFO)
        if not u32.GetCursorInfo(ctypes.byref(ci)) or not ci.hCursor:
            continue
        ii = ICONINFO()
        if not u32.GetIconInfo(ci.hCursor, ctypes.byref(ii)):
            continue
        bm = BITMAP()
        gdi.GetObjectW(ii.hbmColor, ctypes.sizeof(BITMAP), ctypes.byref(bm))
        if ii.hbmColor:
            gdi.DeleteObject(ii.hbmColor)
        if ii.hbmMask:
            gdi.DeleteObject(ii.hbmMask)
        got.append((bm.bmWidth, bm.bmHeight, ii.xHotspot, ii.yHotspot))
        time.sleep(0.15)
    return got


print('=' * 68)
print(' 1) 目录结构')
print('=' * 68)
expect = ['明日方舟鼠标.exe', '启动.bat', '说明.md', '设置.json',
          '指针', '提取工具', '源码', '构建']
for e in expect:
    p = os.path.join(TOP, e)
    chk(e, os.path.exists(p),
        '%.2f MB' % (os.path.getsize(p) / 1048576) if os.path.isfile(p) else '')

print('\n 源码\\arkmouse 模块：')
am = os.path.join(TOP, '源码', 'arkmouse')
for f in sorted(os.listdir(am)):
    if f.endswith(('.py', '.pyw', '.bin')):
        print('    %-18s %8.1f KB' % (f, os.path.getsize(os.path.join(am, f)) / 1024))

print('\n' + '=' * 68)
print(' 2) exe 是最新构建的')
print('=' * 68)
dist = os.path.join(TOP, '构建', 'dist', '明日方舟鼠标.exe')
import hashlib


def h(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()[:16]


chk('exe == dist 内容一致', h(EXE) == h(dist),
    '%s / %s  %.2f MB' % (h(EXE), h(dist), os.path.getsize(EXE) / 1048576))
chk('exe 无异常记录（错误日志为空）',
    not os.path.isfile(os.path.join(TOP, '错误日志.txt')) or
    os.path.getsize(os.path.join(TOP, '错误日志.txt')) == 0)
_run = os.path.join(TOP, '运行日志.txt')
if os.path.isfile(_run):
    print('     运行日志.txt = %d B（普通输出，非异常）' % os.path.getsize(_run))

print('\n' + '=' * 68)
print(' 3) 指针完整（3 档 × 17 角色）')
print('=' * 68)
man = os.path.join(PACK, '_manifest.json')
chk('_manifest.json 存在', os.path.isfile(man))
if os.path.isfile(man):
    m = json.load(open(man, encoding='utf-8'))
    for tier in ('small', 'medium', 'large'):
        d = os.path.join(PACK, 'cursors', tier)
        n = len(os.listdir(d)) if os.path.isdir(d) else 0
        chk('档位 %s' % tier, n == 17, '%d 个文件' % n)

print('\n' + '=' * 68)
print(' 4) 系统光标指向新位置')
print('=' * 68)
with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Control Panel\Cursors') as k:
    n = winreg.QueryInfoKey(k)[1]
    vals = {}
    for i in range(n):
        nm, dt, ty = winreg.EnumValue(k, i)
        vals[nm] = dt
want = os.path.join(PACK, 'cursors', 'large')
ROLES17 = ['Arrow', 'Help', 'AppStarting', 'Wait', 'Crosshair', 'IBeam',
           'NWPen', 'No', 'SizeNS', 'SizeWE', 'SizeNWSE', 'SizeNESW',
           'SizeAll', 'UpArrow', 'Hand', 'Pin', 'Person']
wrong = []
for nm in ROLES17:
    v = vals.get(nm)
    if not isinstance(v, str) or os.path.dirname(v).lower() != want.lower():
        wrong.append(nm)
chk('17 角色全指向 指针', not wrong, '偏差：%s' % wrong if wrong else '')
chk('方案名正确', vals.get('', '').startswith('明日方舟'),
    '现=%r' % vals.get('', ''))
chk('无残留 G: 路径',
    not any(isinstance(v, str) and v.startswith('G:') for v in vals.values()))
print('     方案名 = %r' % vals.get('', ''))

print('\n' + '=' * 68)
print(' 5) 开机自启指向新 exe')
print('=' * 68)
RUN = r'Software\Microsoft\Windows\CurrentVersion\Run'
with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN) as k:
    items = {}
    for i in range(winreg.QueryInfoKey(k)[1]):
        nm, dt, ty = winreg.EnumValue(k, i)
        items[nm] = dt
chk('新键 ArknightsMouse 存在', 'ArknightsMouse' in items)
chk('旧键 ArknightsCursorSize 已清除', 'ArknightsCursorSize' not in items)
for nm in ('ArknightsMouse', 'ArknightsCursorSize'):
    if nm in items:
        print('     %s = %s' % (nm, items[nm]))

print('\n' + '=' * 68)
print(' 6) 桌面指针实际尺寸（对 设置.json 里的档位）')
print('=' * 68)
_cfg = json.load(open(os.path.join(TOP, '设置.json'), encoding='utf-8'))
_want = int(round(96 * float(_cfg.get('scale', 1.20))))
_hx = int(round(28 * _want / 96.0))
_hy = int(round(20 * _want / 96.0))
print('  设置.json 档位 = %s× → 期望 %dpx 热点 (%d,%d)'
      % (_cfg.get('scale'), _want, _hx, _hy))
got = measure(5)
print('  采样：%s' % got)
allok = bool(got) and all(g[0] == _want and g[1] == _want for g in got)
chk('全部 %dx%d' % (_want, _want), allok)
if got:
    chk('热点全为 (%d,%d)' % (_hx, _hy),
        all(g[2:] == (_hx, _hy) for g in got))

print('\n' + '=' * 68)
print(' 7) 鼠标参数合法')
print('=' * 68)
import sys
sys.path.insert(0, am)
import mousep
d = mousep.get_all()
# 基线会随用户调整而变；这里只检查结构完整、类型正确、在 Windows 合法范围内。
_ranges = {'阈值1': (0, 2), '阈值2': (0, 2), '加速': (0, 1),
           '鼠标速度': (1, 20), '滚轮行数': (-1, 100), '双击速度': (100, 900),
           '鼠标轨迹': (0, 10), '悬停时间': (10, 2000)}
for k, (lo, hi) in _ranges.items():
    v = d.get(k)
    chk('%s 合法 (%s)' % (k, '现=%r' % v),
        isinstance(v, int) and lo <= v <= hi)
for k in ('左右键互换', '吸附到默认按钮', '打字时隐藏指针', '指针阴影', '点击锁定'):
    chk('%s 是布尔' % k, isinstance(d.get(k), bool), '现=%r' % d.get(k))

print('\n' + '=' * 68)
print(' 通过 %d 项' % len(OK))
if BAD:
    print(' ✗ 失败 %d 项：%s' % (len(BAD), '、'.join(BAD)))
else:
    print(' ✓ 失败 0 项 —— 迁移与 exe 全部验收通过')
print('=' * 68)
