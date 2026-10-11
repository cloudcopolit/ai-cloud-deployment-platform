from agents.code_analyzer.analyzer import analyze_python_sources


def test_extracts_imports_classes_functions_and_main_guard():
    report = analyze_python_sources(
        {
            "app.py": """
import os
from pathlib import Path

@staticmethod
def helper():
    return os.getcwd()

class Service:
    pass

async def fetch_data():
    pass

if __name__ == "__main__":
    helper()
"""
        }
    )

    assert report.status == "completed"
    assert report.parsed_files == 1

    file = report.files[0]
    assert file.status == "parsed"
    assert file.has_main_guard is True
    assert len(file.imports) == 2

    definitions = {item.name: item for item in file.definitions}
    assert definitions["helper"].kind == "function"
    assert definitions["helper"].decorators == ("staticmethod",)
    assert definitions["Service"].kind == "class"
    assert definitions["fetch_data"].kind == "async_function"


def test_syntax_error_does_not_stop_other_files():
    report = analyze_python_sources(
        {
            "broken.py": "def incomplete(:\n    pass",
            "valid.py": "def greet():\n    return 'hello'\n",
        }
    )

    assert report.status == "partial"
    assert report.parsed_files == 1
    assert report.syntax_error_files == 1

    files = {item.path: item for item in report.files}
    assert files["broken.py"].status == "syntax_error"
    assert files["broken.py"].error is not None
    assert files["valid.py"].status == "parsed"


def test_rejects_unsafe_paths_and_unsupported_files():
    report = analyze_python_sources(
        {
            "../outside.py": "print('ignored')",
            "README.md": "documentation",
            "safe.py": "x = 1",
        }
    )

    files = {item.path: item for item in report.files}
    assert files["../outside.py"].status == "skipped"
    assert files["README.md"].status == "skipped"
    assert files["safe.py"].status == "parsed"
    assert report.status == "partial"


def test_enforces_source_size_limit():
    report = analyze_python_sources(
        {"large.py": "x = 'this source is too large'"},
        max_source_bytes=5,
    )

    assert report.status == "partial"
    assert report.skipped_files == 1
    assert report.files[0].status == "skipped"
    assert report.files[0].error == "Per-file size limit exceeded."


def test_reports_when_no_python_files_are_supported():
    report = analyze_python_sources({"README.md": "Project documentation"})

    assert report.status == "no_supported_files"
    assert report.parsed_files == 0
    assert report.files[0].status == "skipped"


def test_analysis_results_are_deterministic():
    first = analyze_python_sources(
        {
            "z_module.py": "def zebra():\n    pass\n",
            "a_module.py": "import os\ndef alpha():\n    pass\n",
        }
    )
    second = analyze_python_sources(
        {
            "a_module.py": "import os\ndef alpha():\n    pass\n",
            "z_module.py": "def zebra():\n    pass\n",
        }
    )

    assert first == second
    assert [file.path for file in first.files] == [
        "a_module.py",
        "z_module.py",
    ]
