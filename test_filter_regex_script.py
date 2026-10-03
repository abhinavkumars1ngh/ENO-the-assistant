import re

test_cases = [
    "[MOOD: Furious | NAME: Eno] I am angry!",
    "[MOOD: Ready to crush it | NAME: Linda] Let's go!",
    "[NAME: ABHINAV] Hello there.",
    "[CRITICAL SYSTEM DIRECTIVE: angry] System is angry.",
    "[System Note: web search] Searching the web...",
    "Normal text without tags.",
    "[MOOD: Happy] Just happy."
]

def extract_mood_and_name(buffer):
    mood = None
    name = None
    
    # Same regex used in backend/core/conversation.py
    mood_match = re.search(r'\[(?:.*?MOOD:\s*)([^|\]\n]+?)\s*(?:\|\s*NAME:\s*([^\]\n]+))?\]', buffer, re.IGNORECASE)
    if mood_match:
        mood = mood_match.group(1).strip()
        name = mood_match.group(2).strip() if mood_match.group(2) else "Persona"
    else:
        # Check if there is only NAME
        name_match = re.search(r'\[(?:.*?NAME:\s*)([^|\]\n]+?)\]', buffer, re.IGNORECASE)
        if name_match:
            name = name_match.group(1).strip()

    return mood, name

def strip_tags(buffer):
    safe_buffer = re.sub(r'\[(?:.*?MOOD:\s*[^|\]\n]+|.*?NAME:\s*[^\]\n]+)(?:\|[^\]]+)?\]\s*', '', buffer, flags=re.IGNORECASE)
    safe_buffer = re.sub(r'\[(?:System Note|CRITICAL).*?\]\s*', '', safe_buffer, flags=re.IGNORECASE)
    return safe_buffer

for case in test_cases:
    print(f"Original: {case}")
    mood, name = extract_mood_and_name(case)
    print(f"Extracted -> Mood: {mood}, Name: {name}")
    stripped = strip_tags(case)
    print(f"Stripped -> {stripped}")
    print("-" * 40)
