import re

text = "[MOOD: Angry]"
mood_match = re.search(r'\[(?:.*?MOOD:)?\s*([^\|\]\n]+?)\s*(?:\|\s*NAME:\s*([^\]\n]+))?\]', text, re.IGNORECASE)
if mood_match:
    print("Mood:", mood_match.group(1))
    print("Name:", mood_match.group(2))
