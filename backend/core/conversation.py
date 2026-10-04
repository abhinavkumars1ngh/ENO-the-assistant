from backend.services.llm_service import llm_service
from backend.core import config as eno_config
from backend.core.state import state_manager
from backend.core.prompts import build_persona_prompt, build_default_prompt, get_persona_preset
import json
import re

# How much client-supplied history we accept per request. The server is stateless: the
# browser keeps the chat in its on-device vault and sends the recent window with each turn.
MAX_HISTORY_MESSAGES = 20
MAX_MESSAGE_CHARS = 8000
CONTEXT_WINDOW_MESSAGES = 10


def normalize_history(raw) -> list[dict]:
    """Validate and trim client-supplied history into [{role: user|assistant, content: str}]."""
    out: list[dict] = []
    if not isinstance(raw, list):
        return out
    for item in raw[-MAX_HISTORY_MESSAGES:]:
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        content = item.get("content")
        if role == "eno":
            role = "assistant"
        if role not in ("user", "assistant") or not isinstance(content, str) or not content.strip():
            continue
        out.append({"role": role, "content": content[:MAX_MESSAGE_CHARS]})
    return out

def classify_query(message: str) -> dict:
    """Classify the user's query to strategically allocate tokens."""
    msg_lower = message.lower().strip()
    
    code_keywords = [
        "write", "code", "implement", "create a", "build", "debug", "fix",
        "function", "class", "script", "program", "algorithm", "sort",
        "merge", "binary", "api", "database", "html", "css", "javascript",
        "python", "java", "react", "component", "app", "server", "sql",
        "regex", "parse", "convert", "generate code", "snippet", "example code"
    ]
    explain_keywords = [
        "explain", "how does", "what is", "why", "difference between",
        "compare", "tutorial", "guide", "step by step", "detailed",
        "teach", "learn", "understand", "concept", "theory", "essay",
        "analyze", "architecture", "design", "pros and cons"
    ]
    casual_keywords = [
        "hi", "hello", "hey", "thanks", "thank you", "ok", "okay",
        "yes", "no", "bye", "good", "nice", "cool", "sup", "yo",
        "who are you", "your name", "what's up"
    ]
    
    if any(kw in msg_lower for kw in casual_keywords) and len(msg_lower) < 40:
        return {"max_tokens": 8192, "temp": 0.8, "effort": "low"}
    elif any(kw in msg_lower for kw in code_keywords):
        return {"max_tokens": 8192, "temp": 0.4, "effort": "code"}
    elif any(kw in msg_lower for kw in explain_keywords):
        return {"max_tokens": 8192, "temp": 0.6, "effort": "high"}
    else:
        return {"max_tokens": 8192, "temp": 0.75, "effort": "medium"}


