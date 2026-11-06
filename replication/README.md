# Partial replication: Larsen et al. 2015, *ISME J* 9:166–179

"Satellite remote sensing data can be used to model marine microbial metabolite turnover", doi:10.1038/ismej.2014.107, PMID 25072414, PMC4274419.

## What this covers

You can't rerun the full MAP → predicted metagenome → PRMT pipeline from the files here. The model's inputs (the 13 SIM rasters and the fitted MAP/EUREQA equations) aren't in the supplement, and neither is its intermediate output (the predicted Order abundances per cell). The analyses below use the published outputs (Supp. Tables 1, 3 and S4) plus one public validation dataset (SOCAT).

| Paper element | Status | Script |
|---|---|---|
| Model dimensions (5904 cells, 2893 metabolites, 1715 ECs, 24 Orders, 1042 shared ECs, 68,321,088 PRMT scores) | **Reproduced exactly** | 01, 04 |
| Fig. 2, row 4: CO₂ PRMT maps, 4 weeks of 2008 | **Reproduced** from S4 | 02 |
| Fig. 2, rows 1–3: cyanase / CODH / MDH copy-number maps | Not possible. Needs per-cell Order abundances (not published) | — |
| Claim that CODH is mostly from Desulfobacterales and Sphingomonadales | **Consistent**: these have the two highest copy numbers in Supp. Table 1 | 04 |
| PRMT-CO₂ vs SOCAT fCO₂, r = −0.40 (n = 244) | **Partial**. Only 4 of the 2008 weeks have PRMT scores, giving n = 30 | 03 |
| Predicted vs observed EC abundance, r = 0.718 (8 metagenomes) | **Approximate re-run** with substituted inputs (see result 6): r = 0.64 | 05, 06, 07 |
| Fig. 3 and Supp. Fig. 3: 172-week time series, k-means into 6 clusters | Not possible. S4 holds only 4 weeks; an exploratory 4-week k-means is included but isn't comparable | 04 |
| Fig. 4: Dec 2009 maps of 6 metabolites | Not possible (no 2009 data). The same 6 metabolites are mapped for the 4 weeks of 2008 instead | 02 |

## Results

**1. Data structure.** S4 holds 4 weekly averages: 17 Mar, 23 Jun, 22 Sep and 8 Dec 2008. The file named `AUG_PRMTscores.txt` is actually dated **22 Sep 2008**. Each week has 5904 cells on a 123 × 48 grid (0.05°, 48.45–50.80 °N, 7.56–1.46 °W) and 2893 metabolites. 2498 metabolites are non-zero somewhere; the paper reports 2494 over 172 weeks. About 760 cells have an identical full profile in every week. These cells fall on Brittany and SW England, so they're treated as land or no-data fill and masked. 2–6 cells per week contain NaNs.

**2. CO₂ PRMT, channel-wide (sea cells; positive = consumption, negative = accumulation).**

| week | mean | SD | % cells negative |
|---|---|---|---|
| 17 Mar | −0.264 | 0.188 | 96.8 |
| 23 Jun | +0.105 | 0.132 | 16.4 |
| 22 Sep | +0.124 | 0.112 | 11.1 |
| 8 Dec | +0.215 | 0.194 | 10.4 |

- These are consistent with the paper's text: CO₂ accumulation is highest in March, consumption is widespread in June and September, and in December there's a central-channel patch of accumulation surrounded by consumption.
- The spatial patterns of March and December are moderately correlated (r = 0.66), even though their means have opposite signs. The paper says only that CO₂ PRMT "does not mirror" the March/December similarity of the gene maps.
- Figure: `figures/fig2_row4_CO2_PRMT_maps.png`.

**3. SOCAT validation (SOCAT v3, WOCE flag 2).**
- I matched each SOCAT point to the PRMT week it falls in and the nearest grid cell. Using the paper's 11:00–13:00 rule, only **30 observations** match. They come from **2 cruises**, and 27 of the 30 are in the September week.
- Pooled correlation: r = −0.60 (permutation P = 0.001). Collapsing to cell-week means gives r = −0.67, P = 0.02 (n = 13).
- Removing each week's mean (within-week anomalies) gives r = −0.19, P = 0.33.
- Sensitivity check using all hours (n = 214): pooled r = −0.47, anomaly r = −0.33. Within weeks: September r = −0.40, but June r = **+0.62** (n = 9).
- Interpretation: the sign matches the paper's −0.40. But the sample is small and the observations are spatially and temporally autocorrelated along ship tracks, so the permutation P-values are anti-conservative. Part of the pooled correlation comes from the difference between the June and September weeks. **This doesn't independently confirm the paper's result.**

**4. Supp. Table 1 (EC × Order).**
- CO dehydrogenase (1.2.99.2): highest in Desulfobacterales (6.0) and Sphingomonadales (4.0), as stated in the paper.
- Cyanase (4.2.1.104): found in 9 of 24 Orders, highest in Alteromonadales.
- Malate dehydrogenase (1.1.1.37): found in 22 of 24 Orders at about 1 copy each. This fits the paper's description of MDH as the most homogeneous map.
- All 1042 ECs in Supp. Table 3 also appear in Supp. Table 1.

**5. Exploratory clustering.** k-means (k = 6) on 4-week channel means is dominated by the large December scores. Several of the paper's six representative metabolites end up in the same cluster. This is **not comparable** to the paper's 172-week clustering and shouldn't be reported as a replication.

**6. Predicted vs. observed enzyme abundance (approximate; scripts 05–07).**

The paper's inputs aren't available, so both sides were rebuilt:

