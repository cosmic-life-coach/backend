"""
Vedic astrology engine (deterministic, not LLM-guessed).

Uses the Swiss Ephemeris (`pyswisseph`) with the Lahiri ayanamsa to compute
sidereal planetary positions, rashis (signs), nakshatras, and the ascendant
from exact birth details. Gemini then *interprets* this chart -- it never
computes it, which avoids LLM hallucination of astronomical data.
"""

import logging
from datetime import datetime, timedelta

import swisseph as swe

logger = logging.getLogger(__name__)

SIGNS = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
]

NAKSHATRAS = [
    "Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashira", "Ardra",
    "Punarvasu", "Pushya", "Ashlesha", "Magha", "Purva Phalguni",
    "Uttara Phalguni", "Hasta", "Chitra", "Swati", "Vishakha", "Anuradha",
    "Jyeshtha", "Mula", "Purva Ashadha", "Uttara Ashadha", "Shravana",
    "Dhanishta", "Shatabhisha", "Purva Bhadrapada", "Uttara Bhadrapada",
    "Revati",
]

# Grahas used in classical Vedic astrology (Rahu = mean lunar node).
PLANETS = {
    "Sun": swe.SUN,
    "Moon": swe.MOON,
    "Mars": swe.MARS,
    "Mercury": swe.MERCURY,
    "Jupiter": swe.JUPITER,
    "Venus": swe.VENUS,
    "Saturn": swe.SATURN,
    "Rahu": swe.MEAN_NODE,
}


def _sidereal_breakdown(longitude: float) -> dict:
    """Map an absolute sidereal longitude to sign, nakshatra, and pada."""
    nak_span = 360.0 / 27.0          # 13°20' per nakshatra
    pada_span = nak_span / 4.0       # 3°20' per pada
    return {
        "longitude": round(longitude, 4),
        "sign": SIGNS[int(longitude // 30) % 12],
        "nakshatra": NAKSHATRAS[int(longitude // nak_span) % 27],
        "pada": int((longitude % nak_span) // pada_span) + 1,
    }


def compute_birth_chart(
    birth_datetime_local: datetime,
    tz_offset_hours: float,
    latitude: float,
    longitude: float,
) -> dict:
    """
    Compute a sidereal (Lahiri) Vedic birth chart.

    Args:
        birth_datetime_local: Local date & time of birth.
        tz_offset_hours: Timezone offset from UTC (e.g. 5.5 for IST).
        latitude / longitude: Birthplace coordinates in decimal degrees.

    Returns:
        {"ascendant": {...}, "planets": {name: {...}}, "moon_sign": str,
         "sun_sign": str, "ayanamsa": "Lahiri"}
        Each position dict has longitude, sign, nakshatra, pada, and (for
        planets) retrograde flag. Ketu is derived as Rahu + 180°.
    """
    swe.set_sid_mode(swe.SIDM_LAHIRI)

    # Convert local birth time to UT, then to Julian day.
    birth_utc = birth_datetime_local - timedelta(hours=tz_offset_hours)
    jd_ut = swe.julday(
        birth_utc.year, birth_utc.month, birth_utc.day,
        birth_utc.hour + birth_utc.minute / 60.0 + birth_utc.second / 3600.0,
    )

    flags = swe.FLG_SWIEPH | swe.FLG_SIDEREAL | swe.FLG_SPEED

    planets: dict[str, dict] = {}
    for name, planet_id in PLANETS.items():
        position, _ = swe.calc_ut(jd_ut, planet_id, flags)
        planets[name] = _sidereal_breakdown(position[0])
        planets[name]["retrograde"] = position[3] < 0  # negative daily speed

    # Ketu is always exactly opposite Rahu.
    ketu_lon = (planets["Rahu"]["longitude"] + 180.0) % 360.0
    planets["Ketu"] = _sidereal_breakdown(ketu_lon)
    planets["Ketu"]["retrograde"] = True  # nodes are always retrograde

    # Sidereal ascendant (Lagna) via whole-sign friendly houses call.
    _, ascmc = swe.houses_ex(jd_ut, latitude, longitude, b"W", swe.FLG_SIDEREAL)
    ascendant = _sidereal_breakdown(ascmc[0])

    return {
        "ayanamsa": "Lahiri",
        "ascendant": ascendant,
        "planets": planets,
        "moon_sign": planets["Moon"]["sign"],
        "sun_sign": planets["Sun"]["sign"],
    }


def summarize_chart_for_prompt(chart: dict) -> str:
    """Render the computed chart as a compact text block for LLM prompts."""
    lines = [
        f"Ascendant (Lagna): {chart['ascendant']['sign']} "
        f"({chart['ascendant']['nakshatra']} pada {chart['ascendant']['pada']})"
    ]
    for name, p in chart["planets"].items():
        retro = " (R)" if p.get("retrograde") else ""
        lines.append(
            f"{name}: {p['sign']} {p['longitude'] % 30:.2f}°, "
            f"{p['nakshatra']} pada {p['pada']}{retro}"
        )
    return "\n".join(lines)
