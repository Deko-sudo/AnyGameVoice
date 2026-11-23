"""Regression checks for the reference Ren'Py game, without a runtime or models."""

import json
import shutil
import wave
from difflib import unified_diff
from operator import itemgetter
from pathlib import Path

import pytest

from app.core import translate
from app.core.extractor.dialogue_extractor import extract_dialogue
from app.core.replacer.audio_replacer import replace_audio
from app.core.replacer.backup import restore_file
from app.core.tts import generator
from app.main import cmd_mod

REFERENCE = Path(__file__).parent / "fixtures" / "renpy_reference"
BEACON = Path("game/voice/beacon.wav")
FIELDS = ("engine_id", "source_file", "line_no", "speaker", "source_text")


@pytest.fixture
def golden():
    return json.loads((REFERENCE / "expected.json").read_text(encoding="utf-8"))


def test_reference_extraction(golden):
    lines = extract_dialogue(str(REFERENCE))
    actual = [{field: getattr(line, field) for field in FIELDS} for line in lines]

    def rows(records):
        ordered = sorted(records, key=itemgetter("source_file", "line_no"))
        return [json.dumps(row, ensure_ascii=False, sort_keys=True) for row in ordered]

    diff = list(unified_diff(
        rows(golden), rows(actual), "expected.json", "extract_dialogue()", lineterm="",
    ))
    if diff:
        pytest.fail("\n".join(diff), pytrace=False)

    script = (REFERENCE / "game/script.rpy").read_text(encoding="utf-8").splitlines()
    filtered = {n for n, text in enumerate(script, 1) if "# filtered:" in text}
    assert len(filtered) == 2
    assert filtered.isdisjoint(line.line_no for line in lines)
    dialogue = {(line.speaker, line.source_text) for line in lines}
    assert ("e", "The bell hangs above the steps.") in dialogue
    assert ("s", "The lamp points to the breakwater.") in dialogue


@pytest.fixture
def dubbed_copy(tmp_path, monkeypatch):
    game = shutil.copytree(REFERENCE, tmp_path / "reference")
    output = tmp_path / "output"

    def fake_translate(text, target, *args):
        assert target == "es"
        # A fixed utterance also lets placeholder-only lines exercise WAV generation.
        return "Prueba de voz."

    def fake_tts(line, out_path, **kwargs):
        assert (line.target_lang, line.tts_text) == ("es", "Prueba de voz.")
        # Encode the source line number in the period of a short PCM square wave.
        period = b"\x00\x10" * line.line_no + b"\x00\xf0" * line.line_no
        with wave.open(out_path, "wb") as wav:
            wav.setparams((1, 2, 8000, 0, "NONE", "not compressed"))
            wav.writeframes(period * 32)
        return out_path

    monkeypatch.setattr(translate, "translate_text", fake_translate)
    monkeypatch.setattr(generator, "generate_voice_to_file", fake_tts)
    report = cmd_mod(str(game), str(output), translate_to="es")
    saved = json.loads((output / "report.json").read_text(encoding="utf-8"))
    assert saved == report
    return game, output, saved


def test_reference_spanish_wavs(dubbed_copy, golden):
    _, output, report = dubbed_copy
    total = len(golden)
    assert report["status"] == "done"
    assert (report["total"], report["succeeded"], report["failed"]) == (total, total, 0)
    location = itemgetter("source_file", "line_no", "speaker")
    assert sorted(map(location, report["lines"])) == sorted(map(location, golden))
    wav_names = [row["wav"] for row in report["lines"]]
    assert sorted(wav_names) == sorted(path.name for path in output.glob("*.wav"))
    for row in report["lines"]:
        assert row["status"] == "succeeded" and row["skipped_reason"] is None
        with wave.open(str(output / row["wav"]), "rb") as wav:
            assert (wav.getnchannels(), wav.getsampwidth(), wav.getframerate()) == (1, 2, 8000)
            assert wav.getcomptype() == "NONE"
            assert wav.getnframes() == 64 * row["line_no"]
            assert len(wav.readframes(wav.getnframes())) == 2 * wav.getnframes()


@pytest.fixture
def restored_game(dubbed_copy, golden):
    game, output, report = dubbed_copy
    voiced = next(row for row in golden if row["source_text"] == "Do you hear the beacon?")
    location = itemgetter("source_file", "line_no", "speaker")
    row = next(row for row in report["lines"] if location(row) == location(voiced))
    generated = output / row["wav"]
    target = game / BEACON
    original = target.read_bytes()
    assert generated.read_bytes() != original
    backup = Path(replace_audio(str(target), str(generated)))
    assert list(game.rglob("*.bak")) == [backup]
    assert backup.parent == target.parent and backup.read_bytes() == original
    assert target.read_bytes() == generated.read_bytes()
    assert Path(restore_file(str(backup))) == target
    assert set(game.rglob("*.bak")) <= {backup}
    return game


def test_reference_install_and_restore(restored_game):
    assert (restored_game / BEACON).read_bytes() == (REFERENCE / BEACON).read_bytes()


@pytest.mark.xfail(strict=True, raises=AssertionError, reason="restore_file keeps the consumed .bak")
def test_reference_restore_leaves_no_backups(restored_game):
    assert list(restored_game.rglob("*.bak")) == []
