# -*- coding: utf-8 -*-
"""把启动器脚本按系统 ANSI 代码页（本机 936 = GBK）重写。

教训：
  - cscript 按 ACP 读 .vbs，UTF-8 存的中文会变乱码，甚至报
    "Microsoft VBScript 编译器错误: 无效字符"。
  - .bat 同理，cmd.exe 按 OEMCP(936) 读，非 ASCII 必须存 GBK。
"""
import os

HERE = r'G:\ArknightsCursorExtract\CursorSizeTool'

# ---- 启动.vbs：内容全 ASCII，彻底避开编码问题 ----
VBS = '''\' Arknights Crystal Cursor - size tool launcher
\' Double-click to open the GUI without a console window.
Option Explicit

Dim fso, sh, here, target, rc
Set fso = CreateObject("Scripting.FileSystemObject")
Set sh  = CreateObject("WScript.Shell")

here = fso.GetParentFolderName(WScript.ScriptFullName)
target = here & "\\ArknightsCursorSize.pyw"

If Not fso.FileExists(target) Then
    MsgBox "Main script not found:" & vbCrLf & target, 16, "Arknights Cursor"
    WScript.Quit 1
End If

rc = -1
On Error Resume Next
sh.Run "pythonw.exe """ & target & """", 0, False
If Err.Number = 0 Then rc = 0
Err.Clear
If rc <> 0 Then
    sh.Run "python.exe """ & target & """", 0, False
    If Err.Number = 0 Then rc = 0
    Err.Clear
End If
On Error GoTo 0

If rc <> 0 Then
    MsgBox "Python not found." & vbCrLf & vbCrLf & _
           "Please install Python 3 and add it to PATH.", 16, "Arknights Cursor"
    WScript.Quit 2
End If
'''

# ---- 启动.bat：中文，存 GBK ----
BAT = '''@echo off
rem 明日方舟 水晶指针 · 大小调节工具 —— 启动器（会短暂显示控制台窗口）
rem 想完全无窗口，请双击「启动.vbs」
cd /d "%~dp0"

where pythonw.exe >nul 2>nul
if %errorlevel%==0 (
    start "" pythonw.exe "ArknightsCursorSize.pyw"
    exit /b 0
)

where python.exe >nul 2>nul
if %errorlevel%==0 (
    start "" python.exe "ArknightsCursorSize.pyw"
    exit /b 0
)

echo.
echo   找不到 Python。请先安装 Python 3 并勾选 "Add Python to PATH"。
echo.
pause
exit /b 1
'''

vp = os.path.join(HERE, '启动.vbs')
bp = os.path.join(HERE, '启动.bat')

with open(vp, 'w', encoding='ascii', newline='\r\n') as f:
    f.write(VBS)
with open(bp, 'w', encoding='gbk', newline='\r\n') as f:
    f.write(BAT)

for p in (vp, bp):
    raw = open(p, 'rb').read()
    print('%-16s %6d B  head=%r' % (os.path.basename(p), len(raw), raw[:20]))
    # 校验：非 ASCII 字节必须是合法 GBK
    nb = bytes(b for b in raw if b > 127)
    if nb:
        try:
            nb.decode('gbk')
            print('   non-ascii %d bytes -> GBK decode OK' % len(nb))
        except Exception as e:
            print('   !! GBK decode failed:', e)
    else:
        print('   pure ASCII')
