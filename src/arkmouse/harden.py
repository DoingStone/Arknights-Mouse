# -*- coding: utf-8 -*-
"""进程加固：挡住第三方注入，并把「崩了就消失」变成「有记录、可恢复」。

## 为什么要这个模块（2026-10-20 实测出的因果链）

游戏加加（GamePP）用**用户态全局钩子**把
`%LOCALAPPDATA%\\GamePPSDK\\1.2.1618.725\\GPP64.dll` 注入到本进程里。
它的钩子代码在本进程内以 `0xc0000005` / 偏移 `0x9e9c6` 崩掉（事件日志
Application Id=1000 固定是这一条），本程序随之被系统结束 —— 表现就是
「游戏加加开着，双击就闪退」。

代码侧唯一能**真正阻断**这条链的办法，是让那个 DLL 根本进不来：

    SetProcessMitigationPolicy(ProcessSignaturePolicy, MicrosoftSignedOnly)

这条策略（Windows 10 1709+，普通用户权限即可设置）从生效时刻起拒绝
**任何没有 Microsoft 签名的 PE** 载入本进程，加载器直接返回
`ERROR_INVALID_IMAGE_HASH (577)`。GPP64.dll 不是 Microsoft 签名的，注入失败，
钩子不会在本进程里执行，崩溃点自然也就无从触发 —— 而游戏加加本身毫发无损
（它只是没法往本进程塞 DLL，别的功能照常）。

实测要点（都在本机验证过，见 `_audit/evidence/mit_test.py` 的输出）：
  * 策略可以在**已经运行**的进程上设置成功，不需要 CreateProcess 时 opt-in；
  * 设置成功后 `LoadLibrary(GPP64.dll)` 立即失败，错误码 577；
  * 设置**不影响已经加载的模块**，所以 tk86t.dll / _tkinter.pyd 这些
    导入期就加载好的 DLL 不受影响（本程序只有 `harden.apply()` 之后才可能
    需要新 DLL，见下面的 `_PREWARM`）。

`MicrosoftSignedOnly` 是「全拒」而不是「只拒 GPP64」，所以 apply() 之前会把
可能延迟导入的模块先预热一遍，避免误伤自己。

另外两件事是降级保障，不是根治：
  * `SetErrorMode(SEM_NOGPFAULTERRORBOX)` —— 万一还是崩了，不弹 WER 对话框；
  * `WerAddExcludedApplication` —— 不生成 WER 报告、不进「可靠性历史」。

开 `ARK_NO_HARDEN=1` 环境变量可以整体关掉（排障用）。
"""
import ctypes
import os
import sys
import time

SEM_FAILCRITICALERRORS = 0x0001
SEM_NOGPFAULTERRORBOX = 0x0002
SEM_NOOPENFILEERRORBOX = 0x8000

# PROCESS_MITIGATION_POLICY 枚举里的 ProcessSignaturePolicy
POLICY_SIGNATURE = 8
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
PROCESS_VM_READ = 0x0010

# 历史上把本程序打崩 / 可能被打崩的注入模块（小写比较）
_HOSTILE_MODULES = ('gpp64.dll', 'gpp.dll', 'gppfeature_x64.dll',
                    'gppinject_x64.dll')

DLL_GPP = r'%LOCALAPPDATA%\GamePPSDK'

# 策略生效前先导入的模块：都是纯 Python 或导入期本就已加载的扩展，
# 预热它们只是把「万一以后才 import」这条风险消掉。
_PREWARM = ('ctypes', 'winreg', 'shutil', 'json', 'traceback', 'struct',
            'zlib', '_hashlib', '_socket', '_ssl', '_lzma', '_bz2', 'select',
            'math', '_decimal', 'unicodedata')

# Pillow 的 C 扩展**不是**在 `import PIL.Image` 时就全load的：
#   PIL._imagingtk  —— 第一次 ImageTk.PhotoImage(...) 才 import
#   PIL._imagingft  —— 第一次 ImageFont.truetype(...) 才 import
# 这两个 .pyd 都没有微软签名，策略一挂上就变成
#   ImportError: DLL load failed while importing _imagingtk:
#   Windows 无法验证此文件的数字签名
# 实测代价：4 次启动全部走进 _fatal（error.log 4 条「启动失败」）。
# 因为它们只依赖已加载的 tk86t.dll / freetype，这里提前 import 是安全的。
_PREWARM_OPTIONAL = ('PIL._imagingtk', 'PIL._imagingft')


def _k32():
    k = ctypes.WinDLL('kernel32', use_last_error=True)
    return k


