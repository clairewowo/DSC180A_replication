#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/replication"

python 01_load_prmt.py
python 02_maps_and_summary.py
python 03_socat_validation.py
python 04_enzyme_table_and_clusters.py

./05_annotate_ec.sh
python 06_metagenome_validation.py --order-source qiita
python 07_metagenome_validation_figure.py --order-source qiita