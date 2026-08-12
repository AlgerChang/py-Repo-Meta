from prmg.core.command_dependencies import (
    extract_command_targets,
    scan_ci_command_references,
)


def test_extract_command_targets_supports_windows_script_paths(tmp_path):
    assert extract_command_targets(
        r"python .\src\pkg\target.py",
        tmp_path,
    ) == ["pkg.target"]


def test_extract_command_targets_supports_powershell_continuations(tmp_path):
    command = "poetry run python `\n  -X utf8 `\n  -m pkg.target"

    assert extract_command_targets(command, tmp_path) == ["pkg.target"]


def test_scan_ci_commands_supports_native_keys_and_preserves_argument_quotes(tmp_path):
    files = {
        ".gitlab-ci.yml": 'job:\n  script:\n    - python -m pkg.gitlab\n',
        "azure-pipelines.yml": (
            "steps:\n"
            "  - script: python -m pkg.azure_script\n"
            "  - powershell: python -m pkg.azure_powershell\n"
        ),
        ".github/workflows/ci.yml": (
            'jobs:\n  check:\n    steps:\n      - run: python -m pkg.github --name "foo"\n'
        ),
    }
    for relative_path, text in files.items():
        path = tmp_path / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    references = scan_ci_command_references(tmp_path, lambda path: False)

    assert {reference.target_qualname for reference in references} == {
        "pkg.azure_powershell",
        "pkg.azure_script",
        "pkg.github",
        "pkg.gitlab",
    }
