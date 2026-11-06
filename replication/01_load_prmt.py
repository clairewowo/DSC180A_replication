"""Load Supplementary Table S4 (PRMT scores, 4 weekly averages of 2008) into one array.

Input:  big_files/S4-AllPRMTscores/<WEEK>_PRMTscores.txt (large; gitignored)
Output: big_files/derived/prmt_2008.npz (large; gitignored) with
    scores  : float32 [week, cell, metabolite]
    weeks   : week-start dates (ISO)
    lat, lon: per cell (cells sorted by lat, lon so all weeks align)
    metabolites
"""
import re
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "big_files" / "S4-AllPRMTscores"
OUT = ROOT / "big_files" / "derived"
OUT.mkdir(parents=True, exist_ok=True)

FILES = ["MAR", "JUN", "AUG", "DEC"]  # NB: the "AUG" file is dated 2008-09-22
pat = re.compile(r"(\d{4}-\d{2}-\d{2})T[^,]*,([-\d.]+),([-\d.]+)")

arrays, weeks, ref_keys, metabolites = [], [], None, None
for f in FILES:
    df = pd.read_csv(SRC / f"{f}_PRMTscores.txt", sep="\t", index_col=0)
    parsed = df.index.to_series().str.extract(pat)
    assert parsed.notna().all().all(), f"unparsed row labels in {f}"
    date = parsed[0].unique()
    assert len(date) == 1, f"{f}: multiple dates {date}"
    df.index = pd.MultiIndex.from_arrays(
        [parsed[1].astype(float).round(2).values, parsed[2].astype(float).round(2).values],
        names=["lat", "lon"])
    df = df.sort_index()
    assert not df.index.duplicated().any()
    if ref_keys is None:
        ref_keys, metabolites = df.index, list(df.columns)
    else:
        assert df.index.equals(ref_keys), f"{f}: grid differs"
        assert list(df.columns) == metabolites, f"{f}: metabolite columns differ"
    arrays.append(df.to_numpy(dtype=np.float32))
    weeks.append(date[0])
    print(f"{f}: week {date[0]}  shape {df.shape}  NaN {int(df.isna().sum().sum())}")

scores = np.stack(arrays)
lat = np.array([k[0] for k in ref_keys])
lon = np.array([k[1] for k in ref_keys])
np.savez_compressed(OUT / "prmt_2008.npz", scores=scores, weeks=np.array(weeks),
                    lat=lat, lon=lon, metabolites=np.array(metabolites))

# --- dimension checks against numbers stated in the paper -------------------
n_w, n_c, n_m = scores.shape
print(f"\nweeks={n_w} cells={n_c} (paper 5904 = 123x48; unique lat {len(set(lat))}, lon {len(set(lon))})")
print(f"metabolites={n_m} (paper 2893)")
print(f"total PRMT scores={scores.size:,} (paper 68,321,088)")
print(f"implied gene predictions 5904*1715*4={5904*1715*4:,} (paper 40,501,440)")
print(f"implied taxon predictions 5904*24*4={5904*24*4:,} (paper 566,784)")
nz = (np.abs(scores) > 0).any(axis=(0, 1)).sum()
print(f"metabolites non-zero in >=1 cell-week: {nz} (paper: 2494 over 172 weeks)")
