import importlib.metadata
import json
from pathlib import Path
import sys
import tomllib

ROOT = Path(__file__).resolve().parents[1]

def test_installed_package_matches_contract():
    import decision_tracker
    metadata = tomllib.loads((ROOT / "pyproject.toml").read_text())
    assert decision_tracker.__version__ == metadata["project"]["version"]
    assert importlib.metadata.version("decision-tracker") == decision_tracker.__version__
    assert sys.prefix != sys.base_prefix
    assert Path(decision_tracker.__file__).resolve().is_relative_to(ROOT)

def test_portable_project_descriptor_and_roots():
    descriptor = json.loads((ROOT / ".calamum/project.json").read_text())
    assert descriptor["project_id"] == "decision-tracker"
    for key in ("catalog_root", "runs_root", "reports_root", "working_dir"):
        value = descriptor["calamum"][key]
        assert not Path(value).is_absolute()
        assert ".." not in Path(value).parts
    assert (ROOT / "catalog/test_definitions.json").is_file()

def test_repository_contract_and_cli_entry_point():
    contract = json.loads((ROOT / "docs/repository-contract.json").read_text())
    assert contract["visibility"] == "public"
    assert contract["license"] == "not-selected"
    assert tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["scripts"]["decision-tracker"] == "decision_tracker.cli:main"
