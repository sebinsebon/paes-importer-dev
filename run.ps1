param([Parameter(ValueFromRemainingArguments = $true)][string[]]$ImporterArgs)
$ErrorActionPreference = 'Stop'
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:PYTHONUTF8 = '1'
$localPython = Join-Path $PSScriptRoot '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $localPython)) { throw 'Run python -B scripts/setup.py first, or use a Python with requirements.txt installed.' }
& $localPython -B (Join-Path $PSScriptRoot 'scripts/importer.py') @ImporterArgs
exit $LASTEXITCODE
