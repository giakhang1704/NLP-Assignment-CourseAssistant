"""Resolve project resources independently of the current working directory."""
from pathlib import Path
import json

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_GRAMMAR_PATH = PROJECT_ROOT / "models/grammar/course.cfg"
DEFAULT_LEXICON_PATH = PROJECT_ROOT / "models/grammar/lexicon.json"
DEFAULT_SCHEMA_PATH = PROJECT_ROOT / "configs/intent_schema.json"


def load_config(path=None):
    config_path = Path(path) if path else PROJECT_ROOT / "configs/default.json"
    data = json.loads(config_path.read_text(encoding="utf-8-sig"))
    data["project_root"] = str(PROJECT_ROOT)
    return data


def resource_path(value):
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path
