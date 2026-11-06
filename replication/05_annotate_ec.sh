#!/usr/bin/env bash
# Re-annotate the L4 metagenome predicted proteins (MGnify v1.0 CDS) with EC numbers by
# DIAMOND blastp best hit against UniProtKB/Swiss-Prot (release recorded in
# external_data/swissprot/reldate.txt). This REPLACES the MG-RAST 2009 annotation used in the
# paper, which is no longer retrievable. Filtering by identity is done later in Python.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SP="$ROOT/big_files/swissprot"   # large Swiss-Prot FASTA + DIAMOND db (gitignored)
OUT="$ROOT/replication/derived/diamond"
mkdir -p "$OUT"
THREADS=${THREADS:-8}

[ -s "$SP/uniprot_sprot.dmnd" ] || diamond makedb --in "$SP/uniprot_sprot.fasta.gz" -d "$SP/uniprot_sprot" -p "$THREADS"

for faa in "$ROOT"/external_data/mgnify_L4/*/*_CDS.faa.gz; do
  a=$(basename "$(dirname "$faa")")
  out="$OUT/$a.sprot.m8.gz"
  [ -s "$out" ] && { echo "skip $a"; continue; }
  echo "$(date) $a"
  diamond blastp -q "$faa" -d "$SP/uniprot_sprot" -p "$THREADS" -k 1 -e 1e-5 \
    --outfmt 6 qseqid sseqid pident length qlen evalue bitscore \
    --compress 1 -o "$OUT/$a.sprot.m8" --quiet
  mv "$OUT/$a.sprot.m8.gz" "$out" 2>/dev/null || true
done
diamond version
echo "$(date) done"