def _log(lines):
    """把结果追加到 userdata/harden.log（失败就算了，不能因为写日志让程序起不来）。"""
    if isinstance(lines, str):
        lines = [lines]
    try:
        import paths
        paths.ensure_user_dir()
        p = os.path.join(paths.USER_DIR, 'harden.log')
        with open(p, 'a', encoding='utf-8') as f:
            f.write('%s  pid=%d  %s\n'
                    % (time.strftime('%Y-%m-%d %H:%M:%S'), os.getpid(),
                       ' | '.join(lines)))
    except Exception:
        pass


def early():
    """必须**在 import tkinter 之前**调用：只碰 kernel32/Wer.dll，不加载自研 DLL。

    目的只有一个：让「启动期就崩」这种情况也不弹 WER 框。真正的注入防御在
    apply() 里，因为它依赖「tkinter 已经导入完」这个前提。
    """
    if os.environ.get('ARK_NO_HARDEN'):
        return
    try:
        k = _k32()
        old = k.SetErrorMode(0)
        k.SetErrorMode(old | SEM_FAILCRITICALERRORS
                       | SEM_NOGPFAULTERRORBOX | SEM_NOOPENFILEERRORBOX)
    except Exception:
        pass
    try:
        wer = ctypes.WinDLL('Wer.dll', use_last_error=True)
        wer.WerAddExcludedApplicationW.argtypes = [ctypes.c_wchar_p, ctypes.c_bool]
        wer.WerAddExcludedApplicationW.restype = ctypes.c_long
        name = os.path.basename(sys.executable or '')
        if name.lower().endswith('.exe'):
            wer.WerAddExcludedApplicationW(name, False)
    except Exception:
        # 源码模式（python main.pyw）下这个名字不是 exe，忽略即可
        pass


def _set_policy():
    """上签名策略；返回 (是否设置成功, 读回值)。

    注意两个 API 的签名不一样，别照着 Set 的样子写 Get：
        BOOL SetProcessMitigationPolicy(PROCESS_MITIGATION_POLICY, PVOID, SIZE_T);
        BOOL GetProcessMitigationPolicy(HANDLE hProcess, PROCESS_MITIGATION_POLICY,
                                        PVOID, SIZE_T);   // ← 第一个参数是进程句柄
    一开始按 policy 打头去调 Get，结果恒返回 0（读回 -1），策略明明上了却无法自检。
    """
    k = _k32()
    k.GetCurrentProcess.restype = ctypes.c_void_p
    k.SetProcessMitigationPolicy.argtypes = [ctypes.c_int, ctypes.c_void_p,
                                             ctypes.c_size_t]
    k.SetProcessMitigationPolicy.restype = ctypes.c_int
    k.GetProcessMitigationPolicy.argtypes = [ctypes.c_void_p, ctypes.c_int,
                                             ctypes.c_void_p, ctypes.c_size_t]
    k.GetProcessMitigationPolicy.restype = ctypes.c_int
    flags = ctypes.c_uint32(1)          # PROCESS_MITIGATION_POLICY.MicrosoftSignedOnly
    ok = k.SetProcessMitigationPolicy(POLICY_SIGNATURE, ctypes.byref(flags),
                                      ctypes.sizeof(flags))
    back = ctypes.c_uint32(0)
    got = k.GetProcessMitigationPolicy(ctypes.c_void_p(k.GetCurrentProcess()),
                                       POLICY_SIGNATURE, ctypes.byref(back),
                                       ctypes.sizeof(back))
    return bool(ok), (int(back.value) if got else -1)


