# Quickstart Guide — Windows

This guide walks you through running the workflow end-to-end on the included Parana Basin dataset on a Windows machine. For full documentation see [README_windows.md](README_windows.md).

## Prerequisites

- Python 3.10 or later (via conda — see Step 2)
- [Miniconda](https://docs.conda.io/en/latest/miniconda.html) or [Anaconda](https://www.anaconda.com/download) for Windows
- Git for Windows (to clone the repository) — download from [git-scm.com](https://git-scm.com/download/win)

> If you do not want to use Git, you can also download the repository as a ZIP from GitHub and extract it.

## Step 1 — Clone and enter the repository

Open **Git Bash** (or **Command Prompt** / **PowerShell** if Git is on your PATH) and run:

```
git clone https://github.com/<your-username>/formation-depth-interpolation.git
cd formation-depth-interpolation
```

If you downloaded a ZIP instead, extract it and note the folder path.

## Step 2 — Open Anaconda Prompt and navigate to the project folder

Search for **Anaconda Prompt** in the Start menu and open it. Then navigate to the project folder:

```
cd C:\path\to\formation-depth-interpolation
```

Replace `C:\path\to\` with the actual path where you cloned or extracted the repository. You can copy the path from File Explorer's address bar.

> **All remaining steps assume you are working in Anaconda Prompt** (or in PowerShell with conda initialised — see the [Troubleshooting](README_windows.md#troubleshooting) section in the README if you prefer PowerShell).

## Step 3 — Create the conda environment

```
conda create -n geoint python=3.11
conda activate geoint
conda install -c conda-forge numpy pandas geopandas shapely scipy matplotlib pykrige
```

> First-time install may take 2–5 minutes while conda resolves the environment.

## Step 4 — Inspect the sample data

Open `input_wells\parana_basin_well_data.csv` in any text editor or spreadsheet application (Notepad, Notepad++, VS Code, or Excel) to see the 39 sample wells spread across the Parana Basin. Open `config.py` to review the default settings — no changes are needed to run the demo.

## Step 5 — Run the workflow

### Option A — Run all scripts with the PowerShell script (recommended)

From Anaconda Prompt:

```
powershell -ExecutionPolicy Bypass -File run_all.ps1
```

This runs `interpolate.py`, `plot_maps.py`, and optionally `cpg_export.py` in order, and saves all console output to `output\<basin>\console_output.log`. The script stops immediately if any step fails.

> If PowerShell reports that running scripts is disabled, run the following once in PowerShell and then retry:
> ```powershell
> Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
> ```

### Option B — Run scripts individually

```
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
Done. Run plot_maps.py next.
```

> Runtime: ~10–30 seconds on a modern laptop for the 5000 m grid.

### Option C — Use Git Bash

If you have Git Bash installed, you can run the original shell script directly:

```bash
bash run_all.sh
```

## Step 6 — Generate maps (if running scripts individually)

```
python plot_maps.py
```

This produces four PNG files in `output\`. Open them in Windows Photo Viewer, Photos, or any image viewer:

- `output\<basin>\map_depth_top.png` — depth to the top of the formation
- `output\<basin>\map_depth_bot.png` — depth to the base of the formation
- `output\<basin>\map_thickness.png` — formation thickness
- `output\<basin>\map_porosity.png` — vertically-averaged porosity

## Step 7 — Export a corner-point grid (optional, for reservoir simulation)

This step is only needed if you want to run a reservoir simulation. It exports the kriged surfaces as an Eclipse-format corner-point grid.

```
python cpg_export.py
```

This writes `output\<basin>\grid.grdecl`, which can be loaded directly into:
- **Eclipse** (Schlumberger / SLB)
- **OPM Flow** (open-source)
- **tNavigator** (RFD)
- **Petrel** (via GRDECL import)
- **ResInsight** (open-source visualisation)

To include this step when using `run_all.ps1`, uncomment the `cpg_export.py` block near the bottom of that script.

## Step 8 — Adapt to your own data

1. **Add your well attribute CSV** to `input_wells\` named `<basin>_well_data.csv`. The first column must be the well identifier; remaining columns are `depth_top`, `depth_bot`, `thickness`, `porosity`.
   > If you prepare this file in Excel, save it as **CSV UTF-8 (Comma delimited)** to avoid encoding issues.
2. **Add your well location shapefile** to `input_wells\wells_<basin>\wells_<basin>.shp`. The identifier attribute name must match the first column header of the CSV.
3. **Add your boundary shapefile** to `input_boundary\<basin>\<basin>.shp`.
4. **Edit `config.py`** in any text editor:
   - Set `BASIN` to your basin name — all input paths are derived from it automatically.
   - Set `CRS_WORK` to a projected metric CRS covering your study area. See the [Coordinate Reference Systems](README_windows.md#coordinate-reference-systems) section in the README for recommended options by region.
   - Adjust `GRID_RESOLUTION_M` and `CPG_DX/DY/NZ` as needed.
   - Review the kriging parameters (`VARIOGRAM_MODEL`, `DRIFT_TERMS`, `VARIOGRAM_NLAGS`). For most sedimentary basin applications the defaults (`spherical`, `["regional_linear"]`, `8`) are a good starting point. See [Kriging Background](README_windows.md#kriging-background) in the README for a full explanation of each parameter and a practical tuning workflow.
5. **Re-run** the interpolation and map scripts — either individually or with `run_all.ps1`. Uncomment the `cpg_export.py` block in `run_all.ps1` if you also need the corner-point grid.
