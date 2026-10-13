# -*- coding: utf-8 -*-
<#
    打「免安装发布包」：把别人下载下来就能直接跑的东西装进一个 zip。

    里面放什么：
        明日方舟鼠标.exe      主程序（已内含 art.bin / fx.bin）
        启动.bat              双击即开
        快速开始.txt          给不看 markdown 的人
        说明.md               完整产品说明
        手感效果说明.md        三项效果的实现与验收记录
        设置.json             干净默认值（不是开发机的当前设置）
        指针\               水晶指针的 .cur/.ani 与 install.ps1（GUI「安装指针」按钮要用）
        LICENSE               MIT；指针美术的版权声明另见 README.md

    不放什么（这些留在 GitHub 仓库里，不属于用户包）：
        源码\ 构建\ 提取工具\ 测试\ _UI优化审计\ 各种日志与备份

    用法：
        pwsh -File 构建\make_release.ps1
        pwsh -File 构建\make_release.ps1 -Version 1.1
#>
[CmdletBinding()]
param(
    [string]$Version = '1.0',
    [string]$OutDir  = '发布'
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot          # 工程根
Set-Location $root
if ($root -ne 'E:\Qianmory\Desktop\Mouse') { Write-Host "  注意：工程根是 $root" }

$AppName = '明日方舟鼠标'
$stage   = Join-Path $root (Join-Path '_release' $AppName)
$zipName = "${AppName}_v${Version}_portable.zip"
$zipPath = Join-Path $root (Join-Path $OutDir $zipName)

Write-Host "=== 1) 准备暂存目录 ==="
if (Test-Path -LiteralPath $stage) { Remove-Item -LiteralPath $stage -Recurse -Force }
New-Item -ItemType Directory -Path $stage -Force | Out-Null
Write-Host "  $stage"

Write-Host "=== 2) 拷主程序与文档 ==="
foreach ($f in @("$AppName.exe", '启动.bat', '说明.md', '手感效果说明.md', 'LICENSE')) {
    if (-not (Test-Path -LiteralPath $f)) { throw "缺少必需文件：$f" }
    Copy-Item -LiteralPath $f -Destination $stage
    Write-Host ("  {0,-24} {1,10:N0} B" -f $f, (Get-Item -LiteralPath $f).Length)
}

Write-Host "=== 3) 拷指针 ==="
Copy-Item -LiteralPath '指针' -Destination $stage -Recurse
$packMB = (Get-ChildItem (Join-Path $stage '指针') -Recurse -File | Measure-Object Length -Sum).Sum / 1MB
Write-Host ("  指针\  {0:N1} MB" -f $packMB)

Write-Host "=== 4) 写干净的 设置.json（用 store.DEFAULTS，不带开发机的当前值）==="
$py = @'
import json, sys, os
root = sys.argv[1]
sys.path.insert(0, os.path.join(root, '源码'))
from arkmouse import store
out = os.path.join(root, '_release', '明日方舟鼠标', '设置.json')
with open(out, 'w', encoding='utf-8') as f:
    json.dump(store.DEFAULTS, f, ensure_ascii=False, indent=2)
print('  ' + json.dumps(store.DEFAULTS, ensure_ascii=False))
'@
$py | Out-File -FilePath (Join-Path $env:TEMP '_mkcfg.py') -Encoding UTF8
python (Join-Path $env:TEMP '_mkcfg.py') $root

Write-Host "=== 5) 写 快速开始.txt ==="
$quick = @"
明日方舟 · 水晶鼠标指针  v$Version
================================================

【怎么用】

  1. 双击「启动.bat」（或直接双击「明日方舟鼠标.exe」）
  2. 在「指针大小」页签里选一个尺寸，点「应用」
  3. 想让它开机自动生效，把「开机自动启动（含守护）」勾上

  指针太小/太大？点「读当前桌面尺寸」看实际情况，再调滑杆。
  想变回去？点「恢复原始光标」，一切还原，不留痕迹。

【三项手感效果】

  点击挤压    按下鼠标时指针轻轻挤一下（PRTS 原帧美术）
  拖动爪子    拖窗口时指针变成爪子，松手后收回
  待机动画    鼠标放着不动 5 秒，指针会自己动起来

  三个都默认开着，在「指针大小」页签的「效果与启动」里可以单独关。
  它们需要一个常驻进程来驱动 —— 关掉程序（又不跑守护）效果就停。

【这个软件不做什么】

  · 不读、不修改任何游戏目录（全程只读）
  · 不联网络、不上传任何东西
  · 所有改动只影响当前用户（写 HKCU，不需要管理员）
  · 一键可还原

【更多】

  说明.md          完整功能说明
  手感效果说明.md   三项效果的技术细节与验收记录
  指针\README.md  指针的安装/切换/卸载（命令行方式）

【卸载】

  1. 程序里点「恢复原始光标」
  2. 程序里关掉「开机自动启动」
  3. 删掉这个文件夹，完事
"@
$quick | Out-File -FilePath (Join-Path $stage '快速开始.txt') -Encoding UTF8

Write-Host "=== 6) 打包 ==="
if (-not (Test-Path -LiteralPath $OutDir)) { New-Item -ItemType Directory -Path $OutDir -Force | Out-Null }
if (Test-Path -LiteralPath $zipPath) { Remove-Item -LiteralPath $zipPath -Force }
Add-Type -AssemblyName System.IO.Compression.FileSystem
[System.IO.Compression.ZipFile]::CreateFromDirectory(
    $stage, $zipPath, [System.IO.Compression.CompressionLevel]::Fastest, $true)

$zi = Get-Item -LiteralPath $zipPath
$hash = (Get-FileHash -LiteralPath $zipPath -Algorithm SHA256).Hash
Write-Host ''
Write-Host ("  产物 : {0}" -f $zipPath)
Write-Host ("  体积 : {0:N1} MB" -f ($zi.Length/1MB))
Write-Host ("  SHA256: {0}" -f $hash)
Write-Host ("  内含文件数 : {0}" -f (Get-ChildItem -LiteralPath $stage -Recurse -File).Count)

# 上传到 GitHub Release 时必须用 ASCII 附件名：
# GitHub 会把附件名里的非 ASCII 字符整段抹掉，用中文名传上去会变成 "_v1.0_portable.zip"。
$AssetName = 'Arknights-Mouse_v{0}_portable.zip' -f $Version
Write-Host ''
Write-Host '  ── 传到 GitHub Releases 用这个附件名 ──'
Write-Host ("  附件名 : {0}" -f $AssetName)
Write-Host '  （本地文件名是中文，包内容一模一样；只有 Release 附件名必须是 ASCII）'
