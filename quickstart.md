# Quickstart Guide

This guide walks you through running the workflow end-to-end on the included California dataset. For full documentation see [README.md](README.md).

## Prerequisites

- Python 3.10 or later
- conda (Miniconda or Anaconda)
- Git (to clone the repository)

## Step 1 — Clone and enter the repository

```bash
git clone https://github.com/<your-username>/formation-depth-interpolation.git
cd formation-depth-interpolation
```

## Step 2 — Create the conda environment

```bash
conda create -n geoint python=3.11
conda activate geoint
conda install -c conda-forge numpy pandas geopandas shapely scipy matplotlib pykrige
```

> First-time install may take 2–5 minutes while conda resolves the environment.

## Step 3 — Inspect the sample data (optional)

Open `well_data.csv` in any text editor or spreadsheet application to see the 24 sample wells spread across California. Open `config.py` to review the default settings — no changes are needed to run the demo.

## Step 4 — Run the interpolation

```bash
python interpolate.py
```

Expected console output:
```
Loading well data …
  24 wells reprojected to EPSG:3310
  Easting  range: -271504 – 158001 m
  Northing range: -402038 – 205001 m
Loading shapefile …
  Region bounds (m): E -271504–158001  N -402038–205001
  Grid: 87 × 122 = 10614 cells at 5000 m resolution
Computing shapefile mask …
  5423 / 10614 grid points are inside the region (51.1 %)
Kriging depth_top …
Kriging thickness …
Kriging porosity …
  Sanity check passed: max |depth_bot - depth_top - thickness| = …e-… m
  Estimated rock volume: …e+… m³  (… km³)
  Estimated pore volume: …e+… m³  (… km³)

Results saved → output/interp_results.npz
Done. Run plot_maps.py and cpg_export.py next.
```

> Runtime: ~10–30 seconds on a modern laptop for the 5000 m grid.

## Step 5 — Generate maps

```bash
python plot_maps.py
```

This produces four PNG files in `output/`. Open them in any image viewer:

- `output/map_depth_top.png` — depth to the top of the formation
- `output/map_depth_bot.png` — depth to the base of the formation
- `output/map_thickness.png` — formation thickness
- `output/map_porosity.png` — vertically-averaged porosity

## Step 6 — Export the corner-point grid

```bash
python cpg_export.py
```

This writes `output/grid.grdecl`. The file can be loaded directly into:
- **Eclipse** (Schlumberger / SLB)
- **OPM Flow** (open-source)
- **tNavigator** (RFD)
- **Petrel** (via GRDECL import)
- **ResInsight** (open-source visualisation)

## Step 7 — Adapt to your own data

1. **Replace `well_data.csv`** with your own well observations, keeping the same column names.
2. **Replace the shapefile** in `california/` (or a new subdirectory) with your study-area polygon.
3. **Edit `config.py`:**
   - Set `WELL_CSV` and `SHAPEFILE` to your new file paths.
   - Set `CRS_INPUT` to match your data's CRS.
   - Set `CRS_WORK` to a metric CRS appropriate for your region.
   - Adjust `GRID_RESOLUTION_M`, `CPG_DX/DY/NZ`, and kriging parameters as needed.
4. **Re-run** all three scripts in order.
