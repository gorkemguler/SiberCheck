"""
JSON & CSV Report Exporters
Exports query result dictionaries to formatted JSON and CSV files.
"""

import csv
import json
from typing import Dict

def generate_json_report(report_data: Dict, file_path: str):
    """Generates a clean formatted JSON output file."""
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(report_data, f, ensure_ascii=False, indent=2)

def generate_csv_report(report_data: Dict, file_path: str):
    """Generates a CSV output file."""
    results = report_data.get("results", [])
    
    headers = [
        "domain",
        "durum",
        "eslesme_turu",
        "en_yuksek_kritiklik",
        "tehdit_kayit_sayisi",
        "tehdit_kategorisi",
        "tehdit_kaynagi",
        "baglanti_tipi",
        "tespit_tarihi",
        "hata"
    ]
    
    with open(file_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        
        for item in results:
            threats = item.get("threats", [])
            t0 = threats[0] if threats else {}
            
            writer.writerow([
                item.get("domain", ""),
                item.get("status", ""),
                item.get("match_type", ""),
                item.get("max_criticality", ""),
                item.get("match_count", 0),
                t0.get("desc_text", ""),
                t0.get("source_text", ""),
                t0.get("connection_type_text", ""),
                t0.get("date", ""),
                item.get("error", "")
            ])