| | Paper | Here |
|---|---|---|
| Order abundances | MAP predictions from satellite (SIM) data | 16S rRNA reads found in the same metagenomes (MGnify v1.0, Greengenes) |
| Observed ECs | MG-RAST 2009 annotation | DIAMOND 2.1.18 best hit of MGnify proteins vs Swiss-Prot 2026_03 (e ≤ 1e-5) |
| Prediction | Σ (Order abundance × Supp. Table 1), quantile-normalised, log2 | same |

Why the substitutions:
- **MAP inputs.** The Larsen 2012 supplement gives the MAP equations, but they need the 13 ERSEM-type SIM variables (e.g. size-fractionated POC, labile/semi-labile DOC, bacterial carbon). These are no longer served; the NCOF GODIVA link returns 404.
- **MG-RAST annotations.** These have been deleted from MG-RAST; all pipeline files are marked "temporary" and the annotation API returns "Unable to retrieve".

Samples: Jan and Apr daytime each have two MGnify runs. They are summed to give the paper's 8 time points; analysing all 10 runs separately gives the same result.

Results (Swiss-Prot identity ≥ 50 %, 899 of the paper's 1042 ECs with observed reads):
- **Pooled r = 0.64**, compared with the paper's 0.718. Per-sample r ranges 0.63–0.66. With identity ≥ 40 % r = 0.65; with ≥ 60 % r = 0.57.
- **Most of this correlation doesn't depend on the community.**
  - A uniform community (all 24 Orders equal) already gives r = 0.61.
  - Randomly permuting each sample's Order abundances gives a mean r of 0.59 (95th percentile 0.60, max 0.62 over 1000 permutations).
  - So the real compositions add about +0.03–0.05 above these nulls. That gain is consistent (permutation P ≤ 0.001), but small.
- **Between-sample variation is barely tracked.** Within each EC, correlating predicted and observed abundance across the 8 samples gives a median r of 0.10, with only 57 % of ECs positive.
- Figure: `figures/metagenome_validation.png`.

Interpretation:
- A pooled across-EC correlation mostly measures how common each enzyme is across bacterial genomes. It is high for almost any plausible community.
- The pooled P-value is also not meaningful: the 7192 points are 899 ECs × 8 samples, so they aren't independent.
- This applies to our r = 0.64. It plausibly applies to the paper's r = 0.718 as well, since that was reported the same way. We can't test the paper's own numbers.
- What our analysis does show: Supp. Table 1 plus observed Order abundances reproduces the *typical* enzyme profile of an L4 metagenome. It gives little evidence that differences between samples are captured.

Limitations:
- Order abundances rest on only 26–97 classified 16S reads per run, so they're very noisy. This biases the between-sample test toward failure.
- The metagenomes were 1.6 µm-prefiltered, so particle-attached taxa are under-represented.
- The annotation database and pipeline differ from the paper's.

## Caveats / assumptions
- The land mask is inferred (identical profiles), not taken from the authors.
- The paper used SOCAT v2 (2013); v3 (2015) is the oldest release on the PMEL ERDDAP server. The paper's SOCAT filters, grid-matching rule and time zone aren't fully specified.
- PRMT scores are relative and unitless; the reference sample/normalisation used for S4 isn't stated.

## Files
- `01_load_prmt.py` reads S4 and writes `big_files/derived/prmt_2008.npz`.
- `02_maps_and_summary.py` makes the maps, applies the land mask and writes weekly summaries.
- `03_socat_validation.py` runs the fCO₂ comparison (`results/socat_*`).
- `04_enzyme_table_and_clusters.py` runs the Supp. Table 1/3 checks and the exploratory k-means.
- `05_annotate_ec.sh` runs DIAMOND for the 10 L4 metagenomes against Swiss-Prot.
- `06_metagenome_validation.py` builds the predicted and observed EC tables, computes correlations and runs the null models.
- `07_metagenome_validation_figure.py` makes the validation figure.
- Larsen 2012 supplement: `external_data/larsen2012.pdf` (its MAP equations are Supp. Table 1).
- More external data: `external_data/mgnify_L4/` (MGnify v1.0 CDS proteins and OTU BIOM tables, study MGYS00000257) and `external_data/swissprot/` (UniProtKB/Swiss-Prot 2026_03 and its EC mapping).
- External data: `external_data/socat/` (SOCAT v3 subset via the PMEL ERDDAP server) and `external_data/naturalearth/` (coastline, for display only).

Run order: `python replication/01_load_prmt.py`, then 02, 03, 04.

## Large files (`big_files/`, gitignored)
Files over 50 MB are kept in `big_files/` at the repository root and are listed in `.gitignore`, so they aren't pushed to GitHub. Anyone cloning the repo needs to recreate them:

| File | Size | Source |
|---|---|---|
| `big_files/S4-AllPRMTscores/{MAR,JUN,AUG,DEC}_PRMTscores.txt` | ~188 MB each | Supplementary Table S4 of the paper (`ismej2014107x8.zip` on the journal site); unzip into this folder |
| `big_files/derived/prmt_2008.npz` | 155 MB | regenerate with `python replication/01_load_prmt.py` |
| `big_files/swissprot/uniprot_sprot.fasta.gz` | 94 MB | UniProtKB/Swiss-Prot release in `external_data/swissprot/reldate.txt` (UniProt FTP, `knowledgebase/complete/`) |
| `big_files/swissprot/uniprot_sprot.dmnd` | 294 MB | built from the FASTA by `replication/05_annotate_ec.sh` (`diamond makedb`) |

Note: the current Swiss-Prot release on the UniProt FTP will be newer than 2026_03, so rerunning 05 will give slightly different hits. The DIAMOND outputs used in the analysis are already stored in `replication/derived/diamond/`.
