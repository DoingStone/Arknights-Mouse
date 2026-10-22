# -*- coding: utf-8 -*-
<#
    打「免安装发布包」：把别人下载下来就能直接跑的东西装进一个 zip。

    这条脚本按 v3 的英文目录布局（src / cursors / build / docs）走，
    旧版里那些中文目录（源码、指针、构建、提取工具）已经不存在了。

    里面放什么：
        ArknightsMouse.exe    主程序（已内含 art.bin / fx.bin）
        start.bat             双击即开
        QUICKSTART.txt        给不看 markdown 的人（UTF-8 with BOM）
        README.md             中文完整说明
        README_zh.md          英文完整说明（文件名是历史遗留，内容语言与名字相反）
        LICENSE               MIT；指针美术的版权声明另见 README.md
        cursors\              水晶指针的 .cur/.ani（4 档 × 17 角色）与 install.ps1

    为什么不放源码/工具：
        源码和提取工具留在 GitHub 仓库里。发布包只管「拿来就能用」。

    exe 里到底带没带指针？
        没带 —— 只内嵌 art.bin / fx.bin。所以发布包必须把 cursors\ 一起给，
        否则用户点「安装指针」时要现场生成（约 3 秒，能跑但多等一步）。
        两者都行，这里给现成的。

    用法：
        pwsh -File build\make_release.ps1
        pwsh -File build\make_release.ps1 -Version 1.1
