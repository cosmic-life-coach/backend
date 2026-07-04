"""Unit tests for the vector ID convention and the YAML prompt loader."""

import pytest

from config.prompt_loader import get_prompt, load_prompt_file
from repositories.pinecone_memory_handler import build_vector_id


def test_vector_id_format():
    """IDs must follow uid_chat_title_chatnumber with zero-padded number."""
    assert build_vector_id("usr_9f82a", "Vedic Remedies", 1) == "usr_9f82a_vedic_remedies_001"
    assert build_vector_id("u1", "career!!plan", 42) == "u1_career_plan_042"


def test_core_prompt_loads_with_placeholders():
    """prompt.yml parses and contains the placeholders the orchestrator fills."""
    text = get_prompt("prompt.yml", "system_prompt")
    for placeholder in ("{birth_chart}", "{memories}", "{chat_history}"):
        assert placeholder in text


def test_daily_prompt_loads():
    """Daily recommendation prompt parses and is format()-safe."""
    text = get_prompt("prompt_daily_recommendation.yaml", "system_prompt")
    filled = text.format(birth_chart="X", today="2026-07-04", calendar_events="Y")
    assert "2026-07-04" in filled


def test_missing_prompt_file_raises():
    """Unknown prompt files raise FileNotFoundError, not silent defaults."""
    with pytest.raises(FileNotFoundError):
        load_prompt_file("nope.yml")
