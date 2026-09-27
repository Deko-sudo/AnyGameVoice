# FAQ

**Is it free?** Yes — Apache 2.0, no ads, no tracking, no paywalls.

**Does it upload my game or voice samples?** No. Everything runs locally.
Cloud providers (OpenAI etc.) only receive what you explicitly send them.

**Which games work?** Text extraction: Ren'Py, RPG Maker MV/MZ, Godot
(Dialogue Manager). Unity: audio carving from bundles (+UnityPy decode).
Unreal: `.pak` inspection, UnrealPak CLI unpacking, `.ubulk` carving.

**How do emotions work?** `[happy]`-style tags map to Piper prosody flags
(heuristic, not a real emotion model). Bark keeps `[laughs]` etc. natively.

**Do I need a GPU?** No. Piper and Silero run on CPU. XTTS is much
faster with 6GB+ VRAM; Bark is slow on CPU.

**Where is my data?** `~/.anygamevoice/config.json` (hardware scan cache
only, opt-in). `config --show` to view, `--delete` to wipe.

**I get "Piper binary not found".** Install piper from
https://github.com/rhasspy/piper/releases and add it to PATH, then
`python scripts/download_models.py` for a default voice.

**Can I clone a real actor's voice?** Technically possible with XTTS,
legally your responsibility — see [DISCLAIMER](../DISCLAIMER.md). Don't
do it without consent.

**How do I undo a replacement?** Every `replace_audio` writes
`<file>.<timestamp>.bak`. Call `restore_file(backup)`.

**Commercial use of generated mods?** Your game EULA + voice rights
apply. The tool itself is Apache 2.0; generated content is yours to
license responsibly.
