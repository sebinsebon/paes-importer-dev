param(
    [string]$JsonInputPath,
    [string]$JsonOutputPath,
    [string]$WorkspaceRoot,
    [Parameter(ValueFromRemainingArguments = $true)][string[]]$ImporterArgs
)
$ErrorActionPreference = 'Stop'
if (-not $WorkspaceRoot) { $WorkspaceRoot = $PSScriptRoot }
if ($JsonInputPath -or $JsonOutputPath) {
    if (-not $JsonInputPath -or -not $JsonOutputPath -or $ImporterArgs.Count -gt 0) { throw 'Supply both JSON paths and no importer arguments.' }
    & (Join-Path $PSScriptRoot 'scripts/write_json.ps1') -InputPath $JsonInputPath -OutputPath $JsonOutputPath -WorkspaceRoot $WorkspaceRoot
    exit 0
}
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:PYTHONUTF8 = '1'
$localPython = Join-Path $PSScriptRoot '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $localPython)) { throw 'Run python -B scripts/setup.py first, or use a Python with requirements.txt installed.' }
& $localPython -B (Join-Path $PSScriptRoot 'scripts/importer.py') @ImporterArgs
exit $LASTEXITCODE
