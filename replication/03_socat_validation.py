"""Partial re-run of the PRMT-CO2 vs SOCAT fCO2 validation (paper: r = -0.40, n = 244, P < 1e-4).

Limitation: Supplementary Table S4 only contains PRMT for 4 weeks of 2008, so only SOCAT
points falling inside those 4 weeks can be matched (paper used all 2008 weeks).

Matching rules (paper gives few details, so these are stated assumptions):
  * SOCAT v3 (2015; closest available release to the v2 used in the paper), WOCE flag 2 only
  * observation date within [week start, week start + 7 days)  (PRMT files are weekly "-AVERAGE")
  * hour 11:00-13:00 UTC (paper: "between 1100 and 1300 hours"; timezone not stated)
  * nearest grid-cell centre, accepted only if within half a cell (0.025 deg) in lat and lon
  * masked land / fill cells (see 02_maps_and_summary.py) excluded
"""
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "replication/results"
D = np.load(ROOT / "big_files/derived/prmt_2008.npz")
mask = np.load(ROOT / "replication/derived/fill_mask.npy")
mets = list(D["metabolites"]); co2 = D["scores"][:, :, mets.index("CO2")].astype(float)
co2[mask] = np.nan
lat, lon, weeks = D["lat"], D["lon"], pd.to_datetime(D["weeks"])
ulat, ulon = np.unique(lat), np.unique(lon)
cell_index = {(a, b): i for i, (a, b) in enumerate(zip(lat, lon))}

so = pd.read_csv(ROOT / "external_data/socat/socat_v3_WEC_2008.csv", skiprows=[1])
so["time"] = pd.to_datetime(so["time"]).dt.tz_localize(None)
so = so[(so.WOCE_CO2_water == 2) & so.fCO2_recommended.notna()]
print(f"SOCAT v3 WOCE-2 points in grid box, 2008: {len(so)} "
      f"(paper: 1798 overlapping points; boxes/filters not identical)")


def match(df, hour_window=True):
    out = []
    for w, ws in enumerate(weeks):
        sub = df[(df.time >= ws) & (df.time < ws + pd.Timedelta(days=7))]
        if hour_window:
            h = sub.time.dt.hour + sub.time.dt.minute / 60
            sub = sub[(h >= 11) & (h <= 13)]
        for r in sub.itertuples():
            ia = np.abs(ulat - r.latitude).argmin(); io = np.abs(ulon - r.longitude).argmin()
            if abs(ulat[ia] - r.latitude) > 0.0251 or abs(ulon[io] - r.longitude) > 0.0251:
                continue
            c = cell_index.get((ulat[ia], ulon[io]))
            if c is None or np.isnan(co2[w, c]):
                continue
            out.append(dict(week=str(ws.date()), cruise=r.expocode, time=r.time, lat=r.latitude,
                            lon=r.longitude, cell=c, fCO2=r.fCO2_recommended, prmt_co2=co2[w, c]))
    return pd.DataFrame(out)


def perm_p(x, y, n=10000, seed=0):
    rng = np.random.default_rng(seed)
    r0 = stats.pearsonr(x, y)[0]
    null = np.array([stats.pearsonr(x, rng.permutation(y))[0] for _ in range(n)])
    return r0, (np.sum(np.abs(null) >= abs(r0)) + 1) / (n + 1)


rows = []
for label, hw in [("11-13 UTC (paper rule)", True), ("all hours (sensitivity)", False)]:
    m = match(so, hw)
    if len(m) < 3:
        print(f"{label}: only {len(m)} matched points"); continue
    m.to_csv(RES / f"socat_matched_{'1113' if hw else 'allhours'}.csv", index=False)
    print(f"\n== {label}: {len(m)} matched obs, {m.cell.nunique()} distinct cells, "
          f"{m.cruise.nunique()} cruises; per week:\n{m.groupby('week').size().to_string()}")
    # (a) raw pooled correlation, as in the paper
    r, p = perm_p(m.prmt_co2.values, m.fCO2.values)
    rows.append(dict(set=label, analysis="pooled, raw fCO2", n=len(m), r=r, perm_p=p))
    # (b) fCO2 anomaly vs week mean of the matched obs (removes the seasonal offset)
    m["fCO2_anom"] = m.fCO2 - m.groupby("week").fCO2.transform("mean")
    m["prmt_anom"] = m.prmt_co2 - m.groupby("week").prmt_co2.transform("mean")
    r, p = perm_p(m.prmt_anom.values, m.fCO2_anom.values)
    rows.append(dict(set=label, analysis="within-week anomalies", n=len(m), r=r, perm_p=p))
    # (c) collapse to one value per cell-week (repeated obs in one cell share one PRMT value)
    g = m.groupby(["week", "cell"]).agg(fCO2=("fCO2", "mean"), prmt=("prmt_co2", "first")).reset_index()
    if len(g) >= 3:
        r, p = perm_p(g.prmt.values, g.fCO2.values)
        rows.append(dict(set=label, analysis="cell-week means (pseudoreplication reduced)",
                         n=len(g), r=r, perm_p=p))
    for wk, gw in m.groupby("week"):
        if len(gw) >= 5 and gw.prmt_co2.std() > 0:
            r, p = perm_p(gw.prmt_co2.values, gw.fCO2.values, n=2000)
            rows.append(dict(set=label, analysis=f"within week {wk}", n=len(gw), r=r, perm_p=p))

res = pd.DataFrame(rows)
res.to_csv(RES / "socat_validation_correlations.csv", index=False)
print("\n", res.round(4).to_string(index=False))
