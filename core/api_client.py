"""
Siber Güvenlik Başkanlığı REST API Client
Provides integration with https://siberguvenlik.gov.tr/api/ for threat intelligence queries.
"""

import json
import logging
import ssl
import time
import urllib.parse
import urllib.request
from typing import Dict, List, Optional

logger = logging.getLogger("siberguvenlik_api")

SOURCES_MAP: Dict[str, str] = {
    "US": "USOM (TR-CERT)",
    "SO": "SOME (CERT)",
    "RS": "RSA",
    "IH": "İhbar Bildirimi",
    "SB": "Siber Güvenlik Başkanlığı (SGB)"
}

DESCRIPTIONS_MAP: Dict[str, str] = {
    "PH": "Oltalama (Phishing)",
    "MD": "Zararlı Yazılım Barındıran Domain",
    "MI": "Zararlı Yazılım Barındıran IP",
    "MU": "Zararlı Yazılım Barındıran URL",
    "BP": "Banka Oltalama (Bank Phishing)",
    "C2": "Komuta Kontrol Merkezi (C&C Server)",
    "RANSOM": "Fidye Yazılımı (Ransomware)"
}

CONNECTION_TYPES_MAP: Dict[str, str] = {
    "AC": "APT C&C",
    "BC": "Botnet C&C",
    "EK": "Exploit Kit",
    "MC": "Mobil C&C",
    "MF": "Zararlı Dosya İndirme",
    "MM": "Mining Zararlısı",
    "OT": "Diğer Tehditler",
    "PH": "Oltalama"
}

class SiberGuvenlikAPIClient:
    BASE_URL = "https://siberguvenlik.gov.tr/api"
    
    def __init__(self, timeout: int = 15, user_agent: Optional[str] = None):
        self.timeout = timeout
        self.user_agent = user_agent or "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        self.ssl_context = ssl.create_default_context()
        self.ssl_context.check_hostname = False
        self.ssl_context.verify_mode = ssl.CERT_NONE
        
        self._load_metadata()

    def _load_metadata(self):
        """Fetches live description, source, and connection type maps from API."""
        try:
            sources = self._get("address-source/index")
            if sources and "models" in sources:
                for item in sources["models"]:
                    SOURCES_MAP[item["id"]] = f"{item.get('tr_title', item['id'])} ({item.get('en_title', '')})"
            
            descriptions = self._get("address-description/index")
            if descriptions and "models" in descriptions:
                for item in descriptions["models"]:
                    DESCRIPTIONS_MAP[item["id"]] = item.get("tr_title", item["id"])
                    
            connection_types = self._get("address-connection-type/index")
            if connection_types and "models" in connection_types:
                for item in connection_types["models"]:
                    CONNECTION_TYPES_MAP[item["id"]] = item.get("tr_title", item["id"])
        except Exception as e:
            logger.debug(f"Metadata load warning: {e}")

    def _get(self, endpoint: str, params: Optional[Dict[str, str]] = None, retries: int = 2) -> Optional[Dict]:
        """Executes HTTP GET request with retries & graceful rate limiting handling."""
        url = f"{self.BASE_URL}/{endpoint}"
        if params:
            encoded_params = urllib.parse.urlencode(params)
            url = f"{url}?{encoded_params}"
            
        req = urllib.request.Request(url, headers={
            "User-Agent": self.user_agent,
            "Accept": "application/json",
            "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
            "Connection": "keep-alive"
        })
        
        for attempt in range(retries + 1):
            try:
                with urllib.request.urlopen(req, context=self.ssl_context, timeout=self.timeout) as resp:
                    if resp.status == 200:
                        body = resp.read().decode("utf-8")
                        return json.loads(body)
            except Exception as e:
                if attempt < retries:
                    time.sleep(0.5 * (attempt + 1))
                    continue
                logger.error(f"API Request failed for {url}: {e}")
                raise e
        return None

    def check_domain(self, domain: str, strict_match: bool = False, type_filter: Optional[str] = None) -> Dict:
        """
        Queries a domain against the Cyber Security Presidency API.
        """
        clean_target = domain.lower().strip()
        params = {
            "q": clean_target,
            "per-page": "30"
        }
        if type_filter:
            params["type"] = type_filter

        try:
            res = self._get("address/index", params)
            if not res:
                return {
                    "domain": clean_target,
                    "is_blocked": False,
                    "status": "TEMİZ",
                    "match_count": 0,
                    "match_type": "Eşleşme Yok",
                    "threats": [],
                    "max_criticality": None,
                    "error": None
                }

            models = res.get("models", [])
            matching_threats = []
            exact_found = False
            subdomain_found = False

            for item in models:
                raw_url = item.get("url", "").lower().strip()
                item_id = item.get("id")
                
                is_exact = (raw_url == clean_target)
                is_subdomain = (
                    raw_url.endswith("." + clean_target) or 
                    clean_target.endswith("." + raw_url)
                )
                
                if is_exact or is_subdomain or not strict_match:
                    if is_exact:
                        exact_found = True
                    if is_subdomain:
                        subdomain_found = True

                    desc_code = item.get("desc", "")
                    source_code = item.get("source", "")
                    conn_code = item.get("connectiontype", "")

                    matching_threats.append({
                        "id": item_id,
                        "url": raw_url,
                        "type": item.get("type", "domain"),
                        "desc_code": desc_code,
                        "desc_text": DESCRIPTIONS_MAP.get(desc_code, desc_code or "Zararlı Adres"),
                        "source_code": source_code,
                        "source_text": SOURCES_MAP.get(source_code, source_code or "SGB"),
                        "connection_type_code": conn_code,
                        "connection_type_text": CONNECTION_TYPES_MAP.get(conn_code, conn_code or "Bilinmiyor"),
                        "criticality_level": item.get("criticality_level"),
                        "date": item.get("date")
                    })

            is_blocked = len(matching_threats) > 0
            
            if exact_found:
                match_type = "Tam Domain Eşleşmesi"
            elif subdomain_found:
                match_type = "Alt Domain / Üst Domain Eşleşmesi"
            elif is_blocked:
                match_type = "İlişkili Tehdit Kaydı"
            else:
                match_type = "Eşleşme Yok (Güvenli)"

            crit_levels = [t["criticality_level"] for t in matching_threats if t.get("criticality_level") is not None]
            max_crit = min(crit_levels) if crit_levels else None

            return {
                "domain": clean_target,
                "is_blocked": is_blocked,
                "status": "ENGELLENMİŞ" if is_blocked else "TEMİZ",
                "match_count": len(matching_threats),
                "match_type": match_type,
                "threats": matching_threats,
                "max_criticality": max_crit,
                "error": None
            }

        except Exception as e:
            return {
                "domain": clean_target,
                "is_blocked": False,
                "status": "HATA",
                "match_count": 0,
                "match_type": "Sorgu Hatası",
                "threats": [],
                "max_criticality": None,
                "error": str(e)
            }
