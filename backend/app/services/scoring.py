import json

from . import llm

ALLOWED_FLAGS = ["customer_data_shared", "confidential_data_shared", "unreviewed_output", "policy_unaware"]


def score_open_answer(question_text: str, answer: str) -> dict:
    raw = llm.score_answer(question_text, answer)
    # The model can return broken JSON or bad values: never crash, never store a bad score
    try:
        data = json.loads(raw.strip().removeprefix("```json").removesuffix("```"))
    except json.JSONDecodeError:
        return {"score": None, "reason": "Could not be scored automatically; needs review.", "flags": []}
    score = data.get("score")
    if score not in [1, 2, 3, 4, 5]:
        score = None
    flags = [f for f in data.get("flags", []) if f in ALLOWED_FLAGS]
    return {"score": score, "reason": data.get("reason"), "flags": flags}
