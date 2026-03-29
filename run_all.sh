#!/usr/bin/env bash
# run_all.sh — Run the full interpolation workflow and log all output.
# Usage: bash run_all.sh
#
# Reads OUT_DIR from config.py so the log always lands in the correct
# basin-specific output folder, matching the BASIN setting in config.py.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Resolve OUT_DIR from config.py without importing the full module
OUT_DIR=$(conda run -n geoint python -c "import config; print(config.OUT_DIR)")
mkdir -p "$OUT_DIR"

LOG="$OUT_DIR/console_output.log"

echo "Output dir : $OUT_DIR"
echo "Log file   : $LOG"
echo ""

{
    echo "======================================================================"
    echo " Formation depth interpolation workflow"
    echo " Started: $(date)"
    echo " Basin:   $(conda run -n geoint python -c 'import config; print(config.BASIN)')"
    echo "======================================================================"
    echo ""

    echo "--- interpolate.py ---"
    conda run -n geoint python interpolate.py
    echo ""

    echo "--- plot_maps.py ---"
    conda run -n geoint python plot_maps.py
    echo ""

    # Uncomment the block below to also export a corner-point grid (GRDECL) for
    # reservoir simulation in Eclipse, OPM Flow, Petrel, tNavigator, etc.
    # echo "--- cpg_export.py ---"
    # conda run -n geoint python cpg_export.py
    # echo ""

    echo "======================================================================"
    echo " Finished: $(date)"
    echo "======================================================================"
} 2>&1 | tee "$LOG"
