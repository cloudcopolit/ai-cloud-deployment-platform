from app.services.intent import build_intake, extract_intent, merge_intent


def test_complete_prompt_skips_questions():
    result = build_intake("Do a deep production-readiness review focused on AWS deployment and reliability.")
    assert result.complete is True
    assert result.intent.goal == "production_readiness"
    assert result.intent.depth == "production"
    assert result.questions == []


def test_vague_prompt_requests_only_missing_fields():
    result = build_intake("Analyze my architecture.")
    assert result.complete is False
    assert set(result.missing_fields) == {"goal", "depth"}
    assert {q.field for q in result.questions} == {"goal", "depth"}


def test_clarification_merge_completes_intent():
    base = extract_intent("Analyze my architecture.")
    merged = merge_intent(base, {"goal": "understand_architecture", "depth": "standard"})
    assert merged.goal == "understand_architecture"
    assert merged.depth == "standard"
