from prmg.core.command_dependencies import extract_command_targets


def test_extract_command_targets_supports_windows_script_paths(tmp_path):
    assert extract_command_targets(
        r"python .\src\pkg\target.py",
        tmp_path,
    ) == ["pkg.target"]


def test_extract_command_targets_supports_powershell_continuations(tmp_path):
    command = "poetry run python `\n  -X utf8 `\n  -m pkg.target"

    assert extract_command_targets(command, tmp_path) == ["pkg.target"]
