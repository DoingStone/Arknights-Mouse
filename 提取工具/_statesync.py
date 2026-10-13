# -*- coding: utf-8 -*-
"""验证开机自启状态在 设置.json 与注册表之间同步。"""
import json
import os
import sys

sys.path.insert(0, r'E:\Qianmory\Desktop\Mouse\源码\arkmouse')

import paths
import store

print('STATE 文件: %s' % paths.STATE)
print('注册表自启 = %s' % store.get_autostart())
print('\nload() ->')
d = store.load()
for k, v in d.items():
    print('   %-12s = %r' % (k, v))

print('\n文件原内容:')
print(open(paths.STATE, encoding='utf-8').read())

store.save(d)
print('save() 后文件内容:')
print(open(paths.STATE, encoding='utf-8').read())

print('再次 load() autostart = %r  （应与注册表一致：%r）'
      % (store.load()['autostart'], store.get_autostart()))

run = store.app_command(d.get('scale'))
print('\napp_command(1.20) = %r' % run)
print('is_frozen = %s' % paths.is_frozen())
