import json
import requests
import csv
from ragas import evaluate

with open('data/eval_questions.jsonl') as f:
    questions = [json.loads(line) for line in f]

results = []
for q in questions:
    resp = requests.post(
        "http://127.0.0.1:8080/api/ask",
        json={"question": q["question"]}
    ).json()
    metrics = evaluate(q["question"], q["answer"], resp.get("answer", ""), resp.get("contexts", ""))
    results.append({**q, **metrics})

with open('data/eval_results.csv', 'w', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=results[0].keys())
    writer.writeheader()
    writer.writerows(results)

# Print summary
scores = {k: sum(r[k] for r in results)/len(results) for k in results[0] if isinstance(results[0][k], float)}
print("Averages:", scores)
