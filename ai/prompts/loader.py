"""Load and render prompt templates from the local templates directory."""

from pathlib import Path
from string import Template

TEMPLATES_DIR = Path(__file__).parent / "templates"


def load(name: str) -> str:
    """Load a named Markdown prompt template without leaving the templates directory."""
    if not name or name != Path(name).name or name in {".", ".."}:
        raise ValueError("Prompt name must be a simple filename without a path")

    path = (TEMPLATES_DIR / f"{name}.md").resolve()
    templates_root = TEMPLATES_DIR.resolve()

    if not path.is_relative_to(templates_root):
        raise ValueError("Prompt path must remain inside the templates directory")

    if not path.is_file():
        raise FileNotFoundError(f"Prompt template not found: {path}")

    return path.read_text(encoding="utf-8")


def render(name: str, **variables: str) -> str:
    """Render a prompt; raises KeyError if a variable is missing."""
    return Template(load(name)).substitute(**variables)
