import json
from collections import defaultdict

FEEDBACK_FILE = "data/skill_feedback.jsonl"

def load_feedback():
    entries = []
    try:
        with open(FEEDBACK_FILE, "r", encoding="utf-8") as f:
            for line in f:
                entries.append(json.loads(line))
    except FileNotFoundError:
        print("No feedback file found.")
    return entries

def main():
    entries = load_feedback()
    if not entries:
        print("No feedback entries.")
        return
    grouped = defaultdict(list)
    for e in entries:
        grouped[e["skill_name"]].append(e)
    for skill, group in grouped.items():
        print(f"\n=== {skill} ({len(group)} entries) ===")
        for e in sorted(group, key=lambda x: x.get("severity", "low"), reverse=True)[:20]:
            print(f"[{e['severity']}] {e['query']}\n  Issue: {e['issue']}")
        for e in group:
            if e.get("severity") == "high":
                print("\n--- HIGH SEVERITY DETAIL ---")
                print(json.dumps(e, indent=2))

if __name__ == "__main__":
    main()
