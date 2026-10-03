import re

test_cases = [
    "[MOOD: Furious | NAME: Eno] I am angry!",
    "[MOOD: Ready to crush it | NAME: Linda] Let's go!",
    "[NAME: ABHINAV] Hello there.",
    "[CRITICAL SYSTEM DIRECTIVE: angry] System is angry.",
    "[System Note: web search] Searching the web..."
]

def simulate_backend_regex(buffer):
    mood = None
    name = None
    
    # Exact regex from backend/core/conversation.py
    mood_match = re.search(r'\[(?:.*?MOOD:\s*)([^\|\]\n]+?)\s*(?:\|\s*NAME:\s*([^\]\n]+))?\]', buffer, re.IGNORECASE)
    if mood_match:
        mood = mood_match.group(1).strip()
        name = mood_match.group(2).strip() if mood_match.group(2) else "Persona"
        
    safe_buffer = re.sub(r'\[(?:.*?MOOD:\s*[^\|\]\n]+|.*?NAME:\s*[^\]\n]+)(?:\|[^\]]+)?\]\s*', '', buffer, flags=re.IGNORECASE)
    safe_buffer = re.sub(r'\[(?:System Note|CRITICAL).*?\]\s*', '', safe_buffer, flags=re.IGNORECASE)
    
    return mood, name, safe_buffer

print("Running Regex Tests on Backend Implementation:\n")
for case in test_cases:
    print(f"Original Text: {case}")
    mood, name, stripped = simulate_backend_regex(case)
    print(f"Extracted Mood: {mood}")
    print(f"Extracted Name: {name}")
    print(f"Stripped Text: {stripped}")
    print("-" * 50)
