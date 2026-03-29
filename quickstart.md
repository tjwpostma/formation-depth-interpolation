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

- `output/<basin>/map_depth_top.png` — depth to the top of the formation
- `output/<basin>/map_depth_bot.png` — depth to the base of the formation
- `output/<basin>/map_thickness.png` — formation thickness
- `output/<basin>/map_porosity.png` — vertically-averaged porosity

## Step 6 — For reservoir simulations: export a corner-point grid

```bash
python cpg_export.py
```

This writes `output/<basin>/grid.grdecl`. The file can be loaded directly into:
- **Eclipse** (Schlumberger / SLB)
- **OPM Flow** (open-source)
- **tNavigator** (RFD)
- **Petrel** (via GRDECL import)
- **ResInsight** (open-source visualisation)

## Step 7 — Adapt to your own data

1. **Add your well attribute CSV** to `input_wells/` named `<basin>_well_data.csv`. The first column must be the well identifier; remaining columns are `depth_top`, `depth_bot`, `thickness`, `porosity`.
2. **Add your well location shapefile** to `input_wells/wells_<basin>/wells_<basin>.shp`. The identifier attribute name must match the first column header of the CSV.
3. **Add your boundary shapefile** to `input_boundary/<basin>/<basin>.shp`.
4. **Edit `config.py`:**
   - Set `BASIN` to your basin name — all input paths are derived from it automatically.
   - Set `CRS_WORK` to a projected metric CRS covering your study area. See the [Coordinate Reference Systems](README.md#coordinate-reference-systems) section in the README for recommended options by region.
   - Adjust `GRID_RESOLUTION_M` and `CPG_DX/DY/NZ` as needed.
   - Review the kriging parameters (`VARIOGRAM_MODEL`, `DRIFT_TERMS`, `VARIOGRAM_NLAGS`). For most sedimentary basin applications the defaults (`spherical`, `["regional_linear"]`, `8`) are a good starting point. See [Kriging Background](README.md#kriging-background) in the README for a full explanation of each parameter and a practical tuning workflow.
5. **Re-run** all three scripts in order.
