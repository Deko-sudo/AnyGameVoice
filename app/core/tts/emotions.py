"""Emotion control for TTS.

Dialogue lines may carry a leading tag: `[happy] Hello!` or
`<emotion="sad">...`. Engines consume it differently:

- piper: prosody CLI flags (heuristic mapping, documented below);
- bark: native markers ([laughs], [sighs], ...) pass through untouched,
  our tags are stripped;
- xtts/silero: tags stripped (no emotion backend), text stays clean so
  the model never reads "[happy]" aloud.

EMOTIONS supplies the prosody tags, and BARK_MARKERS supplies Bark's sounds.
Unrecognised bracketed names can be Ren'Py substitutions and are preserved.
"""

import re

__all__ = [
    "EMOTIONS",
    "BARK_MARKERS",
    "STRIP_ALWAYS",
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
STRIP_ALWAYS = EMOTIONS.keys() | BARK_MARKERS

_TAG = re.compile(r"\[(\w+)\]|<emotion\s*=\s*[\"'](\w+)[\"']\s*>", re.IGNORECASE)


def parse_emotion(text: str) -> tuple:
    """Split leading emotion tag. Returns (emotion, clean_text)."""
    text = (text or "").strip()
    m = _TAG.match(text)
    if m:
        tag = (m.group(1) or m.group(2)).lower()
        if tag in EMOTIONS:
            return tag, text[m.end():].lstrip()
    return "neutral", text


def strip_emotion_tags(text: str, keep_markers: frozenset = frozenset()) -> str:
    """Remove known emotions and sounds except keep_markers. Preserve variables such as [dragon]."""
    def _drop(m):
        tag = (m.group(1) or m.group(2)).lower()
        return "" if tag in STRIP_ALWAYS and tag not in keep_markers else m.group(0)

    return _TAG.sub(_drop, text or "").strip()


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
    if (engine or "") == "piper":
        emotion, clean = parse_emotion(text)
        return strip_emotion_tags(clean), {"cli_flags": piper_flags(emotion)}
    if (engine or "") == "bark":
        return strip_emotion_tags(text, keep_markers=frozenset(BARK_MARKERS)), {}
    return strip_emotion_tags(text), {}
