$ErrorActionPreference = 'Continue'

Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public class CurApply {
  [DllImport("user32.dll", CharSet=CharSet.Unicode, SetLastError=true)]
  public static extern IntPtr LoadCursorFromFileW(string path);
  [DllImport("user32.dll", SetLastError=true)]
  public static extern bool SetSystemCursor(IntPtr hcur, uint id);
  [DllImport("user32.dll", SetLastError=true)]
  public static extern bool SystemParametersInfo(uint a, uint b, IntPtr c, uint d);
}
"@

$dir = 'G:\ArknightsCursorExtract\CrystalCursorPack\cursors\large'

# OCR id -> 角色名（严格按 WinUser.h 的 OCR_* 常量）
$map = @(
  @(32512, 'Arrow'),      @(32513, 'IBeam'),   @(32514, 'Wait'),
  @(32515, 'Crosshair'),  @(32516, 'UpArrow'), @(32642, 'SizeNWSE'),
  @(32643, 'SizeNESW'),   @(32644, 'SizeWE'),  @(32645, 'SizeNS'),
  @(32646, 'SizeAll'),    @(32648, 'No'),      @(32649, 'Hand'),
  @(32650, 'AppStarting'),@(32651, 'Help'),    @(32671, 'Pin'),
  @(32672, 'Person')
)

$ok = 0
$bad = @()
foreach ($pair in $map) {
  $id = [uint32]$pair[0]
  $role = [string]$pair[1]
  $f = Get-ChildItem -LiteralPath $dir -Filter ('*_' + $role + '_large.*') | Select-Object -First 1
  if (-not $f) { $bad += "$role 缺文件"; continue }

  $h = [CurApply]::LoadCursorFromFileW($f.FullName)
  if ($h -eq [IntPtr]::Zero) {
    $bad += ("$role LoadCursor 失败 err=" + [Runtime.InteropServices.Marshal]::GetLastWin32Error())
    continue
  }
  # SetSystemCursor 成功后接管句柄所有权，不可再 DestroyCursor
  if ([CurApply]::SetSystemCursor($h, $id)) {
    $ok++
  } else {
    $bad += ("$role SetSystemCursor 失败 err=" + [Runtime.InteropServices.Marshal]::GetLastWin32Error())
  }
}

Write-Host ("立即生效的 OCR 角色: {0} / {1}" -f $ok, $map.Count)
if ($bad.Count -gt 0) { Write-Host ("失败: " + ($bad -join '; ')) } else { Write-Host "全部成功" }

# WM_SETTINGCHANGE 广播，让所有窗口刷新
[void][CurApply]::SystemParametersInfo(0x0057, 0, [IntPtr]::Zero, 0x01 -bor 0x02)
Write-Host "已广播刷新"
