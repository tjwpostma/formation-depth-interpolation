"""
interpolate.py — Reproject wells and shapefile to EPSG:3310, run Universal
Kriging on depth_top and thickness, apply the shapefile mask, and save
all results to output/interp_results.npz.

Run:
    conda activate geoint
    python interpolate.py
"""

import os
import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point, MultiPoint
from shapely.ops import unary_union
from pykrige.uk import UniversalKriging

import config

# ── 0. Ensure output directory exists ─────────────────────────────────────────
os.makedirs(config.OUT_DIR, exist_ok=True)

# ── 1. Load and reproject well data ───────────────────────────────────────────
print("Loading well data …")
df = pd.read_csv(config.WELL_CSV)

well_gdf = gpd.GeoDataFrame(
    df,
    geometry=gpd.points_from_xy(df["lon"], df["lat"]),
    crs=config.CRS_INPUT,
)
well_gdf = well_gdf.to_crs(config.CRS_WORK)

print(f"  {len(well_gdf)} wells reprojected to {config.CRS_WORK}")

# ── Deduplicate wells at identical projected locations ─────────────────────────
# (Duplicate lat/lon records produce a singular kriging matrix)
well_gdf["_x"] = well_gdf.geometry.x.round(1)
well_gdf["_y"] = well_gdf.geometry.y.round(1)
n_before = len(well_gdf)
well_gdf = (
    well_gdf
    .groupby(["_x", "_y"], as_index=False)
    .agg(
        well_id   = ("well_id",    lambda s: "+".join(s)),
        lat       = ("lat",        "mean"),
        lon       = ("lon",        "mean"),
        depth_top = ("depth_top",  "mean"),
        depth_bot = ("depth_bot",  "mean"),
        thickness = ("thickness",  "mean"),
        porosity  = ("porosity",   "mean"),
        geometry  = ("geometry",   "first"),
    )
)
well_gdf = gpd.GeoDataFrame(well_gdf, geometry="geometry", crs=config.CRS_WORK)
n_after = len(well_gdf)
if n_before != n_after:
    print(f"  Deduplicated {n_before} → {n_after} wells (averaged co-located records)")

wx = well_gdf.geometry.x.values
wy = well_gdf.geometry.y.values
depth_top_vals = well_gdf["depth_top"].values.astype(float)
thickness_vals = well_gdf["thickness"].values.astype(float)
porosity_vals  = well_gdf["porosity"].values.astype(float)
well_ids       = well_gdf["well_id"].values

print(f"  Easting  range: {wx.min():.0f} – {wx.max():.0f} m")
print(f"  Northing range: {wy.min():.0f} – {wy.max():.0f} m")

# ── 2. Load and reproject shapefile ───────────────────────────────────────────
print("Loading shapefile …")
region_gdf = gpd.read_file(config.SHAPEFILE).to_crs(config.CRS_WORK)
region_geom = unary_union(region_gdf.geometry)   # single (Multi)Polygon

minx, miny, maxx, maxy = region_geom.bounds
print(f"  Region bounds (m): E {minx:.0f}–{maxx:.0f}  N {miny:.0f}–{maxy:.0f}")

# ── 3. Build regular interpolation grid ───────────────────────────────────────
res = config.GRID_RESOLUTION_M
xs = np.arange(minx, maxx + res, res)
ys = np.arange(miny, maxy + res, res)
xx, yy = np.meshgrid(xs, ys)   # shape (ny, nx)
nx, ny = len(xs), len(ys)

print(f"  Grid: {nx} × {ny} = {nx * ny} cells at {res} m resolution")

# ── 4. Compute in-region mask via vectorised point-in-polygon ─────────────────
print("Computing shapefile mask …")
flat_pts   = np.column_stack([xx.ravel(), yy.ravel()])
pts_series = gpd.GeoSeries(
    [Point(x, y) for x, y in flat_pts], crs=config.CRS_WORK
)
mask_flat = pts_series.within(region_geom).values          # bool array
mask      = mask_flat.reshape(xx.shape)                    # (ny, nx)

print(f"  {mask.sum()} / {mask.size} grid points are inside the region "
      f"({100 * mask.mean():.1f} %)")

# ── 5. Universal Kriging — depth_top ──────────────────────────────────────────
print("Kriging depth_top …")
uk_top = UniversalKriging(
    wx, wy, depth_top_vals,
    variogram_model=config.VARIOGRAM_MODEL,
    drift_terms=config.DRIFT_TERMS,
    nlags=config.VARIOGRAM_NLAGS,
    verbose=False,
    enable_plotting=False,
)

