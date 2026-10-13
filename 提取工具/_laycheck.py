# -*- coding: utf-8 -*-
"""量每个子控件的实际 y 位置，找出窗口是否被内容撑破。"""
import os
import sys
import tkinter as tk

APP = r'E:\Qianmory\Desktop\Mouse'
sys.path.insert(0, os.path.join(APP, '源码', 'arkmouse'))
import main as M  # noqa: E402

root = tk.Tk()
app = M.App(root)
root.update_idletasks()
root.update()

print('window: h=%d reqh=%d  w=%d reqw=%d'
      % (root.winfo_height(), root.winfo_reqheight(),
         root.winfo_width(), root.winfo_reqwidth()))

f = app.tab_size
print('\n=== tab_size 子控件（grid 行）===')
for ch in f.winfo_children():
    info = ch.grid_info()
    print('  row=%-3s y=%-4s h=%-4s bottom=%-4s %s'
          % (info.get('row'), ch.winfo_y(), ch.winfo_height(),
             ch.winfo_y() + ch.winfo_height(), ch.winfo_class()))

print('\n  tab_size h=%d reqh=%d' % (f.winfo_height(), f.winfo_reqheight()))

nb = app.nb
print('\nnotebook h=%d reqh=%d' % (nb.winfo_height(), nb.winfo_reqheight()))
print('\n=== root 子控件 ===')
for ch in root.winfo_children():
    print('  y=%-4s h=%-4s bottom=%-4s %s'
          % (ch.winfo_y(), ch.winfo_height(),
             ch.winfo_y() + ch.winfo_height(), ch.winfo_class()))

root.destroy()
