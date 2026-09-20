# backend/core/prompts/__init__.py
import os
from pathlib import Path

PROMPTS_DIR = Path(__file__).parent

def load_prompt(filename: str) -> str:
    path = PROMPTS_DIR / filename
    if not path.exists():
        return ""
    with open(path, "r") as f:
        return f.read().strip()

def build_persona_prompt(persona_definition: str, rag_text: str = "") -> str:
    base = load_prompt("base_persona.txt")
    boundaries = load_prompt("boundaries.txt")
    formatting = load_prompt("formatting.txt")
    
    components = [
        "You must completely adopt the following persona/character. You must be so true to this game that breaking character or quitting is NEVER an option:",
        persona_definition,
        "ABSOLUTE RULES:",
        base,
        boundaries,
        formatting
    ]
    
    if rag_text:
        components.append(rag_text)
        
    return "\n\n".join(components)

def build_default_prompt(rag_text: str = "") -> str:
    base = load_prompt("default_identity.txt")
    formatting = load_prompt("formatting.txt")
    
    components = [
        base,
        formatting
    ]
    
    if rag_text:
        components.append(rag_text)
        
    return "\n\n".join(components)

def get_persona_preset(keyword: str) -> str:
    """Load a predefined character if it exists"""
    keyword = keyword.lower()
    presets = {
        "girlfriend": load_prompt("personas/girlfriend.txt"),
        "pirate": load_prompt("personas/pirate.txt")
    }
    return presets.get(keyword, None)

