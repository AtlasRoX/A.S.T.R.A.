"""Fetch real Inspiration4 astronaut blood values from the NASA Open Science Data Repository.

Two datasets hold the blood work:

  * OSD-575 "SpaceX Inspiration4 Blood Serum Metabolic Panel and Immune/Cardiac Cytokine Arrays
    (Comprehensive Metabolic Panel and Multiplex)" -> the comprehensive metabolic panel (CMP):
    glucose, creatinine, sodium, potassium, ALT, ... with Quest Diagnostics reference ranges.
  * OSD-569 "Whole Blood Measurements from the SpaceX Inspiration4 Mission (RNA-seq,
    epitranscriptome, WGS, clonal hematopoiesis, CBC)" -> the complete blood count (CBC):
    white blood cells, haemoglobin, platelets, ... with reference ranges.

Source: NASA OSDR Biological Data API, https://visualization.osdr.nasa.gov/biodata/api/v2/
Study pages:  https://osdr.nasa.gov/bio/repo/data/studies/OSD-575  and  .../OSD-569
Publication:  Kim et al., Nature Communications 2024, doi:10.1038/s41467-024-45513-1
              (the DOI carried by the OSD-575 metadata is 10.1038/s41586-024-07639-y)

Run from the repo root (astra/):
    uv run --no-project python -I scripts/fetch/osdr_i4.py
"""

from __future__ import annotations

import csv
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import get_url, write_json  # noqa: E402

API = "https://visualization.osdr.nasa.gov/biodata/api/v2"
DOWNLOAD = "https://osdr.nasa.gov/geode-py/ws/studies/{study}/download?source=datamanager&file={file}"

# The two studies and the CSV that carries the numbers we want.
STUDIES = {
    "OSD-575": {
        "assay": "OSD-575_analytical-chemistry_comprehensive-metabolic-panel_quest diagnostics",
        "file": "LSDS-8_Comprehensive_Metabolic_Panel_CMP_TRANSFORMED.csv",
    },
    "OSD-569": {
        "assay": "OSD-575_analytical-chemistry_comprehensive-metabolic-panel_quest diagnostics",
        "file": "LSDS-7_Complete_Blood_Count_CBC_TRANSFORMED.csv",
    },
}

# Analyte -> (CSV value column, CSV min column, CSV max column, unit, ASTRA metric id)
CMP_ANALYTES = {
    "glucose": ("glucose_value_milligram_per_deciliter", "glucose_range_min_milligram_per_deciliter",
                "glucose_range_max_milligram_per_deciliter", "mg/dL", "glucose"),
    "creatinine": ("creatinine_value_milligram_per_deciliter", "creatinine_range_min_milligram_per_deciliter",
                   "creatinine_range_max_milligram_per_deciliter", "mg/dL", "creatinine"),
    "sodium": ("sodium_value_millimol_per_liter", "sodium_range_min_millimol_per_liter",
               "sodium_range_max_millimol_per_liter", "mmol/L", "sodium"),
    "potassium": ("potassium_value_millimol_per_liter", "potassium_range_min_millimol_per_liter",
                  "potassium_range_max_millimol_per_liter", "mmol/L", "potassium"),
    "alt": ("alt_value_units_per_liter", "alt_range_min_units_per_liter",
            "alt_max_units_per_liter", "U/L", "alt"),
    "calcium": ("calcium_value_milligram_per_deciliter", "calcium_range_min_milligram_per_deciliter",
                "calcium_range_max_milligram_per_deciliter", "mg/dL", "calcium"),
}

