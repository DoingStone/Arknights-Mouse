$beforeJson = Get-Content "$env:TEMP\cursor_before.json" -Raw -Encoding UTF8
$now = Get-ItemProperty 'HKCU:\Control Panel\Cursors'
$b = $beforeJson | ConvertFrom-Json

Write-Host "=== 逐键比对（双向）==="
$bad = 0
foreach ($prop in $b.PSObject.Properties) {
    $bv = "$($prop.Value)"
    $av = "$($now.PSObject.Properties[$prop.Name].Value)"
    if ($bv -ne $av) { Write-Host ("  [X] {0}: '{1}' -> '{2}'" -f $prop.Name, $bv, $av); $bad++ }
}
foreach ($prop in $now.PSObject.Properties) {
    if (-not $b.PSObject.Properties[$prop.Name]) { Write-Host ("  [+] 安装前没有的键: {0} = {1}" -f $prop.Name, $prop.Value); $bad++ }
}
Write-Host ""
Write-Host ("键数：安装前 {0}，现在 {1}" -f @($b.PSObject.Properties).Count, @($now.PSObject.Properties).Count)
if ($bad -eq 0) { Write-Host "[OK] 所有键值逐一相同 —— 回滚完全无损" -ForegroundColor Green }
else { Write-Host "[!] $bad 处差异" -ForegroundColor Yellow }
