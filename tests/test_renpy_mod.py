"""Ren'Py voice mod install / verify / uninstall without a Ren'Py SDK."""

import hashlib
import os
from pathlib import Path
import shutil
import threading

import pytest

from app.core.game_detector.engines import renpy_mod
from tests.audio_fixture import wav_bytes

EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "renpy"


def make_game(tmp_path):
    game = tmp_path / "game_root"
    (game / "game" / "chapters").mkdir(parents=True)
    (game / "game" / "script.rpy").write_text(
        'define mira = Character("Мира")\nlabel start:\n    mira "Привет."\n    "Тихо."\n    jump next\n', encoding="utf-8")
    (game / "game" / "chapters" / "next.rpy").write_text('label next:\n    mira "Пока."\n    return\n', encoding="utf-8")
    rows = [
        {"Identifier": "start_aaaa1111", "Character": "mira", "Dialogue": "Привет.", "Filename": "game/script.rpy", "Line Number": "3"},
        {"Identifier": "start_bbbb2222", "Character": "", "Dialogue": "Тихо.", "Filename": "game/script.rpy", "Line Number": "4"},
        {"Identifier": "next_cccc3333", "Character": "mira", "Dialogue": "Пока.", "Filename": "game/chapters/next.rpy", "Line Number": "2"},
    ]
    return game, rows


def make_batch(tmp_path, game, lines):
    out = tmp_path / "out"
    out.mkdir()
    items = []
    for index, (source, line_no, text) in enumerate(lines):
        data = wav_bytes(value=100 + index)
        (out / f"line{index}.wav").write_bytes(data)
        items.append({"id": f"line{index}", "source_file": source, "line_no": line_no, "text": text,
                      "metadata": {}, "filename": f"line{index}.wav", "status": "done",
                      "sha256": hashlib.sha256(data).hexdigest()})
    return {"status": "done", "game_path": str(game), "out": str(out), "lines": items}


LINES = [("script.rpy", 3, "Привет."), ("script.rpy", 4, "Тихо."), ("chapters/next.rpy", 2, "Пока.")]


def test_install_verify_uninstall_round_trip(tmp_path):
    game, rows = make_game(tmp_path)
    before = {p: p.read_bytes() for p in (game / "game").rglob("*.rpy")}
    result = make_batch(tmp_path, game, LINES)

    report = renpy_mod.install_mod(result, rows=rows)
    mod = game / "game" / "anygamevoice"
    assert report["status"] == "installed" and report["voiced"] == 3 and report["engine_total"] == 3
    assert sorted(p.name for p in (mod / "voice").iterdir()) == ["next_cccc3333.wav", "start_aaaa1111.wav", "start_bbbb2222.wav"]
    assert (mod / "voice" / "start_aaaa1111.wav").read_bytes() == (Path(result["out"]) / "line0.wav").read_bytes()
    script = (mod / "anygamevoice_voice.rpy").read_text(encoding="utf-8")
    assert 'config.auto_voice = "anygamevoice/voice/{id}.wav"' in script and "if config.auto_voice is None" in script
    assert {p: p.read_bytes() for p in (game / "game").rglob("*.rpy") if mod not in p.parents} == before

    # Ren'Py compiles our script on launch; that file must not break ownership checks.
    (mod / "anygamevoice_voice.rpyc").write_bytes(b"compiled")
    assert renpy_mod.verify_mod(game)["status"] == "ok"

    removed = renpy_mod.uninstall_mod(game)
    assert removed["status"] == "removed" and not mod.exists()
    assert Path(removed["path"]).parent == game / ".anygamevoice-backups"
    assert renpy_mod.verify_mod(game)["status"] == "absent"
    assert {p: p.read_bytes() for p in (game / "game").rglob("*.rpy")} == before


def test_reinstall_replaces_owned_mod_and_keeps_backup(tmp_path):
    game, rows = make_game(tmp_path)
    result = make_batch(tmp_path, game, LINES)
    renpy_mod.install_mod(result, rows=rows)
    report = renpy_mod.install_mod(result, rows=rows)
    assert report["backup"] and Path(report["backup"]).is_dir()
    assert renpy_mod.verify_mod(game)["status"] == "ok"


@pytest.mark.parametrize("tamper", ["edit", "extra", "delete"])
def test_modified_mod_is_never_overwritten_or_removed(tmp_path, tamper):
    game, rows = make_game(tmp_path)
    result = make_batch(tmp_path, game, LINES)
    renpy_mod.install_mod(result, rows=rows)
    mod = game / "game" / "anygamevoice"
    if tamper == "edit":
        (mod / "voice" / "start_aaaa1111.wav").write_bytes(b"user edit")
    elif tamper == "extra":
        (mod / "notes.txt").write_text("mine")
    else:
        (mod / "voice" / "next_cccc3333.wav").unlink()
    for action in (lambda: renpy_mod.verify_mod(game), lambda: renpy_mod.uninstall_mod(game),
                   lambda: renpy_mod.install_mod(result, rows=rows)):
        with pytest.raises(ValueError):
            action()
    assert mod.is_dir()


