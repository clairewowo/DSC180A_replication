"""Figure for 06: predicted vs observed EC abundance, and real r against null models.
Primary setting only: 8 time points, Swiss-Prot identity >= 50 %, paper's 1042-EC set."""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "replication/results"
E = pd.read_csv(ROOT / "supp_table_1.txt", sep="\t", index_col=0)
COMMON = set(pd.read_csv(ROOT / "supp_table_3.txt", sep="\t").iloc[:, 0].astype(str).str.strip())
ab = pd.read_csv(RES / "mg16S_order_abundance_8samples.csv", index_col=0)
obs = pd.read_csv(RES / "observed_ec_counts_sprot_pid50.csv", index_col=0)
pred = pd.read_csv(RES / "predicted_ec_log2qn_8samples.csv", index_col=0)
ecs = sorted(set(obs.index[obs.sum(axis=1) > 0]) & set(E.index) & COMMON)


def qn(df):
    srt = np.sort(df.values, axis=0).mean(axis=1)
    return pd.DataFrame(srt[df.rank(method="first").astype(int).values - 1], index=df.index, columns=df.columns)


def predict(a):
    a = a.div(a.sum(axis=1), axis=0) * 100
    return np.log2(qn(pd.DataFrame(E.values @ a.T.values, index=E.index, columns=a.index)) + 1)


def pooled_r(p):
    return stats.pearsonr(p.loc[ecs].values.ravel(), np.log2(obs.loc[ecs] + 1).values.ravel())[0]


rng = np.random.default_rng(0)
r_real = pooled_r(pred)
r_uni = pooled_r(predict(pd.DataFrame(1.0, index=ab.index, columns=ab.columns)))
perm = np.array([pooled_r(predict(ab.apply(lambda r: pd.Series(rng.permutation(r.values), index=ab.columns), axis=1)))
                 for _ in range(1000)])

fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 4.4), constrained_layout=True)
x = pred.loc[ecs].values.ravel(); y = np.log2(obs.loc[ecs] + 1).values.ravel()
hb = a1.hexbin(x, y, gridsize=45, mincnt=1, cmap="Blues", bins="log")
a1.set_xlabel("predicted EC abundance, log2 (quantile-normalised)")
a1.set_ylabel("observed EC reads, log2(count+1)")
a1.set_title(f"{len(ecs)} ECs x 8 samples, pooled r = {r_real:.2f}\n(paper: r = 0.718)", fontsize=10)
fig.colorbar(hb, ax=a1, label="points per bin")
a2.hist(perm, bins=40, color="#86b6ef", edgecolor="white")
a2.axvline(r_real, color="#b8322c", lw=2); a2.text(r_real, a2.get_ylim()[1] * 0.92, "observed\ncommunities  ", color="#b8322c", fontsize=9, va="top", ha="right")
a2.axvline(r_uni, color="#333333", lw=1.5, ls="--"); a2.text(r_uni, a2.get_ylim()[1] * 0.6, "uniform\ncommunity  ", ha="right", fontsize=9, va="top")
a2.set_xlabel("pooled Pearson r"); a2.set_ylabel("permutations")
a2.set_title("Order labels permuted within sample (1000x)", fontsize=10)
fig.savefig(ROOT / "replication/figures/metagenome_validation.png", dpi=150)
print(f"r real {r_real:.3f}, uniform {r_uni:.3f}, permuted mean {perm.mean():.3f} (95% {np.percentile(perm, 95):.3f}, max {perm.max():.3f})")
