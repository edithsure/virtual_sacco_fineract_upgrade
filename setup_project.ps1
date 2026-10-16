$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectDir = Join-Path $root 'sacco_fineract_upgrade'
$venvDir = Join-Path $root '.venv'

if (-not (Test-Path $venvDir)) {
    Write-Host 'Creating virtual environment...'
    py -m venv $venvDir
}

Write-Host 'Activating virtual environment...'
. (Join-Path $venvDir 'Scripts\Activate.ps1')

Write-Host 'Upgrading pip and installing dependencies...'
python -m pip install --upgrade pip
pip install -r (Join-Path $projectDir 'requirements.txt')

if (-not (Test-Path (Join-Path $projectDir '.env'))) {
    Copy-Item (Join-Path $projectDir '.env.example') (Join-Path $projectDir '.env')
    Write-Host 'Created .env from .env.example'
}

Write-Host 'Setup complete.'
Write-Host "Run the app with: cd '$projectDir'; python app.py"