def test_foreign_folder_with_same_name_is_refused(tmp_path):
    game, rows = make_game(tmp_path)
    (game / "game" / "anygamevoice").mkdir()
    (game / "game" / "anygamevoice" / "theirs.rpy").write_text("# someone else")
    with pytest.raises(ValueError, match="сторонние"):
        renpy_mod.install_mod(make_batch(tmp_path, game, LINES), rows=rows)
    assert (game / "game" / "anygamevoice" / "theirs.rpy").is_file()


def test_game_that_sets_auto_voice_is_refused(tmp_path):
    game, rows = make_game(tmp_path)
    (game / "game" / "options.rpy").write_text('define config.auto_voice = "voice/{id}.ogg"\n')
    with pytest.raises(ValueError, match="auto_voice"):
        renpy_mod.install_mod(make_batch(tmp_path, game, LINES), rows=rows)
    assert not (game / "game" / "anygamevoice").exists()


def test_changed_text_tampered_audio_and_unfinished_batch_are_refused(tmp_path):
    game, rows = make_game(tmp_path)
    changed = make_batch(tmp_path, game, [("script.rpy", 3, "Другое."), *LINES[1:]])
    with pytest.raises(ValueError, match="изменился"):
        renpy_mod.install_mod(changed, rows=rows)
    shutil.rmtree(tmp_path / "out")
    result = make_batch(tmp_path, game, LINES)
    (Path(result["out"]) / "line1.wav").write_bytes(wav_bytes(value=1))
    with pytest.raises(ValueError, match="изменён"):
        renpy_mod.install_mod(result, rows=rows)
    with pytest.raises(ValueError, match="полностью"):
        renpy_mod.install_mod({**result, "status": "partial"}, rows=rows)
    assert not (game / "game" / "anygamevoice").exists()
    assert not list(game.glob(".agv-stage-*"))


def test_unmatched_lines_are_reported_not_installed(tmp_path):
    game, rows = make_game(tmp_path)
    result = make_batch(tmp_path, game, [*LINES, ("script.rpy", 99, "Не диалог.")])
    report = renpy_mod.install_mod(result, rows=rows)
    assert report["voiced"] == 3 and report["unmatched"] == ["line3"]


def test_cancel_before_publish_leaves_game_unchanged(tmp_path):
    game, rows = make_game(tmp_path)
    cancel = threading.Event()
    cancel.set()
    with pytest.raises(InterruptedError):
        renpy_mod.install_mod(make_batch(tmp_path, game, LINES), rows=rows, cancel_event=cancel)
    assert not (game / "game" / "anygamevoice").exists()
    assert not list(game.glob(".agv-stage-*"))


def test_export_refuses_to_overwrite_existing_dialogue_tab(tmp_path):
    game, _ = make_game(tmp_path)
    sdk = tmp_path / "sdk"
    sdk.mkdir()
    (sdk / "renpy.sh").write_text("#!/bin/sh\nexit 1\n")
    (game / "dialogue.tab").write_text("mine")
    with pytest.raises(ValueError, match="dialogue.tab"):
        renpy_mod.export_dialogue_ids(game, sdk)
    assert (game / "dialogue.tab").read_text() == "mine"


def test_export_reads_and_removes_engine_table(tmp_path):
    game, _ = make_game(tmp_path)
    sdk = tmp_path / "sdk"
    sdk.mkdir()
    launcher = sdk / "renpy.sh"
    launcher.write_text('#!/bin/sh\nprintf "Identifier\\tCharacter\\tDialogue\\tFilename\\tLine Number\\tRen\'Py Script\\n'
                        'start_aaaa1111\\tmira\\tПривет.\\tgame/script.rpy\\t3\\tmira \\"[what]\\"\\n" > "$1/dialogue.tab"\n')
    launcher.chmod(0o755)
    rows = renpy_mod.export_dialogue_ids(game, sdk)
    assert rows[0]["Identifier"] == "start_aaaa1111" and rows[0]["Line Number"] == "3"
    assert not (game / "dialogue.tab").exists()


def test_missing_sdk_is_explained(tmp_path, monkeypatch):
    monkeypatch.delenv("AGV_RENPY_SDK", raising=False)
    with pytest.raises(ValueError, match="SDK"):
        renpy_mod.find_sdk(None)


@pytest.mark.skipif(not os.environ.get("AGV_RENPY_SDK"), reason="set AGV_RENPY_SDK to run against a real Ren'Py SDK")
def test_real_sdk_exports_ids_for_example_scene(tmp_path):
    game = tmp_path / "example"
    shutil.copytree(EXAMPLE, game)
    rows = renpy_mod.export_dialogue_ids(game)
    assert len(rows) == 23 and all(renpy_mod._ID_RE.match(r["Identifier"]) for r in rows)
    assert sorted(p.name for p in game.iterdir()) == ["game"]
