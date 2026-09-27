"""Audio + subtitle utils (Phase 9).

Naive timing model for voice-over planning: estimates how long each
line takes to speak, so batch jobs can be parallelized and SRT/VTT
sidecars generated for testing without game integration.
"""

__all__ = ["to_wav", "estimate_duration", "to_srt", "to_vtt", "fmt_timestamp"]

# Average speaking rate fallback (chars per second) when no audio exists.
CPS = 15.0
MIN_LINE_SEC = 1.0
GAP_SEC = 0.4


def to_wav(data: bytes) -> bytes:
    """Convert to wav (stub: engines already output wav)."""
    return data


def estimate_duration(text: str, cps: float = CPS) -> float:
    """Estimate spoken seconds for a line."""
    if not text:
        return MIN_LINE_SEC
    return max(MIN_LINE_SEC, len(text) / cps)


def fmt_timestamp(seconds: float, vtt: bool = False) -> str:
    """Format seconds as SRT (,) or VTT (.) timestamp."""
    if seconds < 0:
        seconds = 0
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int(round((seconds - int(seconds)) * 1000))
    sep = "." if vtt else ","
    return f"{h:02d}:{m:02d}:{s:02d}{sep}{ms:03d}"


def _cues(lines, cps: float = CPS):
    """Yield (index, start, end, speaker, text) cues back to back."""
    t = 0.0
    for i, ln in enumerate(lines, 1):
        dur = estimate_duration(ln.text if hasattr(ln, "text") else str(ln), cps)
        start, end = t, t + dur
        t = end + GAP_SEC
        speaker = getattr(ln, "speaker", "")
        text = getattr(ln, "text", str(ln))
        yield i, start, end, speaker, text


def to_srt(lines, cps: float = CPS) -> str:
    """Render dialogue lines as SubRip subtitles."""
    out = []
    for i, start, end, speaker, text in _cues(lines, cps):
        label = f"<v {speaker}>{text}" if speaker and speaker != "narrator" else text
        out.append(f"{i}\n{fmt_timestamp(start)} --> {fmt_timestamp(end)}\n{label}\n")
    return "\n".join(out)


def to_vtt(lines, cps: float = CPS) -> str:
    """Render dialogue lines as WebVTT subtitles."""
    out = ["WEBVTT\n"]
    for i, start, end, speaker, text in _cues(lines, cps):
        label = f"<v {speaker}>{text}" if speaker and speaker != "narrator" else text
        out.append(f"{fmt_timestamp(start, vtt=True)} --> {fmt_timestamp(end, vtt=True)}\n{label}\n")
    return "\n".join(out)
