# Third-party components and distribution scope

The AnyGameVoice application code is licensed under Apache-2.0. Keep LICENSE and NOTICE
with redistributed copies. Third-party software and voice models retain their own licenses.

## Offline UI

- **Manrope** — SIL Open Font License 1.1. Copyright 2018 The Manrope Project Authors.
  The font and the complete license are in `ui/fonts/`.
  Source: https://github.com/sharanda/manrope
- **Material Color Utilities 0.3.0** — Apache-2.0. Copyright 2021 Google LLC.
  Generates built-in palettes at build time and custom palettes in the browser.
  The browser bundle is served locally from ui/custom-color.js.
  Source and license: https://github.com/material-foundation/material-color-utilities
- Icons, layout, theme picker and the demo scene are project assets under Apache-2.0.

## Optional speech engines and models

**Modern Piper / piper-tts (OHF-Voice/piper1-gpl) is GPL-3.0-or-later**, not Apache-2.0.
The adapter invokes a separately installed executable through its CLI. The optional
`piper` extra installs this external runtime for local development; it does not relicense it.
Piper, piper_phonemize and onnxruntime are explicitly excluded from the PyInstaller build.
Do not distribute an environment containing optional engines as an Apache-only application.
Any future installer that redistributes an engine must include that engine's required
licenses, notices and corresponding-source arrangements before release.
Source and license: https://github.com/OHF-Voice/piper1-gpl

XTTS, Bark and Silero adapters also depend on separately installed runtimes.
Their software, model weights and training data can have different license terms.
Check each chosen runtime version and model card before distributing a bundle or voice.
No voice model or optional TTS runtime is included in this repository's package resources.

## Python runtime dependencies

Python package dependencies are resolved separately by the package installer and retain
the license files in their installed distributions. This file is not a complete SBOM of a
future executable. A pinned dependency/license inventory and distribution check remain
release gates for native installers (see docs/implementation-plan.md).

## Optional studio component setup

Setup downloads components on user request; they are not bundled into the application.
The catalog pins Piper 1.8.0 and imageio-ffmpeg 0.6.0. Package dependencies are installed
from PyPI into a separate environment and retain their distribution license files.
The FFmpeg executable has its own license; review the notices shipped in that package.
Sources: https://pypi.org/project/piper-tts/1.8.0/ and
https://pypi.org/project/imageio-ffmpeg/0.6.0/

Voice models come from rhasspy/piper-voices, revision
cf910fb59f1d79ab3b625a63993a108751c6c25d. Each model's MODEL_CARD is saved beside
its weights/config. Russian Denis is declared CC0; LJ Speech uses public-domain
training data; consult its model card for the model's terms. Do not assume every voice
in that repository shares these terms.
Source: https://huggingface.co/rhasspy/piper-voices

The separately downloaded Ren’Py SDK 8.5.3 contains Ren’Py under MIT and libraries
under their respective licenses. Keep the SDK's own license information when redistributing it.
Source and licenses: https://www.renpy.org/doc/html/license.html
