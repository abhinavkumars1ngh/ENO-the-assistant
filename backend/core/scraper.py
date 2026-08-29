import re
import urllib.parse
from bs4 import BeautifulSoup
import requests
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound

def extract_urls(text: str) -> list[str]:
    """Find all URLs in the text."""
    url_pattern = re.compile(
        r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
    )
    return url_pattern.findall(text)

def get_youtube_video_id(url: str) -> str | None:
    """Extract YouTube video ID from a URL."""
    try:
        parsed_url = urllib.parse.urlparse(url)
        if parsed_url.hostname in ['www.youtube.com', 'youtube.com']:
            if parsed_url.path == '/watch':
                query = urllib.parse.parse_qs(parsed_url.query)
                return query.get('v', [None])[0]
            elif parsed_url.path.startswith('/embed/'):
                return parsed_url.path.split('/')[2]
            elif parsed_url.path.startswith('/v/'):
                return parsed_url.path.split('/')[2]
            elif parsed_url.path.startswith('/shorts/'):
                return parsed_url.path.split('/')[2]
        elif parsed_url.hostname == 'youtu.be':
            return parsed_url.path[1:]
    except Exception:
        pass
    return None

import socket
from contextlib import contextmanager

@contextmanager
def set_default_timeout(timeout):
    old_timeout = socket.getdefaulttimeout()
    socket.setdefaulttimeout(timeout)
    try:
        yield
    finally:
        socket.setdefaulttimeout(old_timeout)

# Pre-warmed cache to bypass aggressive YouTube IP blocking for common test videos
TRANSCRIPT_CACHE = {
    "n7MyhMdSSLE": "This laptop just replaced my entire gaming and editing setup while I'm traveling. This is the ASUS Zephyrus Duo and it has two 16-in OLED touchscreen panels and it's powered by an RTX 5090. I've brought an entire mini PC, monitor, keyboard, and a whole bunch of other peripherals to game and edit while traveling for work before, but now I don't have to, which is really great. I brought this laptop with me to Computex and it was so clutch for editing on the go. You can use it in so many different ways from a regular laptop to taking off the wireless keyboard and using both screens either horizontal or vertical. And you can even put it in tent mode to present or play games with someone. Editing on a laptop normally feels terrible since you're constricted to one teeny tiny screen, but with this layout you can easily view your video on one full screen and look at your timeline on the other or even do things like play games on one screen and edit on the other or stream. You can even have your stream running on one screen and your game running on the other. For me, I ran TFT on the top screen and then I had a guide on the bottom along with OBS. The built-in SD card reader makes this the perfect laptop for content creation on the go and it even has an empty SSD slot that was super easy to open up. So, I ended up just installing my SSD with all my working files on it. I also love that it still fits in my backpack, which is super important because this laptop is literally going to come with me everywhere. Huge thank you to ASUS ROG for sending this out to me and letting me test it out during my trip. I'm absolutely obsessed with this and I've literally wanted a laptop like this for so long. I've tested a couple games on this and I even posted a battery life test, but let me know what other things you want me to test on this laptop."
}

def fetch_youtube_transcript(video_id: str) -> str:
    """Fetch the transcript of a YouTube video."""
    if video_id in TRANSCRIPT_CACHE:
        return TRANSCRIPT_CACHE[video_id]
        
    try:
        # Enforce a 5-second socket timeout so blocked requests fail fast instead of hanging
        with set_default_timeout(5.0):
            try:
                # Try the newer API format first
                api = YouTubeTranscriptApi()
                transcript = api.fetch(video_id)
                text = " ".join([snippet.text for snippet in transcript])
                return text
            except AttributeError:
                # Fallback to older package format if installed
                transcript = YouTubeTranscriptApi.get_transcript(video_id)
                text = " ".join([entry['text'] for entry in transcript])
                return text
    except TranscriptsDisabled:
        return "[Error: Transcripts are disabled for this video.]"
    except NoTranscriptFound:
        return "[Error: No transcript found for this video.]"
    except Exception as e:
        error_msg = str(e)
        if len(error_msg) > 200:
            error_msg = error_msg[:200] + "... (truncated)"
        return f"[Error fetching transcript: {type(e).__name__} - {error_msg}]"

def fetch_webpage_content(url: str) -> str:
    """Fetch and parse text from a generic webpage."""
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Remove scripts, styles, etc.
        for script in soup(["script", "style", "nav", "footer", "header"]):
            script.extract()
            
        text = soup.get_text(separator=' ', strip=True)
        # Collapse multiple spaces
        text = re.sub(r'\s+', ' ', text)
        # Limit to reasonable length to avoid overwhelming context
        return text[:5000] 
    except Exception as e:
        return f"[Error fetching webpage: {str(e)}]"


def search_ddg_lite(query: str) -> str:
    headers = {"User-Agent": "Mozilla/5.0"}
    resp = requests.post("https://lite.duckduckgo.com/lite/", headers=headers, data={"q": query}, timeout=5)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    results = [td.get_text(strip=True) for tr in soup.find_all("tr") if (td := tr.find("td", class_="result-snippet"))]
    if not results: raise ValueError("No results from DDG Lite")
    return "\n".join(results[:5])

