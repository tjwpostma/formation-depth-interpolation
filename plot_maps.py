"""
plot_maps.py — Load interpolation results and produce four maps:
  • map_depth_top.png
  • map_depth_bot.png
  • map_thickness.png
  • map_porosity.png
Also prints total formation rock volume and pore volume.
"""

import os
import numpy as np
import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from matplotlib.colors import Normalize
from matplotlib.cm import ScalarMappable

import config

# ── Load results ──────────────────────────────────────────────────────────────
npz_path = os.path.join(config.OUT_DIR, "interp_results.npz")
if not os.path.exists(npz_path):
    raise FileNotFoundError(
        f"'{npz_path}' not found — run interpolate.py first."
    )

data = np.load(npz_path, allow_pickle=True)
xx        = data["xx"]
yy        = data["yy"]
mask      = data["mask"]
depth_top = data["depth_top"]
depth_bot = data["depth_bot"]
thickness = data["thickness"]
porosity  = data["porosity"]
wx        = data["wx"]
wy        = data["wy"]
well_ids  = data["well_ids"]
res       = float(data["grid_res"][0])
volume_m3    = float(data["volume_m3"][0])
pore_vol_m3  = float(data["pore_vol_m3"][0])

# ── Report volumes ─────────────────────────────────────────────────────────────
print(f"Formation rock volume: {volume_m3:.4e} m³  ({volume_m3 / 1e9:.4f} km³)")
print(f"Formation pore volume: {pore_vol_m3:.4e} m³  ({pore_vol_m3 / 1e9:.4f} km³)")

# ── Load shapefile boundary for overlay ───────────────────────────────────────
region_gdf = gpd.read_file(config.SHAPEFILE).to_crs(config.CRS_WORK)

# ── Helper: convert metres to km for axis labels ──────────────────────────────
def m2km(x, _=None):
    return f"{x / 1000:.0f}"

# ── Generic map function ──────────────────────────────────────────────────────
def make_map(grid, title, cbar_label, cmap, contour_interval, out_fname):
    fig, ax = plt.subplots(figsize=(10, 12), dpi=config.MAP_DPI)

    # Pcolormesh (mask NaN = transparent)
    cmap_obj = plt.get_cmap(cmap).copy()
    cmap_obj.set_bad(color="lightgrey", alpha=0.4)

    vmin = np.nanmin(grid)
    vmax = np.nanmax(grid)
    norm = Normalize(vmin=vmin, vmax=vmax)

    mesh = ax.pcolormesh(xx, yy, grid, cmap=cmap_obj, norm=norm,
                         shading="auto", zorder=1)

    # Contours on valid cells only
    levels = np.arange(
        np.floor(vmin / contour_interval) * contour_interval,
        np.ceil(vmax / contour_interval) * contour_interval + contour_interval,
        contour_interval,
    )
    try:
        cs = ax.contour(xx, yy, grid, levels=levels,
                        colors="black", linewidths=0.5, alpha=0.6, zorder=2)
        fmt_str = "%g m" if contour_interval >= 1 else "%.3f"
        ax.clabel(cs, inline=True, fontsize=7, fmt=fmt_str)
    except Exception:
        pass  # contours may fail if grid is too sparse

    # Shapefile boundary
    region_gdf.boundary.plot(ax=ax, color="black", linewidth=1.2, zorder=3)

    # Well locations
    ax.scatter(wx, wy, c="red", s=30, zorder=5, label="Wells")
    for wid, x, y in zip(well_ids, wx, wy):
        ax.annotate(wid, (x, y), textcoords="offset points",
                    xytext=(4, 4), fontsize=6, color="darkred", zorder=6)

    # Axes formatting
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(m2km))
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(m2km))
    ax.set_xlabel("Easting (km, EPSG:3310)")
    ax.set_ylabel("Northing (km, EPSG:3310)")
    ax.set_title(title, fontsize=13, fontweight="bold")
    ax.legend(loc="lower right", fontsize=8)

    # Colorbar
    sm = ScalarMappable(cmap=cmap_obj, norm=norm)
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=ax, fraction=0.03, pad=0.02)
    cbar.set_label(cbar_label, fontsize=10)

    plt.tight_layout()
    out_path = os.path.join(config.OUT_DIR, out_fname)
    fig.savefig(out_path, dpi=config.MAP_DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved → {out_path}")


# ── Produce the three maps ────────────────────────────────────────────────────
print("Generating maps …")

make_map(
    grid=depth_top,
    title="Depth to Top of Formation (m below surface)",
    cbar_label="Depth (m)",
    cmap="viridis_r",
    contour_interval=config.CONTOUR_INTERVAL_DEPTH,
    out_fname="map_depth_top.png",
)

make_map(
    grid=depth_bot,
    title="Depth to Bottom of Formation (m below surface)",
    cbar_label="Depth (m)",
    cmap="viridis_r",
    contour_interval=config.CONTOUR_INTERVAL_DEPTH,
    out_fname="map_depth_bot.png",
)

make_map(
    grid=thickness,
    title="Formation Thickness (m)",
    cbar_label="Thickness (m)",
    cmap="YlOrRd",
    contour_interval=config.CONTOUR_INTERVAL_THICKNESS,
    out_fname="map_thickness.png",
)

make_map(
    grid=porosity,
    title="Vertically-Averaged Porosity (fraction)",
    cbar_label="Porosity (fraction)",
    cmap="Blues",
    contour_interval=0.01,
    out_fname="map_porosity.png",
)

print("All maps saved.")
