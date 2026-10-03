import re

def stream_filter(chunks):
    buffer = ""
    for chunk in chunks:
        buffer += chunk
        if "[" in buffer and "]" not in buffer:
            continue
        
        # If there's a complete bracket or no bracket at all
        mood_match = re.search(r'\[(?:.*?MOOD:)?\s*([A-Za-z]+)\s*(?:\|\s*NAME:\s*([^\]\n]+))?\]', buffer, re.IGNORECASE)
        if mood_match:
            print("Extracted mood:", mood_match.groups())
            
        safe_buffer = re.sub(r'\[(?:.*?MOOD:)?\s*[A-Za-z]+\s*(?:\|\s*NAME:\s*[^\]\n]+)?\]\s*', '', buffer, flags=re.IGNORECASE)
        if safe_buffer:
            print("Yielding:", repr(safe_buffer))
        buffer = ""
        
    if buffer:
        safe_buffer = re.sub(r'\[(?:.*?MOOD:)?\s*[A-Za-z]+\s*(?:\|\s*NAME:\s*[^\]\n]+)?\]\s*', '', buffer, flags=re.IGNORECASE)
        if safe_buffer:
            print("Yielding:", repr(safe_buffer))

chunks = ["Hello ", "this is ", "[", "MOOD: ", "Furious ", "| NAME: Eno", "]", " and I am mad"]
stream_filter(chunks)
