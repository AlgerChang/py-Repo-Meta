from pathlib import Path


def classify_consumer_role(source_path: str) -> str:
    path = Path(source_path)
    parts = [part.lower() for part in path.parts]
    stem = path.stem.lower()

    if "smoke" in stem or "smoke" in parts:
        return "smoke"
    if stem.startswith("test_") or stem.endswith("_test") or "tests" in parts:
        return "test"
    if (
        stem.startswith("ci_")
        or ".github" in parts
        or ".circleci" in parts
        or path.name.lower().startswith(".gitlab-ci")
        or path.name.lower().startswith("azure-pipelines")
    ):
        return "ci"
    return "production"


def display_edge_kind(
    base_edge_kind: str,
    consumer_role: str,
    target_symbol_type: str,
) -> str:
    if base_edge_kind == "reference" and target_symbol_type == "data":
        return "data_dependency"
    if base_edge_kind == "call" and consumer_role == "test":
        return "test_call"
    if base_edge_kind == "call" and consumer_role == "smoke":
        return "smoke_call"
    return base_edge_kind