z_top_flat, ss_top_flat = uk_top.execute(
    "points",
    flat_pts[:, 0],
    flat_pts[:, 1],
)
z_top = z_top_flat.reshape(xx.shape)
ss_top = ss_top_flat.reshape(xx.shape)

# ── 6. Universal Kriging — thickness ──────────────────────────────────────────
print("Kriging thickness …")
uk_thick = UniversalKriging(
    wx, wy, thickness_vals,
    variogram_model=config.VARIOGRAM_MODEL,
    drift_terms=config.DRIFT_TERMS,
    nlags=config.VARIOGRAM_NLAGS,
    verbose=False,
    enable_plotting=False,
)

z_thick_flat, ss_thick_flat = uk_thick.execute(
    "points",
    flat_pts[:, 0],
    flat_pts[:, 1],
)
z_thick = z_thick_flat.reshape(xx.shape)
ss_thick = ss_thick_flat.reshape(xx.shape)

# ── 7. Universal Kriging — porosity ──────────────────────────────────────────
print("Kriging porosity …")
uk_poro = UniversalKriging(
    wx, wy, porosity_vals,
    variogram_model=config.VARIOGRAM_MODEL,
    drift_terms=config.DRIFT_TERMS,
    nlags=config.VARIOGRAM_NLAGS,
    verbose=False,
    enable_plotting=False,
)

z_poro_flat, ss_poro_flat = uk_poro.execute(
    "points",
    flat_pts[:, 0],
    flat_pts[:, 1],
)
z_poro  = z_poro_flat.reshape(xx.shape)
ss_poro = ss_poro_flat.reshape(xx.shape)

# ── 8. Derive depth_bot; apply mask ───────────────────────────────────────────
z_bot = z_top + z_thick

# NaN outside the region (do NOT modify in-region values)
z_top_masked   = np.where(mask, z_top,   np.nan)
z_bot_masked   = np.where(mask, z_bot,   np.nan)
z_thick_masked = np.where(mask, z_thick, np.nan)
ss_top_masked  = np.where(mask, ss_top,  np.nan)
ss_thick_masked= np.where(mask, ss_thick,np.nan)
poro_masked    = np.where(mask, z_poro,  np.nan)
ss_poro_masked = np.where(mask, ss_poro, np.nan)

# ── 9. Sanity checks ──────────────────────────────────────────────────────────
err = np.abs(z_bot_masked - z_top_masked - z_thick_masked)
max_err = np.nanmax(err)
assert max_err < 1e-6, f"depth_bot - depth_top != thickness (max err = {max_err})"
print(f"  Sanity check passed: max |depth_bot - depth_top - thickness| = {max_err:.2e} m")

# Volume estimates (m³)
cell_area_m2 = res * res
volume_m3    = float(np.nansum(z_thick_masked) * cell_area_m2)
pore_vol_m3  = float(np.nansum(z_thick_masked * poro_masked) * cell_area_m2)
print(f"  Estimated rock volume: {volume_m3:.4e} m³  ({volume_m3 / 1e9:.4f} km³)")
print(f"  Estimated pore volume: {pore_vol_m3:.4e} m³  ({pore_vol_m3 / 1e9:.4f} km³)")

# ── 10. Save results ──────────────────────────────────────────────────────────
out_path = os.path.join(config.OUT_DIR, "interp_results.npz")
np.savez_compressed(
    out_path,
    xs=xs, ys=ys,
    xx=xx, yy=yy,
    mask=mask,
    depth_top=z_top_masked,
    depth_bot=z_bot_masked,
    thickness=z_thick_masked,
    ss_top=ss_top_masked,
    ss_thick=ss_thick_masked,
    porosity=poro_masked,
    ss_poro=ss_poro_masked,
    wx=wx, wy=wy,
    depth_top_vals=depth_top_vals,
    thickness_vals=thickness_vals,
    porosity_vals=porosity_vals,
    well_ids=well_ids,
    grid_res=np.array([res]),
    volume_m3=np.array([volume_m3]),
    pore_vol_m3=np.array([pore_vol_m3]),
)
print(f"\nResults saved → {out_path}")
print("Done. Run plot_maps.py and cpg_export.py next.")
