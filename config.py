"""
config.py — All user-facing parameters for the formation interpolation workflow.
Edit this file to change inputs, grid resolution, kriging settings, and CPG export options.
"""

import os

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
WELL_CSV   = os.path.join(BASE_DIR, "well_data.csv")
SHAPEFILE  = os.path.join(BASE_DIR, "california", "california.shp")

# Output directory (created automatically if it doesn't exist)
OUT_DIR    = os.path.join(BASE_DIR, "output")

# ── Coordinate reference systems ──────────────────────────────────────────────
# Input CRS for well CSV lat/lon and the shapefile
CRS_INPUT  = "EPSG:4269"   # NAD83 geographic
# Working / output CRS — metric, equal-area, appropriate for California
CRS_WORK   = "EPSG:3310"   # NAD83 / California Albers (metres)

# ── Interpolation grid ────────────────────────────────────────────────────────
# Cell size of the interpolation grid in metres (EPSG:3310 units).
# Smaller = finer resolution but slower kriging. 5000 m is a good starting point.
GRID_RESOLUTION_M = 5000   # metres

# ── Kriging parameters ────────────────────────────────────────────────────────
# Variogram model: 'spherical' | 'gaussian' | 'exponential' | 'linear' | 'power'
VARIOGRAM_MODEL   = "spherical"

# Drift terms for Universal Kriging — linear trend captures regional structural dip
# Options: ['regional_linear'] | ['point_log'] | []  (empty = Ordinary Kriging)
DRIFT_TERMS       = ["regional_linear"]

# Number of lag bins for experimental variogram
VARIOGRAM_NLAGS   = 8

# ── Maps ──────────────────────────────────────────────────────────────────────
# DPI for saved PNG figures
MAP_DPI           = 150

# Contour interval for depth maps (metres)
CONTOUR_INTERVAL_DEPTH     = 50    # metres
CONTOUR_INTERVAL_THICKNESS = 10    # metres

# ── Corner-point grid (GRDECL / Eclipse) ─────────────────────────────────────
# Cell dimensions in the horizontal plane (metres)
CPG_DX            = 5000   # metres
CPG_DY            = 5000   # metres

# Number of layers in the vertical / Z direction
CPG_NZ            = 10

# Output GRDECL file name
CPG_FILENAME      = "grid.grdecl"
