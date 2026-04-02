# run_all.ps1 — Run the full interpolation workflow and log all output.
# Windows equivalent of run_all.sh
#
# Usage (from Anaconda Prompt or PowerShell with conda initialised):
#   powershell -ExecutionPolicy Bypass -File run_all.ps1
#
# Or, if you are already in PowerShell:
#   Set-ExecutionPolicy -Scope Process Bypass
#   .\run_all.ps1

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

# Resolve OUT_DIR from config.py without importing the full module
$OutDir = conda run -n geoint python -c "import config; print(config.OUT_DIR)"
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

$Log = Join-Path $OutDir "console_output.log"

Write-Host "Output dir : $OutDir"
Write-Host "Log file   : $Log"
Write-Host ""

# Clear any previous log
Clear-Content -Path $Log -ErrorAction SilentlyContinue

function Write-Log {
    param([string]$Message)
    Write-Host $Message
    Add-Content -Path $Log -Value $Message
}

$Basin   = conda run -n geoint python -c "import config; print(config.BASIN)"
$Started = Get-Date -Format "ddd MMM dd HH:mm:ss yyyy"

Write-Log "======================================================================"
Write-Log " Formation depth interpolation workflow"
Write-Log " Started: $Started"
Write-Log " Basin:   $Basin"
Write-Log "======================================================================"
Write-Log ""

Write-Log "--- interpolate.py ---"
conda run -n geoint python interpolate.py 2>&1 | Tee-Object -Append -FilePath $Log
Write-Log ""

Write-Log "--- plot_maps.py ---"
conda run -n geoint python plot_maps.py 2>&1 | Tee-Object -Append -FilePath $Log
Write-Log ""

# # Uncomment the block below to also export a corner-point grid (GRDECL) for
# # reservoir simulation in Eclipse, OPM Flow, Petrel, tNavigator, etc.
# Write-Log "--- cpg_export.py ---"
# conda run -n geoint python cpg_export.py 2>&1 | Tee-Object -Append -FilePath $Log
# Write-Log ""

$Finished = Get-Date -Format "ddd MMM dd HH:mm:ss yyyy"
Write-Log "======================================================================"
Write-Log " Finished: $Finished"
Write-Log "======================================================================"
