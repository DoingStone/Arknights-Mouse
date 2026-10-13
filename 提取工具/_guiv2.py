# -*- coding: utf-8 -*-
"""GUI 端到端验收（v2）：启动真实 tk 窗口，检查新增的守护行 / 桌面实际读数 /
页签布局是否正常，并截图。"""
import os
import sys
import time
import tkinter as tk

APP = r'E:\Qianmory\Desktop\Mouse'
SRC = os.path.join(APP, '源码', 'arkmouse')
sys.path.insert(0, SRC)

import main as M  # noqa: E402

root = tk.Tk()
app = M.App(root)
root.update()
root.update_idletasks()
time.sleep(0.5)
root.update()

print('=== 页签一 关键控件 ===')
print('  滑杆值        =', app.sc.get())
print('  scale         =', app.scale)
print('  预览读数      =', app.lbl.cget('text'))
print('  桌面实际读数  =', app.lbl_now.cget('text'))
print('  守护状态      =', app.lbl_guard.cget('text'))
print('  开机自启勾选  =', app.v_auto.get())

print()
print('=== 控件存在性 ===')
for name in ['lbl_now', 'lbl_guard', 'lbl_speed', 'lbl_accel', 'lbl_dbl',
             'lbl_wheel', 'lbl_trail', 'lbl_hover', 'sc', 'cv', 'status']:
    print('  %-12s %s' % (name, hasattr(app, name)))

print()
print('=== 页签二 滑杆初值 ===')
for k, s in app.mv.items():
    print('  %-8s = %s' % (k, s.get()))

print()
print('=== 不支持的开关应置灰 ===')
for k, (cb, var) in app.mb.items():
    st = cb.state()
    print('  %-8s disabled=%-6s state=%s' % (k, 'disabled' in st, list(st)))

print()
print('=== 拖动滑杆不卡（快速路径）===')
t0 = time.time()
for v in range(1, 11):
    app._on_wheel(str(v))
dt = (time.time() - t0) / 10 * 1000
print('  _on_wheel 10 次平均 %.1f ms/次' % dt)

# 还原
import mousep  # noqa: E402
time.sleep(1.2)
mousep.set_wheel_lines(3, verify=False)
print('  已还原滚轮 = %s' % mousep.get_wheel_lines())

# 截图
try:
    from PIL import ImageGrab
    root.update()
    time.sleep(0.4)
    root.update()
    x, y = root.winfo_rootx(), root.winfo_rooty()
    w, h = root.winfo_width(), root.winfo_height()
    im = ImageGrab.grab(bbox=(x, y, x + w, y + h))
    out = r'G:\ArknightsCursorExtract\_diag\newgui\v2_tab1.png'
    os.makedirs(os.path.dirname(out), exist_ok=True)
    im.save(out)
    print('\n截图 -> %s (%dx%d)' % (out, im.width, im.height))
except Exception as e:
    print('\n截图失败：%s' % e)

root.destroy()
print('GUI 正常退出')