#>
[CmdletBinding()]
param(
    [string]$Version = '1.0',
    [string]$OutDir = 'release'
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot          # 工程根
Set-Location $root

$AppName = 'ArknightsMouse'
$stage = Join-Path $root (Join-Path '_release' $AppName)
$zipName = "${AppName}_v${Version}_portable.zip"
$zipPath = Join-Path $root (Join-Path $OutDir $zipName)

Write-Host '=== 1) 准备暂存目录 ==='
if (Test-Path -LiteralPath $stage) { Remove-Item -LiteralPath $stage -Recurse -Force }
New-Item -ItemType Directory -Path $stage -Force | Out-Null
Write-Host "  $stage"

Write-Host '=== 2) 拷主程序与文档 ==='
$files = @("$AppName.exe", 'start.bat', 'README.md', 'README_zh.md', 'LICENSE')
foreach ($f in $files) {
    if (-not (Test-Path -LiteralPath $f)) { throw "缺少必需文件：$f" }
    Copy-Item -LiteralPath $f -Destination $stage
    Write-Host ("  {0,-22} {1,12:N0} B" -f $f, (Get-Item -LiteralPath $f).Length)
}

Write-Host '=== 3) 拷指针 ==='
# 只拷真正要装的东西：cursors\cursors\<档>\ + install.ps1 + install README。
# extracted\（PNG 预览）和 raw\（游戏原始贴图）属于素材归档，不进用户包。
$packSrc = Join-Path $root 'cursors\cursors'
if (-not (Test-Path -LiteralPath $packSrc)) { throw "缺少指针文件：$packSrc" }
$packDst = Join-Path $stage 'cursors\cursors'
New-Item -ItemType Directory -Path $packDst -Force | Out-Null
# 注意：Copy-Item -Recurse 连**源目录本身**也一起复制，直接拷会得到
# cursors\cursors\cursors\<档>\ 这种多一层的路径。所以逐个拷子目录。
foreach ($d in (Get-ChildItem -LiteralPath $packSrc -Directory)) {
    Copy-Item -LiteralPath $d.FullName -Destination $packDst -Recurse
}
foreach ($f in @('install.ps1', 'README.md')) {
    $p = Join-Path $root (Join-Path 'cursors' $f)
    if (Test-Path -LiteralPath $p) { Copy-Item -LiteralPath $p -Destination (Join-Path $stage 'cursors') }
}
$packMB = (Get-ChildItem (Join-Path $stage 'cursors') -Recurse -File |
    Measure-Object Length -Sum).Sum / 1MB
$tiers = (Get-ChildItem $packDst -Directory | Measure-Object).Count
$curCount = (Get-ChildItem $packDst -Recurse -File | Measure-Object).Count
Write-Host ("  cursors\  {0} 档 / {1} 个文件 / {2:N1} MB" -f $tiers, $curCount, $packMB)

Write-Host '=== 4) 写干净的 settings.json（用 store.DEFAULTS，不带开发机的当前值）==='
$py = @'
import json, os, sys
root = sys.argv[1]
sys.path.insert(0, os.path.join(root, 'src', 'arkmouse'))
import store
out = os.path.join(root, '_release', 'ArknightsMouse', 'settings.json')
with open(out, 'w', encoding='utf-8') as f:
    json.dump(store.DEFAULTS, f, ensure_ascii=False, indent=2)
print('  ' + json.dumps(store.DEFAULTS, ensure_ascii=False))
'@
$tmpPy = Join-Path $env:TEMP '_mkcfg_release.py'
$py | Out-File -FilePath $tmpPy -Encoding UTF8
python $tmpPy $root
Remove-Item -LiteralPath $tmpPy -Force -ErrorAction SilentlyContinue

Write-Host '=== 5) 写 QUICKSTART.txt ==='
$quick = @"
明日方舟 · 水晶鼠标指针  v$Version
================================================

【怎么用】

  1. 双击 start.bat（或直接双击 ArknightsMouse.exe）
  2. 在「指针大小」页签里选一个尺寸，点「应用」
  3. 想让它开机自动生效，把「开机自动启动（含守护）」勾上

  指针太小/太大？点「读当前桌面尺寸」看实际情况，再调滑杆。
  想变回去？点「恢复原始光标」，一切还原，不留痕迹。

【想让它出现在「鼠标属性 → 指针」的方案列表里】

  点「安装指针（文件式）」→ 选一档（推荐 72px）。
  装完打开 控制面板 → 鼠标 → 指针，「方案」下拉框里就有
  「明日方舟 水晶指针 72px (0.75×)」，和别的鼠标皮肤一样能选中应用。

  注意：Windows 用「方案」加载光标时一律渲染成 32px（系统限制，
  任何皮肤都一样）。想要真正 72px 的大指针，用「指针大小」页签的
  「应用」——那条路是程序直接按像素造光标。

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

  README.md           中文完整说明
  README_zh.md        英文完整说明
  cursors\README.md   指针的安装/切换/卸载（命令行方式）

【卸载】

  1. 程序里点「恢复原始光标」
  2. 程序里关掉「开机自动启动」
  3. 删掉这个文件夹，完事
"@
$quickPath = Join-Path $stage 'QUICKSTART.txt'
[System.IO.File]::WriteAllText($quickPath, $quick,
    (New-Object System.Text.UTF8Encoding($true)))

Write-Host '=== 6) 打包 ==='
if (-not (Test-Path -LiteralPath $OutDir)) {
    New-Item -ItemType Directory -Path $OutDir -Force | Out-Null
}
if (Test-Path -LiteralPath $zipPath) { Remove-Item -LiteralPath $zipPath -Force }
Add-Type -AssemblyName System.IO.Compression.FileSystem
[System.IO.Compression.ZipFile]::CreateFromDirectory(
    $stage, $zipPath, [System.IO.Compression.CompressionLevel]::Fastest, $true)

$zi = Get-Item -LiteralPath $zipPath
$hash = (Get-FileHash -LiteralPath $zipPath -Algorithm SHA256).Hash
Write-Host ''
Write-Host ("  产物 : {0}" -f $zipPath)
Write-Host ("  体积 : {0:N1} MB" -f ($zi.Length / 1MB))
Write-Host ("  SHA256: {0}" -f $hash)
Write-Host ("  内含文件数 : {0}" -f (Get-ChildItem -LiteralPath $stage -Recurse -File).Count)

# 上传到 GitHub Release 时必须用 ASCII 附件名：
# GitHub 会把附件名里的非 ASCII 字符整段抹掉。本地文件名这次已经是 ASCII，
# 这里只是把 Release 上该用的名字再明确一遍。
$AssetName = 'Arknights-Mouse_v{0}_portable.zip' -f $Version
Write-Host ''
Write-Host '  ── 传到 GitHub Releases 用这个附件名 ──'
Write-Host ("  附件名 : {0}" -f $AssetName)
