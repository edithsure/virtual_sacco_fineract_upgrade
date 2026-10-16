$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectDir = Join-Path $root 'sacco_fineract_upgrade'
$venvDir = Join-Path $root '.venv'

if (Test-Path $venvDir) {
    . (Join-Path $venvDir 'Scripts\Activate.ps1')
}

Set-Location $projectDir
python app.py
