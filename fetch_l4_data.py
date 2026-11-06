#!/usr/bin/env python3
"""
fetch_l4_data.py  --  pull the Western English Channel (L4, 2008) data needed to test
the downstream half of the Larsen et al. 2015 pipeline:
  * Order-level 16S tables      (MGnify, study MGYS00000257 = ENA ERP000118)
  * EC counts per metagenome    (MG-RAST, 8 DNA metagenomes)

Needs only:  pip install requests

Run the three steps in order and send me what they print / save:
  python fetch_l4_data.py mgnify       --out l4_data
  python fetch_l4_data.py mgrast-probe --out l4_data
  python fetch_l4_data.py mgrast-fetch --out l4_data --supp3 supp_table_3.txt

Nothing here has been tested against the live servers. If a step fails, send me the
full error text plus any files it did manage to write -- they are saved as it goes.
"""
import argparse
import csv
import json
import os
import re
import sys
import time

import requests

MGNIFY = "https://www.ebi.ac.uk/metagenomics/api/v1"
STUDY = "MGYS00000257"
MGRAST_BASES = ["https://api.mg-rast.org", "https://api.mg-rast.org/1"]

# DNA metagenome IDs as listed in Larsen et al. 2011 (two look like typos; probe checks them)
LARSEN_IDS = ["4445064.3", "4444077.3", "4445065.3", "4445066.3",
              "4445068.3", "4444083.3", "4445069.3", "4445070.3"]
# every ID mentioned in Gilbert et al. 2010 / Larsen 2011, so probe can sort out which is which
PROBE_IDS = [f"{n}.3" for n in (list(range(4443360, 4443364)) + list(range(4443365, 4443369))
                                + list(range(4445064, 4445071)) + [4444077, 4444083, 4445081])]

EC_RE = re.compile(r"EC[ :]*([0-9]+\.[0-9\-]+\.[0-9\-]+\.[0-9\-]+)")


# ----------------------------------------------------------------------------- http
def get(url, params=None, stream=False, retries=3):
    last = None
    for i in range(retries):
        try:
            r = requests.get(url, params=params, timeout=180, stream=stream,
                             headers={"Accept": "application/json" if not stream else "*/*"})
            if r.status_code == 429 or r.status_code >= 500:
                raise requests.HTTPError(f"HTTP {r.status_code} for {r.url}")
            r.raise_for_status()
            time.sleep(0.3)  # be polite
            return r
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(2 * (i + 1))
    raise last


def paged(url, params=None):
    """Iterate over a JSON:API list endpoint (MGnify), following 'next' links."""
    params = dict(params or {})
    params.setdefault("page_size", 100)
    while url:
        j = get(url, params).json()
        for d in j.get("data", []):
            yield d
        url = (j.get("links") or {}).get("next")
        params = None


def related(rel, key):
    """Fetch a JSON:API related resource; return its 'data' dict ({} on any failure)."""
    try:
        link = rel[key]["links"]["related"]
        data = get(link).json().get("data")
        if isinstance(data, list):
            data = data[0] if data else {}
        return data or {}
    except Exception:  # noqa: BLE001
        return {}


def write_csv(path, rows, fields):
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(f"  wrote {path}  ({len(rows)} rows)")


# ----------------------------------------------------------------------------- MGnify
def version_key(v):
    return tuple(int(x) for x in re.findall(r"\d+", str(v or "0")))


def order_of(attrs):
    """Pull (kingdom, phylum, class, order) out of an MGnify taxonomy record."""
    h = attrs.get("hierarchy") or {}
    if h:
        return (h.get("kingdom") or h.get("superkingdom") or h.get("domain"),
                h.get("phylum"), h.get("class"), h.get("order"))
    parts = {}
    for p in re.split(r"[:;]", attrs.get("lineage") or ""):
        if "__" in p:
            k, v = p.split("__", 1)
            parts[k] = v
    return (parts.get("sk") or parts.get("d"), parts.get("p"), parts.get("c"), parts.get("o"))


