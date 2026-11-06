"""Figure 2 (row 4) analogue + spatial maps of the six cluster-representative metabolites.

Inputs: big_files/derived/prmt_2008.npz (from 01_load_prmt.py)
Outputs: replication/figures/*.png, replication/results/*.csv

PRMT sign convention (paper): positive = relative consumption, negative = relative
production/accumulation. Colour: red = consumption, blue = accumulation (as in the paper).
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm

ROOT = Path(__file__).resolve().parents[1]
D = np.load(ROOT / "big_files/derived/prmt_2008.npz", allow_pickle=False)
S, weeks, lat, lon, mets = D["scores"], D["weeks"], D["lat"], D["lon"], list(D["metabolites"])
FIG = ROOT / "replication/figures"; FIG.mkdir(parents=True, exist_ok=True)
RES = ROOT / "replication/results"; RES.mkdir(parents=True, exist_ok=True)

CMAP = LinearSegmentedColormap.from_list(
    "bu_gy_rd", ["#1c5cab", "#86b6ef", "#f0efec", "#ef9a86", "#b8322c"])
ulat, ulon = np.unique(lat), np.unique(lon)
ilat, ilon = np.searchsorted(ulat, lat), np.searchsorted(ulon, lon)
WEEK_LABEL = {"2008-03-17": "17 Mar 2008", "2008-06-23": "23 Jun 2008",
              "2008-09-22": "22 Sep 2008", "2008-12-08": "8 Dec 2008"}


# --- coastline (Natural Earth 10m, clipped to grid box) and fill-cell mask -----
import json

_coast = []
for f in json.load(open(ROOT / "external_data/naturalearth/ne_10m_coastline.geojson"))["features"]:
    geoms = f["geometry"]["coordinates"]
    geoms = [geoms] if f["geometry"]["type"] == "LineString" else geoms
    for g in geoms:
        g = np.asarray(g)
        if ((g[:, 0] > -8) & (g[:, 0] < -1) & (g[:, 1] > 48) & (g[:, 1] < 51.2)).any():
            _coast.append(g)

# Cells whose full 2893-metabolite profile is identical to ~760 other cells in every week.
# They sit on Brittany / SW England, so they are treated as land / no-SIM fill and masked.
def fill_mask(Sw):
    _, inv, c = np.unique(np.round(np.nan_to_num(Sw), 6), axis=0, return_inverse=True, return_counts=True)
    return inv.ravel() == np.argmax(c)
MASK = np.stack([fill_mask(S[w]) for w in range(S.shape[0])])
print("masked fill cells per week:", MASK.sum(axis=1))
np.save(ROOT / "replication/derived/fill_mask.npy", MASK)
S = np.where(MASK[:, :, None], np.nan, S)


def grid(v):
    g = np.full((len(ulat), len(ulon)), np.nan)
    g[ilat, ilon] = v
    return g


def draw(ax, v, vmax, title):
    m = ax.pcolormesh(ulon, ulat, grid(v), cmap=CMAP, shading="nearest",
                      norm=TwoSlopeNorm(0, -vmax, vmax))
    for g in _coast:
        ax.plot(g[:, 0], g[:, 1], color="#333333", lw=0.6)
    ax.set_xlim(ulon[0] - 0.03, ulon[-1] + 0.03); ax.set_ylim(ulat[0] - 0.03, ulat[-1] + 0.03)
    ax.set_title(title, fontsize=9)
    ax.set_aspect(1 / np.cos(np.deg2rad(49.6)))
    ax.tick_params(labelsize=7)
    return m


def robust_vmax(x):
    x = x[np.isfinite(x)]
    return float(np.percentile(np.abs(x), 98)) or 1e-9


# ---- QC: NaNs and constant (likely no-SIM / land) cells ----------------------
nan_cells = np.isnan(S).any(axis=2)
print("cells with any NaN per week:", nan_cells.sum(axis=1))
nan_mets = np.isnan(S).any(axis=(0, 1))
print("metabolites with any NaN:", [mets[i] for i in np.where(nan_mets)[0]][:20], nan_mets.sum())
for w, wk in enumerate(weeks):
    _, counts = np.unique(np.round(S[w], 6), axis=0, return_counts=True)
    print(f"{wk}: distinct cell profiles {len(counts)}; largest group of identical cells {counts.max()}")

# ---- Figure 2 row 4: CO2 PRMT for the four weeks ------------------------------
co2 = mets.index("CO2")
vmax = robust_vmax(S[:, :, co2])
fig, axes = plt.subplots(1, 4, figsize=(15, 3.2), constrained_layout=True)
for w, ax in enumerate(axes):
    m = draw(ax, S[w, :, co2], vmax, f"CO$_2$ PRMT, week of {WEEK_LABEL[weeks[w]]}")
fig.colorbar(m, ax=axes, shrink=0.8, label="PRMT score\n(red: consumption,\nblue: accumulation)")
fig.savefig(FIG / "fig2_row4_CO2_PRMT_maps.png", dpi=160)
plt.close(fig)

# Channel-wide summary for CO2 per week
rows = []
for w, wk in enumerate(weeks):
    x = S[w, :, co2]
    rows.append(dict(week=wk, mean=np.nanmean(x), median=np.nanmedian(x), sd=np.nanstd(x),
                     frac_negative=np.mean(x[np.isfinite(x)] < 0), frac_positive=np.mean(x[np.isfinite(x)] > 0)))
co2_tab = pd.DataFrame(rows)
co2_tab.to_csv(RES / "co2_prmt_weekly_summary.csv", index=False)
print("\nCO2 PRMT channel summary\n", co2_tab.round(4).to_string(index=False))

# Spatial similarity of CO2 maps between weeks (paper: gene maps similar in Mar & Dec,
# CO2 PRMT maps do not mirror this)
cc = pd.DataFrame(np.corrcoef(np.nan_to_num(S[:, :, co2])), index=weeks, columns=weeks)
cc.to_csv(RES / "co2_prmt_between_week_spatial_correlation.csv")
print("\nSpatial Pearson r of CO2 PRMT maps between weeks\n", cc.round(3))

# ---- Six representative metabolites (paper Fig 3/4 used these) ----------------
REP = [("Trimethylamine_N-oxide", "TMAO (cluster i)"),
       ("Phosphatidylethanolamine", "Phosphatidylethanolamine (ii)"),
       ("Methanethiol", "Methanethiol (iii)"),
       ("Phosphonoacetate", "Phosphonoacetate (iv)"),
       ("Acetate", "Acetate (v)"),
       ("CO2", "CO$_2$ (vi)")]
fig, axes = plt.subplots(len(REP), 4, figsize=(15, 3.0 * len(REP)), constrained_layout=True)
summary = []
for r, (name, label) in enumerate(REP):
    j = mets.index(name)
    vmax = robust_vmax(S[:, :, j])
    for w in range(4):
        m = draw(axes[r, w], S[w, :, j], vmax, f"{label} — {WEEK_LABEL[weeks[w]]}")
        x = S[w, :, j]
        summary.append(dict(metabolite=name, week=weeks[w], mean=np.nanmean(x),
                            sd=np.nanstd(x), frac_positive=np.mean(x[np.isfinite(x)] > 0)))
    fig.colorbar(m, ax=axes[r, :], shrink=0.8, label="PRMT")
fig.savefig(FIG / "representative_metabolites_4weeks_2008.png", dpi=130)
plt.close(fig)
rep = pd.DataFrame(summary)
rep.to_csv(RES / "representative_metabolites_weekly_summary.csv", index=False)
print("\nRepresentative metabolites: channel mean PRMT by week\n",
      rep.pivot(index="metabolite", columns="week", values="mean").round(4))
