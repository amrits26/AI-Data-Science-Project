SKILL_NAME = "complaint_handler"
SKILL_DESCRIPTION = "Handles customer complaints with empathy and offers escalation."
SKILL_PRIORITY = 90
SKILL_TRIGGERS = [
    "complain", "unhappy", "frustrated", "angry", "problem", "issue", "broken", "manager", "upset", "noise"
]
SKILL_EMBEDDING = None

def execute(query: str, context: dict, session_id: str) -> dict:
    return {
        "answer": "I'm sorry to hear about your experience. I understand how frustrating this must be. Would you like me to connect you with a manager or help resolve the issue?",
        "question_type": "complaint",
        "data": {},
        "source": "complaint_handler"
    }
