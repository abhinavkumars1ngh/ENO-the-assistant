class TeachingEngine:
    """
    Transforms user queries into structured teaching prompts.
    """
    def generate_teaching_plan(self, topic: str, user_memories: list[str]) -> str:
        memory_context = "\n".join([f"- {m}" for m in user_memories]) if user_memories else "No prior memories."

        return f"""You are Eno, a senior engineering professor.
Based on the student's background:
{memory_context}

Explain the topic: "{topic}"

Please follow this exact structure in your explanation:
1. Prerequisites (What do they need to know first?)
2. Analogy (Explain it intuitively)
3. Formal Definition
4. Example
5. Code (if applicable)
6. Common Mistakes
7. Quick Quiz (1-2 questions to test understanding)
"""

teaching_engine = TeachingEngine()
