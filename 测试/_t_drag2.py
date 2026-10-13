# -*- coding: utf-8 -*-
"""上屏验收②：跑**打包好的 exe（--guard）**，用真窗口真拖拽看系统槽里有没有爪子。

判据（来自 _t_probe2.py 的实测基线，系统 Arrow 槽 72px）：
    箭头静止帧  墨迹 ≈ 1212，bbox 约 (15, 9, 60, 60)
    grab_loop   墨迹 ≈  932，bbox 约 (20, 37, 60, 72)   <- 爪子明显更高更瘦
所以拖动期间只要墨迹掉到 900~1050 且 bbox 变高，就是爪子真的在屏幕上。
"""
import ctypes
import ctypes.wintypes as wt
import hashlib
import os
import subprocess
import sys
import threading
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
gdi.GetDIBits.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint,
                          ctypes.c_uint, ctypes.c_void_p, ctypes.c_void_p,
                          ctypes.c_uint]
gdi.GetDIBits.restype = ctypes.c_int
u32.GetDC.argtypes = [wt.HWND]
u32.GetDC.restype = ctypes.c_void_p
u32.ReleaseDC.argtypes = [wt.HWND, ctypes.c_void_p]
u32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
u32.mouse_event.argtypes = [ctypes.c_uint, ctypes.c_uint, ctypes.c_uint,
                            ctypes.c_uint, ctypes.c_size_t]

SAMPLES = []
LOCK = threading.Lock()
FAILS = [0]


def slot():
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
        buf = ctypes.create_string_buffer(w * ht * 4)
        hdc = u32.GetDC(None)
        n = gdi.GetDIBits(hdc, ii.hbmColor, 0, ht, buf, ctypes.byref(bmi), 0)
        u32.ReleaseDC(None, hdc)
        if not n:
            return None
        raw = buf.raw
        ink = sum(1 for i in range(3, len(raw), 4) if raw[i] > 8)
        xs, ys = [], []
        for y in range(ht):
            for x in range(w):
                if raw[(y * w + x) * 4 + 3] > 8:
                    xs.append(x)
                    ys.append(y)
        bbox = (min(xs), min(ys), max(xs) + 1, max(ys) + 1) if xs else None
        return w, ht, ink, bbox, hashlib.md5(raw).hexdigest()[:8]
    finally:
        for hb in (ii.hbmColor, ii.hbmMask):
            if hb:
                gdi.DeleteObject(hb)


def sampler(stop):
    while not stop.is_set():
        s = slot()
        if s:
            with LOCK:
                SAMPLES.append((round(time.time() - T0, 2),) + s)
        else:
            with LOCK:
                FAILS[0] += 1
        time.sleep(0.06)


def main():
    global T0
    import tkinter as tk
    u32.SystemParametersInfoW(0x0057, 0, None, 0)
    time.sleep(0.5)
    print('启动前（Windows 默认）: %s' % (slot(),))

    p = subprocess.Popen([EXE, '--guard'])
    print('exe pid=%d (--guard)' % p.pid)

    root = tk.Tk()
    root.title('PRTS 拖动验收靶窗')
    root.geometry('420x260+700+420')
    root.attributes('-topmost', True)
    root.update()
    root.lift()
    root.focus_force()
    root.update()
    time.sleep(0.6)
    me = u32.GetAncestor(root.winfo_id(), 2)          # GA_ROOT
    fr = wt.RECT()
    u32.GetWindowRect(wt.HWND(me), ctypes.byref(fr))
    print('靶窗 root hwnd=%s rect=%s 前台=%s' % (
        me, (fr.left, fr.top, fr.right, fr.bottom), u32.GetForegroundWindow()))

    T0 = time.time()
    stop = threading.Event()
    th = threading.Thread(target=sampler, args=(stop,), daemon=True)
    th.start()

    def drive():
        time.sleep(8)                                  # 等装机 + 过待机门槛
        tx = (fr.left + fr.right) // 2
        ty = fr.top + 14                               # 标题栏正中
        print('压点 = (%d, %d)' % (tx, ty))
        u32.SetCursorPos(tx, ty)
        time.sleep(1.0)
        p0 = cw.POINT()
        u32.GetCursorPos(ctypes.byref(p0))
        print('按下前光标 = (%d, %d)，前台=%s'
              % (p0.x, p0.y, u32.GetForegroundWindow()))
        u32.mouse_event(0x0002, 0, 0, 0, 0)            # LEFTDOWN
        time.sleep(0.25)
        for i in range(24):                            # 慢慢拖 240px
            u32.SetCursorPos(tx + i * 10, ty)
            time.sleep(0.05)
        time.sleep(1.2)                                # 拖着不动（应停在 grab_loop）
        print('拖到中点，光标 = (%d, %d)'
              % (u32.GetCursorPos(ctypes.byref(p0)), 0) if False else
              '拖到中点')
        for i in range(24):
            u32.SetCursorPos(tx + 240 - i * 10, ty)
            time.sleep(0.05)
        u32.mouse_event(0x0004, 0, 0, 0, 0)            # LEFTUP
        time.sleep(1.2)                                # 松手后的 end/return 尾巴
        stop.set()
        u32.PostMessageW(root.winfo_id(), 0x0010, 0, 0)

    threading.Thread(target=drive, daemon=True).start()
    root.mainloop()
    time.sleep(0.5)

    with LOCK:
        s = list(SAMPLES)
        nf = FAILS[0]
    print('读取失败（GetIconInfo/GetDIBits 返回空）次数 = %d' % nf)
    uniq = {}
    for r in s:
        uniq.setdefault(r[4], r)
    print('共 %d 次取样，不同位图 %d 种：' % (len(s), len(uniq)))
    for r in sorted(uniq.values()):
        print('   t=%5.2fs  %dx%d 墨迹=%-5d bbox=%s  %s' % r)

    claws = [r for r in s if 850 <= r[3] <= 1060]
    print('疑似爪子帧取样数 = %d' % len(claws))
    if claws:
        print('  第一张 t=%.2fs bbox=%s' % (claws[0][0], claws[0][4]))
    ok = len(uniq) >= 4 and len(claws) >= 3
    print('== ② 拖动爪子在打包版里%s ==' % ('生效 ✅' if ok else '没看到 ❌'))
    if p.poll() is None:
        p.terminate()
        try:
            p.wait(timeout=10)
        except Exception:
            p.kill()
    time.sleep(1)
    u32.SystemParametersInfoW(0x0057, 0, None, 0)
    print('指针已复位')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
