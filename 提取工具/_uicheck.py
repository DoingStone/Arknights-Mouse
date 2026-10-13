# -*- coding: utf-8 -*-
"""还原测试动过的系统值 + 报告窗口所需高度。"""
import os
import sys
import tkinter as tk

APP = r'E:\Qianmory\Desktop\Mouse'
sys.path.insert(0, os.path.join(APP, '源码', 'arkmouse'))
import mousep  # noqa: E402
import main as M  # noqa: E402

print('=== 还原测试动过的值 ===')
print('  滚轮行数 %s -> 3 : %s' % (mousep.get_wheel_lines(),
                                   mousep.commit_wheel_lines(3)))

root = tk.Tk()
app = M.App(root)
root.update_idletasks()
root.update()
print()
print('=== 窗口尺寸 ===')
print('  实际   %dx%d' % (root.winfo_width(), root.winfo_height()))
print('  需要的 %dx%d' % (root.winfo_reqwidth(), root.winfo_reqheight()))
app.nb.select(app.tab_mouse)
root.update_idletasks()
root.update()
print('  页签二需要的 %dx%d' % (root.winfo_reqwidth(), root.winfo_reqheight()))
print()
print('=== 状态栏 / 底注 ===')
print('  status =', app.status.cget('text'))
root.destroy()

print()
print('=== 系统最终状态 ===')
d = mousep.get_all()
for k in ['鼠标速度', '滚轮行数', '悬停时间', '鼠标轨迹', '双击速度',
          '打字时隐藏指针', '指针阴影', '点击锁定']:
    print('  %-14s %s' % (k, d[k]))