def cmd_mgnify(a):
    out = os.path.join(a.out, "mgnify")
    os.makedirs(os.path.join(out, "files"), exist_ok=True)
    os.makedirs(os.path.join(out, "taxonomy_json"), exist_ok=True)

    print(f"Listing analyses in {STUDY} ...")
    analyses = list(paged(f"{MGNIFY}/studies/{STUDY}/analyses"))
    print(f"  {len(analyses)} analyses found")

    rows = []
    for d in analyses:
        at, rel = d.get("attributes", {}), d.get("relationships", {})
        run, sample = related(rel, "run"), related(rel, "sample")
        sa = sample.get("attributes", {})
        rows.append({
            "analysis": d.get("id"),
            "experiment_type": at.get("experiment-type"),
            "pipeline": at.get("pipeline-version"),
            "status": at.get("analysis-status"),
            "run": run.get("id"),
            "sample": sample.get("id"),
            "sample_name": sa.get("sample-name"),
            "sample_desc": (sa.get("sample-desc") or "")[:200],
            "collection_date": sa.get("collection-date"),
            "lat": sa.get("latitude"),
            "lon": sa.get("longitude"),
            "_rel": rel,
        })
    write_csv(os.path.join(out, "analyses_overview.csv"), rows,
              ["analysis", "experiment_type", "pipeline", "status", "run", "sample",
               "sample_name", "sample_desc", "collection_date", "lat", "lon"])

    # keep amplicon analyses; by default only the newest pipeline version per run
    amp = [r for r in rows if (r["experiment_type"] or "").lower() == "amplicon"]
    if not a.all_versions:
        best = {}
        for r in amp:
            k = r["run"]
            if k not in best or version_key(r["pipeline"]) > version_key(best[k]["pipeline"]):
                best[k] = r
        amp = list(best.values())
    print(f"  {len(amp)} amplicon analyses selected (see analyses_overview.csv for all)")

    manifest, order_rows = [], []
    for r in amp:
        acc, rel = r["analysis"], r["_rel"]
        print(f"- {acc}  run={r['run']}  sample={r['sample_name']}  date={r['collection_date']}")

        # (1) pre-computed taxonomy tables offered as downloads
        try:
            link = rel["downloads"]["links"]["related"]
            for f in paged(link):
                fa = f.get("attributes", {})
                alias = fa.get("alias") or ""
                group = ((fa.get("group-type") or "") + " " +
                         json.dumps(fa.get("description") or "")).lower()
                ext = ((fa.get("file-format") or {}).get("extension") or "").lower()
                url = (f.get("links") or {}).get("self")
                want = ("taxonom" in group or "otu" in alias.lower()) and \
                       ext in ("tsv", "csv", "biom", "txt")
                saved = ""
                if want and url:
                    dest_dir = os.path.join(out, "files", acc)
                    os.makedirs(dest_dir, exist_ok=True)
                    saved = os.path.join(dest_dir, alias)
                    with get(url, stream=True) as resp, open(saved, "wb") as fh:
                        for chunk in resp.iter_content(1 << 16):
                            fh.write(chunk)
                manifest.append({"analysis": acc, "file": alias, "group": group[:80],
                                 "format": ext, "url": url, "saved_as": saved})
        except Exception as e:  # noqa: BLE001
            print(f"    downloads failed: {e}")

        # (2) SSU taxonomy straight from the API, aggregated to Order
        try:
            counts = {}
            raw = []
            for t in paged(f"{MGNIFY}/analyses/{acc}/taxonomy/ssu", {"page_size": 500}):
                raw.append(t)
                at = t.get("attributes", {})
                key = order_of(at)
                counts[key] = counts.get(key, 0) + (at.get("count") or 0)
            with open(os.path.join(out, "taxonomy_json", f"{acc}_ssu_raw.json"), "w") as fh:
                json.dump(raw, fh)
            for (k, p, c, o), n in counts.items():
                order_rows.append({"analysis": acc, "run": r["run"], "sample_name": r["sample_name"],
                                   "kingdom": k, "phylum": p, "class": c, "order": o, "count": n})
            if raw and not any(k[3] for k in counts):
                print("    WARNING: no 'order' field parsed -- send me taxonomy_json/*.json")
        except Exception as e:  # noqa: BLE001
            print(f"    taxonomy/ssu failed: {e}")

    write_csv(os.path.join(out, "downloads_manifest.csv"), manifest,
              ["analysis", "file", "group", "format", "url", "saved_as"])
    write_csv(os.path.join(out, "order_counts_long.csv"), order_rows,
              ["analysis", "run", "sample_name", "kingdom", "phylum", "class", "order", "count"])
    print("\nDone. Send me: analyses_overview.csv, order_counts_long.csv, downloads_manifest.csv\n"
          "(and any files under mgnify/files/ if order_counts_long.csv is empty).")


