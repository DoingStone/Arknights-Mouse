# -*- coding: utf-8 -*-
<#
    明日方舟 · 水晶指针 —— 安装 / 切换 / 卸载

    用法（在 PowerShell 里执行）：
        .\install.ps1                  列出可用档位并提示选择
        .\install.ps1 -Tier small      安装「小」档（48px 视觉大小）
        .\install.ps1 -Tier medium     安装「中」档（1/√2 ≈ 68px 视觉大小）
        .\install.ps1 -Tier p72        安装「72px」档（0.75×，程序默认 scale）
        .\install.ps1 -Tier large      安装「大」档（96px，原始分辨率）
        .\install.ps1 -Restore         回滚到安装前的系统指针方案
        .\install.ps1 -Status          只查看当前应用的是哪一套

    说明：只写 HKCU\Control Panel\Cursors，不需要管理员权限；
          不修改任何游戏文件，游戏目录全程只读。
#>
[CmdletBinding()]
param(
    [ValidateSet('small', 'medium', 'p72', 'large')]
    [string]$Tier,
    [switch]$Restore,
    [switch]$Status
)

$ErrorActionPreference = 'Stop'
$PackRoot = Split-Path -Parent $MyInvocation.MyCommand.Definition
$Backup   = Join-Path $PackRoot 'before-install-backup.json'
$RegPath  = 'HKCU:\Control Panel\Cursors'

# 注册表角色 -> 包内文件名片段（安装前备份里的键名与 Windows 角色同名）
$Roles = @('Arrow','Help','AppStarting','Wait','Crosshair','IBeam','NWPen','No',
           'SizeNS','SizeWE','SizeNWSE','SizeNESW','SizeAll','UpArrow','Hand',
           'Pin','Person')

# 档名必须与源码里 cursorwin.PACK_TIERS 的 scheme_display_name() 逐字一致：
# 程序里的守护进程也往同一个 Schemes 子键写方案名，两边不一致的话
# 「鼠标属性 → 方案」里会同时出现两条指向本包的条目。
$TierName = @{ small = '小 (0.50×)'; medium = '中 (0.71×)'
               p72   = '72px (0.75×)'; large = '大 (1.00×)' }

# 角色 -> WinUser.h 的 OCR_* 常量。仅写注册表时，已经打开的窗口要等重登才刷新；
# 调用 SetSystemCursor 才能真正让当前会话立即换图。
$OcrId = @{
    Arrow = 32512; IBeam = 32513; Wait = 32514; Crosshair = 32515; UpArrow = 32516
    SizeNWSE = 32642; SizeNESW = 32643; SizeWE = 32644; SizeNS = 32645; SizeAll = 32646
    No = 32648; Hand = 32649; AppStarting = 32650; Help = 32651; Pin = 32671; Person = 32672
}

if (-not ('Win32.CursorApi' -as [type])) {
    Add-Type -Namespace Win32 -Name CursorApi -MemberDefinition @'
[DllImport("user32.dll", CharSet=CharSet.Unicode, SetLastError=true)]
public static extern IntPtr LoadCursorFromFileW(string path);
[DllImport("user32.dll", SetLastError=true)]
public static extern bool SetSystemCursor(IntPtr hcur, uint id);
[DllImport("user32.dll", SetLastError=true)]
public static extern bool SystemParametersInfo(uint uAction, uint uParam, IntPtr lpvParam, uint fuWinIni);
'@
}

function Broadcast-Change {
    [Win32.CursorApi]::SystemParametersInfo(0x0057, 0, [IntPtr]::Zero, 0x01 -bor 0x02) | Out-Null
}

# 让当前登录会话立刻换图（不依赖注销/重启资源管理器）
function Apply-Immediate([string]$dir, [string]$t) {
    $ok = 0; $skip = 0
    foreach ($role in $Roles) {
        if (-not $OcrId.ContainsKey($role)) { $skip++; continue }
        $f = Get-ChildItem -Path $dir -Filter "*_$role`_$t.*" -ErrorAction SilentlyContinue |
             Select-Object -First 1
        if (-not $f) { $skip++; continue }
        $h = [Win32.CursorApi]::LoadCursorFromFileW($f.FullName)
        if ($h -eq [IntPtr]::Zero) { $skip++; continue }
        # SetSystemCursor 成功后接管句柄所有权，不可再 DestroyCursor
        if ([Win32.CursorApi]::SetSystemCursor($h, [uint32]$OcrId[$role])) { $ok++ } else { $skip++ }
    }
    Broadcast-Change
    Write-Host "  立即生效：$ok / 16 个可即时切换的角色" -ForegroundColor DarkGray
}

