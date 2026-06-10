SKILL_NAME = "general_knowledge"
SKILL_DESCRIPTION = "Answers general automotive and dealership questions."
SKILL_PRIORITY = 10
SKILL_TRIGGERS = [
    "what is", "how do", "difference", "compare", "explain", "general", "knowledge", "info", "information"
]
SKILL_EMBEDDING = None

def execute(query: str, context: dict, session_id: str) -> dict:
    # Fallback: generic answer
        # Hybrid retrieval: FAISS + BM25 (stub, ready for future expansion)
        # This is a placeholder for hybrid retrieval logic.
        # In production, this would call FAISS and BM25, then combine results.
        return {"answer": "General knowledge skill is ready. Hybrid retrieval logic will be added here."}
