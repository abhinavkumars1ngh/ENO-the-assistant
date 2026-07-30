import requests
import urllib.parse
from bs4 import BeautifulSoup

query = "lamine yamal is in fifa worldcup finals?"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}
data = {"q": query}
try:
    resp = requests.post("https://lite.duckduckgo.com/lite/", headers=headers, data=data)
    soup = BeautifulSoup(resp.text, "html.parser")
    results = []
    for tr in soup.find_all("tr"):
        td = tr.find("td", class_="result-snippet")
        if td:
            results.append(td.get_text(strip=True))
    print("RESULTS:\n", "\n".join(results[:5]))
except Exception as e:
    print("ERROR:", e)
