SKILL_NAME = "global_car_knowledge"
SKILL_DESCRIPTION = "Answers questions about any car in the world using global datasets."
SKILL_PRIORITY = 50
SKILL_TRIGGERS = ["towing capacity", "specs", "top speed", "dimensions", "compare", "global", "any car", "not on your lot"]
def execute(query, context, session_id):
    import os
    import re
    from pathlib import Path
    KB_PATH = Path("data/global_car_knowledge.txt")
    if not KB_PATH.exists():
        return {
            "answer": "Global car knowledge base not found. Please run the ingestion scripts first.",
            "source": "global_car_knowledge",
            "question_type": "global_car_knowledge"
        }
    query_lc = query.lower()
    results = []
    with open(KB_PATH, encoding="utf-8") as f:
        for line in f:
            if any(word in line.lower() for word in query_lc.split() if len(word) > 2):
                results.append(line.strip())
    if not results:
        return {
            "answer": "No global car knowledge found for your query.",
            "source": "global_car_knowledge",
            "question_type": "global_car_knowledge"
        }
    answer = "\n".join(results[:10])
    return {
        "answer": answer,
        "source": "global_car_knowledge",
        "question_type": "global_car_knowledge"
    }
