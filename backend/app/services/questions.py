import json
import os

_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "questions.json")

# Lowest to highest. Compare positions, not text ("lead" < "mid" alphabetically).
SENIORITY = ["junior", "mid", "senior", "lead"]


def load_questions():
    with open(_PATH) as f:
        return json.load(f)


def questions_for(job_role: str, seniority: str):
    """Common questions for everyone + questions for this job role, filtered by seniority."""
    result = []
    for q in load_questions():
        if q["roles"] != ["all"] and job_role not in q["roles"]:
            continue
        if SENIORITY.index(seniority) < SENIORITY.index(q.get("min_seniority", "junior")):
            continue
        result.append(q)
    return result
