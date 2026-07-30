import sys
from backend.core.scraper import search_web_selenium

res = search_web_selenium("lamine yamal is in fifa worldcup finals?")
print(f"SEARCH RESULTS:\n{res}")
