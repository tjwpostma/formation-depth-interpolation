---
name: grdecl-cpg
description: "Build or modify an Eclipse/OGS GRDECL corner-point grid from depth surfaces or geometry. Use when: writing COORD, ZCORN, ACTNUM, SPECGRID; converting geometry to .grdecl; constructing corner-point grids; debugging pillar indexing or cell corner ordering; understanding NW-origin convention, j-axis direction, or ZCORN loop order."
argument-hint: "describe the geometry source and target grid resolution"
---

# GRDECL Corner-Point Grid Construction

## When to Use
- Building a `.grdecl` file from kriged/interpolated depth surfaces
- Converting a corner-point grid from another format (BP, EDX) to GRDECL
- Debugging incorrect cell geometry (flipped axes, wrong corner ordering)
- Adding ACTNUM masking to an existing grid

## Key Insight: Index Direction vs Coordinate System
i/j/k index direction is **completely independent** of the real-world coordinate system.
COORD stores absolute (x, y, z) values; the simulator reconstructs geometry from those.
`MAPAXES` handles real-world orientation. A grid where y decreases as j increases is
perfectly legal. Choose the pillar numbering convention that is convenient and be consistent.

---

## Format Structure

A `.grdecl` file contains these sections in order:

```
SPECGRID          -- or DIMENS in some simulators
  NX  NY  NZ  1  F
/

METRIC            -- optional unit declaration

COORD             -- pillar geometry: (NX+1)×(NY+1) pillars × 6 values each
  x_top y_top z_top   x_bot y_bot z_bot
  ...
/

ZCORN             -- corner depths: NX×NY×NZ×8 values
  ...
/

ACTNUM            -- active cell flags: NX×NY×NZ integers (1 or 0)
  ...
/

END
```

---

## NW-Origin Convention (used in this project)

**Pillar indexing**: j=0 is the **northernmost** row; j increases southward.
i=0 is the **westernmost** column; i increases eastward.
k=0 is the **shallowest** (top) layer; k increases downward.

```python
pillar_xs = np.arange(minx, maxx + DX, DX)            # W→E, length NX+1
pillar_ys = np.arange(miny, maxy + DY, DY)[::-1]      # N→S, length NY+1 (flip!)
```

Cell (i, j) has corners on pillars:
| Corner | Pillar index | Note |
|--------|-------------|------|
| NW     | (i,   j  )  | north edge of cell |
| NE     | (i+1, j  )  | north edge of cell |
| SW     | (i,   j+1)  | south edge of cell |
| SE     | (i+1, j+1)  | south edge of cell |

---

## COORD Section

Each pillar is defined by a **top point** and a **bottom point** (x, y, z each).
For vertical pillars x and y are identical for top and bottom; only z changes.
z is depth positive downward (TVD).

**Loop order**: j outer (0 → NY), i inner (0 → NX):
```python
for j in range(NY + 1):
    for i in range(NX + 1):
        x, y = pillar_xs[i], pillar_ys[j]
        emit: x  y  z_top   x  y  z_bot
```

z_top = minimum depth on the pillar (shallowest); z_bot = maximum (deepest).

---

## ZCORN Section

Total values: `NX × NY × NZ × 8`

**Loop order** (strictly follow this):
```
for k in 0..NZ-1:
    for face in [top_of_layer_k, bottom_of_layer_k]:   # two passes
        for j in 0..NY-1:
            # sub-row 1: NW and NE corners for all cells in row j
            for i in 0..NX-1:  emit  z[j,   i]    z[j,   i+1]   # NW  NE
            # sub-row 2: SW and SE corners for all cells in row j
            for i in 0..NX-1:  emit  z[j+1, i]    z[j+1, i+1]  # SW  SE
```

NW/NE use `z_node[j, ...]` (north = smaller j index in NW-origin convention).
SW/SE use `z_node[j+1, ...]` (south = larger j index).

**Layer subdivision** (linear interpolation between top and bottom surfaces):
```python
layer_z = np.empty((NZ+1, NY+1, NX+1))
for lk in range(NZ+1):
    frac = lk / NZ
    layer_z[lk] = top_pillars + frac * (bot_pillars - top_pillars)
# layer k uses layer_z[k] (top face) and layer_z[k+1] (bottom face)
```

---

## ACTNUM Section

Loop order: **k outer, j middle, i fastest** (same as ZCORN cell order).
Run-length encoding is idiomatic: `10*1  5*0  3*1` etc.

```python
actnum_3d = np.broadcast_to(actnum_2d[np.newaxis,:,:], (NZ, NY, NX)).copy()
actnum_flat = actnum_3d.ravel()   # k-j-i order
```

ACTNUM=1 where: (a) cell centre is inside the region polygon AND (b) both depth surfaces are finite.

---

## Workflow for This Project

```
well_data.csv  +  california.shp
        │
        ▼
  interpolate.py          — Universal Kriging → output/interp_results.npz
        │                   (depth_top, depth_bot surfaces on a regular grid)
        ▼
  cpg_export.py           — builds COORD, ZCORN, ACTNUM → output/grid.grdecl
```

Run commands:
```bash
conda activate geoint
python interpolate.py      # only needed when well data or grid resolution changes
python cpg_export.py       # re-run whenever CPG_DX/DY/NZ or shapefile changes
```

Key config parameters in `config.py`:
| Parameter | Purpose |
|-----------|---------|
| `CPG_DX`, `CPG_DY` | Horizontal cell size (metres) |
| `CPG_NZ` | Number of vertical layers |
| `GRID_RESOLUTION_M` | Kriging grid cell size |
| `CRS_WORK` | Working CRS (`EPSG:3310` = NAD83/California Albers) |

---

## Common Pitfalls

- **`cell_cy` direction**: Use `(pillar_ys[:-1] + pillar_ys[1:]) / 2` (direction-agnostic midpoint), not `pillar_ys[:-1] + 0.5*DY` which assumes ascending y.
- **NaN pillars**: Fill NaNs before building `RegularGridInterpolator` (use `distance_transform_edt` nearest-neighbour fill) so ACTNUM=0 pillars still have finite coordinates.
- **ZCORN face order**: Top face of layer k must come before bottom face within the j-loop, not after all j-rows.
- **COORD z values**: `z_top = min(zs)`, `z_bot = max(zs)` — if a pillar is shared by many cells, take the global min/max across all z values registered to it.

---

## Reference Files
- [`cpg_export.py`](../../cpg_export.py) — canonical implementation for this project
- [`grid_nexus_to_ogs.py`](../../grid_nexus_to_ogs.py) — format converter showing BP/EDX → GRDECL, confirms NW-origin convention