def _modules():
    """列出本进程已加载的模块名（小写）。取不到就返回 None。"""
    k = _k32()
    k.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
    k.OpenProcess.restype = ctypes.c_void_p
    k.CloseHandle.argtypes = [ctypes.c_void_p]
    k.K32EnumProcessModules.argtypes = [ctypes.c_void_p, ctypes.c_void_p,
                                        ctypes.c_uint32, ctypes.POINTER(ctypes.c_uint32)]
    k.K32EnumProcessModules.restype = ctypes.c_int
    k.K32GetModuleBaseNameW.argtypes = [ctypes.c_void_p, ctypes.c_void_p,
                                        ctypes.c_wchar_p, ctypes.c_uint32]
    k.K32GetModuleBaseNameW.restype = ctypes.c_uint32
    h = k.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION | PROCESS_VM_READ,
                      0, os.getpid())
    if not h:
        return None
    try:
        buf = (ctypes.c_void_p * 1024)()
        need = ctypes.c_uint32(0)
        if not k.K32EnumProcessModules(h, buf, ctypes.sizeof(buf),
                                       ctypes.byref(need)):
            return None
        step = ctypes.sizeof(ctypes.c_void_p)
        n = min(need.value // step, 1024)
        out = []
        name = ctypes.create_unicode_buffer(260)
        for i in range(n):
            if not buf[i]:
                continue
            if k.K32GetModuleBaseNameW(h, buf[i], name, 260):
                out.append(name.value.lower())
        return out
    finally:
        k.CloseHandle(h)


def _gpp_injected():
    mods = _modules()
    if mods is None:
        return None
    hit = [m for m in mods if m in _HOSTILE_MODULES]
    return hit or []


def _probe(dll_path):
    """真去载入一次 GPP64.dll，确认策略确实挡住了。

    只在策略读回为 1 时才做 —— 否则这一步本身就会把会崩的 DLL 塞进自己进程。
    """
    if not os.path.isfile(dll_path):
        return 'no-file'
    k = _k32()
    k.LoadLibraryExW.argtypes = [ctypes.c_wchar_p, ctypes.c_void_p, ctypes.c_uint32]
    k.LoadLibraryExW.restype = ctypes.c_void_p
    k.FreeLibrary.argtypes = [ctypes.c_void_p]
    ctypes.set_last_error(0)
    h = k.LoadLibraryExW(dll_path, None, 0)
    err = ctypes.get_last_error()
    if h:
        k.FreeLibrary(ctypes.c_void_p(h))
        return 'LOADED(!=%d)' % err
    return 'blocked(%d)' % err


def _find_gpp_dll():
    base = os.path.expandvars(DLL_GPP)
    best = None
    try:
        for ver in os.listdir(base):
            p = os.path.join(base, ver, 'GPP64.dll')
            if os.path.isfile(p):
                if best is None or os.path.getmtime(p) > os.path.getmtime(best):
                    best = p
    except OSError:
        return None
    return best


def _prewarm():
    """把策略生效后**不允许再加载**的模块先加载掉。返回失败清单（写进日志）。"""
    import importlib
    bad = []
    for name in _PREWARM:
        try:
            __import__(name)
        except Exception as e:
            bad.append('%s(%s)' % (name, e))
    # 界面真正会用到的延迟导入项：prtsfx 由 cursorwin 在 FX 启动时才 import，
    # PIL 的画布/字体扩展更是第一次用到才 import。
    names = ('prtsfx', 'PIL.Image', 'PIL.ImageTk', 'PIL.ImageDraw')
    for name in names + _PREWARM_OPTIONAL:
        try:
            importlib.import_module(name)
        except Exception as e:
            bad.append('%s(%s)' % (name, e))
    return bad


def apply():
    """真正的注入防御。必须在 import tkinter / PIL 之后、创建窗口之前调用。

    返回一个 dict，方便调用方（界面）判断要不要提示用户。
    """
    res = {'skipped': False, 'policy': 0, 'readback': -1,
           'preinjected': [], 'preinjected_unknown': False,
           'probe': 'not-run', 'prewarm_fail': []}
    if os.environ.get('ARK_NO_HARDEN'):
        res['skipped'] = True
        _log(['harden=SKIPPED(ARK_NO_HARDEN)'])
        return res

    # ① 预热可能延迟导入的模块，避免被自己的策略误伤
    try:
        res['prewarm_fail'] = _prewarm()
    except Exception as e:
        res['prewarm_fail'] = ['prewarm(%s)' % e]

    # ② 上策略
    try:
        ok, back = _set_policy()
    except Exception:
        ok, back = False, -1
    res['policy'] = 1 if ok else 0
    res['readback'] = back

    # ③ 看有没有在我们加固之前就被塞进来的
    try:
        hit = _gpp_injected()
    except Exception:
        hit = None
    if hit is None:
        res['preinjected_unknown'] = True
    else:
        res['preinjected'] = hit

    # ④ 自检：真的去载入，确认挡住了（只有读回确认时才敢做）
    # 读回值是 PROCESS_MITIGATION_BINARY_SIGNATURE_POLICY.Flags 位域，
    # 不是「1 = 开」。实测本机 Set(flags=1) 之后读回是 5（bit0 MicrosoftSignedOnly
    # + bit2 MitigationOptIn），所以只能按 bit0 判断，不能整体 ==1 比较。
    if back > 0 and (back & 1):
        try:
            p = _find_gpp_dll()
            if p:
                res['probe'] = _probe(p)
        except Exception as e:
            res['probe'] = 'err:%s' % e

    _log(['policy=%d readback=%d probe=%s preinjected=%s prewarm_fail=%d%s'
          % (res['policy'], res['readback'], res['probe'],
             ','.join(res['preinjected']) or ('?' if res['preinjected_unknown'] else 'no'),
             len(res['prewarm_fail']),
             ('[' + '; '.join(res['prewarm_fail'][:4]) + ']') if res['prewarm_fail'] else '')])
    return res