CBC_ANALYTES = {
    "wbc": ("white_blood_cell_count_value_thousand_per_microliter",
            "white_blood_cell_count_range_min_thousand_per_microliter",
            "white_blood_cell_count_range_max_thousand_per_microliter", "10^3/µL", "wbc"),
    "hemoglobin": ("hemoglobin_value_grams_per_deciliter", "hemoglobin_range_min_grams_per_deciliter",
                   "hemoglobin_range_max_grams_per_deciliter", "g/dL", "hemoglobin"),
    "platelets": ("platelet_count_value_thousand_per_microliter",
                  "platelet_count_range_min_thousand_per_microliter",
                  "platelet_count_range_max_thousand_per_microliter", "10^3/µL", "platelets"),
    "neutrophils": ("absolute_neutrophils_value_cells_per_microliter",
                    "absolute_neutrophils_range_min_cells_per_microliter",
                    "absolute_neutrophils_range_max_cells_per_microliter", "cells/µL", "neutrophils"),
    "lymphocytes": ("absolute_lymphocytes_value_cells_per_microliter",
                    "absolute_lymphocytes_range_min_cells_per_microliter",
                    "absolute_lymphocytes_range_max_cells_per_microliter", "cells/µL", "lymphocytes"),
    "hematocrit": ("hematocrit_value_percent", "hematocrit_range_min_percent",
                   "hematocrit_range_max_percent", "%", "hematocrit"),
}

# The CBC CSV reports haemoglobin as a percentage (this dataset's own convention).
CBC_HEMOGLOBIN_PERCENT_COLUMNS = (
    "hemoglobin_value_percent", "hemoglobin_range_min_percent", "hemoglobin_range_max_percent")


def download_csv(study: str, filename: str) -> str:
    url = DOWNLOAD.format(study=study, file=filename)
    print(f"GET {url}")
    return get_url(url)


def parse_rows(text: str) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(text.lstrip("﻿"))))


def num(value: str) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def timepoint_day(sample: str) -> tuple[str, int] | None:
    """Map an OSDR sample name to a flight-relative day.

    Inspiration4 flew for 3 days (launch 2021-09-15, splashdown 2021-09-18).
    L-<n> is n days before launch, R+<n> is n days after landing.
    """
    for part in sample.split("_"):
        if part.startswith("L-"):
            return part, -int(part[2:])
        if part.startswith("L+"):
            return part, int(part[2:])
        if part.startswith("R+"):
            return part, int(part[2:])
    return None


def subject_of(sample: str) -> str:
    return sample.split("_")[0]


def collect(study: str, filename: str, analytes: dict[str, tuple[str, str, str, str, str]],
            special: dict[str, tuple[str, str, str]] | None = None) -> list[dict[str, object]]:
    rows = parse_rows(download_csv(study, filename))
    out: list[dict[str, object]] = []
    for row in rows:
        sample = row.get("Sample Name") or ""
        tp = timepoint_day(sample)
        if tp is None:
            continue
        label, day = tp
        subject = subject_of(sample)
        for analyte, (vcol, lcol, hcol, unit, metric) in analytes.items():
            cols = special.get(analyte) if special else None
            if cols:
                vcol, lcol, hcol = cols
            value = num(row.get(vcol, ""))
            if value is None:
                continue
            out.append({
                "subject": subject,
                "timepoint": label,
                "day": day,
                "analyte": analyte,
                "metric": metric,
                "value": value,
                "unit": unit,
                "ref_low": num(row.get(lcol, "")),
                "ref_high": num(row.get(hcol, "")),
            })
    return out


def main() -> None:
    cmp_rows = collect("OSD-575", STUDIES["OSD-575"]["file"], CMP_ANALYTES)
    cbc_rows = collect("OSD-569", STUDIES["OSD-569"]["file"], CBC_ANALYTES,
                        special={"hemoglobin": CBC_HEMOGLOBIN_PERCENT_COLUMNS})
    rows = cmp_rows + cbc_rows
    if not rows:
        raise SystemExit("ERROR: no laboratory values parsed from the OSDR downloads")
    subjects = sorted({r["subject"] for r in rows})
    analytes = sorted({r["analyte"] for r in rows})
    print(f"subjects: {subjects}")
    print(f"analytes: {analytes}")
    print(f"values: {len(rows)}")
    write_json("osdr_i4/labs.json", rows)


if __name__ == "__main__":
    main()
