$p = 'G:\ArknightsCursorExtract\CrystalCursorPack\install.ps1'
$errs = $null
[void][System.Management.Automation.Language.Parser]::ParseFile($p, [ref]$null, [ref]$errs)
if ($errs) { $errs | ForEach-Object { "PARSE: " + $_.Message } } else { "parse OK (PowerShell 5.1)" }
