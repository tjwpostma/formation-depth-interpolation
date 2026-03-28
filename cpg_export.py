"""
cpg_export.py — Build an Eclipse-format corner-point grid (GRDECL) from the
interpolated depth_top and depth_bot surfaces and write it to output/grid.grdecl.

Grid geometry:
  • Regular rectangular pillars (perfectly vertical) aligned to CPG_DX / CPG_DY
  • Origin at the SW corner of the shapefile bounding box (EPSG:3310)
  • NX × NY columns, CPG_NZ layers subdivided linearly between top and bot surfaces
  • ACTNUM = 1 where the column centre is inside the shapefile AND both surface
    values are finite; ACTNUM = 0 otherwise

GRDECL sections written:
  SPECGRID  NX NY NZ 1 F
  METRIC    (depths in metres)
  COORD     6 values per pillar  (NX+1)×(NY+1) pillars, row-major (X fastest)
  ZCORN     8 corner depths per cell, NX×NY×NZ cells
  ACTNUM    NX×NY×NZ integers (1 or 0)
  END

Run:
    conda activate geoint
    python cpg_export.py
"""

import os
import numpy as np
import geopandas as gpd
from shapely.geometry import Point
from shapely.ops import unary_union
from scipy.interpolate import RegularGridInterpolator

import config

# ── Load interpolation results ────────────────────────────────────────────────
npz_path = os.path.join(config.OUT_DIR, "interp_results.npz")
if not os.path.exists(npz_path):
    raise FileNotFoundError(
        f"'{npz_path}' not found — run interpolate.py first."
    )

data      = np.load(npz_path, allow_pickle=True)
xs        = data["xs"]           # 1-D easting  of kriging grid
ys        = data["ys"]           # 1-D northing of kriging grid
depth_top = data["depth_top"]    # (ny, nx)
depth_bot = data["depth_bot"]    # (ny, nx)
porosity  = data["porosity"]     # (ny, nx)  vertically-averaged

# ── Build interpolators from kriging grid to CPG grid ─────────────────────────
# RegularGridInterpolator expects (y, x) ordering which matches (row, col)
# Fill NaN with nearest valid value before building interpolators so that
# extrapolation into ACTNUM=0 pillars still produces finite pillar coordinates.

def fill_nans_nearest(arr):
    """Replace NaN in a 2-D array with the nearest non-NaN neighbour."""
    from scipy.ndimage import distance_transform_edt
    nan_mask = np.isnan(arr)
    if not nan_mask.any():
        return arr
    filled = arr.copy()
    _, indices = distance_transform_edt(
        nan_mask, return_distances=True, return_indices=True
    )
    filled[nan_mask] = arr[indices[0][nan_mask], indices[1][nan_mask]]
    return filled

top_filled  = fill_nans_nearest(depth_top)
bot_filled  = fill_nans_nearest(depth_bot)
poro_filled = fill_nans_nearest(porosity)

# ys is in ascending order (south→north); RegularGridInterpolator requires
# strictly increasing axes — ys must already be ascending from np.arange.
interp_top = RegularGridInterpolator(
    (ys, xs), top_filled, method="linear", bounds_error=False, fill_value=None
)
interp_bot = RegularGridInterpolator(
    (ys, xs), bot_filled, method="linear", bounds_error=False, fill_value=None
)
interp_poro = RegularGridInterpolator(
    (ys, xs), poro_filled, method="linear", bounds_error=False, fill_value=None
)

# ── Load shapefile for ACTNUM mask ────────────────────────────────────────────
print("Loading shapefile …")
region_gdf  = gpd.read_file(config.SHAPEFILE).to_crs(config.CRS_WORK)
region_geom = unary_union(region_gdf.geometry)
minx, miny, maxx, maxy = region_geom.bounds

# ── CPG grid dimensions ───────────────────────────────────────────────────────
DX = config.CPG_DX
DY = config.CPG_DY
NZ = config.CPG_NZ

# Pillar node coordinates (NX+1 × NY+1 nodes)
pillar_xs = np.arange(minx, maxx + DX, DX)
pillar_ys = np.arange(miny, maxy + DY, DY)[::-1]  # N→S: j=0 is northernmost
NX        = len(pillar_xs) - 1
NY        = len(pillar_ys) - 1

print(f"CPG grid: NX={NX}, NY={NY}, NZ={NZ}  "
      f"(DX={DX} m, DY={DY} m)  →  {NX * NY * NZ} cells")

# Cell-centre coordinates used for ACTNUM test
cell_cx = pillar_xs[:-1] + 0.5 * DX                     # (NX,)
cell_cy = (pillar_ys[:-1] + pillar_ys[1:]) / 2.0        # (NY,) direction-agnostic midpoint

