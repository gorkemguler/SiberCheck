"""
Localhost Web UI Backend (FastAPI Application)
Provides REST API endpoints and streaming web interface for Cyber Security Presidency bulk domain checking.
"""

import io
import json
import os
from typing import List, Optional
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from core.domain_checker import BulkDomainChecker
from core.normalizer import clean_domain
from exporters.excel_exporter import generate_excel_report
from exporters.json_exporter import generate_csv_report, generate_json_report

app = FastAPI(
    title="SiberCheck - Toplu Domain Engelleme Sorgulama",
    description="Localhost Cybersecurity Threat Intelligence Dashboard",
    version="2.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index_file = os.path.join(TEMPLATES_DIR, "index.html")
    if not os.path.exists(index_file):
        raise HTTPException(status_code=404, detail="Web UI template bulunamadı")
    with open(index_file, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

@app.post("/api/check")
async def check_domains(payload: dict):
    """
    Executes bulk query for provided domains array or text string.
    """
    raw_domains = payload.get("domains", [])
    threads = int(payload.get("threads", 15))
    strict = bool(payload.get("strict", False))

    if isinstance(raw_domains, str):
        lines = raw_domains.replace(",", "\n").split("\n")
        raw_domains = [l.strip() for l in lines if l.strip()]

    if not raw_domains:
        raise HTTPException(status_code=400, detail="Lütfen sorgulanacak en az 1 alan adı giriniz.")

    checker = BulkDomainChecker(max_threads=threads, strict_match=strict)
    report = checker.scan_domains(raw_domains)
    return report

@app.post("/api/check/stream")
async def check_domains_stream(payload: dict):
    """
    Streams query results domain by domain as NDJSON in real-time.
    """
    raw_domains = payload.get("domains", [])
    threads = int(payload.get("threads", 15))
    strict = bool(payload.get("strict", False))

    if isinstance(raw_domains, str):
        lines = raw_domains.replace(",", "\n").split("\n")
        raw_domains = [l.strip() for l in lines if l.strip()]

    if not raw_domains:
        raise HTTPException(status_code=400, detail="Lütfen sorgulanacak en az 1 alan adı giriniz.")

    checker = BulkDomainChecker(max_threads=threads, strict_match=strict)
    
    def event_generator():
        for event in checker.scan_domains_stream(raw_domains):
            yield json.dumps(event, ensure_ascii=False) + "\n"

    return StreamingResponse(
        event_generator(),
        media_type="application/x-ndjson"
    )

@app.post("/api/upload")
async def upload_and_check(
    file: UploadFile = File(...),
    threads: int = Form(15),
    strict: bool = Form(False)
):
    """
    Parses uploaded file (.txt, .csv) and executes bulk query.
    """
    content = await file.read()
    text = content.decode("utf-8", errors="ignore")
    lines = text.replace("\r", "\n").replace(",", "\n").split("\n")
    domains = [l.strip() for l in lines if l.strip() and not l.startswith("#")]

    if not domains:
        raise HTTPException(status_code=400, detail="Yüklenen dosyada geçerli domain bulunamadı.")

    checker = BulkDomainChecker(max_threads=threads, strict_match=strict)
    report = checker.scan_domains(domains)
    return report

@app.post("/api/export/excel")
async def export_excel(payload: dict):
    """
    Generates and returns Excel file download from query report payload.
    """
    tmp_path = os.path.join(BASE_DIR, "tmp_report.xlsx")
    try:
        generate_excel_report(payload, tmp_path)
        with open(tmp_path, "rb") as f:
            excel_bytes = f.read()
        
        return StreamingResponse(
            io.BytesIO(excel_bytes),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=sibercheck_domain_raporu.xlsx"}
        )
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass

@app.post("/api/export/json")
async def export_json(payload: dict):
    """Generates JSON download."""
    json_str = json.dumps(payload, ensure_ascii=False, indent=2)
    return StreamingResponse(
        io.BytesIO(json_str.encode("utf-8")),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=sibercheck_domain_raporu.json"}
    )

@app.post("/api/export/csv")
async def export_csv(payload: dict):
    """Generates CSV download."""
    tmp_path = os.path.join(BASE_DIR, "tmp_report.csv")
    try:
        generate_csv_report(payload, tmp_path)
        with open(tmp_path, "rb") as f:
            csv_bytes = f.read()
        return StreamingResponse(
            io.BytesIO(csv_bytes),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=sibercheck_domain_raporu.csv"}
        )
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass
