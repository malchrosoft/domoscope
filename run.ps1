param(
    [Parameter(Position = 0)]
    [ValidateSet("scan", "serve", "report", "devices", "init")]
    [string]$Command = "serve",

    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Rest
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path ".venv")) {
    uv sync --extra tuya
}

uv run domoscope $Command @Rest
