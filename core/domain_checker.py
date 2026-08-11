"""
Bulk Domain Threat Checker Module
Manages multi-threaded query execution, deduplication, progress reporting, and statistics.
"""

import concurrent.futures
import time
from typing import Callable, Dict, Generator, List, Optional
from core.api_client import SiberGuvenlikAPIClient
from core.normalizer import clean_domain, is_valid_domain

class BulkDomainChecker:
    def __init__(self, max_threads: int = 15, timeout: int = 10, strict_match: bool = False):
        self.max_threads = max_threads
        self.strict_match = strict_match
        self.api_client = SiberGuvenlikAPIClient(timeout=timeout)

    def scan_domains(
        self,
        domain_list: List[str],
        progress_callback: Optional[Callable[[int, int, Dict], None]] = None
    ) -> Dict:
        """
        Scans a list of domains concurrently and returns full report.
        """
        start_time = time.time()
        
        cleaned_domains = []
        seen = set()
        invalid_domains = []

        for raw in domain_list:
            cd = clean_domain(raw)
            if not cd or cd in seen:
                continue
            seen.add(cd)
            
            if is_valid_domain(cd) or "." in cd:
                cleaned_domains.append(cd)
            else:
                invalid_domains.append(raw)

        total_domains = len(cleaned_domains)
        results: List[Dict] = []
        completed_count = 0
        blocked_count = 0
        clean_count = 0
        error_count = 0
        high_criticality_count = 0

        def worker(dom: str) -> Dict:
            return self.api_client.check_domain(dom, strict_match=self.strict_match)

        if total_domains > 0:
            with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_threads) as executor:
                future_to_domain = {
                    executor.submit(worker, dom): dom for dom in cleaned_domains
                }

                for future in concurrent.futures.as_completed(future_to_domain):
                    completed_count += 1
                    try:
                        res = future.result()
                    except Exception as e:
                        dom = future_to_domain[future]
                        res = {
                            "domain": dom,
                            "is_blocked": False,
                            "status": "HATA",
                            "match_count": 0,
                            "match_type": "İstisna Hatası",
                            "threats": [],
                            "max_criticality": None,
                            "error": str(e)
                        }
                    
                    if res["status"] == "ENGELLENMİŞ":
                        blocked_count += 1
                        if res.get("max_criticality") is not None and res["max_criticality"] <= 3:
                            high_criticality_count += 1
                    elif res["status"] == "TEMİZ":
                        clean_count += 1
                    else:
                        error_count += 1

                    results.append(res)
                    
                    if progress_callback:
                        progress_callback(completed_count, total_domains, res)

        duration = round(time.time() - start_time, 2)
        rate = round(total_domains / duration, 1) if duration > 0 else 0.0

        results.sort(key=lambda x: (0 if x["is_blocked"] else 1, x["domain"]))

        return {
            "summary": {
                "total_scanned": total_domains,
                "blocked_count": blocked_count,
                "clean_count": clean_count,
                "error_count": error_count,
                "invalid_count": len(invalid_domains),
                "high_criticality_count": high_criticality_count,
                "duration_seconds": duration,
                "domains_per_second": rate,
                "scan_timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
            },
            "results": results,
            "invalid_domains": invalid_domains
        }

    def scan_domains_stream(self, domain_list: List[str]) -> Generator[Dict, None, None]:
        """
        Yields real-time events as each domain completes for live web UI streaming.
        """
        start_time = time.time()
        
        cleaned_domains = []
        seen = set()
        invalid_domains = []

        for raw in domain_list:
            cd = clean_domain(raw)
            if not cd or cd in seen:
                continue
            seen.add(cd)
            
            if is_valid_domain(cd) or "." in cd:
                cleaned_domains.append(cd)
            else:
                invalid_domains.append(raw)

        total_domains = len(cleaned_domains)
        yield {
            "type": "start",
            "total": total_domains,
            "invalid_count": len(invalid_domains)
        }

        results: List[Dict] = []
        completed_count = 0
        blocked_count = 0
        clean_count = 0
        error_count = 0
        high_criticality_count = 0

        def worker(dom: str) -> Dict:
            return self.api_client.check_domain(dom, strict_match=self.strict_match)

        if total_domains > 0:
            with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_threads) as executor:
                future_to_domain = {
                    executor.submit(worker, dom): dom for dom in cleaned_domains
                }

                for future in concurrent.futures.as_completed(future_to_domain):
                    completed_count += 1
                    try:
                        res = future.result()
                    except Exception as e:
                        dom = future_to_domain[future]
                        res = {
                            "domain": dom,
                            "is_blocked": False,
                            "status": "HATA",
                            "match_count": 0,
                            "match_type": "İstisna Hatası",
                            "threats": [],
                            "max_criticality": None,
                            "error": str(e)
                        }

                    if res["status"] == "ENGELLENMİŞ":
                        blocked_count += 1
                        if res.get("max_criticality") is not None and res["max_criticality"] <= 3:
                            high_criticality_count += 1
                    elif res["status"] == "TEMİZ":
                        clean_count += 1
                    else:
                        error_count += 1

                    results.append(res)
                    duration = round(time.time() - start_time, 2)
                    rate = round(completed_count / duration, 1) if duration > 0 else 0.0

                    yield {
                        "type": "progress",
                        "completed": completed_count,
                        "total": total_domains,
                        "result": res,
                        "stats": {
                            "blocked_count": blocked_count,
                            "clean_count": clean_count,
                            "error_count": error_count,
                            "high_criticality_count": high_criticality_count,
                            "duration_seconds": duration,
                            "domains_per_second": rate
                        }
                    }

        duration = round(time.time() - start_time, 2)
        rate = round(total_domains / duration, 1) if duration > 0 else 0.0
        results.sort(key=lambda x: (0 if x["is_blocked"] else 1, x["domain"]))

        yield {
            "type": "complete",
            "summary": {
                "total_scanned": total_domains,
                "blocked_count": blocked_count,
                "clean_count": clean_count,
                "error_count": error_count,
                "invalid_count": len(invalid_domains),
                "high_criticality_count": high_criticality_count,
                "duration_seconds": duration,
                "domains_per_second": rate,
                "scan_timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
            },
            "results": results
        }
