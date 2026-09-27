"""Engine extractor tests (fake game folders, offline)."""

import json


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_rpgmaker_extraction(tmp_path):
    from app.core.game_detector.engines.rpgmaker import extract_rpgmaker_folder

    data = tmp_path / "data"
    data.mkdir()
    (data / "Map001.json").write_text(
        json.dumps(
            {
                "events": [
                    {
                        "id": 1,
                        "name": "EV001",
                        "pages": [
                            {
                                "list": [
                                    {"code": 101, "parameters": ["Actor1", 0, 0, 2, "Hero"]},
                                    {"code": 401, "parameters": ["Take this sword!"]},
                                    {"code": 401, "parameters": ["It is dangerous."]},
                                    {"code": 0, "parameters": []},
                                ]
                            }
                        ],
                    },
                    None,  # real files contain nulls
                ]
            }
        ),
        encoding="utf-8",
    )
    lines = extract_rpgmaker_folder(str(tmp_path))
    assert len(lines) == 2
    assert lines[0].speaker == "Hero"
    assert lines[0].text == "Take this sword!"


def test_rpgmaker_routed(tmp_path):
    from app.core.extractor.dialogue_extractor import extract_dialogue, supported_engines

    (tmp_path / "Game.rpgproject").write_text("[RPG Maker]", encoding="utf-8")
    data = tmp_path / "data"
    data.mkdir()
    (data / "System.json").write_text("{}", encoding="utf-8")
    (data / "Map001.json").write_text(
        json.dumps({"events": [{"id": 1, "pages": [{"list": [{"code": 401, "parameters": ["Hi!"]}]}]}]}),
        encoding="utf-8",
    )
    assert "rpgmaker" in supported_engines()
    lines = extract_dialogue(str(tmp_path))
    assert len(lines) == 1 and lines[0].text == "Hi!"


def test_godot_dialogue(tmp_path):
    from app.core.extractor.dialogue_extractor import extract_dialogue

    (tmp_path / "project.godot").write_text("; Godot", encoding="utf-8")
    _write(tmp_path / "dialog" / "main.dialogue", "~ start\nAlice: Hello, traveler!\nA cold wind blows.\n- Go north\n")
    lines = extract_dialogue(str(tmp_path))
    speakers = {(ln.speaker, ln.text) for ln in lines}
    assert ("Alice", "Hello, traveler!") in speakers
    assert ("narrator", "A cold wind blows.") in speakers
    assert all("Go north" not in ln.text for ln in lines)  # choices skipped


def test_unity_unreal_inventory(tmp_path):
    from app.core.game_detector.detector import scan_game_folder
    from app.core.game_detector.engines.unity import extract_unity_folder

    (tmp_path / "Assets").mkdir()
    (tmp_path / "Assets" / "hit.wav").write_bytes(b"RIFF")
    (tmp_path / "Game_Data").mkdir()
    info = scan_game_folder(str(tmp_path))
    assert info["engine"] == "unity"
    assert any(f.endswith("hit.wav") for f in info["audio_files"])
    assert extract_unity_folder(str(tmp_path)) == []
