# -*- coding: utf-8 -*-
"""上屏验收：跑**打包好的 exe**，只看系统 Arrow 槽的位图会不会自己变。

③ 待机动画是这个测试的主角：鼠标不动、不按键，静止 5 秒后 Arrow 槽的内容
应该开始按 15fps 推进。取样方式与 _t_probe2.py 一致 —— LoadCursorW 拿的是
「当前系统光标」（不是悬停窗口的私有光标），GetIconInfo + GetDIBits 抠位图。
"""
import ctypes
import ctypes.wintypes as wt
import hashlib
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                '源码', 'arkmouse'))
import cursorwin as cw                                    # noqa: E402

u32 = ctypes.windll.user32
gdi = ctypes.windll.gdi32
EXE = r'E:\Qianmory\Desktop\Mouse\明日方舟鼠标.exe'
ARROW = 32512

u32.LoadCursorW.restype = ctypes.c_void_p
u32.LoadCursorW.argtypes = [wt.HINSTANCE, ctypes.c_void_p]
gdi.GetObjectW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
gdi.GetObjectW.restype = ctypes.c_int
gdi.DeleteObject.argtypes = [ctypes.c_void_p]
gdi.DeleteObject.restype = ctypes.c_int
gdi.GetDIBits.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint,
                          ctypes.c_uint, ctypes.c_void_p, ctypes.c_void_p,
                          ctypes.c_uint]
gdi.GetDIBits.restype = ctypes.c_int
u32.GetDC.argtypes = [wt.HWND]
u32.GetDC.restype = ctypes.c_void_p
u32.ReleaseDC.argtypes = [wt.HWND, ctypes.c_void_p]
u32.ReleaseDC.restype = ctypes.c_int


def slot_ink():
    """读系统 Arrow 槽：返回 (宽, 高, 不透明像素数, 位图 md5)。"""
    h = u32.LoadCursorW(None, ctypes.c_void_p(ARROW))
    if not h:
        return None
    ii = cw.ICONINFO()
    if not u32.GetIconInfo(wt.HANDLE(h), ctypes.byref(ii)):
        return None
    try:
        bm = cw.BITMAP()
        if not gdi.GetObjectW(ii.hbmColor, ctypes.sizeof(bm), ctypes.byref(bm)):
            return None
        w, ht = int(bm.bmWidth), int(bm.bmHeight)
        bmi = cw.BITMAPINFOHEADER()
        bmi.biSize = ctypes.sizeof(bmi)
        bmi.biWidth, bmi.biHeight = w, -ht
        bmi.biPlanes, bmi.biBitCount = 1, 32
        bmi.biCompression = 0
        buf = ctypes.create_string_buffer(w * ht * 4)
        hdc = u32.GetDC(None)
        n = gdi.GetDIBits(hdc, ii.hbmColor, 0, ht, buf,
                          ctypes.byref(bmi), 0)
        u32.ReleaseDC(None, hdc)
        if not n:
            return None
        raw = buf.raw
        ink = sum(1 for i in range(3, len(raw), 4) if raw[i] > 8)
        return w, ht, ink, hashlib.md5(raw).hexdigest()[:10]
    finally:
        for hb in (ii.hbmColor, ii.hbmMask):
            if hb:
                gdi.DeleteObject(hb)


def main():
    u32.SystemParametersInfoW(0x0057, 0, None, 0)          # 先复位成 Windows 默认
    time.sleep(0.5)
    base = slot_ink()
    print('启动前（Windows 默认）: %s' % (base,))

    p = subprocess.Popen([EXE, '--guard'])   # 生产路径：开机自启就是带 --guard 起的
    print('exe pid=%d (--guard)' % p.pid)
    try:
        time.sleep(8)                                      # 装机 + 过 5 秒待机门槛
        seen = []
        for _ in range(16):
            s = slot_ink()
            seen.append(s)
            time.sleep(0.4)
        uniq = []
        for s in seen:
            if s and s[3] not in [u[3] for u in uniq]:
                uniq.append(s)
        print('静止 8 秒后连续 16 次取样：')
        for s in seen:
            print('   %s' % (s,))
        print('不同位图数 = %d' % len(uniq))
        alive = p.poll() is None
        print('exe 仍在运行 = %s' % alive)
        ok = alive and len(uniq) > 1
        print('== ③ 待机动画在打包版里%s ==' % ('生效 ✅' if ok else '没看到变化 ❌'))
        return 0 if ok else 1
    finally:
        if p.poll() is None:
            p.terminate()
            try:
                p.wait(timeout=10)
            except Exception:
                p.kill()
        time.sleep(1)
        u32.SystemParametersInfoW(0x0057, 0, None, 0)
        print('指针已复位')


if __name__ == '__main__':
    sys.exit(main())
