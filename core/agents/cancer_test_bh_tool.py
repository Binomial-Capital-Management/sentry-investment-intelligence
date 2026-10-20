"""
Synthetic genomics stress-test tool for BinomialHash + manifold pipeline.

Temporary tool: intended only for manual trigger phrase testing.
"""

import json
import random
from typing import Dict, List

from agents import function_tool

from core.agents.binomial_hash import bh_ingest


@function_tool
async def cancer_test_bh(activation_phrase: str) -> str:
    """Generate a synthetic DNA dataset and ingest into BinomialHash.

    This tool is intentionally gated and should only run when activation_phrase
    is exactly "APPLEBEE".

    Output:
      - Returns the BH compact summary string for the generated dataset.
      - Dataset contains 20,000 points with 5 synthetic cancer marker channels.

    Args:
        activation_phrase: Must be "APPLEBEE".
    """
    if activation_phrase != "APPLEBEE":
        return json.dumps(
            {
                "error": "Tool disabled unless activation phrase is exactly 'APPLEBEE'."
            }
        )

    random.seed(20260225)

    n_points = 20000
    chromosomes = [f"chr{i}" for i in range(1, 23)] + ["chrX", "chrY"]
    strands = ["+", "-"]
    regions = ["promoter", "exon", "intron", "enhancer", "intergenic"]
    marker_names = [
        "marker_tp53_like",
        "marker_brca1_like",
        "marker_egfr_like",
        "marker_alk_like",
        "marker_kras_like",
    ]

    rows: List[Dict] = []
    for i in range(n_points):
        chromosome = chromosomes[i % len(chromosomes)]
        strand = strands[i % 2]
        region = regions[i % len(regions)]
        pos = (i % 120000) + 1
        gc_content = 0.30 + 0.30 * ((pos % 1000) / 1000.0)
        read_depth = 40 + (pos % 180) + (15 if strand == "+" else 0)
        methylation = 0.10 + 0.80 * ((i % 97) / 97.0)

        markers = {
            "marker_tp53_like": 0.20 + 0.60 * ((i % 31) / 31.0),
            "marker_brca1_like": 0.15 + 0.70 * ((i % 37) / 37.0),
            "marker_egfr_like": 0.10 + 0.75 * ((i % 43) / 43.0),
            "marker_alk_like": 0.05 + 0.80 * ((i % 47) / 47.0),
            "marker_kras_like": 0.25 + 0.65 * ((i % 53) / 53.0),
        }

        # Build a synthetic cancer signal with structural dependencies.
        region_boost = {
            "promoter": 0.08,
            "exon": 0.06,
            "intron": 0.02,
            "enhancer": 0.10,
            "intergenic": 0.01,
        }[region]
        chr_boost = 0.05 if chromosome in {"chr7", "chr8", "chr17", "chrX"} else 0.0
        marker_pressure = (
            0.25 * markers["marker_tp53_like"]
            + 0.20 * markers["marker_brca1_like"]
            + 0.22 * markers["marker_egfr_like"]
            + 0.15 * markers["marker_alk_like"]
            + 0.18 * markers["marker_kras_like"]
        )
        cancer_signal = (
            0.25 * gc_content
            + 0.002 * read_depth
            + 0.30 * methylation
            + marker_pressure
            + region_boost
            + chr_boost
        )

        row = {
            "sample_id": f"S{i % 300}",
            "chromosome": chromosome,
            "strand": strand,
            "gene_region": region,
            "position_bin": pos,
            "gc_content": round(gc_content, 6),
            "read_depth": int(read_depth),
            "methylation_level": round(methylation, 6),
            "expression_level": round(4.0 + 1.8 * gc_content + 0.008 * read_depth, 6),
            "cancer_signal_score": round(cancer_signal, 6),
        }
        for marker in marker_names:
            row[marker] = round(markers[marker], 6)
        rows.append(row)

    payload = json.dumps({"dna_records": rows})
    summary = bh_ingest(payload, "cancer_test_bh")
    return summary