# 检测第三方「动态指针」常驻程序：它们会周期性重新写注册表，从而覆盖本包
function Test-Conflict {
    $p = Get-Process -ErrorAction SilentlyContinue |
         Where-Object { $_.ProcessName -match 'PRTS-Motion|Replica|CursorMotion' }
    if ($p) {
        Write-Host ''
        Write-Host "注意：检测到常驻指针程序 $($p[0].ProcessName).exe（PID $($p[0].Id)）。" -ForegroundColor Yellow
        Write-Host '      它会周期性重写指针注册表，可能覆盖本包。若指针被换回去，' -ForegroundColor Yellow
        Write-Host '      请先结束该进程（或移除其开机自启项），再重新运行本脚本。' -ForegroundColor Yellow
    }
}

function Show-Status {
    $cur = Get-ItemProperty -Path $RegPath
    $scheme = $cur.'(default)'
    Write-Host ''
    Write-Host '当前系统指针方案：' -NoNewline
    Write-Host $scheme -ForegroundColor Cyan
    $arrow = $cur.Arrow
    Write-Host '箭头指针文件：' -NoNewline
    Write-Host $arrow -ForegroundColor DarkGray
    # 用本脚本所在目录判断，而不是写死文件夹名 —— 这样整个包可以随意搬位置。
    if ($arrow -and $arrow.StartsWith($PackRoot, [StringComparison]::OrdinalIgnoreCase)) {
        $t = ($arrow -split '_')[-1] -replace '\.cur$',''
        Write-Host "→ 正在使用本包（档位：$t）" -ForegroundColor Green
    } else {
        Write-Host '→ 未使用本包' -ForegroundColor Yellow
    }
    Write-Host ''
}

