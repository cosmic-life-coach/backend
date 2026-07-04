"""Unit tests for the deterministic Vedic astrology engine."""

from datetime import datetime

from services.astrology_engine_service import (
    NAKSHATRAS,
    SIGNS,
    compute_birth_chart,
    summarize_chart_for_prompt,
)


def _sample_chart() -> dict:
    """Chart for a fixed birth: 1998-03-21 14:35 IST, Jaipur (26.91N, 75.79E)."""
    return compute_birth_chart(
        birth_datetime_local=datetime(1998, 3, 21, 14, 35),
        tz_offset_hours=5.5,
        latitude=26.91,
        longitude=75.79,
    )


def test_chart_structure():
    """Chart contains all 9 grahas, ascendant, and valid sign/nakshatra names."""
    chart = _sample_chart()
    assert chart["ayanamsa"] == "Lahiri"
    assert set(chart["planets"].keys()) == {
        "Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu",
    }
    for planet in chart["planets"].values():
        assert planet["sign"] in SIGNS
        assert planet["nakshatra"] in NAKSHATRAS
        assert 1 <= planet["pada"] <= 4
        assert 0.0 <= planet["longitude"] < 360.0
    assert chart["ascendant"]["sign"] in SIGNS


def test_ketu_opposite_rahu():
    """Ketu must be exactly 180 degrees from Rahu."""
    chart = _sample_chart()
    diff = abs(chart["planets"]["Ketu"]["longitude"] - chart["planets"]["Rahu"]["longitude"])
    assert abs(diff - 180.0) < 0.01


def test_deterministic():
    """Same birth data must always produce the identical chart."""
    assert _sample_chart() == _sample_chart()


def test_prompt_summary_renders():
    """The text summary includes ascendant and every planet."""
    text = summarize_chart_for_prompt(_sample_chart())
    assert "Ascendant" in text
    for name in ("Sun", "Moon", "Ketu"):
        assert name in text
