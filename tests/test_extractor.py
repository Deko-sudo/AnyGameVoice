"""Extractor tests."""


def test_extract_stub():
    from app.core.extractor.dialogue_extractor import extract_dialogue

    assert extract_dialogue("dummy") == []


def test_renpy_extraction(tmp_path):
    from app.core.game_detector.engines.renpy import extract_renpy_file

    rpy = tmp_path / "script.rpy"
    rpy.write_text(
        'define e = Character("Eileen")\n'
        'label start:\n'
        '    e "Hello, world!"\n'
        '    "Narration line."\n'
        "    # e \"commented out\"\n"
        '    jump next\n',
        encoding="utf-8",
    )
    lines = extract_renpy_file(str(rpy))
    assert len(lines) == 2
    assert lines[0].speaker == "e"
    assert lines[0].text == "Hello, world!"
    assert lines[1].speaker == "narrator"


def test_detector_renpy(tmp_path):
    from app.core.game_detector.detector import detect_engine, scan_game_folder

    game = tmp_path / "game"
    game.mkdir()
    (game / "script.rpy").write_text('e "hi"\n', encoding="utf-8")
    assert detect_engine(str(tmp_path)) == "renpy"
    info = scan_game_folder(str(tmp_path))
    assert info["exists"] and info["engine"] == "renpy"
    assert info["files"] >= 1


def test_detector_unknown(tmp_path):
    from app.core.game_detector.detector import detect_engine

    assert detect_engine(str(tmp_path)) == "unknown"
    assert detect_engine(str(tmp_path / "missing")) == "unknown"
