param([string]$Godot = 'D:\Magicians!\_tools\Godot\4.7.2\Godot_v4.7.2-stable_mono_win64\Godot_v4.7.2-stable_mono_win64_console.exe')
$ErrorActionPreference = 'Stop'
$projectPath = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$workspacePath = Split-Path -Parent $projectPath
$runtimePath = Join-Path $workspacePath 'runtime'
New-Item -ItemType Directory -Force -Path $runtimePath | Out-Null
$env:DOTNET_CLI_HOME = Join-Path $workspacePath '.dotnet-home'
$env:NUGET_PACKAGES = Join-Path $workspacePath '.nuget\packages'
$env:APPDATA = Join-Path $env:DOTNET_CLI_HOME 'AppData'
New-Item -ItemType Directory -Force -Path $env:APPDATA | Out-Null
& dotnet build (Join-Path $projectPath 'Magicians!.csproj') --no-restore
if ($LASTEXITCODE -ne 0) { throw 'Client build failed.' }
& $Godot --headless --log-file (Join-Path $runtimePath 'draft-quick-audit.log') --path $projectPath 'res://Scenes/Tests/DraftAuditRunner.tscn'
if ($LASTEXITCODE -ne 0) { throw 'Draft allocation or display settings audit failed.' }
& $Godot --headless --log-file (Join-Path $runtimePath 'trained-ai-regression.log') --path $projectPath 'res://Scenes/Tests/HeadlessScenarioRunner.tscn'
if ($LASTEXITCODE -ne 0) { throw 'Client fixed-seed regression failed.' }
& $Godot --headless --log-file (Join-Path $runtimePath 'ai-async-flow.log') --path $projectPath 'res://Scenes/Tests/AiAsyncFlowRunner.tscn'
if ($LASTEXITCODE -ne 0) { throw 'Asynchronous AI client flow failed.' }
& $Godot --headless --log-file (Join-Path $runtimePath 'combat-client-flow.log') --path $projectPath 'res://Scenes/Tests/CombatClientFlowRunner.tscn'
if ($LASTEXITCODE -ne 0) { throw 'Combat visibility or round delegation flow failed.' }
& $Godot --headless --log-file (Join-Path $runtimePath 'draft-ui-revision.log') --path $projectPath 'res://Scenes/Tests/DraftUiRevisionRunner.tscn'
if ($LASTEXITCODE -ne 0) { throw 'Draft UI, route cap or post-match review failed.' }
& $Godot --headless --log-file (Join-Path $runtimePath 'main-menu-flow.log') --path $projectPath 'res://Scenes/Tests/MainMenuFlowRunner.tscn'
if ($LASTEXITCODE -ne 0) { throw 'Main menu or spectator entry flow failed.' }
& $Godot --headless --log-file (Join-Path $runtimePath 'spectator-flow.log') --path $projectPath 'res://Scenes/Tests/SpectatorFlowRunner.tscn'
if ($LASTEXITCODE -ne 0) { throw 'AI spectator-to-champion flow failed.' }
Write-Output (Join-Path $runtimePath 'regressions\trained-ai\summary.json')