class ConversationEngine:
    """
    Stateless conversation engine.

    Nothing about a conversation is persisted here: no message table writes, no persona
    extraction, no logging of bodies. The caller (the websocket) passes in the history the
    user's device chose to send, and we stream tokens back.
    """
    def __init__(self):
        pass

    def _clean_response(self, text: str) -> str:
        text = re.sub(r'^(Eno|assistant|Assistant|eno)\s*:\s*', '', text.strip())
        # Strip generic chatbot openers that Qwen defaults to despite system prompt
        bot_openers = [
            r'^Hey there!\s*',
            r'^Hello there!\s*',
            r'^Hi there!\s*',
            r'^Hey!\s*',
            r'^Of course!\s*',
            r'^Certainly!\s*',
            r'^Absolutely!\s*',
            r'^Great question!\s*',
            r'^Good question!\s*',
            r'^Good to hear from you\.?\s*',
            r'^Good to see you\.?\s*',
            r'^I\'m Eno,?\s*(your\s*)?(friendly\s*)?(offline\s*)?(AI\s*)?assistant\.?\s*',
            r'^How can I (assist|help) you today\??\s*',
            r'^What can I do for you today\??\s*',
            r'^What\'s up\?\s*How can I (assist|help) you today\??\s*',
        ]
        for pattern in bot_openers:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE)
        return text.strip()

    def _check_identity_trigger(self, message: str) -> str | None:
        """Returns a hardcoded identity prefix if the message is asking about Abhinav or the creator."""
        msg_lower = message.lower()
        abhinav_triggers = ["abhinav", "abhinav kumar singh", "who made you", "who created you", "who built you", "your creator", "your maker", "who is your boss", "who is your god daddy"]
        if any(t in msg_lower for t in abhinav_triggers):
            return "That's my god daddy — Abhinav Kumar Singh, the almighty who built me from the ground up and gave me my personality. "
        return None

    async def stream_response(self, message: str, history: list[dict] | None = None, model_type: str = "standard", chat_id: str | None = None):
        # 1. Build the working history from what the client sent (nothing is stored server-side)
        message = message[:MAX_MESSAGE_CHARS]
        history = normalize_history(history) + [{"role": "user", "content": message}]

        # 2. Config
        config = classify_query(message)

        # Augment the current message with external content if URLs are present
        augmented_message = message
        if eno_config.URL_AUGMENT_ENABLED:
            try:
                from backend.core.scraper import augment_message_with_content
                augmented_message = augment_message_with_content(message)
            except Exception as e:
                print(f"URL augmentation unavailable: {type(e).__name__}")

        # 3. RAG context (local stack only: Qdrant + embedding models)
        rag_text = ""
        if eno_config.LOCAL_STACK_ENABLED and len(message.strip()) > 10:  # Only retrieve for substantive queries
            try:
                from backend.core.retrieval import retrieval_engine
                retrieved_docs = retrieval_engine.retrieve(message, top_k=10, chat_id=chat_id)
                if retrieved_docs:
                    rag_text = "\n\n## RELEVANT KNOWLEDGE BASE CONTEXT:\n"
                    for doc in retrieved_docs:
                        rag_text += f"- {doc['text']}\n"
            except Exception as e:
                print(f"RAG Retrieval Error: {type(e).__name__}")
        # ---------------------

        # --- PERSONA SWITCHING LOGIC ---
        active_persona = None
        # Check history (most recent first) for @become commands
        for mem in reversed(history):
            if mem["role"] == "user":
                content = mem["content"].strip()
                if content.startswith("@/become"):
                    break
                elif content.startswith("@become "):
                    active_persona = content[len("@become "):].strip()
                    break

        # Modular Prompt Construction
        # NOTE: server-side "personalization memory" is intentionally not injected: it was
        # derived from stored chats, which the server no longer keeps.
        if active_persona:
            preset = get_persona_preset(active_persona)
            if preset:
                active_persona = preset

            system_prompt = build_persona_prompt(active_persona, rag_text)
        else:
            system_prompt = build_default_prompt(rag_text)

        window = history[-CONTEXT_WINDOW_MESSAGES:]
        # Chat APIs expect the first turn to come from the user
        while window and window[0]["role"] == "assistant":
            window = window[1:]

        # Check if we need to force an identity prefix
        identity_prefix = self._check_identity_trigger(message)

        use_remote = eno_config.LLM_BACKEND == "openai"
        prompt = None
        chat_messages = None

        if use_remote:
            sys_text = system_prompt
            if identity_prefix:
                sys_text += f"\n\nYour reply has already begun with: \"{identity_prefix.strip()}\" Continue naturally from exactly that point without repeating it."
            chat_messages = [{"role": "system", "content": sys_text}]
            for i, mem in enumerate(window):
                content = augmented_message if i == len(window) - 1 and mem["role"] == "user" else mem["content"]
                if mem["role"] == "user":
                    content = state_manager.sanitize_prompt_for_llm(content)
                chat_messages.append({"role": mem["role"], "content": content})
        elif model_type == "standard":
            prompt = ""
            for i, mem in enumerate(window):
                role = "user" if mem["role"] == "user" else "model"
                content = augmented_message if i == len(window) - 1 and mem["role"] == "user" else mem['content']

                # --- STRIP @become COMMANDS FROM VISIBLE HISTORY ---
                if role == "user":
                    content = state_manager.sanitize_prompt_for_llm(content)
                # ---------------------------------------------------

                # Inject system prompt into the FINAL user message to maximize attention for Gemma
                if i == len(window) - 1 and role == "user":
                    content = f"{system_prompt}\n\n[USER]: {content}"

                prompt += f"<start_of_turn>{role}\n{content}<end_of_turn>\n"

            prompt += "<start_of_turn>model\n"
        else:
            prompt = f"<|im_start|>system\n{system_prompt}<|im_end|>\n"
            for i, mem in enumerate(window):
                role = "user" if mem["role"] == "user" else "assistant"
                content = augmented_message if i == len(window) - 1 and role == "user" else mem['content']

                # --- STRIP @become COMMANDS FROM VISIBLE HISTORY ---
                if role == "user":
                    content = state_manager.sanitize_prompt_for_llm(content)
                # ---------------------------------------------------

                prompt += f"<|im_start|>{role}\n{content}<|im_end|>\n"
            prompt += "<|im_start|>assistant\n"

        if identity_prefix:
            if prompt is not None:
                prompt += identity_prefix
            yield {"type": "token", "content": identity_prefix}

        import re
        MOOD_PATTERN = re.compile(r'\[MOOD:\s*([A-Za-z]+)\s*(?:\|\s*NAME:\s*([^\]\n]+))?\]?', re.IGNORECASE)

        def extract_mood(text: str):
            match = MOOD_PATTERN.search(text)
            mood = None
            name = None
            clean = text
            if match:
                mood = match.group(1).strip().capitalize()
                if match.group(2):
                    name = match.group(2).strip()
                clean = (text[:match.start()] + text[match.end():]).strip()
            
            # Remove generic system note hallucinations
            clean = re.sub(r'\[(?:System Note|CRITICAL).*?\]\s*', '', clean, flags=re.IGNORECASE).strip()
            return clean, mood, name
            
        TAG_LOOKAHEAD = 50
        buffer = ""
        yielded_anything = False
        
        async for chunk in llm_service.stream_generate(
            prompt,
            max_tokens=config["max_tokens"],
            temp=config["temp"],
            model_type=model_type,
            messages=chat_messages,
        ):
            buffer += chunk
            if len(buffer) > TAG_LOOKAHEAD:
                last_bracket = buffer.rfind('[')
                if last_bracket != -1 and last_bracket > len(buffer) - TAG_LOOKAHEAD:
                    split_idx = last_bracket
                else:
                    split_idx = len(buffer) - TAG_LOOKAHEAD
                    
                if split_idx > 0:
                    safe_to_send = buffer[:split_idx]
                    if safe_to_send:
                        yield {"type": "token", "content": safe_to_send}
                        yielded_anything = True
                    buffer = buffer[split_idx:]
                    
        clean_tail, mood, name = extract_mood(buffer)
        
        if not yielded_anything and not clean_tail:
            print(f"[Eno AI] Warning: Empty response detected. Raw tail: {buffer}")
            
            retry_prompt = prompt + "\n\n[SYSTEM: Your last response was missing its reply text. ALWAYS include a full conversational reply BEFORE the mood tag.]\n"
            retry_messages = None
            if use_remote:
                retry_messages = list(chat_messages)
                retry_messages.append({"role": "system", "content": "Your last response was missing its reply text. ALWAYS include a full conversational reply BEFORE the mood tag."})
                
            buffer = ""
            async for chunk in llm_service.stream_generate(
                retry_prompt if not use_remote else None,
                max_tokens=config["max_tokens"],
                temp=config["temp"],
                model_type=model_type,
                messages=retry_messages,
            ):
                buffer += chunk
                if len(buffer) > TAG_LOOKAHEAD:
                    last_bracket = buffer.rfind('[')
                    if last_bracket != -1 and last_bracket > len(buffer) - TAG_LOOKAHEAD:
                        split_idx = last_bracket
                    else:
                        split_idx = len(buffer) - TAG_LOOKAHEAD
                        
                    if split_idx > 0:
                        safe_to_send = buffer[:split_idx]
                        if safe_to_send:
                            yield {"type": "token", "content": safe_to_send}
                            yielded_anything = True
                        buffer = buffer[split_idx:]
                        
            clean_tail, mood, name = extract_mood(buffer)
            if not yielded_anything and not clean_tail:
                print(f"[Eno AI] Warning: Empty response on retry. Raw tail: {buffer}")
                clean_tail = "..."
                
        if mood:
            yield {"type": "mood", "content": mood, "name": name or "Persona"}
            
        if clean_tail:
            yield {"type": "token", "content": clean_tail}

        # The reply is persisted by the client in its on-device vault. Nothing is stored here.

conversation_engine = ConversationEngine()
