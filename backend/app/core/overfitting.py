"""
Overfitting Risk Evaluation
"""

def compute_overfitting_risk(train_score: float, val_score: float) -> dict:
    gap = train_score - val_score

    if gap > 0.15:
        risk = "high"
    elif gap > 0.07:
        risk = "moderate"
    else:
        risk = "low"

    return {
        "train_score": train_score,
        "validation_score": val_score,
        "score_gap": round(gap, 4),
        "overfitting_risk": risk,
    }