# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added
- Phase 1 core engine:
  - Hardware scan + recommended settings (`app/core/scanner`)
  - Game folder scan + engine detection for Ren'Py/RPG Maker/Unity/Unreal/Godot
  - Ren'Py .rpy dialogue extractor
  - Piper TTS adapter + voice manager (local presets/user voices)
  - Audio replacer with timestamped backup + restore
  - CLI: `python app/main.py scan|extract <game_folder>`
  - Tests for scanner, detector, extractor, TTS, replacer
- README with project description
- Apache 2.0 license
- Privacy policy
- Disclaimer
- Contributing guidelines
- Issue templates
- Basic Python project configuration
