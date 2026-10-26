$ErrorActionPreference = 'Stop'
$desktop = [Environment]::GetFolderPath('Desktop')
$shortcutPath = Join-Path $desktop 'Magicians! 单人模式.lnk'
$godot = 'D:\Magicians!\_tools\Godot\4.7.2\Godot_v4.7.2-stable_mono_win64\Godot_v4.7.2-stable_mono_win64.exe'
$project = 'D:\Magicians!\Magicians!'
$logDirectory = 'D:\Magicians!\runtime'
New-Item -ItemType Directory -Force -Path $logDirectory | Out-Null
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $godot
$shortcut.Arguments = '--path "' + $project + '" --log-file "' + (Join-Path $logDirectory 'client.log') + '"'
$shortcut.WorkingDirectory = $project
$shortcut.Description = '启动 Magicians! 单人模式'
$shortcut.Save()
Write-Output $shortcutPath
