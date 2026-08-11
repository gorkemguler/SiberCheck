"""
Domain Normalizer & Sanitizer Module
Handles cleaning, URL parsing, IDN Punycode conversion, and domain validation.
"""

import re
import urllib.parse

def clean_domain(raw_input: str) -> str:
    """
    Cleans raw domain or URL string to a standard domain format.
    Example:
        - "https://www.example.com:8443/login?a=1" -> "example.com"
        - "  SUB.DOMAIN.COM.  " -> "sub.domain.com"
        - "http://şekerbank-test.org" -> "xn--ekerbank-test-r4b.org"
    """
    if not raw_input:
        return ""
    
    text = raw_input.strip()
    
    # Strip protocol if present
    if "://" in text:
        try:
            parsed = urllib.parse.urlparse(text)
            text = parsed.netloc or parsed.path
        except Exception:
            text = text.split("://", 1)[1]
    
    # Remove path, query, and fragment if remaining
    text = text.split("/")[0].split("?")[0].split("#")[0]
    
    # Remove port if present
    if ":" in text and not text.startswith("["):  # Avoid breaking IPv6
        text = text.split(":")[0]
    
    # Remove userinfo (e.g. user:pass@domain.com)
    if "@" in text:
        text = text.split("@")[-1]
    
    # Remove trailing dot
    text = text.rstrip(".")
    
    # Lowercase
    text = text.lower()
    
    # IDN / Punycode conversion for Turkish/Non-ASCII characters
    try:
        text = text.encode("idna").decode("ascii")
    except Exception:
        pass
    
    return text

def is_valid_domain(domain: str) -> bool:
    """
    Validates if a string resembles a valid domain structure.
    """
    if not domain or len(domain) > 253:
        return False
    
    # Simple regex for domain matching (allows subdomains, hyphens, IDN punycode)
    domain_regex = re.compile(
        r'^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$'
    )
    return bool(domain_regex.match(domain))
