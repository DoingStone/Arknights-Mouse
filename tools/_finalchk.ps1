$before = (Get-Content "$env:TEMP\cursor_before.json" -Raw -Encoding UTF8) | ConvertFrom-Json
$now = Get-ItemProperty 'HKCU:\Control Panel\Cursors'
$bad = 0; $n = 0
foreach ($prop in $before.PSObject.Properties) {
    if ($prop.Name -like 'PS*') { continue }     # 跳过 PowerShell 元数据属性
    $n++
    if ("$($prop.Value)" -ne "$($now.PSObject.Properties[$prop.Name].Value)") {
        Write-Host ("  [X] {0}: '{1}' -> '{2}'" -f $prop.Name, $prop.Value, $now.PSObject.Properties[$prop.Name].Value); $bad++
    }
}
Write-Host ""
Write-Host "比对真实注册表值：$n 项"
if ($bad -eq 0) { Write-Host "[验收通过] 全部逐键一致，回滚无损" -ForegroundColor Green }
else { Write-Host "[失败] $bad 处不一致" -ForegroundColor Red }
