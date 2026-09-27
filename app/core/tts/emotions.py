"""Emotion control for TTS.

Dialogue lines may carry a leading tag: `[happy] Hello!` or
`<emotion="sad">...`. Engines consume it differently:

- piper: prosody CLI flags (heuristic mapping, documented below);
- bark: native markers ([laughs], [sighs], ...) pass through untouched,
  our tags are stripped;
- xtts/silero: tags stripped (no emotion backend), text stays clean so
  the model never reads "[happy]" aloud.

Unknown tags are stripped and treated as neutral — never synthesized.
"""

import re

__all__ = [
    "EMOTIONS",
    "BARK_MARKERS",
    "parse_emotion",
    "strip_emotion_tags",
    "piper_flags",
    "apply_emotion",
]

# Heuristic piper prosody mapping. Piper has no real emotion model;
# these only nudge speed/variability. Values mirror piper CLI defaults
# (length 1.0, noise 0.667, w 0.8) with small per-emotion offsets.
EMOTIONS = {
    "neutral": {"length_scale": 1.0, "noise_scale": 0.667, "noise_w": 0.8},
    "happy": {"length_scale": 0.9, "noise_scale": 0.8, "noise_w": 0.8},
    "sad": {"length_scale": 1.15, "noise_scale": 0.5, "noise_w": 0.6},
    "angry": {"length_scale": 0.95, "noise_scale": 1.0, "noise_w": 0.9},
    "whisper": {"length_scale": 1.1, "noise_scale": 0.3, "noise_w": 0.5},
    "shouting": {"length_scale": 0.9, "noise_scale": 1.2, "noise_w": 1.0},
}

# Markers bark understands natively — never stripped for bark.
BARK_MARKERS = {"laughs", "sighs", "gasps", "coughs", "uh", "um", "music"}

_LEAD_TAG = re.compile(r"^\s*(?:\[(\w+)\]|<emotion\s*=\s*[\"'](\w+)[\"']\s*>)\s*", re.IGNORECASE)
_ANY_TAG = re.compile(r"\[\w+\]|<emotion\s*=\s*[\"']\w+[\"']\s*>", re.IGNORECASE)


def parse_emotion(text: str) -> tuple:
    """Split leading emotion tag. Returns (emotion, clean_text)."""
    m = _LEAD_TAG.match(text or "")
    if not m:
        return "neutral", (text or "").strip()
    tag = (m.group(1) or m.group(2) or "").lower()
    rest = text[m.end():].strip()
    if tag in EMOTIONS:
        return tag, rest
    if tag in BARK_MARKERS:
        return "neutral", text.strip()  # bark-native marker, keep in text
    return "neutral", rest  # unknown tag: drop it, never synthesize


def strip_emotion_tags(text: str, keep_markers: frozenset = frozenset()) -> str:
    """Remove our [tag]/<emotion> markers; keep listed bark-native ones."""
    def _drop(m):
        inner = m.group(0).strip("[]<>")
        word = inner.split("=")[-1].strip("\"' ").lower()
        return m.group(0) if word in keep_markers else ""

    return _ANY_TAG.sub(_drop, text or "").strip()


def piper_flags(emotion: str) -> list:
    """Piper CLI flags for an emotion (empty for neutral/unknown)."""
    params = EMOTIONS.get((emotion or "").lower(), EMOTIONS["neutral"])
    if params == EMOTIONS["neutral"]:
        return []
    return [
        "--length-scale", str(params["length_scale"]),
        "--noise-scale", str(params["noise_scale"]),
        "--noise-w", str(params["noise_w"]),
    ]


def apply_emotion(engine: str, text: str) -> tuple:
    """Prepare (clean_text, extra_kwargs) for an engine.

    extra_kwargs: piper -> {"cli_flags": [...]}, others -> {}.
    """
    emotion, clean = parse_emotion(text)
    if (engine or "") == "piper":
        return clean, {"cli_flags": piper_flags(emotion)}
    if (engine or "") == "bark":
        return strip_emotion_tags(text, keep_markers=frozenset(BARK_MARKERS)), {}
    return strip_emotion_tags(text), {}
