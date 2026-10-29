param(
    [string]$ClientDirectory = (Join-Path (Split-Path (Split-Path $PSScriptRoot -Parent) -Parent) '_installers\Magicians-v1.1-Portable-20261028')
)
$ErrorActionPreference = 'Stop'
$desktop = [Environment]::GetFolderPath('Desktop')
$shortcutPath = Join-Path $desktop 'Magicians! 单人模式.lnk'
$client = Join-Path $ClientDirectory 'Magicians.exe'
if (!(Test-Path -LiteralPath $client -PathType Leaf) -or !(Test-Path -LiteralPath (Join-Path $ClientDirectory 'integrity.json'))) {
    throw 'Please select a complete extracted portable release with -ClientDirectory.'
}
$ClientDirectory = (Resolve-Path -LiteralPath $ClientDirectory).Path
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = Join-Path $ClientDirectory 'Magicians.exe'
$shortcut.Arguments = ''
$shortcut.WorkingDirectory = $ClientDirectory
$shortcut.IconLocation = $shortcut.TargetPath + ',0'
$shortcut.Description = '启动 Magicians! v1.1 单人模式（冻结卡牌 · 基础飞弹间隔50）'
$shortcut.Save()
Write-Output $shortcutPath
