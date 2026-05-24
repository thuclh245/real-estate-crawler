param(
    [Parameter(Mandatory = $true)]
    [string]$RunId,
    [string[]]$Config = @(),
    [switch]$RequireSpark,
    [string]$OutputDir = "data/logs/preflight"
)

$ErrorActionPreference = "Stop"
$ProjectDir = if ($env:PROJECT_DIR) { $env:PROJECT_DIR } else { (Resolve-Path (Join-Path $PSScriptRoot "..")).Path }
Set-Location $ProjectDir
$env:PYTHONPATH = "src"

$argsList = @("-m", "src.validation.preflight", "--run-id", $RunId)
foreach ($configPath in $Config) {
    $argsList += @("--config", $configPath)
}
if ($RequireSpark) {
    $argsList += "--require-spark"
}
$argsList += @("--output-dir", $OutputDir)

if (Test-Path ".\.venv\Scripts\python.exe") {
    & .\.venv\Scripts\python.exe @argsList
} else {
    python @argsList
}
