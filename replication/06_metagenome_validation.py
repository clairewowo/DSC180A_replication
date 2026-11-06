"""Approximate re-run of the paper's predicted-vs-observed enzyme validation (paper: PCC 0.718,
P < 1e-6, 1042 ECs, 8 L4 metagenomes from 2008).

What differs from the paper (stated, not hidden):
  PREDICTED side: the paper used MAP-predicted Order abundances (from satellite SIM data). The
    SIM inputs are no longer served, so we use Order abundances OBSERVED from 16S rRNA reads in
    the same metagenomes (MGnify v1.0, Greengenes). This tests the "Order abundance x EC table"
    step (Supp. Table 1), not the satellite -> community step.
  OBSERVED side: the paper used MG-RAST (2009) EC annotations, which are no longer retrievable.
    We use DIAMOND best hits of MGnify predicted proteins against Swiss-Prot (2026_03).

Steps follow the paper's description: predicted EC = sum_t a_t * E[EC, t] with a summing to 100
over the 24 Orders; predicted values quantile-normalised across samples and log2-transformed;
observed counts log-transformed; Pearson r over the ECs common to both sets.

Controls added here (not in the paper) because a pooled across-EC correlation is dominated by
how common each enzyme is in genomes in general:
  * null 1: uniform community (all 24 Orders equal)  -> how much r needs no sample information
  * null 2: Order abundances permuted among the 24 Orders within each sample (1000x)
  * within-EC, across-sample correlation (does the prediction track differences BETWEEN samples?)
"""
import gzip
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
MG = ROOT / "external_data/mgnify_L4"
DM = ROOT / "replication/derived/diamond"
RES = ROOT / "replication/results"; RES.mkdir(parents=True, exist_ok=True)
rng = np.random.default_rng(0)

E = pd.read_csv(ROOT / "supp_table_1.txt", sep="\t", index_col=0)          # 1715 EC x 24 Orders
COMMON = set(pd.read_csv(ROOT / "supp_table_3.txt", sep="\t").iloc[:, 0].astype(str).str.strip())
ORDERS = list(E.columns)

# Sampling time points (Gilbert et al. 2010). Jan & Apr daytime have two MGnify runs each;
# primary analysis sums them (8 samples), sensitivity analysis keeps all 10.
SAMPLES = {
    "MGYA00000241": "Jan_Day", "MGYA00000259": "Jan_Day", "MGYA00000243": "Jan_Night",
    "MGYA00000253": "Apr_Day", "MGYA00000257": "Apr_Day", "MGYA00000255": "Apr_Night",
    "MGYA00000245": "Aug_4pm", "MGYA00000247": "Aug_10pm", "MGYA00000249": "Aug_4am",
    "MGYA00000251": "Aug_10am",
}


# ---------------- Order abundances from 16S reads in each metagenome -----------
def order_of(tax):
    """Map a Greengenes lineage to one of the paper's 24 Orders (or None)."""
    t = {x[0]: x[3:] for x in tax if len(x) > 3 and x[1:3] == "__"}
    if t.get("c") == "Chloroplast" or t.get("f") == "mitochondria":
        return None
    if t.get("p") == "Cyanobacteria":
        return "Prochlorales" if t.get("g") == "Prochlorococcus" else "Cyanobacteria"
    o = t.get("o", "")
    if o == "Pirellulales":          # split from Planctomycetales in later Greengenes
        o = "Planctomycetales"
    return o if o in ORDERS else None


order_counts, n16s = {}, {}
for a in SAMPLES:
    j = json.load(open(next((MG / a).glob("*_otu.biom"))))
    rowsum = np.zeros(len(j["rows"]))
    for r, c, v in j["data"]:
        rowsum[r] += v
    cnt = defaultdict(float)
    for row, s in zip(j["rows"], rowsum):
        o = order_of(row["metadata"]["taxonomy"])
        if o:
            cnt[o] += s
    order_counts[a] = pd.Series(cnt, index=ORDERS).fillna(0)
    n16s[a] = (rowsum.sum(), sum(cnt.values()))
oc = pd.DataFrame(order_counts).T
print("16S reads per run (total, assigned to one of the 24 Orders):")
for a, (t, k) in n16s.items():
    print(f"  {a} {SAMPLES[a]:9s} {t:5.0f} {k:5.0f}")


# ---------------- Observed EC counts from DIAMOND vs Swiss-Prot ----------------
ec_map = pd.read_csv(ROOT / "external_data/swissprot/sprot_ec.tsv", sep="\t").dropna()
ec_map = dict(zip(ec_map["Entry"], ec_map["EC number"].str.split("; ")))


def observed_ec(a, min_pid):
    cnt = defaultdict(float)
    n_hit = n_ec = 0
    with gzip.open(DM / f"{a}.sprot.m8.gz", "rt") as fh:
        for line in fh:
            q, s, pid, *_ = line.split("\t")
            if float(pid) < min_pid:
                continue
            n_hit += 1
            acc = s.split("|")[1] if "|" in s else s
            ecs = ec_map.get(acc)
            if ecs:
                n_ec += 1
                for e in ecs:                     # split a multi-EC hit evenly
                    cnt[e.strip()] += 1 / len(ecs)
    return pd.Series(cnt), n_hit, n_ec