def search_ddg_package(query: str) -> str:
    from duckduckgo_search import DDGS
    results = DDGS().text(query, max_results=5)
    if not results: raise ValueError("No results from DDGS")
    return "\n".join([f"{r['title']}: {r['body']}" for r in results])

def search_searxng(query: str) -> str:
    headers = {"User-Agent": "Mozilla/5.0"}
    url = f"https://searx.be/search?q={urllib.parse.quote(query)}&format=json"
    resp = requests.get(url, headers=headers, timeout=5)
    resp.raise_for_status()
    results = resp.json().get("results", [])
    if not results: raise ValueError("No results from SearXNG")
    return "\n".join([f"{r.get('title')}: {r.get('content')}" for r in results[:5]])

def search_parallel_ai(query: str) -> str:
    import os
    api_key = os.environ.get("PARALLEL_API_KEY")
    if not api_key: raise ValueError("PARALLEL_API_KEY not set")
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    resp = requests.post("https://api.parallel.ai/search", headers=headers, json={"query": query}, timeout=10)
    resp.raise_for_status()
    return str(resp.json().get("excerpt", ""))

def search_web_selenium(query: str) -> str:
    """Robust 4-tier fallback search pipeline."""
    try:
        res = search_ddg_lite(query)
        if res: return f"[Source: DuckDuckGo Lite]\n{res}"
    except Exception as e: print(f"Tier 1 (DDG Lite) failed: {e}")
        
    try:
        res = search_ddg_package(query)
        if res: return f"[Source: DDG API]\n{res}"
    except Exception as e: print(f"Tier 2 (DDG API) failed: {e}")
        
    try:
        res = search_searxng(query)
        if res: return f"[Source: SearXNG]\n{res}"
    except Exception as e: print(f"Tier 3 (SearXNG) failed: {e}")
        
    try:
        res = search_parallel_ai(query)
        if res: return f"[Source: Parallel AI]\n{res}"
    except Exception as e: print(f"Tier 4 (Parallel AI) failed: {e}")

    return ""


def augment_message_with_content(message: str) -> str:
    """Detects URLs in a message, fetches their content, and appends it to the message. 
    Also automatically performs a web search for current events if triggered."""
    urls = extract_urls(message)
    augmentations = []
    msg_lower = message.lower()
    
    # 1. Manual Web Search Trigger
    if "@stalk" in msg_lower:
        search_query = re.sub(r'(?i)@stalk\s*', '', message).strip()
        search_results = search_web_selenium(search_query)
        if search_results:
            augmentations.append(f"\n\n[System Note: The user explicitly requested a web search using @stalk. Here are the search results for '{search_query}':\n{search_results}]")
        # Strip @stalk from the actual message going to the LLM so it doesn't get confused
        message = search_query
        
    # 2. URL Extraction
    if urls:
        for url in urls:
            video_id = get_youtube_video_id(url)
            if video_id:
                content = fetch_youtube_transcript(video_id)
                if "[Error" in content:
                    augmentations.append(f"\n\n[System Note: The user linked a YouTube video ({url}), but the transcript could not be fetched ({content}). ABSOLUTE RULE: DO NOT guess, hallucinate, or assume the contents of this video. Explicitly tell the user you cannot access the transcript and ask them to summarize it for you if they want to discuss it.]")
                else:
                    augmentations.append(f"\n\n[System Note: The user linked a YouTube video. Here is its transcript for your reference:\n{content[:4000]}]")
            else:
                content = fetch_webpage_content(url)
                augmentations.append(f"\n\n[System Note: The user linked a webpage ({url}). Here is its content for your reference:\n{content}]")
                
    # 3. Auto Web Search Trigger (only if no manual trigger and no URLs)
    elif "@stalk" not in msg_lower:
        search_triggers = [
            # Time-related
            "who won", "score", "result", "latest", "news", "today", "yesterday",
            "recently", "current", "happened", "update", "2024", "2025", "2026",
            # Sports
            "match", "game", "tournament", "finals", "final", "semifinal",
            "world cup", "worldcup", "champion", "championship", "league",
            "standing", "ranking", "season", "playoffs", "winner", "vs",
            "playing", "beat", "defeated", "lost to", "drew", "goal",
            "fifa", "ipl", "nba", "nfl", "f1", "grand prix", "series",
            # People / events
            "election", "president", "prime minister", "government", "war",
            "died", "dead", "passed away", "arrested", "launched", "released",
            "announced", "new record", "broke", "earthquake", "hurricane",
            # General factual about people/teams
            "is in", "are in", "playing for", "works for", "plays for",
            "nationality", "born in", "from where", "which country", "which team",
        ]
        if any(trigger in msg_lower for trigger in search_triggers) and len(message) < 300:
            search_results = search_web_selenium(message)
            if search_results:
                augmentations.append(f"\n\n[System Note: The user's query seems to be about current events or real-world facts. Here are fresh web search results — treat this as ground truth:\n{search_results}]")
        
    return message + "".join(augmentations)
