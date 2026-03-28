# Formation Depth Interpolation & CPG Export

A Python workflow for subsurface formation mapping from well data. It reprojects well observations into a metric CRS, runs **Universal Kriging** to produce continuous depth, thickness, and porosity surfaces, renders publication-quality maps, and exports a fully-populated **Eclipse / OGS corner-point grid (GRDECL)** ready for reservoir simulation.

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
11. [Quickstart Guide](quickstart.md)
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
| 3 | `cpg_export.py` | Reads `.npz`, builds and writes `grid.grdecl` |

Steps 2 and 3 are independent of each other and both depend on step 1.

---

## Repository Structure

```
.
├── config.py              # All user-facing parameters
├── interpolate.py         # Kriging interpolation engine
├── plot_maps.py           # Map generation
├── cpg_export.py          # GRDECL corner-point grid export
├── well_data.csv          # Input well observations
├── california/            # Polygon boundary shapefile
│   ├── california.shp
│   ├── california.dbf
│   ├── california.prj
│   └── california.shx
└── output/                # Created automatically on first run
    ├── interp_results.npz
    ├── grid.grdecl
    ├── map_depth_top.png
    ├── map_depth_bot.png
    ├── map_thickness.png
    └── map_porosity.png
```

---

## Dependencies & Environment

The workflow is designed for a **conda** environment. The following packages are required:

| Package | Tested version | Role |
|---------|---------------|------|
| `numpy` | 2.4.3 | Array operations, grid construction |
| `pandas` | 3.0.1 | Well CSV loading |
| `geopandas` | 1.1.3 | Shapefile I/O, CRS reprojection, masking |
| `shapely` | (with geopandas) | Geometry operations |
| `pykrige` | 1.7.3 | Universal Kriging |
| `scipy` | 1.17.1 | `RegularGridInterpolator`, `distance_transform_edt` |
| `matplotlib` | 3.10.8 | Map figures |

### Create and activate the environment

```bash
conda create -n geoint python=3.11
conda activate geoint
conda install -c conda-forge numpy pandas geopandas shapely scipy matplotlib pykrige
```

Or with pip after activating an existing environment:

```bash
pip install numpy pandas geopandas shapely scipy matplotlib pykrige
```

---

## Input Data

### Well CSV

**File:** `well_data.csv`

The well data file must be a CSV with the following columns (header row required):

| Column | Type | Units | Description |
|--------|------|-------|-------------|
| `well_id` | string | — | Unique well identifier label |
| `lat` | float | decimal degrees | Latitude (WGS84 / NAD83) |
| `lon` | float | decimal degrees | Longitude (WGS84 / NAD83) |
| `depth_top` | float | metres | Depth to the top of the formation |
| `depth_bot` | float | metres | Depth to the base of the formation |
| `thickness` | float | metres | Formation thickness (`depth_bot − depth_top`) |
| `porosity` | float | fraction (0–1) | Vertically-averaged porosity |

Example row:
```
W01,38.90291,-121.74683,1881,1981,100,0.13
```

> **Duplicate locations:** If two or more wells share the same projected coordinates (within 0.1 m), the script automatically averages their attribute values to avoid a singular kriging matrix. Merged well IDs are reported in the console output.

### Shapefile boundary

**Directory:** `california/` (or any path set in `config.SHAPEFILE`)

A polygon shapefile defining the region of interest. The kriging is performed over the full bounding box of this polygon, then grid points and CPG cells outside the polygon are masked (`NaN` / `ACTNUM = 0`). The shapefile may use any CRS — it is reprojected to `CRS_WORK` automatically.

To use a different region:
1. Place your shapefile in a subdirectory.
2. Update `SHAPEFILE` in `config.py` to point to the `.shp` file.
3. Update `CRS_INPUT` / `CRS_WORK` if appropriate for your region.

---

## Configuration Reference (`config.py`)

All parameters live in one place. Edit `config.py` before running any script.

### Paths

| Parameter | Default | Description |
|-----------|---------|-------------|
| `WELL_CSV` | `well_data.csv` (beside `config.py`) | Path to the input well CSV |
| `SHAPEFILE` | `california/california.shp` | Path to the region-of-interest shapefile |
| `OUT_DIR` | `output/` | Directory for all outputs (auto-created) |

### Coordinate Reference Systems

| Parameter | Default | Description |
|-----------|---------|-------------|
| `CRS_INPUT` | `EPSG:4269` (NAD83 geographic) | CRS of the well lat/lon coordinates and the shapefile |
| `CRS_WORK` | `EPSG:3310` (NAD83 / California Albers, metres) | Metric equal-area CRS for kriging and grid construction |

> Change `CRS_WORK` to any projected metric CRS appropriate for your region (e.g. `EPSG:32633` for UTM zone 33N).

### Interpolation Grid

| Parameter | Default | Description |
|-----------|---------|-------------|
| `GRID_RESOLUTION_M` | `5000` | Cell size of the kriging grid in metres |

A finer resolution produces smoother maps but increases kriging time quadratically. For a 500 km × 500 km study area, `5000 m` gives a 100 × 100 grid (10 000 points); `1000 m` gives 500 × 500 (250 000 points).

### Kriging Parameters

| Parameter | Default | Options | Description |
|-----------|---------|---------|-------------|
| `VARIOGRAM_MODEL` | `"spherical"` | `spherical`, `gaussian`, `exponential`, `linear`, `power` | Theoretical variogram model |
| `DRIFT_TERMS` | `["regional_linear"]` | `["regional_linear"]`, `["point_log"]`, `[]` | Drift functions for Universal Kriging. Empty list = Ordinary Kriging |
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

