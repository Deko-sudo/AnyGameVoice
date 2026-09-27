"""Download default TTS models (Piper voice, ~60MB).

Source: rhasspy/piper-voices on HuggingFace (open CC0 voices).
Stdlib only. Skips files that already exist.
"""

import argparse
import os
import sys
import urllib.request

BASE = "https://huggingface.co/rhasspy/piper-voices/resolve/main"
DEFAULT_VOICE = "en/en_US/lessac/medium/en_US-lessac-medium"

FILES = [DEFAULT_VOICE + ".onnx", DEFAULT_VOICE + ".onnx.json"]


def download(url: str, dest: str) -> None:
    """Download url to dest with progress."""
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    if os.path.isfile(dest):
        print(f"exists, skipping: {dest}")
        return
    print(f"downloading: {url}")
    try:
        urllib.request.urlretrieve(url, dest)
    except Exception as exc:
        try:
            os.unlink(dest)
        except OSError:
            pass
        raise RuntimeError(f"download failed: {exc}") from exc
    print(f"saved: {dest}")


def main(argv=None) -> int:
    """Download default models into models/. Returns exit code."""
    parser = argparse.ArgumentParser(description="Download default Piper voice model.")
    parser.add_argument("--out", default="models", help="target directory")
    parser.add_argument("--voice", default=DEFAULT_VOICE, help="voice path prefix")
    args = parser.parse_args(argv)
    for suffix in (".onnx", ".onnx.json"):
        download(f"{BASE}/{args.voice}{suffix}", os.path.join(args.out, os.path.basename(args.voice) + suffix))
    print(f"\nUse it: python app/main.py mod <game> --out ./out --voice {args.out}/{os.path.basename(args.voice)}.onnx")
    return 0


if __name__ == "__main__":
    sys.exit(main())