function Restore-Backup {
    if (-not (Test-Path $Backup)) { throw "找不到备份文件：$Backup" }

    # Windows PowerShell 5.1 的 ConvertFrom-Json 不接受空字符串键名，
    # 而备份里方案名恰好存在 "" 键下 —— 先用正则改成安全占位键再解析。
    $rawJson  = Get-Content $Backup -Raw -Encoding UTF8
    $safeJson = [regex]::Replace($rawJson, '"\s*":', '"__SCHEME__":')
    $b = $safeJson | ConvertFrom-Json
    $n = 0
    foreach ($p in $b.PSObject.Properties) {
        $name = $p.Name
        if ($name -eq '__SCHEME__') { $name = '(default)' }   # 还原成注册表默认值
        New-ItemProperty -Path $RegPath -Name $name -Value $p.Value -PropertyType String -Force | Out-Null
        $n++
    }
    # 顺手把本包登记过的「方案」条目摘掉 —— 回滚就该回到干净状态，否则
    # 「鼠标属性 → 方案」列表里会一直留着几条指向本包目录的条目，而这个
    # 目录可能已经被删了（那几条会变成选不动的死条目）。
    $schemesPath = 'HKCU:\Control Panel\Cursors\Schemes'
    if (Test-Path $schemesPath) {
        foreach ($t in $TierName.Keys) {
            Remove-ItemProperty -Path $schemesPath `
                -Name "明日方舟 水晶指针 $($TierName[$t])" -ErrorAction SilentlyContinue
        }
    }
    # 广播设置变更，让系统立即重载指针
    Broadcast-Change
    Write-Host "已回滚到安装前的指针方案（还原 $n 项）。" -ForegroundColor Green

    # 回滚也要立刻生效：把还原后的每个角色重新喂给 SetSystemCursor
    $ok = 0
    $cur = Get-ItemProperty -Path $RegPath
    foreach ($role in $Roles) {
        if (-not $OcrId.ContainsKey($role)) { continue }
        $path = $cur.$role
        if (-not $path -or -not (Test-Path -LiteralPath $path)) { continue }
        $h = [Win32.CursorApi]::LoadCursorFromFileW($path)
        if ($h -eq [IntPtr]::Zero) { continue }
        if ([Win32.CursorApi]::SetSystemCursor($h, [uint32]$OcrId[$role])) { $ok++ }
    }
    Broadcast-Change
    Write-Host "  立即生效：$ok / 16 个已还原的角色" -ForegroundColor DarkGray
}

function Install-Tier([string]$t) {
    $dir = Join-Path $PackRoot "cursors\$t"
    if (-not (Test-Path $dir)) { throw "找不到档位目录：$dir" }
    if (-not (Test-Path $Backup)) { throw "找不到备份文件：$Backup" }

    # 首次安装前把现有方案存一份（仅供参考）
    if (-not (Test-Path (Join-Path $PackRoot 'backup-applied.txt'))) {
        # 排除 PowerShell 自动附加的 PS* 元数据属性，只留真正的注册表值
        $snap = @{}
        (Get-ItemProperty -Path $RegPath).PSObject.Properties |
            Where-Object { $_.Name -notlike 'PS*' } |
            ForEach-Object { $snap[$_.Name] = $_.Value }
        $snap | ConvertTo-Json -Depth 3 |
            Set-Content -Path (Join-Path $PackRoot 'backup-applied.txt') -Encoding UTF8
    }

    $set = 0
    $paths = @()
    foreach ($role in $Roles) {
        # .cur 优先于 .ani —— 必须和 guard.py 的 scheme_files() 挑同一个文件，
        # 否则程序复核时会认为方案被改过，随手把它重写一遍。
        $f = Get-ChildItem -Path $dir -Filter "*_$role`_$t.cur" -ErrorAction SilentlyContinue
        if (-not $f) { $f = Get-ChildItem -Path $dir -Filter "*_$role`_$t.ani" -ErrorAction SilentlyContinue }
        if (-not $f) {
            $f = Get-ChildItem -Path $dir -Filter "*_$role.cur" -ErrorAction SilentlyContinue
            if (-not $f) { $f = Get-ChildItem -Path $dir -Filter "*_$role.ani" -ErrorAction SilentlyContinue }
        }
        if (-not $f) { Write-Warning "缺少角色 $role 的指针文件，跳过"; $paths += ''; continue }
        # 槽位用 ExpandString：Windows 自己写槽位时就是这个类型，第三方皮肤也一样。
        # 绝对路径里没有 %变量% 时与 String 完全等价，纯粹为了和基准一致。
        New-ItemProperty -Path $RegPath -Name $role -Value $f[0].FullName -PropertyType ExpandString -Force | Out-Null
        $paths += $f[0].FullName
        $set++
    }

    $schemeName = "明日方舟 水晶指针 $($TierName[$t])"
    New-ItemProperty -Path $RegPath -Name '(default)' -Value $schemeName -PropertyType String -Force | Out-Null
    New-ItemProperty -Path $RegPath -Name 'Scheme Source' -Value 1 -PropertyType DWord -Force | Out-Null

    # 「现在用的是哪套」和「方案下拉框里有哪些选项」是两个键：上面写的是前者，
    # 「鼠标属性 → 指针 → 方案」那个列表读的是 Control Panel\Cursors\Schemes
    # 子键（值名 = 方案名，值 = 17 条路径、逗号分隔、顺序固定为 $Roles 的顺序）。
    # 只写上面 17 个角色值的话，用户在方案列表里根本看不到本包，系统把方案冲掉
    # 之后也没法自己选回来。17 个角色齐了才写整条 —— 残缺的方案条目会让
    # Windows 把缺的那几个角色清成空，用户点一下反而把指针弄丢几个。
    $schemesPath = 'HKCU:\Control Panel\Cursors\Schemes'
    if ($set -eq $Roles.Count) {
        if (-not (Test-Path $schemesPath)) { New-Item -Path $schemesPath -Force | Out-Null }
        # 字符串用 ExpandString、分隔符是**纯逗号、不带空格** —— 本机 12 条系统内置方案
        # （HKLM\...\Control Panel\Cursors\Schemes）和已有的第三方方案条目全是这个写法。
        # 写成 ", " + String 系统虽然也能解析，但和别的鼠标皮肤不一致。
        New-ItemProperty -Path $schemesPath -Name $schemeName `
            -Value ($paths -join ',') -PropertyType ExpandString -Force | Out-Null
        # 摘掉本包**别的档位**留下的旧条目：程序里的守护会按当前 scale 把方案认回
        # 来，留着「大 (1.00×)」这种过期条目，用户点了也只会被立刻改回去，等于挖坑。
        # 只删名字能和我们自己的档名逐字对上的，用户另存的方案一律不动。
        foreach ($other in $TierName.Keys) {
            if ($other -eq $t) { continue }
            $stale = "明日方舟 水晶指针 $($TierName[$other])"
            Remove-ItemProperty -Path $schemesPath -Name $stale -ErrorAction SilentlyContinue
        }
    } else {
        Write-Warning "只找到 $set/$($Roles.Count) 个角色，跳过方案列表登记（残缺条目会被系统当成空指针）"
    }

    Apply-Immediate $dir $t

    Write-Host ''
    Write-Host "已应用档位：$($TierName[$t])" -ForegroundColor Green
    Write-Host "  方案名：$schemeName"
    Write-Host "  角色数：$set / $($Roles.Count)"
    Write-Host "  目录：  $dir"
    Write-Host ''
    Test-Conflict
}

if ($Status) { Show-Status; return }
if ($Restore) { Restore-Backup; return }

if (-not $Tier) {
    Show-Status
    Write-Host '可用档位：' -ForegroundColor Cyan
    Write-Host '  small   小   —— 视觉大小 0.50×，最贴近 Windows 默认指针的观感'
    Write-Host '  medium  中   —— 视觉大小 0.71×（1/√2），与游戏内「中」档完全一致'
    Write-Host '  p72     72px —— 视觉大小 0.75×，程序默认 scale 对应的那一档'
    Write-Host '  large   大   —— 视觉大小 1.00×，96px 原始分辨率，最清晰'
    Write-Host ''
    Write-Host '用法示例： .\install.ps1 -Tier p72'
    Write-Host '回滚：     .\install.ps1 -Restore'
    return
}

Install-Tier $Tier
