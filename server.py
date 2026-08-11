#!/usr/bin/env python3
"""
Siber Güvenlik Başkanlığı - Localhost Web Application Launcher
Run this script to start the local web UI dashboard on http://127.0.0.1:8000
"""

import sys
import os
import uvicorn

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    print("==========================================================================")
    print("  T.C. SİBER GÜVENLİK BAŞKANLIĞI — YEREL WEB ARAYÜZÜ (LOCALHOST DASHBOARD)")
    print("  Tarayıcınızda açın: http://127.0.0.1:8000")
    print("==========================================================================")
    uvicorn.run("web.app:app", host="127.0.0.1", port=8000, reload=True)
