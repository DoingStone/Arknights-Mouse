# -*- coding: utf-8 -*-
"""打包 exe：把 arkmouse 源码 + art.bin 打成一个自包含的 Windows 可执行文件。

用法： python 构建\build_exe.py
产物： 构建\dist\<名字>.exe
"""
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))          # ...\Mouse\构建
ROOT = os.path.dirname(HERE)                               # ...\Mouse
SRC = os.path.join(ROOT, 'src', 'arkmouse')
ENTRY = os.path.join(SRC, 'main.pyw')
ART = os.path.join(SRC, 'art.bin')
FX = os.path.join(SRC, 'fx.bin')          # PRTS 移植层：① 点击原帧 / ② 爪子 / ③ 待机
ICON = os.path.join(HERE, 'app.ico')
NAME = 'ArknightsMouse'
WORK = os.path.join(HERE, '_work')
DIST = os.path.join(HERE, 'dist')
# **解包目录不再用 %TEMP%**。
# 踩过的坑：onefile 每次启动都要把 28MB 解包到 %TEMP%\_MEIxxxxx，只要那一步
# 被拦（Defender 实时防护对新编译的未知 exe 拦目录创建、临时目录残留过多、
# 磁盘/权限异常），用户双击得到的就是一句
#   Error  Could not create temporary directory!
# 界面根本出不来 —— 而且**每次重新编译都会重演**（新哈希 = 未知文件）。
# 指定 --runtime-tmpdir 后，解包固定落在工程目录下的 runtime\，与系统临时目录
# 彻底解耦；这个目录也由本脚本负责清理，不会越攒越多。
RUNTIME = os.path.join(ROOT, 'runtime')

for p in (ENTRY, ART, FX, ICON):
    if not os.path.isfile(p):
        sys.exit('缺少文件：%s' % p)

if os.path.isdir(WORK):
    shutil.rmtree(WORK, ignore_errors=True)
os.makedirs(RUNTIME, exist_ok=True)
# 清掉上一次运行残留的 _MEI*（bootloader 会在这里再建自己的子目录）
for _n in os.listdir(RUNTIME):
    if _n.startswith('_MEI'):
        shutil.rmtree(os.path.join(RUNTIME, _n), ignore_errors=True)

cmd = [
    sys.executable, '-m', 'PyInstaller',
    '--noconfirm', '--clean',
    '--onefile',
    '--windowed',                      # 不弹控制台
    '--name', NAME,
    '--icon', ICON,
    '--runtime-tmpdir', RUNTIME,       # 解包目录固定在工程内，不碰 %TEMP%
    '--add-data', '%s;.' % ART,        # art.bin -> _MEIPASS 根
    '--add-data', '%s;.' % FX,         # fx.bin  -> _MEIPASS 根（PRTS 三项效果靠它）
    '--distpath', DIST,
    '--workpath', WORK,
    '--specpath', WORK,
    '--paths', SRC,
    '--hidden-import', 'PIL._tkinter_finder',
    '--exclude-module', 'numpy',
    '--exclude-module', 'matplotlib',
    '--exclude-module', 'scipy',
    '--exclude-module', 'pytest',
    ENTRY,
]
print(' '.join('"%s"' % c if ' ' in c else c for c in cmd))
print('-' * 70)
r = subprocess.run(cmd, cwd=HERE)
print('-' * 70)
exe = os.path.join(DIST, NAME + '.exe')
if r.returncode != 0 or not os.path.isfile(exe):
    print('FAILED  returncode=%s' % r.returncode)
    sys.exit(r.returncode or 1)

size = os.path.getsize(exe)
print('OK  %s  %.2f MB' % (exe, size / 1048576.0))

# ---------------------------------------------------------------- 收尾：部署
# 根目录那个 exe 才是用户实际运行的那一个：双击走它，开机自启的 Run 键也指向它。
# 以前这里只打印 OK、从不复制，于是「源码改好了，跑的还是旧 exe」——这条坑
# 已经踩过两次（_MEI 自解包目录修复、动画帧率修复都是被旧 exe 掩盖的）。
# 所以构建成功后必须把产物覆盖到根目录，并且**校验**，失败就要显式报错退出，
# 不能静默留下一个"看起来成功"的旧二进制。
#
# 注意「目录标记」这件事：本工程目录会给**在这个目录里新建的每个文件**打上
# Internet 区（zone=3）。zone 记在文件对象上（不是 ADS/EA，fsutil 看不到），
# 于是双击 exe 时 shell32 会先弹「打开文件 - 安全警告 / 发行商: 未知发布者」，
# 必须点“运行”才真正启动。签名无法消除它（自签证书 Valid 也照样弹）。
# 唯一可行的修法：让部署后的文件对象在**干净目录**里生成，再用同卷 rename 搬进来
# （rename 保留原 inode 与 zone=0）。跨卷会退化成复制、zone 会被重新打上，故暂存
# 目录固定在 ROOT 的父目录下——与本工程同卷。
DEPLOY = os.path.join(ROOT, NAME + '.exe')
STAGE = os.path.join(os.path.dirname(ROOT), '.ark_deploy')
try:
    os.makedirs(STAGE, exist_ok=True)
    staged = os.path.join(STAGE, NAME + '.exe')
    shutil.copy2(exe, staged)             # 在干净目录里生成新文件对象
    ino = os.stat(staged).st_ino
    if os.path.exists(DEPLOY):
        os.remove(DEPLOY)
    os.replace(staged, DEPLOY)            # 同卷 rename：保留 zone=0
except OSError as e:                      # 典型原因：程序/守护还在运行，文件被占用
    print('FAILED  无法覆盖 %s' % DEPLOY)
    print('        是不是程序或守护进程还在运行？先关掉再构建。')
    print('        %s' % e)
    sys.exit(1)

if os.stat(DEPLOY).st_ino != ino:
    print('WARN    部署走了跨卷复制（inode 变了），安全警告可能复现：%s' % DEPLOY)

if not os.path.isfile(DEPLOY):
    print('FAILED  部署后找不到 %s' % DEPLOY)
    sys.exit(1)

dsize = os.path.getsize(DEPLOY)
if dsize != size:
    print('FAILED  部署后大小不符：dist=%d  根目录=%d' % (size, dsize))
    sys.exit(1)

print('DEPLOYED  %s  %.2f MB' % (DEPLOY, dsize / 1048576.0))


# ------------------------------------------------------- 签名：SmartScreen 的唯一根治
# 为什么必须签名：exe 未签名时，双击走 ShellExecute → AppRep 每次都判「未知发布者」，
# 弹「Windows 已保护你的电脑」。实测（2026-10-20）本机 SAC 关闭、exe 无 MOTW、E: 是
# 本地固定盘，仍然每次弹 —— 说明触发条件是「无签名 + 无信誉」，与文件来源、改名、
# 重新打包都无关。「仍要运行」只对当次有效，不会被持久记住。
# 唯一能根治的是公共 CA 签发的代码签名证书：证书有效 → WinVerifyTrust 通过 →
# 不再走「未知发布者」分支。EV 证书立即有信誉；OV 证书需要累积下载量/时间。
# 没有证书时，本脚本照常构建，只在最后明确提示「未签名」，不假装成功。
SIGN_PFX = os.environ.get('ARK_SIGN_PFX', '').strip()
SIGN_PASS = os.environ.get('ARK_SIGN_PASS', '')
SIGN_TS = os.environ.get('ARK_SIGN_TS', 'http://timestamp.digicert.com').strip()


def _find_signtool():
    """先找 PATH，再找 Windows SDK 的 Signing Tools（按版本号倒序取最新）。"""
    p = shutil.which('signtool')
    if p:
        return p
    bases = [os.environ.get('ProgramFiles(x86)'), os.environ.get('ProgramFiles'),
             r'C:\Program Files (x86)', r'C:\Program Files']
    for base in bases:
        if not base:
            continue
        binroot = os.path.join(base, 'Windows Kits', '10', 'bin')
        if not os.path.isdir(binroot):
            continue
        found = []
        for ver in os.listdir(binroot):
            for arch in ('x64', 'x86'):
                cand = os.path.join(binroot, ver, arch, 'signtool.exe')
                if os.path.isfile(cand):
                    found.append(cand)
        if found:
            found.sort(reverse=True)          # 10.0.26100.0 > 10.0.22621.0
            return found[0]
    return None


def _sig_status(path):
    """用 PowerShell 读回 Authenticode 状态，签名后必须等于 Valid。"""
    cmd = ['powershell', '-NoProfile', '-NonInteractive', '-Command',
           '(Get-AuthenticodeSignature -LiteralPath %r).Status' % path]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        return (r.stdout or '').strip() or (r.stderr or '').strip()
    except Exception as e:
        return 'err:%s' % e


if SIGN_PFX:
    if not os.path.isfile(SIGN_PFX):
        print('FAILED  ARK_SIGN_PFX 指向的证书不存在：%s' % SIGN_PFX)
        sys.exit(1)
    _tool = _find_signtool()
    if not _tool:
        print('FAILED  找不到 signtool.exe —— 装 Windows SDK 的 Signing Tools，'
              '或把它加进 PATH')
        sys.exit(1)
    _args = [_tool, 'sign', '/fd', 'sha256', '/f', SIGN_PFX]
    if SIGN_PASS:
        _args += ['/p', SIGN_PASS]
    _args += ['/tr', SIGN_TS, '/td', 'sha256', '/d', '明日方舟鼠标', DEPLOY]
    print('-' * 70)
    print('SIGN  %s' % _tool)
    sr = subprocess.run(_args)
    if sr.returncode != 0:
        print('FAILED  signtool 返回 %s（检查证书密码 / 时间戳服务器网络）'
              % sr.returncode)
        sys.exit(1)
    _st = _sig_status(DEPLOY)
    if _st != 'Valid':
        print('FAILED  签名复核不是 Valid，而是：%s' % _st)
        sys.exit(1)
    print('SIGNED  Status=Valid  %s  %.2f MB' % (DEPLOY, dsize / 1048576.0))
else:
    print('-' * 70)
    print('未签名：SmartScreen 会继续提示「未知发布者」（每次双击都弹）。')
    print('  根治需要一张公共 CA 的代码签名证书（.pfx，含私钥），然后：')
    print('    set ARK_SIGN_PFX=D:\\mycert.pfx')
    print('    set ARK_SIGN_PASS=证书密码')
    print('    python build\\build_exe.py        # 重新构建，本段自动签名并复核')
    print('  EV 证书立即有信誉；OV 证书需要时间/下载量累积。')

