$ErrorActionPreference = 'Stop'
$installRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$clientRoot = Join-Path $installRoot 'client'
$godot = Join-Path $installRoot 'runtimes\Godot\Godot_v4.7.2-stable_mono_win64.exe'
$python = Join-Path $clientRoot 'tools\client_ai\python-runtime\python.exe'
$godotUrl = 'https://github.com/godotengine/godot/releases/download/4.7.2-stable/Godot_v4.7.2-stable_mono_win64.zip'
$pythonUrl = 'https://www.python.org/ftp/python/3.12.10/python-3.12.10-embed-amd64.zip'
function Download-Runtime([string]$url, [string]$destination, [string]$extractTo) {
    $archive = Join-Path $env:TEMP ([IO.Path]::GetRandomFileName() + '.zip')
    Invoke-WebRequest -UseBasicParsing -Uri $url -OutFile $archive
    New-Item -ItemType Directory -Force -Path $extractTo | Out-Null
    Expand-Archive -LiteralPath $archive -DestinationPath $extractTo -Force
    Remove-Item -LiteralPath $archive -Force
}
if (!(Test-Path $godot)) {
    $godotDir = Join-Path $installRoot 'runtimes\Godot'
    Download-Runtime $godotUrl $godot $godotDir
    $nested = Get-ChildItem -LiteralPath $godotDir -Filter 'Godot_v4.7.2-stable_mono_win64.exe' -Recurse | Select-Object -First 1
    if ($nested) { Copy-Item $nested.FullName $godot -Force }
}
if (!(Test-Path $python)) {
    if ($env:MAGICIANS_PYTHON -and (Test-Path $env:MAGICIANS_PYTHON)) { $python = $env:MAGICIANS_PYTHON }
}
if (!(Test-Path $python)) {
    $pythonDir = Split-Path -Parent $python
    Download-Runtime $pythonUrl $python $pythonDir
}
if (!(Test-Path $godot)) { throw 'Godot 运行时不可用。' }
if (!(Test-Path $python)) { throw 'Python 运行时不可用。' }
$env:MAGICIANS_PYTHON = $python
$env:PYTHONDONTWRITEBYTECODE = '1'
$sessionRoot = Join-Path $env:TEMP ('Magicians-session-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Force -Path $sessionRoot | Out-Null
Copy-Item -LiteralPath $clientRoot -Destination $sessionRoot -Recurse -Force
$sessionClient = Join-Path $sessionRoot 'client'
Set-ItemProperty -LiteralPath $sessionClient -Name IsReadOnly -Value $true -ErrorAction SilentlyContinue
& $godot --path $sessionClient --log-file (Join-Path $installRoot 'client.log')
$exitCode = $LASTEXITCODE
Remove-Item -LiteralPath $sessionRoot -Recurse -Force -ErrorAction SilentlyContinue
exit $exitCode

