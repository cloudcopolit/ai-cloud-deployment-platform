import pytest

from prompts.loader import load, render


def test_load_support_agent_template():
    prompt = load("support_agent")

    assert "support agent" in prompt
    assert "$product" in prompt


def test_render_substitutes_variables():
    prompt = render("support_agent", product="CloudPilot")

    assert "CloudPilot" in prompt
    assert "$product" not in prompt


def test_render_rejects_missing_variable():
    with pytest.raises(KeyError):
        render("support_agent")


def test_load_rejects_missing_template():
    with pytest.raises(FileNotFoundError, match="Prompt template not found"):
        load("missing_template")


@pytest.mark.parametrize(
    "name",
    ["../support_agent", "../../pyproject", "/tmp/prompt", ".."],
)
def test_load_rejects_path_traversal(name):
    with pytest.raises(ValueError, match="Prompt name"):
        load(name)