def quantile_normalize(df):
    """Columns = samples. Classic quantile normalisation (ties get averaged ranks' mean)."""
    srt = np.sort(df.values, axis=0).mean(axis=1)
    ranks = df.rank(method="first").astype(int).values - 1
    return pd.DataFrame(srt[ranks], index=df.index, columns=df.columns)


def predict(ab):
    """ab: samples x 24 Orders (any scale). Returns EC x samples, log2(quantile-normalised)."""
    ab = ab.div(ab.sum(axis=1), axis=0) * 100
    pred = E.values @ ab.T.values                                      # EC x samples
    pred = pd.DataFrame(pred, index=E.index, columns=ab.index)
    return np.log2(quantile_normalize(pred) + 1)


def compare(pred, obs, ecs):
    p, o = pred.loc[ecs], np.log2(obs.loc[ecs] + 1)
    pooled = stats.pearsonr(p.values.ravel(), o.values.ravel())
    mean_r = stats.pearsonr(p.mean(axis=1), o.mean(axis=1))
    per_sample = [stats.pearsonr(p[c], o[c])[0] for c in p.columns]
    return pooled, mean_r, per_sample


def run(label, groups, min_pid):
    # groups: {sample_name: [analysis ids]}
    ab = pd.DataFrame({g: oc.loc[ids].sum() for g, ids in groups.items()}).T
    obs = {}
    stats_rows = []
    for g, ids in groups.items():
        tot = pd.Series(dtype=float)
        for a in ids:
            s, n_hit, n_ec = observed_ec(a, min_pid)
            tot = tot.add(s, fill_value=0)
            stats_rows.append((a, g, n_hit, n_ec))
        obs[g] = tot
    obs = pd.DataFrame(obs).fillna(0)
    ecs = sorted(set(obs.index[obs.sum(axis=1) > 0]) & set(E.index))
    ecs_c = sorted(set(ecs) & COMMON)
    pred = predict(ab)
    out = []
    for name, ec_set in [("ECs in both (this run)", ecs), ("paper's 1042 ECs, observed>0", ecs_c)]:
        (r, p), (rm, pm), per = compare(pred, obs, ec_set)
        out.append(dict(analysis=label, min_identity=min_pid, ec_set=name, n_ec=len(ec_set),
                        n_samples=len(groups), pooled_r=r, pooled_p=p, mean_profile_r=rm,
                        per_sample_r_min=min(per), per_sample_r_max=max(per)))
    # nulls on the paper's EC set
    ec_set = ecs_c
    uni = predict(pd.DataFrame(1.0, index=ab.index, columns=ORDERS))
    r_uni = compare(uni, obs, ec_set)[0][0]
    perm = []
    for _ in range(1000):
        abp = ab.apply(lambda row: pd.Series(rng.permutation(row.values), index=ORDERS), axis=1)
        perm.append(compare(predict(abp), obs, ec_set)[0][0])
    perm = np.array(perm)
    r_real = out[1]["pooled_r"]
    out[1].update(r_uniform_community=r_uni, r_permuted_orders_mean=perm.mean(),
                  r_permuted_orders_95pct=np.percentile(perm, 95),
                  perm_p=(np.sum(perm >= r_real) + 1) / (len(perm) + 1))
    # within-EC across-sample correlation (only ECs that vary in both)
    p, o = pred.loc[ec_set], np.log2(obs.loc[ec_set] + 1)
    o_rel = np.log2(obs.loc[ec_set].div(obs.loc[ec_set].sum()) * 1e6 + 1)  # depth-normalised
    w = [stats.pearsonr(p.loc[e], o_rel.loc[e])[0] for e in ec_set
         if p.loc[e].std() > 0 and o_rel.loc[e].std() > 0]
    out[1].update(within_ec_median_r=float(np.median(w)), within_ec_n=len(w),
                  within_ec_frac_positive=float(np.mean(np.array(w) > 0)))
    return out, ab, obs, pred, stats_rows


primary_groups = defaultdict(list)
for a, g in SAMPLES.items():
    primary_groups[g].append(a)
all_runs = {f"{g}|{a}": [a] for a, g in SAMPLES.items()}

results = []
for label, groups in [("8 time points (duplicate runs summed)", dict(primary_groups)),
                      ("10 runs separately", all_runs)]:
    for pid in ([40, 50, 60] if label.startswith("8") else [50]):
        out, ab, obs, pred, srows = run(label, groups, pid)
        results += out
        if label.startswith("8") and pid == 50:
            ab.to_csv(RES / "mg16S_order_abundance_8samples.csv")
            obs.to_csv(RES / "observed_ec_counts_sprot_pid50.csv")
            pred.to_csv(RES / "predicted_ec_log2qn_8samples.csv")
            print("\nDIAMOND hits (pid>=50) and EC-bearing hits per run:")
            for a, g, nh, ne in srows:
                print(f"  {a} {g:9s} hits {nh:7d}  EC hits {ne:7d}")
            print("\nOrder relative abundance (%) from 16S reads:\n",
                  (ab.div(ab.sum(axis=1), axis=0) * 100).round(1).T.to_string())

res = pd.DataFrame(results)
res.to_csv(RES / "metagenome_validation_correlations.csv", index=False)
pd.set_option("display.width", 250)
print("\n", res.round(4).T.to_string())
