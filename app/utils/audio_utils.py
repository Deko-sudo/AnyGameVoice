"""Audio + subtitle utils (Phase 9).

Naive timing model for voice-over planning: estimates how long each
line takes to speak, so batch jobs can be parallelized and SRT/VTT
sidecars generated for testing without game integration.
"""

__all__ = [
    "to_wav",
    "estimate_duration",
    "to_srt",
    "to_vtt",
    "fmt_timestamp",
    "find_embedded_audio",
    "carve_embedded_audio",
]

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


# ---------------------------------------------------------------------------
# Embedded-audio carving (Unity .assets/.bundle, Unreal .ubulk, ...).
# Finds playable blobs by magic bytes without parsing container formats.
# ---------------------------------------------------------------------------

import os as _os
import struct as _struct

_WAV_MAGIC = b"RIFF"
_OGG_MAGIC = b"OggS"
_FSB5_MAGIC = b"FSB5"


def _u32le(buf: bytes, off: int) -> int:
    return _struct.unpack_from("<I", buf, off)[0]


def _wav_size(buf: bytes, off: int) -> int:
    """Total RIFF chunk size or 0 if invalid."""
    if off + 12 > len(buf) or buf[off:off + 4] != _WAV_MAGIC:
        return 0
    if buf[off + 8:off + 12] != b"WAVE":
        return 0
    size = _u32le(buf, off + 4) + 8
    if size < 44 or off + size > len(buf):
        return 0
    return size


def _ogg_size(buf: bytes, off: int) -> int:
    """Walk chained Ogg pages from off; total bytes or 0 if invalid."""
    pos = off
    n = len(buf)
    if off + 27 > n or buf[off:off + 4] != _OGG_MAGIC:
        return 0
    while True:
        if pos + 27 > n or buf[pos:pos + 4] != _OGG_MAGIC:
            return 0
        flags = buf[pos + 5]
        seg_count = buf[pos + 26]
        if pos + 27 + seg_count > n:
            return 0
        table = buf[pos + 27:pos + 27 + seg_count]
        pos += 27 + seg_count + sum(table)
        if pos > n:
            return 0
        if flags & 0x04:  # end-of-stream page
            return pos - off
        if pos - off > 256 * 1024 * 1024:  # sanity cap: 256MB
            return 0


def _fsb5_size(buf: bytes, off: int) -> int:
    """Total FSB5 bank size or 0 if invalid."""
    if off + 60 > len(buf) or buf[off:off + 4] != _FSB5_MAGIC:
        return 0
    try:
        shdr = _struct.unpack_from("<i", buf, off + 12)[0]
        names = _struct.unpack_from("<i", buf, off + 16)[0]
        data = _struct.unpack_from("<i", buf, off + 20)[0]
    except _struct.error:
        return 0
    if shdr < 0 or names < 0 or data <= 0:
        return 0
    total = 60 + shdr + names + data
    if off + total > len(buf) or total > 512 * 1024 * 1024:
        return 0
    return total


def find_embedded_audio(data: bytes) -> list:
    """Scan bytes for embedded audio.

    Returns [{"offset": int, "format": "wav"|"ogg"|"fsb5", "size": int}],
    sorted by offset, non-overlapping (first match wins).
    """
    found: list = []
    i = 0
    n = len(data)
    while i < n:
        size, fmt = 0, ""
        head4 = data[i:i + 4]
        if head4 == _WAV_MAGIC:
            size = _wav_size(data, i)
            fmt = "wav"
        elif head4 == _OGG_MAGIC:
            size = _ogg_size(data, i)
            fmt = "ogg"
        elif head4 == _FSB5_MAGIC:
            size = _fsb5_size(data, i)
            fmt = "fsb5"
        if size > 0:
            found.append({"offset": i, "format": fmt, "size": size})
            i += size
        else:
            # skip ahead: next candidate must start with R/O/F
            nxt = n
            for byte in (ord("R"), ord("O"), ord("F")):
                j = data.find(bytes((byte,)), i + 1)
                if j != -1:
                    nxt = min(nxt, j)
            i = nxt if nxt < n else n
    return found


def carve_embedded_audio(data: bytes, out_dir: str, prefix: str = "carved") -> list:
    """Write each embedded blob to out_dir. Returns written paths."""
    _os.makedirs(out_dir, exist_ok=True)
    paths: list = []
    for k, hit in enumerate(find_embedded_audio(data)):
        name = f"{prefix}_{k:03d}_{hit['offset']:08x}.{hit['format']}"
        dest = _os.path.join(out_dir, name)
        with open(dest, "wb") as fh:
            fh.write(data[hit["offset"]:hit["offset"] + hit["size"]])
        paths.append(dest)
    return paths
