class StateManager:
    """Manages chat-level state (like Personas) abstractly."""
    
    @staticmethod
    def get_active_persona(history: list) -> str:
        """Parses the chat history event stream to find the latest persona state."""
        for mem in reversed(history):
            if mem.get("role") == "user":
                content = mem.get("content", "").strip()
                if content.startswith("@/become"):
                    return None
                elif content.startswith("@become "):
                    # Extract the entire string after @become
                    return content[len("@become "):].strip()
        return None

    @staticmethod
    def sanitize_prompt_for_llm(content: str) -> str:
        """
        Cleans the user's prompt before it reaches the LLM. 
        It hides the raw '@become' commands so the LLM doesn't get confused by system directives.
        """
        content = content.strip()
        if content.startswith("@/become"):
            return "Hey!"
        if content.startswith("@become "):
            return "Hi!"
        return content

state_manager = StateManager()