# ----------------------------------------------------------------------------- MG-RAST
def mg_get(path, params=None):
    params = dict(params or {})
    if os.environ.get("MGRAST_KEY"):          # only needed for private data
        params["auth"] = os.environ["MGRAST_KEY"]
    last = None
    for base in MGRAST_BASES:
        try:
            return get(f"{base}/{path}", params).json()
        except Exception as e:  # noqa: BLE001
            last = e
    raise last


def find_key(obj, needle):
    """First value whose key contains `needle`, searching nested dicts."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if needle in str(k).lower() and not isinstance(v, (dict, list)):
                return v
        for v in obj.values():
            r = find_key(v, needle)
            if r is not None:
                return r
    return None


def mgid(i):
    return i if str(i).startswith("mgm") else f"mgm{i}"


def cmd_mgrast_probe(a):
    out = os.path.join(a.out, "mgrast")
    os.makedirs(out, exist_ok=True)
    rows = []
    for i in (a.ids or PROBE_IDS):
        j, used = None, None
        for cand in dict.fromkeys([i, i.split(".")[0]]):   # try with and without the '.3'
            try:
                j = mg_get(f"metagenome/{mgid(cand)}", {"verbosity": "full"})
                used = cand
                break
            except Exception:  # noqa: BLE001
                continue
        if j is None:
            print(f"  {i}: not found / not reachable")
            rows.append({"id": i, "found": "no"})
            continue
        with open(os.path.join(out, f"meta_{mgid(used)}.json"), "w") as fh:
            json.dump(j, fh)
        row = {"id": used, "found": "yes", "name": j.get("name"),
               "sequence_type": j.get("sequence_type") or find_key(j, "seq_type"),
               "created_on": j.get("created_on"),
               "collection_date": find_key(j, "collection_date"),
               "collection_time": find_key(j, "collection_time"),
               "status": j.get("status")}
        print("  ", {k: row[k] for k in ("id", "name", "sequence_type", "collection_date")})
        rows.append(row)
    write_csv(os.path.join(out, "probe.csv"), rows,
              ["id", "found", "name", "sequence_type", "created_on",
               "collection_date", "collection_time", "status"])
    print("\nSend me probe.csv. We need the 8 whose sequence type is WGS/metagenome (not metatranscriptome).")


def parse_biom(j):
    """MG-RAST matrix (BIOM) -> {column_id: {row_id: value}}."""
    rows = [r["id"] for r in j["rows"]]
    cols = [c["id"] for c in j["columns"]]
    table = {c: {} for c in cols}
    if j.get("matrix_type") == "sparse":
        for ri, ci, v in j["data"]:
            table[cols[ci]][rows[ri]] = v
    else:
        for ri, rowvals in enumerate(j["data"]):
            for ci, v in enumerate(rowvals):
                if v:
                    table[cols[ci]][rows[ri]] = v
    return table


def mg_matrix(params):
    j = mg_get("matrix/function", params)
    t0 = time.time()
    while True:
        if "rows" in j:
            return j
        if isinstance(j.get("data"), dict) and "rows" in j["data"]:
            return j["data"]
        if not j.get("url") or time.time() - t0 > 1800:
            raise RuntimeError(f"unexpected matrix response: {str(j)[:300]}")
        print("    ... server is still computing, waiting")
        time.sleep(15)
        j = get(j["url"]).json()


def cmd_mgrast_fetch(a):
    out = os.path.join(a.out, "mgrast")
    os.makedirs(out, exist_ok=True)
    ids = a.ids or LARSEN_IDS
    per_sample = {}
    for i in ids:
        print(f"- {i}")
        params = {"id": mgid(i), "source": a.source, "result_type": "abundance",
                  "group_level": "function", "evalue": a.evalue,
                  "identity": a.identity, "length": a.length}
        try:
            j = mg_matrix(params)
        except Exception:  # noqa: BLE001
            j = mg_matrix({**params, "id": mgid(i.split(".")[0])})
        with open(os.path.join(out, f"function_{mgid(i)}.json"), "w") as fh:
            json.dump(j, fh)
        t = parse_biom(j)
        per_sample[i] = next(iter(t.values())) if t else {}
        print(f"    {len(per_sample[i])} functions, {sum(per_sample[i].values()):.0f} total hits")

    # function x sample table
    funcs = sorted({f for s in per_sample.values() for f in s})
    with open(os.path.join(out, "function_matrix.csv"), "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["function"] + list(per_sample))
        for f in funcs:
            w.writerow([f] + [per_sample[s].get(f, 0) for s in per_sample])
    print(f"  wrote function_matrix.csv ({len(funcs)} functions)")

    # EC x sample table (a function naming several ECs counts toward each of them)
    ec = {}
    with_ec = total = 0.0
    for s, d in per_sample.items():
        for f, v in d.items():
            total += v
            ecs = EC_RE.findall(f)
            if ecs:
                with_ec += v
            for e in ecs:
                ec.setdefault(e, {})[s] = ec.get(e, {}).get(s, 0) + v
    with open(os.path.join(out, "ec_counts.csv"), "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["EC"] + list(per_sample))
        for e in sorted(ec):
            w.writerow([e] + [ec[e].get(s, 0) for s in per_sample])
    frac = (with_ec / total) if total else 0
    print(f"  wrote ec_counts.csv ({len(ec)} ECs); {frac:.0%} of hits carried an EC number")
    if frac < 0.05:
        print("  WARNING: very few EC numbers found -- send me function_matrix.csv; "
              "we may need to use source=KO and map KO->EC instead.")

    if a.supp3 and os.path.exists(a.supp3):
        s3 = [l.strip() for l in open(a.supp3)][1:]
        print(f"  {len(set(s3) & set(ec))} of {len(set(s3))} Supp Table 3 ECs found in these metagenomes")
    print("\nDone. Send me: function_matrix.csv, ec_counts.csv, mgrast/probe.csv")


# ----------------------------------------------------------------------------- main
def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    m = sub.add_parser("mgnify")
    m.add_argument("--out", default="l4_data")
    m.add_argument("--all-versions", action="store_true",
                   help="keep every pipeline version of each run (default: newest only)")
    m.set_defaults(fn=cmd_mgnify)

    pr = sub.add_parser("mgrast-probe")
    pr.add_argument("--out", default="l4_data")
    pr.add_argument("--ids", nargs="*", help="override the built-in candidate list")
    pr.set_defaults(fn=cmd_mgrast_probe)

    f = sub.add_parser("mgrast-fetch")
    f.add_argument("--out", default="l4_data")
    f.add_argument("--ids", nargs="*", help="MG-RAST IDs (default: the 8 from Larsen 2011)")
    f.add_argument("--source", default="Subsystems", help="annotation source (Larsen used SEED)")
    f.add_argument("--evalue", type=int, default=3, help="negative exponent: 3 means 1e-3")
    f.add_argument("--identity", type=int, default=50)
    f.add_argument("--length", type=int, default=50)
    f.add_argument("--supp3", help="path to supp_table_3.txt for an overlap check")
    f.set_defaults(fn=cmd_mgrast_fetch)

    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
