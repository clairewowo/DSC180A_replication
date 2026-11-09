# Partial replication: Larsen et al. 2015, *ISME J* 9:166–179

"Satellite remote sensing data can be used to model marine microbial metabolite turnover", doi:10.1038/ismej.2014.107, PMID 25072414, PMC4274419.

Our replication uses large files that cannot be pushed to Git. Currently they are under .gitignore but you can download these folders: (https://drive.google.com/file/d/106T7Kky1tDBZZhojlEEkqqOAWj71t2Kt/view?usp=sharing, https://drive.google.com/file/d/1zKeApbvz_Ia0cJbJ_8K5lbNOvgzs-OjO/view?usp=sharing) and put both at the root of the directory. Then everything should be able to run. 

Our main blocker was that we could not obtain the data because the paper is old and the links no longer work. Currenlty our plan is to use alternate data sources that are very similar because the authors no longer have the original data. So, our code covers the end of the pipeline. We'll spend the rest of the quarter working on the beginning and middle, now that we have the right input data. Here is what we have in sequential steps:

1. Reading in PRMT data into one array: **01_load_prmt.py** (PRMT scores only available for 4 weeks instead of the years of the replication, since they have not published the full ~3 years used)
2. Plotting the array from step 1: **02_maps_and_summary.py**. Creates Figure 2, row 4 of the paper. Also writes weekly summary tables
3. Validating CO2 PRMT results: **03_socat_validation.py**. Correlates PRMT CO2 scores with measured fCO2 from SOCAT. Again, only 4 weeks of PRMT are available. 
4. Exploratory enzyme clustering (not a main figure in the paper): **04_enzyme_table_and_clusters.py**. 
5. Validate predicted enzyme abundances: **05_annotate_ec.sh**, **06_metagenome_validation.py**, **07_metagenome_validation_figure.py**
- We use 05_annotate_ec.sh because we were unable to obtain the original functional annotation of the 8 metagenomes, so we ran some software (DIAMOND, Swiss-Prot) to obtain our own. 
- We use 06_metagenome_validation.py to build predicted enzyme abundances (using the E matrix from supplemental materials) and compare them to the output of 05_annotate_ec.sh.
- 07_metagenome_validation_figure.py plots the comparison from the previous step

Additionally, **fetch_l4_data.py** was used to download data in the folder l4_data. 

## AI Usage
We used Claude code for a significant portion of this replication and we were told by our mentor to do this. A lot of the process with finding data was done by hand by going through the paper, browsing the web, etc. Since our input data was not the same as the original data from the paper, there was not a "ground truth" for us to test our code on. 

## Usage ##
```bash
./run_code.sh
```

## Installing dependencies ##
```bash
conda install -c conda-forge -c bioconda python=3.12 numpy=1.26 pandas=2.3 scipy=1.16 matplotlib=3.10 scikit-learn=1.7 h5py=3.15 diamond=2.1.18
```

