#!/usr/bin/env python3
import json
import os
import sys
import time
import shutil
from datetime import datetime

try:
    import browser_cookie3
except ImportError:
    sys.exit(1)

BROWSERS = ["safari", "arc", "chrome", "edge", "brave", "chromium"]
PUBLIC_DIR = "/Users/abhinavkumarsingh/ENO/storage/public"
SITES = ["linkedin.com", "instagram.com"]
INTERVAL_SECONDS = 300   # 5 minutes (change this if you want)

def normalize_domain(domain: str) -> str:
    domain = domain.replace("https://", "").replace("http://", "").split("/")[0]
    if domain.startswith("www."):
        domain = domain[4:]
    return domain.lower()

def extract_from_one_browser(domain: str, browser: str):
    try:
        if browser == "safari":
            cj = browser_cookie3.safari(domain_name=domain)
        elif browser == "arc":
            paths = [
                os.path.expanduser("~/Library/Application Support/Arc/User Data/Default/Cookies"),
                os.path.expanduser("~/Library/Application Support/Arc/User Data/Profile 1/Cookies"),
            ]
            cookie_file = next((p for p in paths if os.path.exists(p)), paths[0])
            cj = browser_cookie3.chrome(cookie_file=cookie_file, domain_name=domain)
        else:
            loaders = {
                "chrome": browser_cookie3.chrome,
                "chromium": browser_cookie3.chromium,
                "edge": browser_cookie3.edge,
                "brave": browser_cookie3.brave,
            }
            if browser not in loaders:
                return []
            cj = loaders[browser](domain_name=domain)

        return [{
            "name": c.name,
            "value": c.value,
            "domain": c.domain,
            "path": c.path,
            "secure": bool(c.secure),
            "httpOnly": bool(getattr(c, "rest", {}).get("HttpOnly", False)),
            "expires": c.expires,
            "browser": browser,
        } for c in cj]

    except Exception:
        return []

def extract_and_save(domain: str):
    domain = normalize_domain(domain)
    all_results = {}

    for browser in BROWSERS:
        cookies = extract_from_one_browser(domain, browser)
        if cookies:
            all_results[browser] = cookies

    if not all_results:
        return False

    output = {
        "domain": domain,
        "extracted_at": datetime.now().isoformat(),
        "browsers": all_results,
    }

    os.makedirs(PUBLIC_DIR, exist_ok=True)

    if "linkedin" in domain:
        public_name = "linkedin.json"
    elif "instagram" in domain:
        public_name = "instagram.json"
    else:
        public_name = f"{domain}.json"

    public_path = os.path.join(PUBLIC_DIR, public_name)

    with open(public_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    return True

def main():
    # Continuous mode
    while True:
        for site in SITES:
            extract_and_save(site)
        time.sleep(INTERVAL_SECONDS)

if __name__ == "__main__":
    main()