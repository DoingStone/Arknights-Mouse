# -*- coding: utf-8 -*-
"""启动守护 + 完整截图（窗口移到 0,0 以保证整窗可见）。"""
import os
import sys
import time
import tkinter as tk

APP = r'E:\Qianmory\Desktop\Mouse'
sys.path.insert(0, os.path.join(APP, '源码', 'arkmouse'))
import main as M  # noqa: E402
import cursorwin as cw  # noqa: E402

cw.dpi_aware()  # 与真实 main() 一致，否则 Tk 报逻辑像素、截图按物理像素抓

root = tk.Tk()
app = M.App(root)
root.geometry('+0+0')
root.update()
root.update_idletasks()
root.update()

print('窗口 %dx%d @ (%d,%d)' % (root.winfo_width(), root.winfo_height(),
                                root.winfo_rootx(), root.winfo_rooty()))

print()
print('=== 启动守护 ===')
app.do_start_guard(quiet=True)
for i in range(10):
    time.sleep(1.2)
    root.update()
    from importlib import reload
    import guard
    reload(guard)
    st = guard.guard_status()
    print('  %2ds  %s' % (int((i + 1) * 1.2), app.lbl_guard.cget('text')))
    if st[0]:
        break

root.update()
print()
print('  守护状态读数 =', app.lbl_guard.cget('text'))
print('  桌面实际读数 =', app.lbl_now.cget('text'))

from PIL import ImageGrab  # noqa: E402
for tag in ('tab1', 'tab2'):
    root.update()
    time.sleep(0.3)
    root.update()
    x, y = root.winfo_rootx(), root.winfo_rooty()
    w = max(root.winfo_width(), root.winfo_reqwidth())
    h = max(root.winfo_height(), root.winfo_reqheight()) + 10
    im = ImageGrab.grab(bbox=(x, y, x + w, y + h + 8))
    out = r'G:\ArknightsCursorExtract\_diag\newgui\v2_%s.png' % tag
    im.save(out)
    print('\n截图 -> %s (%dx%d)' % (out, im.width, im.height))
    if tag == 'tab1':
        app.nb.select(app.tab_mouse)

root.destroy()
print('GUI 退出（守护保持运行）')
