"""Unpack/carve tests (synthetic fixtures, offline)."""

import struct


def _wav_blob() -> bytes:
    pcm = b"\x00\x01" * 100
    body = b"fmt " + struct.pack("<IHHIIHH", 16, 1, 1, 8000, 16000, 2, 16) + b"data" + struct.pack("<I", len(pcm)) + pcm
    return b"RIFF" + struct.pack("<I", 4 + len(body)) + b"WAVE" + body


def _ogg_page(flags: int, payload: bytes, seq: int) -> bytes:
    segs = [len(payload)] if payload else [0]
    head = b"OggS" + bytes((0, flags)) + b"\x00" * 8 + struct.pack("<III", 1, seq, 0)
    return head + bytes((len(segs),)) + bytes(segs) + payload


def _ogg_blob() -> bytes:
    return _ogg_page(0x00, b"A" * 50, 0) + _ogg_page(0x04, b"B" * 30, 1)


def _fsb5_blob() -> bytes:
    shdr, names, data = 16, 32, 64
    head = b"FSB5" + struct.pack("<5i", 1, 2, shdr, names, data) + b"\x00" * (60 - 24)
    assert len(head) == 60
    return head + b"S" * shdr + b"N" * names + b"D" * data


def _blob() -> tuple:
    wav, ogg, fsb = _wav_blob(), _ogg_blob(), _fsb5_blob()
    filler1, filler2, filler3 = b"ZZZ", b"QQ", b"WW"
    data = filler1 + wav + filler2 + ogg + filler3 + fsb
    return data, [(len(filler1), "wav", len(wav)),
                  (len(filler1) + len(wav) + len(filler2), "ogg", len(ogg)),
                  (len(filler1) + len(wav) + len(filler2) + len(ogg) + len(filler3), "fsb5", len(fsb))]


def test_find_embedded_audio():
    from app.utils.audio_utils import find_embedded_audio

    data, expected = _blob()
    hits = find_embedded_audio(data)
    assert [(h["offset"], h["format"], h["size"]) for h in hits] == expected


def test_carve_roundtrip(tmp_path):
    from app.utils.audio_utils import carve_embedded_audio, find_embedded_audio

    data, _ = _blob()
    paths = carve_embedded_audio(data, str(tmp_path))
    assert len(paths) == 3
    for h, p in zip(find_embedded_audio(data), paths):
        with open(p, "rb") as fh:
            assert fh.read() == data[h["offset"]:h["offset"] + h["size"]]
        assert p.endswith("." + h["format"])


def test_truncated_blob_skipped():
    from app.utils.audio_utils import find_embedded_audio

    assert find_embedded_audio(b"RIFF\xff\xff\xff\xffWAVE") == []  # claims more than exists
    assert find_embedded_audio(b"hello world") == []


def test_unity_carve_fallback(tmp_path, monkeypatch):
    from app.core.game_detector.engines import unity

    monkeypatch.setattr(unity, "is_unitypy_available", lambda: False)
    bundle = tmp_path / "level0.assets"
    wav = _wav_blob()
    bundle.write_bytes(b"UNITYBUNDLE" + wav)
    out = unity.extract_unity_audio(str(tmp_path), str(tmp_path / "out"))
    assert out["unitypy"] == []
    assert len(out["carved"]) == 1
    with open(out["carved"][0], "rb") as fh:
        assert fh.read() == wav


def test_unreal_inspect(tmp_path):
    import pytest

    from app.core.game_detector.engines.unreal import find_unrealpak, inspect_pak, unpack_pak

    pak = tmp_path / "game.pak"
    pak.write_bytes(b"DATA" * 100 + struct.pack("<I", 0x5A6FA11E) + struct.pack("<i", 8) + b"\x00" * 100)
    info = inspect_pak(str(pak))
    assert info["is_pak"] and info["version"] == 8 and info["footer_offset"] > 0

    (tmp_path / "notes.txt").write_text("hi")
    assert inspect_pak(str(tmp_path / "notes.txt"))["is_pak"] is False
    with pytest.raises(FileNotFoundError):
        inspect_pak(str(tmp_path / "missing.pak"))

    # explicit tool path is honored
    assert find_unrealpak(str(pak)) == str(pak)
    # no tool -> clear error, no crash
    with pytest.raises(RuntimeError, match="UnrealPak"):
        unpack_pak(str(pak), str(tmp_path / "out"), unrealpak=str(tmp_path / "nope.exe"))


def test_unreal_ubulk_carve(tmp_path):
    from app.core.game_detector.engines.unreal import extract_unreal_audio

    (tmp_path / "sfx.ubulk").write_bytes(b"BULK" + _ogg_blob())
    out = extract_unreal_audio(str(tmp_path), str(tmp_path / "out"))
    assert len(out["carved"]) == 1
    assert out["carved"][0].endswith(".ogg")
