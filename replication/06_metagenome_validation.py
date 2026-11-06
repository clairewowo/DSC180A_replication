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

Order-abundance source (--order-source):
  mgnify       (default) 16S reads found inside the same shotgun metagenomes (MGnify v1.0).
  qiita        16S V4 amplicons from Qiita study 1240 (L4, 2009-2010; table 46780, closed-ref
               Greengenes 13_8). No 2008 amplicons are public, so each metagenome is matched by
               SEASON: mean Order composition of all DNA samples within +/-7 days of the same
               calendar day (any year); surface ("T") samples if any have >=1000 reads, otherwise
               bottom ("B"). Surface DNA samples Jan-Apr are empty in this table.
  qiita_bottom sensitivity: as qiita but bottom samples only, for every date.
Outputs for the Qiita sources carry the suffix _qiita16S / _qiita16S_bottom.
"""
import argparse
import datetime as dt
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
ap = argparse.ArgumentParser()
ap.add_argument("--order-source", choices=["mgnify", "qiita", "qiita_bottom"], default="mgnify")
SRC = ap.parse_args().order_source
SUFFIX = {"mgnify": "", "qiita": "_qiita16S", "qiita_bottom": "_qiita16S_bottom"}[SRC]
QIITA_BIOM = ROOT / "qiita_data/BIOM/46780/otu_table.biom"
WINDOW_DAYS, MIN_READS = 7, 1000

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
SAMPLE_DATE = {"Jan_Day": "2008-01-28", "Jan_Night": "2008-01-28", "Apr_Day": "2008-04-22",
               "Apr_Night": "2008-04-22", "Aug_4pm": "2008-08-26", "Aug_10pm": "2008-08-26",
               "Aug_4am": "2008-08-27", "Aug_10am": "2008-08-27"}


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


def mgnify_order_counts():
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
    print("16S reads per run (total, assigned to one of the 24 Orders):")
    for a, (t, k) in n16s.items():
        print(f"  {a} {SAMPLES[a]:9s} {t:5.0f} {k:5.0f}")
    return pd.DataFrame(order_counts).T


def qiita_order_counts(bottom_only):
    """Season-matched Order composition (%, 24 Orders) per metagenome run from Qiita study 1240."""
    import h5py
    f = h5py.File(QIITA_BIOM, "r")
    sids = [x.decode() for x in f["sample/ids"][:]]
    orders = [order_of([t.decode() for t in row]) for row in f["observation/metadata/taxonomy"][:]]
    ip, idx, dat = f["sample/matrix/indptr"][:], f["sample/matrix/indices"][:], f["sample/matrix/data"][:]
    rows, info = {}, []
    for sid, a, b in zip(sids, ip[:-1], ip[1:]):
        code, kind = sid.split(".")[1][:4], sid.split(".")[1][4:].upper()   # DDMM + T/B/TCDNA/BCDNA
        if kind not in ("T", "B"):
            continue                                            # DNA only; cDNA (RNA) excluded
        cnt = defaultdict(float)
        for k, v in zip(idx[a:b], dat[a:b]):
            if orders[k]:
                cnt[orders[k]] += v
        rows[sid] = pd.Series(cnt, index=ORDERS).fillna(0)
        info.append(dict(qiita_sample=sid, ddmm=code, depth="surface" if kind == "T" else "bottom",
                         total_reads=float(dat[a:b].sum()), reads_in_24_orders=sum(cnt.values())))
    info = pd.DataFrame(info)
    info = info[info.reads_in_24_orders >= MIN_READS]
    pct = pd.DataFrame(rows).T
    pct = pct.div(pct.sum(axis=1), axis=0) * 100

    def doy_gap(ddmm, date):
        d = dt.date.fromisoformat(date)
        g = abs(dt.date(d.year, int(ddmm[2:]), int(ddmm[:2])).timetuple().tm_yday - d.timetuple().tm_yday)
        return min(g, 365 - g)

    out, used = {}, []
    for a, name in SAMPLES.items():
        date = SAMPLE_DATE[name]
        near = info[[doy_gap(c, date) <= WINDOW_DAYS for c in info.ddmm]]
        surf = near[near.depth == "surface"]
        pick = near[near.depth == "bottom"] if (bottom_only or surf.empty) else surf
        assert len(pick), f"no Qiita sample within {WINDOW_DAYS} d of {date}"
        out[a] = pct.loc[pick.qiita_sample].mean()
        used += [dict(mgnify_analysis=a, metagenome=name, metagenome_date=date, **r,
                      days_apart=doy_gap(r["ddmm"], date)) for r in pick.to_dict("records")]
    used = pd.DataFrame(used)
    used.to_csv(RES / f"qiita16S_samples_used{SUFFIX}.csv", index=False)
    print("Qiita samples used per metagenome date (season-matched, DNA):")
    print(used.drop_duplicates(["metagenome_date", "qiita_sample"])[
        ["metagenome_date", "qiita_sample", "depth", "days_apart", "reads_in_24_orders"]].to_string(index=False))
    return pd.DataFrame(out).T[ORDERS]


oc = mgnify_order_counts() if SRC == "mgnify" else qiita_order_counts(SRC == "qiita_bottom")


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
            ab.to_csv(RES / (f"order_abundance_8samples{SUFFIX}.csv" if SUFFIX else "mg16S_order_abundance_8samples.csv"))
            obs.to_csv(RES / "observed_ec_counts_sprot_pid50.csv")   # identical for every source
            pred.to_csv(RES / f"predicted_ec_log2qn_8samples{SUFFIX}.csv")
            print("\nDIAMOND hits (pid>=50) and EC-bearing hits per run:")
            for a, g, nh, ne in srows:
                print(f"  {a} {g:9s} hits {nh:7d}  EC hits {ne:7d}")
            print(f"\nOrder relative abundance (%) from 16S ({SRC}):\n",
                  (ab.div(ab.sum(axis=1), axis=0) * 100).round(1).T.to_string())

res = pd.DataFrame(results)
res.insert(0, "order_source", SRC)
res.to_csv(RES / f"metagenome_validation_correlations{SUFFIX}.csv", index=False)
pd.set_option("display.width", 250)
print("\n", res.round(4).T.to_string())