**Run:**
```bash
conda activate geoint
python interpolate.py
```

#### Processing steps

| Step | Description |
|------|-------------|
| 0 | Create `output/` directory if absent |
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
| 12 | Save everything to `output/interp_results.npz` |

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

**Run:**
```bash
conda activate geoint
python plot_maps.py
```

**Requires:** `interpolate.py` must have been run first.

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

### `cpg_export.py`

**Purpose:** Constructs a fully Eclipse-compatible corner-point grid from the kriged surfaces and writes it as a `.grdecl` file.

**Run:**
```bash
conda activate geoint
python cpg_export.py
```

**Requires:** `interpolate.py` must have been run first.

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

All outputs are written to `OUT_DIR` (`output/` by default):

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

The workflow uses two CRS:

| Role | Default EPSG | Name | Units |
|------|-------------|------|-------|
| Input (wells + shapefile) | 4269 | NAD83 geographic | degrees |
| Working / output | 3310 | NAD83 / California Albers | metres |

**Why reproject?** Kriging requires a Euclidean distance metric. Geographic coordinates (degrees) produce distorted distance calculations, especially at mid-latitudes. A metric equal-area projection ensures that distance-based semivariogram fitting is physically meaningful and that cell area / volume calculations are correct.

To adapt for a different region, change `CRS_WORK` to an appropriate metric CRS. Examples:

| Region | Recommended CRS_WORK |
|--------|---------------------|
| California | `EPSG:3310` — NAD83 / California Albers |
| Continental US | `EPSG:5070` — NAD83 / Conus Albers |
| UK / North Sea | `EPSG:27700` — British National Grid |
| Europe | `EPSG:3035` — ETRS89-LAEA |
| Global (WGS84) | `EPSG:4326` → use a local UTM zone instead |

---

## Kriging Background

Universal Kriging (UK) is a geostatistical interpolation technique that extends Ordinary Kriging by allowing for a **spatially varying mean** modelled as a linear combination of drift functions. The standard form is:

$$Z(\mathbf{x}) = \sum_k a_k f_k(\mathbf{x}) + \delta(\mathbf{x})$$

where $f_k$ are known drift functions (e.g. a linear trend in $x$ and $y$), $a_k$ are unknown coefficients, and $\delta(\mathbf{x})$ is a zero-mean stationary random field described by the semivariogram $\gamma(h)$.

### Implemented via PyKrige

This workflow uses [`pykrige.uk.UniversalKriging`](https://geostat-framework.readthedocs.io/projects/pykrige/en/stable/generated/pykrige.uk.UniversalKriging.html). Key settings:

- **`variogram_model`** — shape of the theoretical semivariogram. `spherical` is the most common choice for geological data; it reaches a finite sill at a finite range.
- **`drift_terms = ["regional_linear"]`** — models a linear trend surface $f(x, y) = a_0 + a_1 x + a_2 y$, appropriate when the formation has a regional structural dip.
- **`nlags`** — number of lag distance bins used to compute the experimental semivariogram from which model parameters are fitted automatically.

### Kriging variance

The output includes the kriging variance (`ss_*` arrays), which is a by-product of solving the kriging system: high variance indicates cells far from any well, while low variance indicates well-constrained locations. The variance can be used to map interpolation uncertainty or to condition further analysis.

---

## Corner-Point Grid Format

The GRDECL format is the standard grid description file for Eclipse-family reservoir simulators (including OGS, tNavigator, and others). Key conventions used in this implementation:

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

See [quickstart.md](quickstart.md) for a step-by-step guide to running the workflow on the included California dataset, including environment setup and instructions for adapting the workflow to your own data.

---

## Troubleshooting

### `FileNotFoundError: 'output/interp_results.npz' not found`

Run `interpolate.py` before `plot_maps.py` or `cpg_export.py`.

### Kriging is very slow

Reduce `GRID_RESOLUTION_M` to a coarser value (e.g. `10000` or `20000`). Universal Kriging scales as $O(n_w^3)$ for the system solve (where $n_w$ is the number of wells) and $O(n_g \cdot n_w)$ for prediction (where $n_g$ is the number of grid points).

### Singular kriging matrix / `LinAlgError`

This usually means two or more wells are at identical projected coordinates. The deduplication step in `interpolate.py` should handle this automatically; check the console for a deduplication message. If the error persists, inspect your CSV for wells with very similar coordinates.

### Negative thickness values in the kriging output

Outside the data cloud, kriging can extrapolate to unphysical values. These cells will be masked `NaN` if they fall outside the shapefile, but if they are inside the region you may need to:
- Constrain kriging with a non-negativity post-processing step (clamp `z_thick = np.maximum(z_thick, 0)`).
- Add more wells at the boundary of the region.
- Switch to a variogram model with a shorter effective range (e.g. `exponential`).

### Contours do not appear on the maps

PyKrige may return a near-uniform surface if the variogram fit is poor (e.g. too few wells for the chosen `VARIOGRAM_NLAGS`). Try reducing `VARIOGRAM_NLAGS` to `4` or `6`.

### GRDECL does not load in my simulator

- Ensure depths are positive downward (Eclipse convention). The code outputs depths exactly as provided in the well CSV.
- Check that the simulator expects `METRIC` units (metres). If it expects `FIELD` units (feet), convert your depth values accordingly.
- Some simulators require a `GRIDUNIT` keyword in addition to `METRIC`. Consult your simulator's GRDECL reference.
