"""
Prompt loader.

All LLM instructions live in external YAML files under /prompts.
Nothing is hardcoded in Python -- this module is the single gateway
for reading those files, with in-process caching.
"""

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


@lru_cache(maxsize=32)
def load_prompt_file(filename: str) -> dict[str, Any]:
    """
    Parse a YAML prompt file from the /prompts directory and cache it.

    Args:
        filename: File name inside /prompts, e.g. "prompt.yml".

    Returns:
        The parsed YAML document as a dict.

    Raises:
        FileNotFoundError: If the prompt file does not exist.
        ValueError: If the YAML is invalid or not a mapping.
    """
    path = PROMPTS_DIR / filename
    if not path.is_file():
        raise FileNotFoundError(f"Prompt file not found: {path}")

    with path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh)

    if not isinstance(data, dict):
        raise ValueError(f"Prompt file {filename} must contain a YAML mapping.")
    return data


def get_prompt(filename: str, key: str) -> str:
    """
    Return a single named prompt string from a YAML file.

    Args:
        filename: YAML file inside /prompts.
        key: Top-level key holding the prompt text.

    Raises:
        KeyError: If the key is missing from the file.
    """
    data = load_prompt_file(filename)
    if key not in data:
        raise KeyError(f"Prompt key '{key}' missing in {filename}.")
    return str(data[key])
