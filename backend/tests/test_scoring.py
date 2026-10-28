from app.services import llm
from app.services.scoring import score_open_answer


def fake_model(monkeypatch, output):
    monkeypatch.setattr(llm, "score_answer", lambda q, a: output)


def test_bad_model_output_is_not_trusted(monkeypatch):
    fake_model(monkeypatch, '{"score": "four", "flags": ["made_up_flag"]}')
    assert score_open_answer("q", "a") == {"score": None, "reason": None, "flags": []}

    fake_model(monkeypatch, '{"score": 7, "reason": "x", "flags": []}')
    assert score_open_answer("q", "a")["score"] is None

    fake_model(monkeypatch, '```json\n{"score": 4, "reason": "x", "flags": []}\n```')
    assert score_open_answer("q", "a")["score"] == 4

    fake_model(monkeypatch, "not json at all")
    assert score_open_answer("q", "a")["score"] is None