# Evaluate surfaces at every pillar node for COORD and at cell centres  for ZCORN
# Pillar mesh (NY+1, NX+1)
pxx, pyy    = np.meshgrid(pillar_xs, pillar_ys)   # shape (NY+1, NX+1)
pts_pillars = np.column_stack([pyy.ravel(), pxx.ravel()])   # (y, x) pairs
top_pillars = interp_top(pts_pillars).reshape(NY + 1, NX + 1)
bot_pillars = interp_bot(pts_pillars).reshape(NY + 1, NX + 1)

# Cell-centre mesh (NY, NX) for ZCORN bilinear corners and ACTNUM
cxx, cyy     = np.meshgrid(cell_cx, cell_cy)       # shape (NY, NX)
pts_centres  = np.column_stack([cyy.ravel(), cxx.ravel()])
top_centres  = interp_top(pts_centres).reshape(NY, NX)
bot_centres  = interp_bot(pts_centres).reshape(NY, NX)
poro_centres = interp_poro(pts_centres).reshape(NY, NX)

# ── ACTNUM ────────────────────────────────────────────────────────────────────
print("Computing ACTNUM …")
pts_geom = gpd.GeoSeries(
    [Point(x, y) for x, y in zip(cxx.ravel(), cyy.ravel())],
    crs=config.CRS_WORK,
)
inside = pts_geom.within(region_geom).values.reshape(NY, NX)  # (NY, NX)
valid  = np.isfinite(top_centres) & np.isfinite(bot_centres)
actnum_2d = (inside & valid).astype(np.int32)                 # (NY, NX)

# Replicate to NZ layers: shape (NZ, NY, NX), then ravel in (k, j, i) order
# Eclipse ACTNUM is listed k-slowest, j-middle, i-fastest (i = X-direction)
actnum_3d = np.broadcast_to(actnum_2d[np.newaxis, :, :], (NZ, NY, NX)).copy()
actnum_flat = actnum_3d.ravel()   # length NX*NY*NZ, k-j-i order

n_active = int(actnum_flat.sum())
print(f"  Active cells: {n_active} / {NX * NY * NZ} "
      f"({100 * n_active / (NX * NY * NZ):.1f} %)")

# ── COORD ─────────────────────────────────────────────────────────────────────
# Each pillar: [x_top, y_top, z_top,  x_bot, y_bot, z_bot]
# Pillars are vertical so x and y are the same for top and bottom.
# Eclipse convention: z increases downward (positive = depth).
# Order: j-slowest (Y), i-fastest (X)  →  pillar_ys outer loop, pillar_xs inner
# j=0 is the northernmost row (pillar_ys descends N→S)

print("Building COORD …")
coord_list = []
for j in range(NY + 1):
    for i in range(NX + 1):
        x   = pillar_xs[i]
        y   = pillar_ys[j]
        zt  = float(top_pillars[j, i])
        zb  = float(bot_pillars[j, i])
        coord_list.extend([x, y, zt, x, y, zb])

coord_array = np.array(coord_list, dtype=np.float64)

# ── ZCORN ─────────────────────────────────────────────────────────────────────
# Eclipse ZCORN ordering:
#   for k in range(NZ):            — layer (top-surface first)
#     for j in range(NY):
#       top face of row j — two z values per cell in X direction
#         left corner then right corner, for each cell i
#       (top face = 2 values per cell × NX cells per row, upper then lower Y)
#
# More precisely, for each layer k, each cell (i,j) has 8 corners arranged as:
#   4 corners of the top face (k_top), then 4 of the bottom face (k_bot)
# Eclipse ZCORN is listed in the following bit pattern per layer:
#   for j in NY rows:
#     upper-tops of row j:   zz[i, j, k, top,  NW] zz[i, j, k, top,  NE]  (i = 0..NX-1)
#     lower-tops of row j:   zz[i, j, k, top,  SW] zz[i, j, k, top,  SE]
#   for j in NY rows:
#     upper-bots of row j:   zz[i, j, k, bot,  NW] zz[i, j, k, bot,  NE]
#     lower-bots of row j:   zz[i, j, k, bot,  SW] zz[i, j, k, bot,  SE]
#
# For vertical pillars at grid nodes the corner depths are simply interpolated
# from the pillar node values at the four corners of the (i,j) cell.
# NW-origin convention (j=0 north, j increases southward):
#   NW corner = pillar (i,   j  )  — north edge of cell
#   NE corner = pillar (i+1, j  )  — north edge of cell
#   SW corner = pillar (i,   j+1)  — south edge of cell
#   SE corner = pillar (i+1, j+1)  — south edge of cell

print("Building ZCORN …")

# Pre-compute pillar top / bot at every (j, i) node.
# top_pillars[j, i] and bot_pillars[j, i] already computed above.

