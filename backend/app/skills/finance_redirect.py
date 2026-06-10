SKILL_NAME = "finance_redirect"
SKILL_DESCRIPTION = "Redirects all finance-related questions to a human agent."
SKILL_PRIORITY = 100
SKILL_TRIGGERS = [
    "finance", "loan", "monthly payment", "apr", "interest rate", "lease", "payment", "credit"
]
SKILL_EMBEDDING = None

def execute(query: str, context: dict, session_id: str) -> dict:
    return {
        "answer": "I can't calculate payments or financing details — that's handled by our finance manager. I can tell you all about the vehicle itself, though! What else would you like to know?",
        "question_type": "finance_redirect",
        "data": {},
        "source": "finance_redirect"
    }
