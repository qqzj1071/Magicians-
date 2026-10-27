param(
    [string]$InstallRoot = (Join-Path $env:LOCALAPPDATA 'Magicians!'),
    [switch]$NoShortcut
)
$ErrorActionPreference = 'Stop'
$packageRoot = $PSScriptRoot
$clientSource = Join-Path $packageRoot 'client'
$runtimeSource = Join-Path $packageRoot 'runtimes'
if (!(Test-Path (Join-Path $clientSource 'project.godot'))) { throw 'Installer package is missing the client payload.' }
New-Item -ItemType Directory -Force -Path $InstallRoot | Out-Null
$clientTarget = Join-Path $InstallRoot 'client'
if (Test-Path $clientTarget) { Remove-Item -LiteralPath $clientTarget -Recurse -Force }
Copy-Item -LiteralPath $clientSource -Destination $clientTarget -Recurse -Force
Get-ChildItem -LiteralPath $clientTarget -Recurse -File | ForEach-Object { $_.IsReadOnly = $true }
if (Test-Path $runtimeSource) { Copy-Item -LiteralPath $runtimeSource -Destination $InstallRoot -Recurse -Force }
$launcher = Join-Path $InstallRoot 'Launch-Magicians.ps1'
Copy-Item -LiteralPath (Join-Path $packageRoot 'Launch-Magicians.ps1') -Destination $launcher -Force
$catalogue = Join-Path $packageRoot 'Magicians-v1.0-card-catalogue.docx'
if (Test-Path $catalogue) { Copy-Item -LiteralPath $catalogue -Destination (Join-Path $InstallRoot 'Magicians-v1.0-card-catalogue.docx') -Force }
if (!$NoShortcut) {
$desktop = [Environment]::GetFolderPath('Desktop')
$shortcutPath = Join-Path $desktop 'Magicians! Single Player.lnk'
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = [IO.Path]::Combine([Environment]::GetEnvironmentVariable('SystemRoot'), 'System32\\WindowsPowerShell\\v1.0\\powershell.exe')
$shortcut.Arguments = '-NoProfile -ExecutionPolicy Bypass -File ' + [char]34 + $launcher + [char]34
$shortcut.WorkingDirectory = $InstallRoot
$shortcut.Description = 'Launch Magicians single player'
$shortcut.Save()
}
Write-Output ('MAGICIANS_INSTALLED ' + $InstallRoot)


