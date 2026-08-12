import os
import re
import shlex
from pathlib import Path
from typing import Callable, Iterable

from prmg.storage.models import ConsumerReference


_COMMAND_DIRECTIVE = re.compile(
    r"^(?P<indent>\s*)(?:-\s*)?(?:run|script|powershell):\s*(?P<value>.*)$"
)
_COMMAND_SEPARATOR = re.compile(r"(?:&&|;|\r?\n)")
_PYTHON_LAUNCHERS = {"py", "py.exe", "python", "python.exe"}


def _is_python_launcher(token: str) -> bool:
    name = Path(token.strip('"\'')).name.lower()
    return (
        name in _PYTHON_LAUNCHERS
        or re.fullmatch(r"python\d+(?:\.\d+)?", name) is not None
    )


def module_qualname_from_script(project_root: Path, script: str) -> str | None:
    normalized = script.strip().strip('"\'').replace("\\", "/")
    if not normalized.lower().endswith(".py"):
        return None

    script_path = Path(normalized)
    if not script_path.is_absolute():
        script_path = project_root / script_path

    try:
        relative = script_path.resolve().relative_to(project_root.resolve())
    except ValueError:
        return None

    parts = list(relative.parts)
    if parts and parts[0] == "src":
        parts = parts[1:]
    if not parts:
        return None
    if parts[-1] == "__init__.py":
        parts = parts[:-1]
    else:
        parts[-1] = parts[-1][:-3]
    if not parts or any(not part.isidentifier() for part in parts):
        return None
    return ".".join(parts)


def _targets_from_tokens(tokens: list[str], project_root: Path) -> list[str]:
    if not tokens:
        return []

    launcher_index = next(
        (index for index, token in enumerate(tokens) if _is_python_launcher(token)),
        None,
    )
    if launcher_index is not None:
        command_tokens = tokens[launcher_index + 1 :]
        if "-m" in command_tokens:
            module_index = command_tokens.index("-m") + 1
            if module_index < len(command_tokens):
                module = command_tokens[module_index].strip().strip('"\'')
                if module and all(part.isidentifier() for part in module.split(".")):
                    return [module]

        for token in command_tokens:
            target = module_qualname_from_script(project_root, token)
            if target:
                return [target]

    for token in tokens:
        target = module_qualname_from_script(project_root, token)
        if target:
            return [target]
    return []


def extract_command_token_targets(tokens: list[str], project_root: Path) -> list[str]:
    return list(dict.fromkeys(_targets_from_tokens(tokens, project_root)))


def extract_command_targets(command: str, project_root: Path) -> list[str]:
    targets: list[str] = []
    command = re.sub(r"`\s*\r?\n\s*", " ", command)
    command = re.sub(r"\\\s*\r?\n\s*", " ", command)
    for segment in _COMMAND_SEPARATOR.split(command):
        segment = segment.strip()
        if not segment:
            continue
        try:
            tokens = shlex.split(segment.replace("\\", "/"), posix=True)
        except ValueError:
            continue
        targets.extend(_targets_from_tokens(tokens, project_root))
    return list(dict.fromkeys(targets))


def _iter_run_commands(text: str) -> Iterable[tuple[int, str]]:
    lines = text.splitlines()
    index = 0
    while index < len(lines):
        match = _COMMAND_DIRECTIVE.match(lines[index])
        if not match:
            index += 1
            continue

        directive_line = index + 1
        indent = len(match.group("indent"))
        value = match.group("value").strip()
        if value and value not in {"|", ">", "|-", ">-", "|+", ">+"}:
            if len(value) >= 2 and value[0] == value[-1] and value[0] in '"\'':
                value = value[1:-1]
            yield directive_line, value
            index += 1
            continue

        block: list[str] = []
        index += 1
        while index < len(lines):
            line = lines[index]
            if not line.strip():
                block.append("")
                index += 1
                continue
            child_indent = len(line) - len(line.lstrip())
            if child_indent <= indent:
                break
            block.append(line.strip())
            index += 1
        if block:
            yield directive_line, "\n".join(block)


def _is_ci_yaml(path: Path, project_root: Path) -> bool:
    try:
        relative = path.relative_to(project_root)
    except ValueError:
        return False

    lowered_parts = [part.lower() for part in relative.parts]
    lowered_name = path.name.lower()
    if len(lowered_parts) >= 3 and lowered_parts[:2] == [".github", "workflows"]:
        return True
    if len(lowered_parts) >= 3 and lowered_parts[:2] == [".github", "actions"]:
        return True
    if lowered_parts and lowered_parts[0] == ".circleci":
        return True
    return lowered_name in {
        ".gitlab-ci.yml",
        ".gitlab-ci.yaml",
        "azure-pipelines.yml",
        "azure-pipelines.yaml",
    }


def scan_ci_command_references(
    project_root: Path,
    is_ignored: Callable[[Path], bool],
) -> list[ConsumerReference]:
    references: list[ConsumerReference] = []
    for root, dirs, files in os.walk(project_root):
        root_path = Path(root)
        dirs[:] = [directory for directory in dirs if not is_ignored(root_path / directory)]
        for filename in files:
            path = root_path / filename
            if path.suffix.lower() not in {".yml", ".yaml"}:
                continue
            if is_ignored(path) or not _is_ci_yaml(path, project_root):
                continue
            try:
                text = path.read_text(encoding="utf-8-sig")
            except (OSError, UnicodeError):
                continue

            for line_start, command in _iter_run_commands(text):
                for target in extract_command_targets(command, project_root):
                    references.append(
                        ConsumerReference(
                            source_path=str(path.resolve()),
                            source_symbol_qualname="",
                            target_qualname=target,
                            base_edge_kind="command_dependency",
                            line_start=line_start,
                            col_start=0,
                            raw_reference=command,
                            origin="ci_command",
                        )
                    )
    return references
