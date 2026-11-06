"""Checks on Supplementary Tables 1 & 3, plus an EXPLORATORY k-means of metabolite profiles.

The paper's k-means (6 clusters; 108/114/103/163/1189/817 metabolites) used 172 weekly
channel means (2007-2010). Only 4 weeks are available here, so the clustering below is a
coarse analogue, not a replication: the cluster sizes are not expected to match.
"""
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "replication/results"

# ---- Supplementary Table 1: average EC copy number per bacterial Order ---------
E = pd.read_csv(ROOT / "supp_table_1.txt", sep="\t", index_col=0)
print(f"Supp Table 1: {E.shape[0]} EC annotations x {E.shape[1]} Orders (paper: 1715 x 24)")
common = pd.read_csv(ROOT / "supp_table_3.txt", sep="\t").iloc[:, 0].astype(str).str.strip()
print(f"Supp Table 3: {len(common)} ECs common to predicted & observed (paper: 1042); "
      f"{common.isin(E.index).sum()} of them are in Supp Table 1")

ENZ = {"4.2.1.104": "cyanase", "1.2.99.2": "CO dehydrogenase", "1.1.1.37": "malate dehydrogenase",
       "1.4.4.2": "glycine dehydrogenase (decarboxylating)", "2.3.1.-": "acyltransferase (2.3.1.-)",
       "2.7.2.2": "carbamate kinase", "3.5.1.54": "allophanate hydrolase"}
rows = []
for ec, name in ENZ.items():
    if ec not in E.index:
        print(f"{ec} ({name}): NOT in Supp Table 1"); continue
    v = E.loc[ec].sort_values(ascending=False)
    top = ", ".join(f"{o} {x:.2f}" for o, x in v.head(4).items() if x > 0)
    print(f"{ec} ({name}): present in {int((v > 0).sum())}/24 Orders; highest copy numbers: {top}")
    rows.append(dict(ec=ec, enzyme=name, n_orders=int((v > 0).sum()), top_orders=top))
pd.DataFrame(rows).to_csv(RES / "supp_table1_key_enzymes.csv", index=False)

# ---- Exploratory clustering of metabolite PRMT time profiles (4 weeks) ---------
D = np.load(ROOT / "big_files/derived/prmt_2008.npz")
mask = np.load(ROOT / "replication/derived/fill_mask.npy")
S = np.where(mask[:, :, None], np.nan, D["scores"].astype(float))
mets = np.array(D["metabolites"])
prof = np.nanmean(S, axis=1).T                       # metabolites x 4 weeks (channel mean)
keep = np.nan_to_num(np.abs(prof)).sum(axis=1) > 0
print(f"\nmetabolites with non-zero channel-mean profile: {keep.sum()} (paper: 2494 over 172 weeks)")
X = np.nan_to_num(prof[keep])
km = KMeans(n_clusters=6, n_init=50, random_state=0).fit(X)   # Euclidean, as in MeV
lab = km.labels_
out = pd.DataFrame(X, columns=[str(w) for w in D["weeks"]]); out.insert(0, "metabolite", mets[keep])
out["cluster"] = lab
out.to_csv(RES / "exploratory_kmeans_4weeks.csv", index=False)
cent = pd.DataFrame(km.cluster_centers_, columns=[str(w) for w in D["weeks"]])
cent["n_metabolites"] = np.bincount(lab)
print("Exploratory k-means (k=6) centroids, channel-mean PRMT:\n", cent.round(3).to_string())
REP = ["Trimethylamine_N-oxide", "Phosphatidylethanolamine", "Methanethiol",
       "Phosphonoacetate", "Acetate", "CO2"]
print("\ncluster of the paper's representative metabolites:")
for r in REP:
    print(f"  {r}: {out.loc[out.metabolite == r, 'cluster'].item()}")
print("(paper: each of these represents a DIFFERENT cluster i-vi)")
