"""Subtitle + batch pipeline tests."""

from unittest.mock import patch


def _line(speaker, text):
    from app.models.dialogue import Dialogue

    return Dialogue(speaker=speaker, text=text)


def test_srt_format():
    from app.utils.audio_utils import estimate_duration, fmt_timestamp, to_srt, to_vtt

    assert fmt_timestamp(0) == "00:00:00,000"
    assert fmt_timestamp(61.5) == "00:01:01,500"
    assert fmt_timestamp(61.5, vtt=True) == "00:01:01.500"
    assert estimate_duration("") == 1.0
    srt = to_srt([_line("e", "Hello!"), _line("narrator", "Wind blows.")])
    assert "1\n00:00:00,000 --> " in srt
    assert "<v e>Hello!" in srt
    assert "Wind blows." in srt  # narrator has no <v> tag
    vtt = to_vtt([_line("e", "Hi")])
    assert vtt.startswith("WEBVTT")


def test_batch_mod(tmp_path):
    from app.main import cmd_mod

    game = tmp_path / "game"
    (game / "game").mkdir(parents=True)
    (game / "game" / "script.rpy").write_text('e "Hello there!"\n"Wind."\n', encoding="utf-8")
    out = tmp_path / "out"

    def fake_gen(text, out_path, voice="", engine="piper", emotion="neutral"):
        with open(out_path, "wb") as fh:
            fh.write(b"FAKEWAV" + text.encode())
        return out_path

    # cmd_mod imports generate_voice_to_file lazily, so patch the source.
    with patch("app.core.tts.generator.generate_voice_to_file", side_effect=fake_gen):
        cmd_mod(str(game), str(out))
    wavs = sorted(out.glob("*.wav"))
    assert len(wavs) == 2
    assert (out / "dialogue.srt").is_file()
