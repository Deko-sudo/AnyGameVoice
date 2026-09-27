"""Extractor tests."""


def test_extract_stub():
    from app.core.extractor.dialogue_extractor import extract_dialogue

    assert extract_dialogue("dummy") == []