# Layer fractions: layer k spans [k/NZ, (k+1)/NZ] of (top→bot) interval
# For each cell column (i,j) the top-surface depth of layer k is:
#   z_top_k(i,j) = top + k/NZ * (bot - top)
# and the bottom-surface depth of the same layer is:
#   z_bot_k(i,j) = top + (k+1)/NZ * (bot - top)

# Build the per-layer top/bot depth arrays at pillar nodes: shape (NZ+1, NY+1, NX+1)
layer_z = np.empty((NZ + 1, NY + 1, NX + 1), dtype=np.float64)
for lk in range(NZ + 1):
    frac = lk / NZ
    layer_z[lk] = top_pillars + frac * (bot_pillars - top_pillars)

# Assemble ZCORN — pre-allocate the full array for speed
# Total values = NZ layers × NY rows × (2 z-values for top face + 2 for bot face) × NX cells
# = NX * NY * NZ * 8
zcorn = np.empty(NX * NY * NZ * 8, dtype=np.float64)
idx = 0

for k in range(NZ):
    # Top face of layer k uses layer_z[k], bottom face uses layer_z[k+1]
    for face, lk in enumerate([k, k + 1]):
        z_node = layer_z[lk]   # shape (NY+1, NX+1)
        for j in range(NY):
            # "upper" sub-row: j (North edge of cell, j=0 is north)
            for i in range(NX):
                zcorn[idx]     = z_node[j, i]            # NW corner
                zcorn[idx + 1] = z_node[j, i + 1]        # NE corner
                idx += 2
            # "lower" sub-row: j+1 (South edge of cell)
            for i in range(NX):
                zcorn[idx]     = z_node[j + 1, i]        # SW corner
                zcorn[idx + 1] = z_node[j + 1, i + 1]    # SE corner
                idx += 2

# ── Write GRDECL ──────────────────────────────────────────────────────────────
out_path = os.path.join(config.OUT_DIR, config.CPG_FILENAME)
print(f"Writing GRDECL → {out_path} …")

VALS_PER_LINE = 6   # Eclipse convention: 6 numbers per line

def write_array_section(fh, keyword, arr, fmt="{:.4f}"):
    fh.write(f"{keyword}\n")
    line_vals = []
    for v in arr:
        line_vals.append(fmt.format(v))
        if len(line_vals) == VALS_PER_LINE:
            fh.write("  " + "  ".join(line_vals) + "\n")
            line_vals = []
    if line_vals:
        fh.write("  " + "  ".join(line_vals) + "\n")
    fh.write("/\n\n")

def write_int_array_section(fh, keyword, arr):
    fh.write(f"{keyword}\n")
    # Use run-length encoding to keep file size manageable
    from itertools import groupby
    tokens = []
    for val, grp in groupby(arr):
        count = sum(1 for _ in grp)
        if count == 1:
            tokens.append(str(int(val)))
        else:
            tokens.append(f"{count}*{int(val)}")
    line_tokens = []
    for t in tokens:
        line_tokens.append(t)
        if len(line_tokens) == 10:
            fh.write("  " + "  ".join(line_tokens) + "\n")
            line_tokens = []
    if line_tokens:
        fh.write("  " + "  ".join(line_tokens) + "\n")
    fh.write("/\n\n")

with open(out_path, "w") as fh:
    fh.write("-- Corner-point grid generated by cpg_export.py\n")
    fh.write(f"-- CRS: {config.CRS_WORK}\n")
    fh.write(f"-- Grid: NX={NX}  NY={NY}  NZ={NZ}  DX={DX} m  DY={DY} m\n")
    fh.write(f"-- Active cells: {n_active}\n\n")

    fh.write(f"SPECGRID\n  {NX}  {NY}  {NZ}  1  F\n/\n\n")
    fh.write("METRIC\n\n")

    write_array_section(fh, "COORD", coord_array)
    write_array_section(fh, "ZCORN", zcorn)
    write_int_array_section(fh, "ACTNUM", actnum_flat)

    # PORO — vertically-averaged porosity; constant for all k at each (i,j)
    # ACTNUM=0 cells receive 0.0 (simulator convention)
    poro_2d_clean = np.where(actnum_2d, poro_centres, 0.0)           # (NY, NX)
    poro_3d       = np.broadcast_to(
        poro_2d_clean[np.newaxis, :, :], (NZ, NY, NX)
    ).copy()
    poro_flat = poro_3d.ravel()   # k-j-i order, matches ACTNUM
    write_array_section(fh, "PORO", poro_flat, fmt="{:.6f}")

    fh.write("END\n")

print(f"GRDECL file written: {out_path}")
print(f"  COORD entries : {len(coord_array)}")
print(f"  ZCORN entries : {len(zcorn)}")
print(f"  ACTNUM entries: {len(actnum_flat)}")
print("Done.")
