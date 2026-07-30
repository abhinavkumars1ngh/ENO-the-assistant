import requests
import urllib.parse
from bs4 import BeautifulSoup

query = "lamine yamal is in fifa worldcup finals?"
headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}
encoded_query = urllib.parse.quote_plus(query)
try:
    resp = requests.get(
        f"https://www.bing.com/search?q={encoded_query}&setlang=en",
        headers=headers,
        timeout=10,
    )
    print("STATUS:", resp.status_code)
    soup = BeautifulSoup(resp.text, "html.parser")
    results = []
    for item in soup.select("li.b_algo")[:5]:
        title_el = item.select_one("h2 a")
        snippet_el = item.select_one(".b_caption p") or item.select_one("p")
        if title_el and snippet_el:
            title = title_el.get_text(strip=True)
            snippet = snippet_el.get_text(strip=True)
            results.append(f"- {title}: {snippet}")
    print("RESULTS:\n", "\n".join(results) if results else "No results found in HTML")
except Exception as e:
    print("ERROR:", e)
