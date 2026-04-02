# Formation Depth Interpolation & CPG Export — Windows Guide

A Python workflow for subsurface formation mapping from well data. It reprojects well observations into a metric CRS, runs **Universal Kriging** to produce continuous depth, thickness, and porosity surfaces, renders publication-quality maps, and exports a fully-populated **Eclipse / OGS corner-point grid (GRDECL)** ready for reservoir simulation.

> **Windows users:** This file covers Windows-specific setup and usage. All Python code, input formats, and outputs are identical to the macOS/Linux version. The differences are limited to environment setup, terminal usage, and how to run the workflow scripts.

---

## Table of Contents

1. [Overview](#overview)
2. [Repository Structure](#repository-structure)
3. [Dependencies & Environment](#dependencies--environment)
4. [Input Data](#input-data)
   - [Well CSV](#well-csv)
   - [Shapefile boundary](#shapefile-boundary)
5. [Configuration Reference (`config.py`)](#configuration-reference-configpy)
6. [Module Documentation](#module-documentation)
   - [interpolate.py](#interpolatepy)
   - [plot_maps.py](#plot_mapspy)
   - [cpg_export.py](#cpg_exportpy)
7. [Outputs](#outputs)
8. [Coordinate Reference Systems](#coordinate-reference-systems)
9. [Kriging Background](#kriging-background)
10. [Corner-Point Grid Format](#corner-point-grid-format)
11. [Quickstart Guide (Windows)](quickstart_windows.md)
12. [Troubleshooting](#troubleshooting)

---

## Overview

```
well_data.csv ──┐
                ├──► interpolate.py ──► interp_results.npz ──┬──► plot_maps.py  ──► PNG maps
california.shp ─┘                                            └──► cpg_export.py ──► grid.grdecl
```

The workflow is split into three independent scripts, each configured entirely through `config.py`:

| Step | Script | What it does |
|------|--------|--------------|
| 1 | `interpolate.py` | Loads wells, reprojects, kriging interpolation, saves `.npz` |
| 2 | `plot_maps.py` | Reads `.npz`, plots four PNG maps |
| 3 *(optional)* | `cpg_export.py` | Reads `.npz`, builds and writes `grid.grdecl` for reservoir simulation |

Steps 2 and 3 are independent of each other and both depend on step 1. Step 3 is only needed for reservoir simulation workflows.

Steps 1 and 2 can be run in one go using the provided PowerShell script, which also writes all console output to `output\<basin>\console_output.log`:

```powershell
powershell -ExecutionPolicy Bypass -File run_all.ps1
```

If you have Git Bash installed you can also use the original shell script:

```bash
bash run_all.sh
```

To include the CPG export, uncomment the `cpg_export.py` block near the bottom of `run_all.ps1` (or `run_all.sh`).

---

## Repository Structure

```
.
├── config.py              # All user-facing parameters
├── interpolate.py         # Kriging interpolation engine
├── plot_maps.py           # Map generation
├── cpg_export.py          # GRDECL corner-point grid export
├── run_all.ps1            # PowerShell script — run all steps in sequence (Windows)
├── run_all.sh             # Bash script — run all steps in sequence (macOS / Linux / Git Bash)
├── input_wells\           # Well data, one subdirectory per basin
│   ├── california_well_data.csv          # Horizon attributes (no coordinates)
│   └── wells_california\                 # Well location shapefile
│       ├── wells_california.shp
│       └── ...
├── input_boundary\        # Boundary polygon shapefiles, one subdirectory per basin
│   └── california\
│       ├── california.shp
│       └── ...
└── output\                # Created automatically on first run
    └── california\        # One subdirectory per basin (matches BASIN in config.py)
        ├── interp_results.npz
        ├── grid.grdecl
        ├── map_depth_top.png
        ├── map_depth_bot.png
        ├── map_thickness.png
        └── map_porosity.png
```

---

## Dependencies & Environment

The workflow is designed for a **conda** environment. Install [Miniconda](https://docs.conda.io/en/latest/miniconda.html) or [Anaconda](https://www.anaconda.com/download) for Windows before proceeding.

The following packages are required:

| Package | Tested version | Role |
|---------|---------------|------|
| `numpy` | 2.4.3 | Array operations, grid construction |
| `pandas` | 3.0.1 | Well CSV loading |
| `geopandas` | 1.1.3 | Shapefile I/O, CRS reprojection, masking |
| `shapely` | (with geopandas) | Geometry operations |
| `pykrige` | 1.7.3 | Universal Kriging |
| `scipy` | 1.17.1 | `RegularGridInterpolator`, `distance_transform_edt` |
| `matplotlib` | 3.10.8 | Map figures |

### Recommended terminal: Anaconda Prompt

All commands in this guide should be run in **Anaconda Prompt** (installed with Miniconda/Anaconda). You can find it in the Start menu. It has conda on the PATH and activates the base environment automatically.

Alternatively, use **PowerShell** after running `conda init powershell` once:

```powershell
conda init powershell
```

Then close and reopen PowerShell. You may also need to allow script execution:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

### Create and activate the environment

Open Anaconda Prompt and run:

```
conda create -n geoint python=3.11
conda activate geoint
conda install -c conda-forge numpy pandas geopandas shapely scipy matplotlib pykrige
```

Or with pip after activating an existing environment:

```
pip install numpy pandas geopandas shapely scipy matplotlib pykrige
```

> First-time install may take 2–5 minutes while conda resolves the environment.

---

## Input Data

### Well shapefile

**Path:** `input_wells\wells_<basin>\wells_<basin>.shp`

A point shapefile with one feature per well. The CRS is read from the embedded `.prj` file and reprojected to `CRS_WORK` automatically — no manual CRS configuration is needed for the wells. The only requirement is that the attribute table contains a well identifier column whose name matches the first column of the well data CSV.

### Well CSV

**File:** `input_wells\<basin>_well_data.csv`

Contains the horizon attributes for each well. The first column is the well identifier (the column name must match the identifier field in the shapefile). The remaining columns are:

| Column | Type | Units | Description |
|--------|------|-------|-------------|
| *(first column)* | string | — | Well identifier — must match the shapefile attribute name |
| `depth_top` | float | metres | Depth to the top of the formation |
| `depth_bot` | float | metres | Depth to the base of the formation |
| `thickness` | float | metres | Formation thickness (`depth_bot − depth_top`) |
| `porosity` | float | fraction (0–1) | Vertically-averaged porosity |

> **Depth convention:** all depth values must be **positive downward** (increasing with depth below surface). This is the standard well-log and Eclipse convention used throughout the workflow.

Example row (california, where the ID column is `well_id`):
```
W01,1881,1981,100,0.13
```

The two files are joined on the shared well ID column. Wells present in only one file are dropped with a warning. If two or more wells share the same projected coordinates (within 0.1 m), their attribute values are averaged to avoid a singular kriging matrix.

> **Note for Windows users:** If you edit the CSV in Excel and save it, ensure it is saved as **CSV UTF-8** or **CSV (Comma delimited)** — not as an Excel workbook (`.xlsx`). Excel may silently add a BOM or change line endings; both are handled correctly by pandas.

### Shapefile boundary

**Path:** `input_boundary\<basin>\<basin>.shp`

A polygon shapefile defining the region of interest. The kriging is performed over the full bounding box of this polygon, then grid points and CPG cells outside the polygon are masked (`NaN` / `ACTNUM = 0`). The shapefile may use any CRS — it is reprojected to `CRS_WORK` automatically.

---

## Configuration Reference (`config.py`)

All parameters live in one place. Edit `config.py` before running any script. Any plain text editor works — Notepad, Notepad++, VS Code, etc.

### Paths

| Parameter | Default | Description |
|-----------|---------|-------------|
| `BASIN` | `"california"` | Basin name — drives all input paths. Change this to switch datasets. |
| `WELL_CSV` | `input_wells/<BASIN>_well_data.csv` | Derived automatically from `BASIN` |
| `WELL_SHP` | `input_wells/wells_<BASIN>/wells_<BASIN>.shp` | Derived automatically from `BASIN` |
| `SHAPEFILE` | `input_boundary/<BASIN>/<BASIN>.shp` | Derived automatically from `BASIN` |
| `OUT_DIR` | `output/<BASIN>` | Directory for all outputs (auto-created) |

> Python accepts forward slashes (`/`) on Windows, so the path strings in `config.py` do not need to be changed.

### Coordinate Reference Systems

| Parameter | Default | Description |
|-----------|---------|-------------|
| `CRS_WORK` | `EPSG:5880` (SIRGAS 2000 / Brazil Polyconic, metres) | Metric projected CRS for kriging and grid construction. All input shapefiles are reprojected to this automatically. |

> Set `CRS_WORK` to a projected metric CRS that covers your study area. See [**Coordinate Reference Systems**](#coordinate-reference-systems) for a table of recommended options by region.

### Interpolation Grid

| Parameter | Default | Description |
|-----------|---------|-------------|
| `GRID_RESOLUTION_M` | `5000` | Cell size of the kriging grid in metres |

A finer resolution produces smoother maps but increases kriging time quadratically. For a 500 km × 500 km study area, `5000 m` gives a 100 × 100 grid (10 000 points); `1000 m` gives 500 × 500 (250 000 points).

### Kriging Parameters

| Parameter | Default | Options | Description |
|-----------|---------|---------|-------------|
| `VARIOGRAM_MODEL` | `"spherical"` | `spherical`, `gaussian`, `exponential`, `linear`, `power` | Theoretical variogram model |
| `DRIFT_TERMS` | `["regional_linear"]` | `["regional_linear"]`, `["point_log"]`, `[]` | Drift functions for Universal Kriging of **depth_top only**. Thickness and porosity always use Ordinary Kriging — see [Kriging Background](#kriging-background). |
| `VARIOGRAM_NLAGS` | `8` | integer | Number of lag bins for the experimental variogram |

> With `DRIFT_TERMS = []` the script falls back to Ordinary Kriging, which is appropriate when no regional trend is present.

### Maps

| Parameter | Default | Description |
|-----------|---------|-------------|
| `MAP_DPI` | `150` | DPI for saved PNG figures |
| `CONTOUR_INTERVAL_DEPTH` | `50` | Contour line spacing on depth maps (metres) |
| `CONTOUR_INTERVAL_THICKNESS` | `10` | Contour line spacing on the thickness map (metres) |

### Corner-Point Grid (GRDECL)

| Parameter | Default | Description |
|-----------|---------|-------------|
| `CPG_DX` | `5000` | Horizontal cell width in the X (easting) direction (metres) |
| `CPG_DY` | `5000` | Horizontal cell width in the Y (northing) direction (metres) |
| `CPG_NZ` | `10` | Number of vertical layers |
| `CPG_FILENAME` | `"grid.grdecl"` | Output filename inside `OUT_DIR` |

---

## Module Documentation

### `interpolate.py`

**Purpose:** The core interpolation engine. Reads well observations, reprojects to the working CRS, runs Universal Kriging for three attributes, applies the shapefile mask, and persists all results to a compressed NumPy archive.

**Run (Anaconda Prompt):**
```
conda activate geoint
python interpolate.py
```

Or run all scripts together with `run_all.ps1` (see [Overview](#overview)).

#### Processing steps

| Step | Description |
|------|-------------|
| 0 | Create `output\` directory if absent |
| 1 | Load `well_data.csv` into a GeoDataFrame; reproject from `CRS_INPUT` → `CRS_WORK` |
| 2 | Deduplicate co-located wells (round coordinates to 0.1 m, group-average attributes) |
| 3 | Load shapefile; dissolve to a single (Multi)Polygon; compute its bounding box |
| 4 | Build a regular `nx × ny` grid of points at `GRID_RESOLUTION_M` spacing inside the bounding box |
| 5 | Compute an in-region boolean mask via vectorised `GeoSeries.within()` |
| 6–8 | Universal Kriging for `depth_top`, `thickness`, and `porosity` |
| 8 | Derive `depth_bot = depth_top + thickness` |
| 9 | Apply mask (set out-of-region cells to `NaN`) |
| 10 | Sanity-check: assert `|depth_bot − depth_top − thickness| < 1e-6` everywhere |
| 11 | Compute rock volume and pore volume from the gridded data |
| 12 | Save everything to `output\interp_results.npz` |

#### Kriging variance output

For each of the three kriged attributes, the script also outputs a **kriging variance** (prefix `ss_`) stored alongside the interpolated surface in the `.npz` file. This provides a cell-by-cell measure of interpolation uncertainty.

#### Output arrays in `interp_results.npz`

| Array | Shape | Description |
|-------|-------|-------------|
| `xs` | `(nx,)` | Easting grid coordinates (m) |
| `ys` | `(ny,)` | Northing grid coordinates (m) |
| `xx`, `yy` | `(ny, nx)` | 2-D meshgrid |
| `mask` | `(ny, nx)` | Boolean: `True` inside shapefile |
| `depth_top` | `(ny, nx)` | Kriged depth to formation top (m), `NaN` outside |
| `depth_bot` | `(ny, nx)` | Derived depth to formation base (m), `NaN` outside |
| `thickness` | `(ny, nx)` | Kriged formation thickness (m), `NaN` outside |
| `porosity` | `(ny, nx)` | Kriged porosity (fraction), `NaN` outside |
| `ss_top` | `(ny, nx)` | Kriging variance for `depth_top` |
| `ss_thick` | `(ny, nx)` | Kriging variance for `thickness` |
| `ss_poro` | `(ny, nx)` | Kriging variance for `porosity` |
| `wx`, `wy` | `(nw,)` | Projected well coordinates (m) |
| `depth_top_vals` | `(nw,)` | Well-observed depth_top |
| `thickness_vals` | `(nw,)` | Well-observed thickness |
| `porosity_vals` | `(nw,)` | Well-observed porosity |
| `well_ids` | `(nw,)` | Well ID strings |
| `grid_res` | `(1,)` | Grid resolution in metres |
| `volume_m3` | `(1,)` | Total rock volume (m³) |
| `pore_vol_m3` | `(1,)` | Total pore volume (m³) |

---

### `plot_maps.py`

**Purpose:** Reads `interp_results.npz` and produces four georeferenced PNG maps.

**Run (Anaconda Prompt):**
```
conda activate geoint
python plot_maps.py
```

**Requires:** `interpolate.py` must have been run first. Or run all scripts together with `run_all.ps1` (see [Overview](#overview)).

#### Output maps

| File | Attribute | Colormap | Contour interval |
|------|-----------|----------|-----------------|
| `map_depth_top.png` | Depth to formation top | `viridis_r` | `CONTOUR_INTERVAL_DEPTH` |
| `map_depth_bot.png` | Depth to formation base | `viridis_r` | `CONTOUR_INTERVAL_DEPTH` |
| `map_thickness.png` | Formation thickness | `YlOrRd` | `CONTOUR_INTERVAL_THICKNESS` |
| `map_porosity.png` | Vertically-averaged porosity | `Blues` | 0.01 |

Each map includes:
- A filled pcolormesh colour surface for the interpolated attribute
- Labelled contour lines
- The shapefile polygon boundary
- Red scatter points at well locations with annotated well IDs
- Axes in kilometres (easting / northing), labelled with the working CRS
- A colorbar

Also prints the formation rock volume and pore volume to the console.

---

### `cpg_export.py` *(optional — reservoir simulation only)*

**Purpose:** Constructs a fully Eclipse-compatible corner-point grid from the kriged surfaces and writes it as a `.grdecl` file. Only needed if you intend to run a reservoir simulation.

**Run (Anaconda Prompt):**
```
conda activate geoint
python cpg_export.py
```

Or uncomment the `cpg_export.py` block in `run_all.ps1` to include it in the automated run.

#### Processing steps

| Step | Description |
|------|-------------|
| 1 | Load `interp_results.npz`; build `RegularGridInterpolator` objects for `depth_top`, `depth_bot`, and `porosity` |
| 2 | Fill `NaN` values in the kriging surfaces using nearest-neighbour distance transform (`scipy.ndimage.distance_transform_edt`) so that inactive-column pillar coordinates remain finite |
| 3 | Create the CPG pillar coordinate arrays (`pillar_xs`, `pillar_ys`), with `j = 0` at the **north** edge (NW-origin convention) |
| 4 | Determine grid dimensions `NX × NY × NZ` from the shapefile bounding box and `CPG_DX/DY/NZ` settings |
| 5 | Evaluate interpolated surfaces at all `(NY+1) × (NX+1)` pillar nodes and at all `NY × NX` cell centres |
| 6 | Compute `ACTNUM`: cell centre is inside the shapefile AND both surface values are finite; replicate uniformly across all `NZ` layers |
| 7 | Build `COORD` array: 6 values per pillar `[x, y, z_top, x, y, z_bot]`, ordered j-slowest / i-fastest |
| 8 | Build `ZCORN` array: 8 depth values per cell subdivided linearly between `depth_top` and `depth_bot` in `NZ` equal layers, following Eclipse corner ordering |
| 9 | Build `PORO` array: vertically-averaged porosity, constant through all layers, zero for inactive cells |
| 10 | Write the `.grdecl` file with sections: `SPECGRID`, `METRIC`, `COORD`, `ZCORN`, `ACTNUM`, `PORO`, `END` |

#### GRDECL file structure

```
-- Corner-point grid generated by cpg_export.py
-- CRS: EPSG:3310
-- Grid: NX=…  NY=…  NZ=10  DX=5000 m  DY=5000 m
-- Active cells: …

SPECGRID
  NX  NY  NZ  1  F
/

METRIC

COORD
  x0 y0 ztop0 x0 y0 zbot0  x1 y1 ztop1 ...
/

ZCORN
  z000 z001 ... (8 values per cell × NX×NY×NZ cells)
/

ACTNUM
  1  0  1*3  0  ...  (run-length encoded)
/

PORO
  0.130000  0.150000 ...
/

END
```

---

## Outputs

All outputs are written to `OUT_DIR` (`output\<basin>` by default):

| File | Created by | Description |
|------|-----------|-------------|
| `interp_results.npz` | `interpolate.py` | Compressed NumPy archive of all kriging results |
| `map_depth_top.png` | `plot_maps.py` | Depth to formation top map |
| `map_depth_bot.png` | `plot_maps.py` | Depth to formation base map |
| `map_thickness.png` | `plot_maps.py` | Formation thickness map |
| `map_porosity.png` | `plot_maps.py` | Vertically-averaged porosity map |
| `grid.grdecl` | `cpg_export.py` | Eclipse / OGS corner-point grid |

---

## Coordinate Reference Systems

**Why a projected CRS?** Kriging requires a Euclidean distance metric. Geographic coordinates (degrees) produce distorted distance calculations, especially at mid-latitudes. A metric projected CRS ensures that distance-based semivariogram fitting is physically meaningful and that cell area / volume calculations are correct.

All input shapefiles (wells and boundary) carry their own CRS in the `.prj` file and are reprojected to `CRS_WORK` automatically. You only need to set `CRS_WORK` once in `config.py`.

### Choosing a working CRS

Pick a **projected, metric** CRS that covers your study area with reasonably low distortion. For basin-scale work (tens to a few hundred kilometres across) the distortion introduced by any of the options below is far smaller than well-data uncertainty, so any reasonable choice will do.

**General-purpose options — valid anywhere on Earth:**

| CRS | EPSG | Notes |
|-----|------|-------|
| UTM zone for your area | see table below | Best geometric accuracy within the 6° zone; use when your basin fits comfortably in one zone |
| World Mercator | `EPSG:3395` | Good up to ~70° latitude; avoid near the poles |
| WGS 84 / Pseudo-Mercator | `EPSG:3857` | Widespread web-mapping CRS; metric but area-distorted at high latitudes — acceptable for rough estimates |

To find your UTM zone: divide your central longitude by 6, round up, and prepend 326 (northern hemisphere) or 327 (southern hemisphere). For example, a basin centred at 50°E in the southern hemisphere → zone 38S → `EPSG:32738`.

**Brazil and South America:**

| Region | EPSG | Name |
|--------|------|------|
| All of Brazil (recommended default) | `EPSG:5880` | SIRGAS 2000 / Brazil Polyconic |
| Brazil — south / Paraná Basin | `EPSG:31982` | SIRGAS 2000 / UTM zone 22S |
| Brazil — north / Amazon | `EPSG:31974` | SIRGAS 2000 / UTM zone 20S |
| Brazil — offshore pre-salt | `EPSG:31983` | SIRGAS 2000 / UTM zone 23S |
| South America (continental) | `EPSG:102033` | South America Albers Equal Area |

**Major oil and gas regions:**

| Region | EPSG | Name |
|--------|------|------|
| North Sea (UK sector) | `EPSG:27700` | British National Grid |
| North Sea (Norwegian sector) | `EPSG:23032` | ED50 / UTM zone 32N |
| North Sea (Dutch sector) | `EPSG:28992` | Amersfoort / RD New |
| Middle East / Arabian Peninsula | `EPSG:32638` | WGS 84 / UTM zone 38N |
| Permian Basin / US Southwest | `EPSG:32613` | WGS 84 / UTM zone 13N |
| Gulf of Mexico | `EPSG:32615` | WGS 84 / UTM zone 15N |
| West Siberia | `EPSG:32642` | WGS 84 / UTM zone 42N |
| Caspian / Kazakhstan | `EPSG:32639` | WGS 84 / UTM zone 39N |
| West Africa (Gulf of Guinea) | `EPSG:32632` | WGS 84 / UTM zone 32N |
| California | `EPSG:3310` | NAD83 / California Albers |
| Alberta / Western Canada | `EPSG:3400` | NAD83 / Alberta 10-TM (Forest) |

---

## Kriging Background

Universal Kriging (UK) is a geostatistical interpolation technique that extends Ordinary Kriging by allowing for a **spatially varying mean** modelled as a linear combination of drift functions. The standard form is:

$$Z(\mathbf{x}) = \sum_k a_k f_k(\mathbf{x}) + \delta(\mathbf{x})$$

where $f_k$ are known drift functions (e.g. a linear trend in $x$ and $y$), $a_k$ are unknown coefficients, and $\delta(\mathbf{x})$ is a zero-mean stationary random field described by the semivariogram $\gamma(h)$.

### Implemented via PyKrige

This workflow uses [`pykrige.uk.UniversalKriging`](https://geostat-framework.readthedocs.io/projects/pykrige/en/stable/generated/pykrige.uk.UniversalKriging.html). The three key parameters — variogram model, drift terms, and lag count — are all set in `config.py` and explained in detail below.

#### Variogram model

The **variogram** quantifies how spatial correlation between well observations decays with distance. The theoretical model is fitted to an experimental variogram computed from your data, and its shape directly controls how the interpolated surface behaves away from wells.

| Model | Behaviour | When to use |
|---|---|---|
| `spherical` | Rises steadily then **flattens** at a finite range and sill | **Default for geology.** Correct for formations where spatial correlation exists up to a finite distance and then vanishes — the standard choice in petroleum geostatistics. |
| `exponential` | Rises steeply near origin, asymptotically approaches sill | Similar to spherical but correlation decays more slowly near the range. Useful when the transition to uncorrelated behaviour is gradual. |
| `gaussian` | Very smooth, parabolic near the origin | For highly continuous phenomena. Can cause numerical instability with sparse well data — use with caution. |
| `linear` | Rises indefinitely, no sill | No finite range of correlation. Rarely appropriate for formation tops. |
| `power` | Fractal-like, no sill | Self-similar roughness. Rarely appropriate for formation depths or thicknesses. |

For formation-top and thickness interpolation, **`spherical`** is the standard starting point. Only switch models if your experimental variogram clearly shows a different shape.

#### Drift terms

Drift terms switch kriging from **Ordinary Kriging** (assumes a constant unknown mean) to **Universal Kriging** (assumes a spatially varying mean). They model a large-scale deterministic trend explicitly; kriging then fits the residual, smaller-scale spatial variability on top of it.

In this workflow, `DRIFT_TERMS` applies **only to `depth_top`**. Thickness and porosity always use Ordinary Kriging:
- A linear drift on **thickness** would imply systematic basin-wide wedging — a specific geological claim rather than a safe default. Thickness variability is better treated as a purely spatial random field.
- A linear drift on **porosity** has no physical basis in a structural context.

| Setting | What it models | When to use |
|---|---|---|
| `["regional_linear"]` | Linear plane $z = a_0 + a_1 x + a_2 y$ | **Default.** Captures a regional structural dip — almost all sedimentary basins have a systematic deepening direction. Extrapolates sensibly into data-sparse areas. |
| `[]` | No trend — Ordinary Kriging | Use when depth shows no systematic directional gradient, or when you have very few wells (< ~10) and UK becomes over-parameterised. |
| `["point_log"]` | Logarithmic trend around a central point | Radially symmetric phenomena. Rarely applicable to formation mapping. |

#### Lag bins (`VARIOGRAM_NLAGS`)

The experimental variogram is built by grouping all well pairs into distance bins (lags) and averaging their squared depth differences $\frac{1}{2}[\Delta z]^2$ within each bin. `VARIOGRAM_NLAGS` controls how many bins to use.

- **Too few (< 6):** Bins are wide — produces a smooth but coarse experimental variogram that may miss the true correlation range.
- **Too many (> 20):** Bins are narrow — produces a noisy, erratic variogram, especially at large distances where few pairs exist.
- **Rule of thumb:** Aim for at least **30 well pairs per lag bin** and cover lags up to roughly **half the maximum inter-well distance**. The default of `8` is a safe, conservative starting point.

#### Practical tuning workflow

1. **Check for a regional trend first.** Plot your well `depth_top` values coloured by magnitude on a map. If there is a clear gradient across the basin, keep `drift_terms = ["regional_linear"]`. If depth is patchy with no strong directional signal, switch to `[]`.
2. **Inspect the variogram fit.** Temporarily set `enable_plotting=True` in `interpolate.py` — pykrige will display the fitted model overlaid on the experimental points. If the fit is poor, try a different `VARIOGRAM_MODEL`.
3. **Adjust lag count if needed.** If the experimental variogram looks erratic, reduce `VARIOGRAM_NLAGS`. If it looks too coarse to resolve the correlation structure, increase it gradually and refit.

### Kriging variance

The output includes the kriging variance (`ss_*` arrays), which is a by-product of solving the kriging system: high variance indicates cells far from any well, while low variance indicates well-constrained locations. The variance can be used to map interpolation uncertainty or to condition further analysis.

---

## Corner-Point Grid Format

The GRDECL format is the standard grid description file for Eclipse-family reservoir simulators (including OGS, tNavigator, and others). Key conventions used in this implementation:

### Depth convention

All Z-coordinates are **positive downward** — a value of `2000` means 2000 m below the surface datum. This is consistent with the input well CSV, the Eclipse GRDECL format, and standard well-log convention. Never supply negative depth values (elevation-style coordinates) as input.

### Pillar convention (NW origin)

- Pillar indices follow an **NW-origin, j-north** convention: `j = 0` is the northernmost row and increases southward; `i = 0` is the westernmost column and increases eastward.
- This matches the Eclipse standard where `j` corresponds to the Y-direction (northing) and `i` to the X-direction (easting).

### COORD

6 values per pillar: `[x_top, y_top, z_top, x_bot, y_bot, z_bot]`. Pillars are perfectly vertical so `x_top == x_bot` and `y_top == y_bot`. The total number of pillars is `(NX+1) × (NY+1)`.

### ZCORN

8 depth values per grid cell (4 top corners + 4 bottom corners). The total array length is `8 × NX × NY × NZ`. The ordering follows the Eclipse convention:

```
for k in range(NZ):
  for face in [top, bottom]:     # each layer has a top face and a bottom face
    for j in range(NY):
      upper sub-row: NW, NE corners for each i    (2 × NX values)
      lower sub-row: SW, SE corners for each i    (2 × NX values)
```

Layers are subdivided **linearly** between `depth_top` and `depth_bot` at each column.

### ACTNUM

A `NX × NY × NZ` integer array: `1` = active cell, `0` = inactive. Listed in k-slowest, j-middle, i-fastest order. The same 2-D mask is replicated uniformly across all NZ layers. **Run-length encoding** (`count*value`) is used to keep file size compact.

---

## Quickstart Guide

See [quickstart_windows.md](quickstart_windows.md) for a step-by-step guide to running the workflow on the included Parana Basin dataset, including environment setup and instructions for adapting the workflow to your own data.

---

## Troubleshooting

### `FileNotFoundError: 'output/interp_results.npz' not found`

Run `interpolate.py` before `plot_maps.py` or `cpg_export.py`.

### `conda` is not recognised as a command

You are probably running in a plain Command Prompt or a PowerShell that has not been initialised for conda. Either:
- Use **Anaconda Prompt** from the Start menu instead, or
- Run `conda init powershell` in a PowerShell window opened as Administrator, then close and reopen it.

### PowerShell reports "running scripts is disabled on this system"

Run the following once to allow local scripts for the current user:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

### Kriging is very slow

Reduce `GRID_RESOLUTION_M` to a coarser value (e.g. `10000` or `20000`). Universal Kriging scales as $O(n_w^3)$ for the system solve (where $n_w$ is the number of wells) and $O(n_g \cdot n_w)$ for prediction (where $n_g$ is the number of grid points).

### Singular kriging matrix / `LinAlgError`

This usually means two or more wells are at identical projected coordinates. The deduplication step in `interpolate.py` should handle this automatically; check the console for a deduplication message. If the error persists, inspect your CSV for wells with very similar coordinates.

### Negative thickness values in the kriging output

Kriging can extrapolate to unphysical negative values in data-sparse or boundary areas. `interpolate.py` automatically clamps any negative thickness to zero and prints a warning with the cell count — check the console output after running it. If many cells are affected it suggests the variogram is over-fitting a regional dip that doesn't hold at the basin edge; consider:
- Switching to Ordinary Kriging (`DRIFT_TERMS = []`) to remove the linear extrapolation.
- Adding more wells at the boundary of the region.
- Using a variogram model with a shorter effective range (e.g. `exponential`).

### Contours do not appear on the maps

PyKrige may return a near-uniform surface if the variogram fit is poor (e.g. too few wells for the chosen `VARIOGRAM_NLAGS`). Try reducing `VARIOGRAM_NLAGS` to `4` or `6`.

### GRDECL does not load in my simulator

- Ensure depths are positive downward (Eclipse convention). The code outputs depths exactly as provided in the well CSV.
- Check that the simulator expects `METRIC` units (metres). If it expects `FIELD` units (feet), convert your depth values accordingly.
- Some simulators require a `GRIDUNIT` keyword in addition to `METRIC`. Consult your simulator's GRDECL reference.

### `UnicodeDecodeError` when loading the well CSV

This can happen if the CSV was edited and saved in Excel with a non-UTF-8 encoding. Re-open the file in Excel, choose **Save As → CSV UTF-8 (Comma delimited)**, and re-run the script.
